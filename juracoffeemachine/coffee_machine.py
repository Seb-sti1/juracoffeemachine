from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import IntEnum
from threading import Lock, Thread
from typing import Optional, Tuple, Callable, List

from juracoffeemachine.jura import JuraProtocol, JuraCommand, JuraAddress, EmptyResponse, InvalidResponse
from juracoffeemachine.response import HZ, CS
from juracoffeemachine.serial import JuraSerial

logger = logging.getLogger(__name__)


try:
    import RPi.GPIO as GPIO
except:
    logger.warning("This is not a RPI, it will not load RPi.GPIO module.")

class CoffeeType(IntEnum):
    ESPRESSO = 0
    RISTRETTO = 1
    COFFEE = 2
    SPECIAL = 3


class CoffeeMakerResult(IntEnum):
    OK = 0

    CANNOT_COMMUNICATE = 10
    CANNOT_FETCH_HZ = 11
    CANNOT_FETCH_GROUNDS_TANK = 12
    CANNOT_SET_PARAM = 13
    CANNOT_PRESS_BTN = 14
    CANNOT_CONFIRM_SUCCESSFUL_COFFEE = 15

    SLEEPING = 20
    DRAINING_TRAY_FULL = 21
    DRAINING_TRAY_MISSING = 22
    WATER_TANK_MISSING = 23
    GROUNDS_TANK_FULL = 24
    MISSING_COFFEE = 25


class BrewingStage(IntEnum):
    CHECKING_AVAILABILITY = 0
    SETTING_PARAM = 1
    PRESSING_BTN = 2
    BREWING = 3


@dataclass
class BrewingStatus:
    stage: BrewingStage
    water_volume: Optional[float]
    last_msg: Optional[HZ | CS]


@dataclass
class CoffeeStatistics:
    tot_espresso: Optional[int]
    tot_2_espresso: Optional[int]
    tot_ristretto: Optional[int]
    tot_2_ristretto: Optional[int]
    tot_coffee: Optional[int]
    tot_2_coffee: Optional[int]
    tot_special: Optional[int]


class CoffeeMaker:
    # Mapping coffee type to button
    coffee_button_map = {
        CoffeeType.ESPRESSO: JuraCommand.BUTTON_1,
        CoffeeType.RISTRETTO: JuraCommand.BUTTON_2,
        CoffeeType.COFFEE: JuraCommand.BUTTON_4,
        CoffeeType.SPECIAL: JuraCommand.BUTTON_5,
    }

    # This is to ensure that the code can only be run with the same Jura coffee machine.
    # /!\/!\/!\/!\/!\/!\/!\/!\ /!\/!\/!\/!\/!\/!\/!\/!\
    # /!\/!\/!\/!\ CHANGE AT YOUR OWN RISK /!\/!\/!\/!\
    # /!\/!\/!\/!\/!\/!\/!\/!\ /!\/!\/!\/!\/!\/!\/!\/!\
    type = "ty:EF532M V02.03"
    bootloader = "tl:BL_RL78 V01.31"

    def __init__(self, protocol: JuraProtocol, power_gpio: Optional[int] = None):
        self.jura: JuraProtocol = protocol
        self.last_valid_contact: Optional[datetime] = None
        self.jura_version_verified: bool = False
        self.__power_gpio__ = power_gpio
        if self.__power_gpio__ is not None:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.__power_gpio__, GPIO.OUT)

        self.__comm_lock__ = Lock()
        self.__brew_threads__: List[Thread] = []

        self.__brewing_status__ = None

    @staticmethod
    def create_from_uart(port: str) -> CoffeeMaker:
        return CoffeeMaker(JuraProtocol(JuraSerial(port), lambda _: logger.error("Received unexpected message.")))

    # ====================== Status

    def __update_last_contact__(self):
        self.last_valid_contact = datetime.now(timezone.utc)

    def get_brewing_status(self) -> BrewingStatus:
        return self.__brewing_status__

    # ====================== Communication checks

    def __test_connection__(self) -> Tuple[bool, Optional[bool]]:
        try:
            if not self.jura_version_verified:
                logger.info("Coffee Maker connected.")
                response = self.jura.write_with_response(JuraCommand.GET_TYPE)
                if response != self.type:
                    logger.error(f"This code was created for '{self.type}' machine not '{response}'.")
                    return False, None
                self.__update_last_contact__()
                response = self.jura.write_with_response(JuraCommand.GET_LOADER)
                if response != self.bootloader:
                    logger.error(f"This code was created for '{self.bootloader}' machine not '{response}'.")
                    return False, None
                self.jura_version_verified = True
                self.__update_last_contact__()
                logger.info("Coffee Maker connected.")
                return True, None
            else:
                t = self.jura.write_with_response(JuraCommand.GET_TYPE)
                if t == self.type:
                    self.__update_last_contact__()
                    return True, None
                else:
                    logger.info(f"Received invalid response {t} != {self.type}.")
                    return False, True
        except EmptyResponse:
            logger.info("Received empty response.")
            return False, False
        except InvalidResponse as e:
            logger.info(f"Received invalid response {e}.")
            return False, True

    def __check_connection__(self, is_invalid: bool = False, _tries_left: int = 3) -> bool:
        """
        Check if the driver can communicate to the jura machin. If not it tries up to 3 times to restore connection.

        Note: On the first connection attempt it will also check the type and the bootloader to prevent misuse of this
        driver.

        :param is_invalid:
        :param _tries_left:
        :return: If it was possible to communicate with the jura machine
        """
        if _tries_left == 0:
            logger.error(f"Reached maximum number of tries.")
            return False
        elif _tries_left == 1:
            logger.info(f"Trying to reopen serial.")
            self.jura.reopen_serial()
        elif _tries_left == 2:
            logger.info(f"Trying to reset buffers.")
            self.jura.reset_streams()
        connected, is_invalid = self.__test_connection__()
        if connected:
            if _tries_left != 3:
                logger.info("Connection recovered.")
            return True
        else:
            return self.__check_connection__(is_invalid, _tries_left - 1)

    @staticmethod
    def __is_hz_valid__(hz: HZ) -> CoffeeMakerResult:
        if hz.is_sleeping:
            return CoffeeMakerResult.SLEEPING
        if hz.is_draining_tray_full:
            return CoffeeMakerResult.DRAINING_TRAY_FULL
        if not hz.is_draining_tray_present:
            return CoffeeMakerResult.DRAINING_TRAY_MISSING
        if not hz.is_water_tank_present:
            return CoffeeMakerResult.WATER_TANK_MISSING
        # TODO confirm or find the MISSING_COFFEE flag
        # if not hz.missing_coffee:
        #     return CoffeeMakerResult.MISSING_COFFEE
        return CoffeeMakerResult.OK

    @staticmethod
    def __is_grounds_valid__(grounds: int) -> CoffeeMakerResult:
        if grounds >= 1100:
            return CoffeeMakerResult.GROUNDS_TANK_FULL
        return CoffeeMakerResult.OK

    def __check_availability__(self) -> CoffeeMakerResult:
        if not self.__check_connection__():
            return CoffeeMakerResult.CANNOT_COMMUNICATE

        try:
            hz = self.jura.get_and_parse_message(JuraCommand.HZ)
            if hz is None:
                return CoffeeMakerResult.CANNOT_FETCH_HZ
            self.__update_last_contact__()
            r = self.__is_hz_valid__(hz)
            if r != CoffeeMakerResult.OK:
                return r

            grounds = self.jura.read_eeprom(int(JuraAddress.COFFEE_GROUNDS_TANK.value))
            if grounds is None:
                return CoffeeMakerResult.CANNOT_FETCH_GROUNDS_TANK
            self.__update_last_contact__()
            r = self.__is_grounds_valid__(grounds)
            if r != CoffeeMakerResult.OK:
                return r
            return CoffeeMakerResult.OK
        except EmptyResponse:
            return CoffeeMakerResult.CANNOT_COMMUNICATE
        except InvalidResponse:
            return CoffeeMakerResult.CANNOT_COMMUNICATE

    # ====================== Actions

    def can_brew(self, cb: Callable[[CoffeeMakerResult], None]):
        """
        Check if the jura is ready to brew a coffee.
        To monitor more closely the status of the jura use the CoffeeMaker::get_brewing_status method.

        :param cb: Callback indicating if the jura is ready
        """

        def _end(result):
            cb(result)
            self.__comm_lock__.release()
            return None

        def _exec():
            self.__comm_lock__.acquire()
            return _end(self.__check_availability__())

        t = Thread(target=_exec)
        t.start()
        self.__brew_threads__.append(t)

    def brew_coffee(self, coffee_bean: int, water_volume: int, cb: Callable[[CoffeeMakerResult], None]):
        """
        BE EXTREMELY CAREFUL WHEN USING THIS FUNCTION AS IT OVERWRITE DIRECTLY TO THE EEPROM!!!!!

        :param coffee_bean: the quantity of coffee (number of beans as per jura's gui)
        :param water_volume: the water volume in mL
        :param cb: callback when it ends, returns if the coffee was brewed
        """

        def _end(result: CoffeeMakerResult):
            cb(result)
            self.__brewing_status__ = None
            self.__comm_lock__.release()
            return None

        def _exec():
            self.__comm_lock__.acquire()
            self.__brewing_status__ = BrewingStatus(BrewingStage.CHECKING_AVAILABILITY, None, None)
            r = self.__check_availability__()
            if r != CoffeeMakerResult.OK:
                logger.warning(f"Cannot brew, not available: {r.name}.")
                return _end(r)
            self.__brewing_status__ = BrewingStatus(BrewingStage.SETTING_PARAM, None, None)

            try:
                _coffee_bean = max(self.jura.coffee_param[0],
                                   min(self.jura.coffee_param[2], coffee_bean))
                _water_volume = max(self.jura.water_param[0],
                                    min(self.jura.water_param[2], water_volume))
                if not self.jura.set_coffee_param(_coffee_bean, _water_volume):
                    logger.error("Could not send coffee params.")
                    return _end(CoffeeMakerResult.CANNOT_SET_PARAM)
                self.__update_last_contact__()
                self.__brewing_status__ = BrewingStatus(BrewingStage.PRESSING_BTN, None, None)
                if self.jura.write_with_response(self.coffee_button_map[CoffeeType.COFFEE]) != "ok:":
                    logger.warning("Could not press button.")
                    return _end(CoffeeMakerResult.CANNOT_PRESS_BTN)
                self.__update_last_contact__()
                self.__brewing_status__ = BrewingStatus(BrewingStage.BREWING, None, None)
                # for robustness purposes the following design choices were made:
                #   - the program first monitor hz: this makes it possible to check if there is no coffee left
                #           while still monitoring water volume
                #   - once there is a zero in water volume, (it seems) the machin performed its checks so that there is
                #           no point in continuing to check for MISSING_COFFEE flag
                #   - then, to increase frequency of monitoring (len(hz) > len(cs)), the program switches to monitor cs
                #   - at this point it is (extremely) likely that the user will have its coffee but to further decrease
                #           the chance of wrong detection, a coffee is considered served if there is at least > 0
                #   - the possible issue with this is that, on a communication error (intentional or not) with the jura,
                #           the coffee will not be paid. To avoid that, a coffee is also considered served if no msg
                #           are received 7s after the water_val is reset to 0.
                logger.info(f"Brewing {_coffee_bean} beans and {_water_volume} mL.")
                start_time = time.time()
                water_vol_reset_time = None
                # after water_val is reset to 0, it stays at 0 for ~6s, there is a small bump for ~6s then it brew at
                # a fixed pump speed. Finally, it takes 3 measurements (~3s) to detect the end of the coffee
                # TODO estimate duration from the start_time
                estimated_duration = 6 + 6 + _water_volume / self.jura.pump_speed + 3
                end_detected = False
                msg_type = JuraCommand.HZ
                read_non_zero_water_value = False
                is_successfully_brewed = False
                last_water_sensor_values = [0, 0, 0]
                all_sensors_values = []
                while not end_detected and \
                        (water_vol_reset_time is None or (time.time() - water_vol_reset_time) < estimated_duration + 10) \
                        and (time.time() - start_time) < 90:
                    msg = None
                    try:
                        msg = self.jura.get_and_parse_message(msg_type)
                        self.__update_last_contact__()
                    except EmptyResponse:
                        logger.warning(f"Received empty response.")
                    except InvalidResponse as e:
                        logger.warning(f"Received invalid response: {e}.")

                    if msg is None:
                        logger.warning(f"Received cs == None.")
                    else:
                        all_sensors_values.append(msg.water_vol)
                        self.__brewing_status__.last_msg = msg
                        self.__brewing_status__.water_volume = int(msg.water_vol / self.jura.sensor_to_water_value)
                        if msg_type == JuraCommand.HZ:
                            # the MISSING_COFFEE flag is updated in the last message before the water_vol goes to 0
                            # TODO confirm or find the MISSING_COFFEE flag
                            # if msg.missing_coffee:
                            #     return CoffeeMakerResult.MISSING_COFFEE
                            # the water_vol value stays at 0 for about 5s so that it should be seen at least 4 times.
                            # the probably of missing this is low.
                            if msg.water_vol == 0:
                                water_vol_reset_time = time.time()
                                # at this point (unless newer data change this) the coffee is considered successful
                                is_successfully_brewed = True
                                msg_type = JuraCommand.CS
                        elif msg_type == JuraCommand.CS:
                            # when a water_vol > 0 is read, the coffee is considered successful no matter what
                            if msg.water_vol > 0:
                                logger.info(f"{msg.water_vol} > 0, the coffee is considered successful.")
                                is_successfully_brewed = True
                                read_non_zero_water_value = True
                            # for a nominal coffee, water_vol should be > 0 after ~5s of resetting water_vol to 0.
                            # so if after 7s of resetting water_vol to 0, no water_vol > 0 were measured, the coffee is
                            # considered unsuccessful (unless later measurements shows water_vol > 0)
                            if time.time() - water_vol_reset_time > 7 and not read_non_zero_water_value:
                                is_successfully_brewed = False
                            # this is relating to detecting the end of the coffee (3 consecutive identical values)
                            if msg.water_vol > 0:
                                last_water_sensor_values = last_water_sensor_values[1:3] + [msg.water_vol]
                                end_detected = last_water_sensor_values[0] != 0 and \
                                               all(v == last_water_sensor_values[0] for v in last_water_sensor_values)
                logger.debug(",".join(map(str, all_sensors_values)))
                if end_detected:
                    logger.info(f"Coffee ending was properly detected.")
                else:
                    logger.warning(f"Coffee ending could not be detected.")
                return _end(CoffeeMakerResult.OK if is_successfully_brewed else
                            CoffeeMakerResult.CANNOT_CONFIRM_SUCCESSFUL_COFFEE)
            except EmptyResponse:
                logger.fatal(f"Received empty response while trying to brew_coffee.")
                return _end(CoffeeMakerResult.CANNOT_COMMUNICATE)
            except InvalidResponse as e:
                logger.fatal(f"Received invalid response: {e} while trying to brew_coffee.")
                return _end(CoffeeMakerResult.CANNOT_COMMUNICATE)

        t = Thread(target=_exec)
        t.start()
        self.__brew_threads__.append(t)

    def reset_coffee_param(self, cb: Callable[[bool], None]):
        """
        BE EXTREMELY CAREFUL WHEN USING THIS FUNCTION AS IT OVERWRITE DIRECTLY TO THE EEPROM!!!!!

        Reset coffee default parameters to actual default
        """

        def _end(result):
            cb(result)
            self.__comm_lock__.release()
            return None

        def _exec():
            self.__comm_lock__.acquire()
            if not self.__check_connection__():
                logger.warning(f"Cannot reset param: can't communicate.")
                return _end(False)
            try:
                r = self.jura.set_coffee_param(self.jura.coffee_param[1], self.jura.water_param[1])
                self.__update_last_contact__()
                return _end(r)
            except EmptyResponse:
                logger.fatal(f"Received empty response while trying to reset_coffee_param.")
            except InvalidResponse as e:
                logger.fatal(f"Received invalid response: '{e}' while trying to reset_coffee_param.")
            return _end(False)

        t = Thread(target=_exec)
        t.start()
        self.__brew_threads__.append(t)

    def get_totals_statistics(self, cb: Callable[[Optional[CoffeeStatistics]], None]):

        def _end(result):
            cb(result)
            if self.__power_gpio__ is not None:
                GPIO.output(self.__power_gpio__, False)
            self.__comm_lock__.release()
            return None

        def _exec():
            self.__comm_lock__.acquire()
            if self.__power_gpio__ is not None:
                GPIO.output(self.__power_gpio__, True)
                time.sleep(0.1)

            if not self.__check_connection__():
                logger.warning(f"Cannot get statistics: can't communicate.")
                return _end(None)
            try:
                logger.debug("Fetching statistics.")
                r = self.jura.get_totals_statistics()
                self.__update_last_contact__()
                return _end(CoffeeStatistics(*r))
            except EmptyResponse:
                logger.fatal(f"Received empty response while trying to get_totals_statistics.")
            except InvalidResponse as e:
                logger.fatal(f"Received invalid response: '{e}' while trying to get_totals_statistics.")
            return _end(None)

        t = Thread(target=_exec)
        t.start()
        self.__brew_threads__.append(t)

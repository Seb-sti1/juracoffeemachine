from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import IntEnum
from threading import Lock, Thread
from typing import Optional, Tuple, Callable, List

from juracoffeemachine.jura import JuraProtocol, JuraCommand, JuraAddress, EmptyResponse, InvalidResponse
from juracoffeemachine.response import HZ
from juracoffeemachine.serial import JuraSerial

logger = logging.getLogger(__name__)


@dataclass
class FullStatus:
    jura_version_verified: bool

    last_valid_contact: Optional[datetime]

    water_volume: Optional[float]

    last_hz: Optional[HZ]
    last_hz_date: Optional[datetime]

    last_coffee_grounds_tank: Optional[int]
    last_coffee_grounds_tank_date: Optional[datetime]

    def can_brew(self) -> bool:
        if self.last_hz is None:
            return False
        if self.last_hz.is_sleeping:
            return False
        if self.last_hz.is_draining_tray_full:
            return False
        if not self.last_hz.is_draining_tray_present:
            return False
        if not self.last_hz.is_water_tank_present:
            return False
        if self.last_coffee_grounds_tank is None or self.last_coffee_grounds_tank >= 1100:
            return False
        return True

    def __str__(self):
        valid_contact_str = "None"
        if self.last_valid_contact is not None:
            valid_contact_str = str(datetime.now(timezone.utc) - self.last_valid_contact).split('.')[0]

        return (f"FullStatus[version {'' if self.jura_version_verified else 'not'} ok,"
                f" {valid_contact_str} ago, wv {self.water_volume}, {'' if self.can_brew() else 'not'} ready]")

    def __repr__(self):
        return str(self)


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
    class CoffeeType(IntEnum):
        ESPRESSO = 0
        RISTRETTO = 1
        COFFEE = 2
        SPECIAL = 3

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

    def __init__(self, protocol: JuraProtocol):
        self.jura: JuraProtocol = protocol

        self.__comm_lock__ = Lock()
        self.__brew_threads__: List[Thread] = []

        self.__status__ = FullStatus(False, None, None, None, None, None, None)

    @staticmethod
    def create_from_uart(port: str) -> CoffeeMaker:
        return CoffeeMaker(JuraProtocol(JuraSerial(port), lambda _: logger.error("Received unexpected message.")))

    # ====================== Status

    def __update_last_contact__(self):
        self.__status__.last_valid_contact = datetime.now(timezone.utc)

    def get_last_status(self) -> FullStatus:
        return self.__status__

    # ====================== Communication checks

    def __test_connection__(self) -> Tuple[bool, Optional[bool]]:
        try:
            if not self.__status__.jura_version_verified:
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
                self.__status__.jura_version_verified = True
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

    def __check_availability__(self) -> bool:
        if not self.__check_connection__():
            return False

        try:
            hz = self.jura.get_and_parse_message(JuraCommand.HZ)
            if hz is None:
                return False
            self.__update_last_contact__()
            self.__status__.last_hz = hz
            self.__status__.last_hz_date = datetime.now()

            grounds = self.jura.read_eeprom(int(JuraAddress.COFFEE_GROUNDS_TANK.value))
            if grounds is None:
                return False
            self.__update_last_contact__()
            self.__status__.last_coffee_grounds_tank = grounds
            self.__status__.last_coffee_grounds_tank_date = datetime.now()
        except EmptyResponse:
            return False
        except InvalidResponse:
            return False

        return self.get_last_status().can_brew()

    # ====================== Actions

    def can_brew(self, cb: Callable[[bool], None]):
        """
        Check if the jura is ready to brew a coffee.
        To monitor more closely the status of the jura use the CoffeeMaker::get_last_status method.

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

    def brew_coffee(self, coffee_bean: int, water_volume: int, cb: Callable[[bool], None]):
        """
        BE EXTREMELY CAREFUL WHEN USING THIS FUNCTION AS IT OVERWRITE DIRECTLY TO THE EEPROM!!!!!

        :param coffee_bean: the quantity of coffee (number of beans as per jura's gui)
        :param water_volume: the water volume in mL
        :param cb: callback when it ends, returns if the coffee was brewed
        """

        def _end(result):
            cb(result)
            self.__comm_lock__.release()
            return None

        def _exec():
            self.__comm_lock__.acquire()
            if not self.__check_availability__():
                logger.warning(f"Cannot brew, status is {self.get_last_status()}.")
                return _end(False)

            try:
                _coffee_bean = max(self.jura.coffee_param[0],
                                   min(self.jura.coffee_param[2], coffee_bean))
                _water_volume = max(self.jura.water_param[0],
                                    min(self.jura.water_param[2], water_volume))
                if not self.jura.set_coffee_param(_coffee_bean, _water_volume):
                    logger.error("Could not send coffee params.")
                    return _end(False)
                self.__update_last_contact__()
                # FIXME this is not enough to confirm a coffee was started
                if self.jura.write_with_response(self.coffee_button_map[CoffeeMaker.CoffeeType.COFFEE]) != "ok:":
                    logger.warning("Could not press button.")
                    return _end(False)
                self.__update_last_contact__()
                # TODO detect start of coffee
                logger.info(f"Brewing {_coffee_bean} beans and {_water_volume} mL.")
                start_time = time.time()
                end_detected = False
                initial_water_sensor_value = None
                last_water_sensor_values = [0, 0, 0]

                while (time.time() - start_time) < 90 and not end_detected:
                    cs = None
                    try:
                        cs = self.jura.get_and_parse_message(JuraCommand.CS)
                        self.__update_last_contact__()
                    except EmptyResponse:
                        logger.warning(f"Received empty response.")
                    except InvalidResponse as e:
                        logger.warning(f"Received invalid response: {e}.")

                    if cs is None:
                        logger.warning(f"Received cs == None.")
                    else:
                        last_water_sensor_values.append(cs.water_vol)
                        if (time.time() - start_time) < 5 and initial_water_sensor_value is None:
                            initial_water_sensor_value = cs.water_vol
                        last_water_sensor_values = last_water_sensor_values[1:4]
                        end_detected = last_water_sensor_values[0] not in [0, initial_water_sensor_value] and \
                                       all(v == last_water_sensor_values[0] for v in last_water_sensor_values)
                        self.__status__.water_volume = int(
                            last_water_sensor_values[-1] / self.jura.water_sensor_to_water_value)
                if end_detected:
                    logger.info(f"Coffee was brewed!")
                    logger.warning(f"Last water sensor: {last_water_sensor_values}.")
                else:
                    logger.warning(f"Coffee ending could not be detected.")

                self.__status__.water_volume = None
                return _end(True)
            except EmptyResponse:
                logger.fatal(f"Received empty response while trying to brew_coffee.")
            except InvalidResponse as e:
                logger.fatal(f"Received invalid response: {e} while trying to brew_coffee.")
            return _end(False)

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
                logger.warning(f"Cannot reset param, status is {self.get_last_status()}.")
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
            self.__comm_lock__.release()
            return None

        def _exec():
            self.__comm_lock__.acquire()
            if not self.__check_connection__():
                logger.warning(f"Cannot get statistics, status is {self.get_last_status()}.")
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

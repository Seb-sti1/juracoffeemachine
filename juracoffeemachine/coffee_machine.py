from __future__ import annotations

import logging
import time
from datetime import datetime
from enum import IntEnum, Enum
from threading import Lock, Thread
from typing import Optional, overload, Tuple, Callable

from juracoffeemachine.jura import JuraProtocol, JuraCommand, HZ, CS, IC, EmptyResponse, InvalidResponse, Response
from juracoffeemachine.serial import JuraSerial

logger = logging.getLogger(__name__)


class MakerStatus(Enum):
    NOT_CONNECTED = 0
    IDLE = 1
    CHECKING_CONNECTION = 2
    RECOVERING_CONNECTION = 3
    OFF = 4
    UNSYNCHRONISED = 5
    BREWING = 6
    DUMPING_STATISTICS = 7


class FullStatus:
    last_valid_contact: Optional[datetime]
    last_maker_status_change: datetime
    maker_status: MakerStatus
    water_volume: float

    def __init__(self, last_contact: Optional[datetime], last_maker_status_change: Optional[datetime],
                 maker_status: MakerStatus, water_volume: float):
        self.last_valid_contact = last_contact
        self.last_maker_status_change = last_maker_status_change
        self.maker_status = maker_status
        self.water_volume = water_volume


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
    # Change to your own risk!
    type = "ty:EF532M V02.03"
    bootloader = "tl:BL_RL78 V01.31"

    # min, initial, max, step
    coffee_bean_param = (0, 3, 7, 1)
    water_volume_param = (25, 100, 240, 5)
    water_sensor_to_water_value = 2.18595512820513

    def __init__(self, protocol: JuraProtocol):
        self.jura: JuraProtocol = protocol
        self.__status__: FullStatus = FullStatus(None, datetime.now(), MakerStatus.NOT_CONNECTED, 0)
        self.__brew_thread__ = None
        self.__jura_lock__ = Lock()

    def __update_maker_status__(self, new_status: MakerStatus, version_checked: bool = False):
        if self.get_last_status().maker_status == MakerStatus.NOT_CONNECTED and not version_checked:
            return
        if new_status != self.get_last_status().maker_status:
            dt = str(datetime.now() - self.get_last_status().last_maker_status_change).split('.')[0]
            logger.info(f"Status: {self.get_last_status().maker_status} -> {new_status}."
                        f" It was in the previous status for {dt}")
            self.__status__.maker_status = new_status
            self.__status__.last_maker_status_change = datetime.now()

    def __update_brewing__(self, water_volume: float):
        self.__status__.water_volume = water_volume

    def __update_last_contact__(self):
        self.__status__.last_valid_contact = datetime.now()

    def __check_maker_versions__(self) -> bool:
        if self.__status__.maker_status == MakerStatus.NOT_CONNECTED:
            try:
                response = self.jura.write_with_response(JuraCommand.GET_TYPE)
                assert response == self.type, f"This code was created for '{self.type}' machine not '{response}'"
                self.__update_last_contact__()
                response = self.jura.write_with_response(JuraCommand.GET_LOADER)
                assert response == self.bootloader, f"This code was created for '{self.bootloader}' machine not '{response}'"
                self.__update_last_contact__()
                self.__update_maker_status__(MakerStatus.IDLE, True)
                logger.info("Coffee Maker connected.")
                return True
            except EmptyResponse:
                logger.info("Received empty response")
            except InvalidResponse as e:
                logger.info(f"Received invalid response {e}")
            return False
        return True

    def __test_connection__(self) -> Tuple[bool, Optional[bool]]:
        try:
            t = self.jura.write_with_response(JuraCommand.GET_TYPE)
            if t == self.type:
                self.__update_last_contact__()
                self.__update_maker_status__(MakerStatus.IDLE)
                return True, None
            else:
                logger.info(f"Received invalid response {t} != {self.type}")
                return False, True
        except EmptyResponse:
            logger.info("Received empty response")
            return False, False
        except InvalidResponse as e:
            logger.info(f"Received invalid response {e}")
            return False, True

    def __recover_connection__(self, is_invalid: bool, _tries: int = 3) -> bool:
        self.__update_maker_status__(MakerStatus.RECOVERING_CONNECTION)
        if _tries > 0:
            if _tries == 3:
                logger.info(f"Trying to reset buffers")
                self.jura.reset_streams()
            else:
                logger.info(f"Trying to reopen serial")
                self.jura.reopen_serial()
            connected, is_invalid = self.__test_connection__()
            if connected:
                logger.info("Connection recovered")
                return True
            return self.__recover_connection__(is_invalid, _tries=_tries - 1)
        else:
            logger.error(f"Reached maximum number of tries")
            self.__update_maker_status__(MakerStatus.UNSYNCHRONISED if is_invalid else MakerStatus.OFF)
            return False

    def get_last_status(self) -> FullStatus:
        return self.__status__

    def test_connection(self, cb: Callable[[bool], None]):
        self.__update_maker_status__(MakerStatus.CHECKING_CONNECTION)
        self.__jura_lock__.acquire()
        if self.__brew_thread__ is not None:
            self.__brew_thread__.join()
            self.__brew_thread__ = None

        def __exec__():
            if not self.__check_maker_versions__():
                cb(False)
                self.__jura_lock__.release()
                return

            logger.info(f"Testing coffee maker connection")
            connected, is_invalid = self.__test_connection__()
            if connected:
                cb(True)
            else:
                cb(self.__recover_connection__(is_invalid))
            self.__jura_lock__.release()

        self.__brew_thread__ = Thread(target=__exec__)
        self.__brew_thread__.start()

    @staticmethod
    def create_from_uart(port: str) -> CoffeeMaker:
        return CoffeeMaker(JuraProtocol(JuraSerial(port), lambda _: logger.warning("Received unexpected message")))
        # lambda b: b.dump(os.path.join(os.path.dirname(__file__),
        #                               str(int(time.time()))))))

    @overload
    def ping(self, command: JuraCommand.HZ, cb: Callable[[Optional[HZ]], None]) -> Optional[HZ]:
        ...

    @overload
    def ping(self, command: JuraCommand.CS, cb: Callable[[Optional[CS]], None]) -> Optional[CS]:
        ...

    @overload
    def ping(self, command: JuraCommand.IC, cb: Callable[[Optional[IC]], None]) -> Optional[IC]:
        ...

    def ping(self, command: JuraCommand, cb: Callable[[Optional[Response]], None]):
        self.__jura_lock__.acquire()
        if self.__brew_thread__ is not None:
            self.__brew_thread__.join()
            self.__brew_thread__ = None

        def __exec__():
            if not self.__check_maker_versions__():
                cb(None)
                self.__jura_lock__.release()
                return

            try:
                r = self.jura.get_and_parse_message(command)
                self.__update_last_contact__()
                self.__update_maker_status__(MakerStatus.IDLE)
                cb(r)
                self.__jura_lock__.release()
                return
            except EmptyResponse:
                logger.debug(f"Received empty response")
                self.__recover_connection__(False)
            except InvalidResponse as e:
                logger.debug(f"Received invalid response: {e}")
                self.__recover_connection__(True)
            cb(None)
            self.__jura_lock__.release()

        self.__brew_thread__ = Thread(target=__exec__)
        self.__brew_thread__.start()

    def brew_coffee(self, coffee_bean: int, water_volume: int, cb: Callable[[bool], None]):
        """
        BE EXTREMELY CAREFUL WHEN USING THIS FUNCTION AS IT OVERWRITE DIRECTLY TO THE EEPROM!!!!!

        :param coffee_bean: the number of bean (= [jura's gui] - 1)
        :param water_volume: the water volume in mL
        :param cb: callback when it ends, returns if the coffee was brewed
        """
        self.__jura_lock__.acquire()
        if self.__brew_thread__ is not None:
            self.__brew_thread__.join()
            self.__brew_thread__ = None

        def __exec__():
            if not self.__check_maker_versions__():
                cb(False)
                self.__jura_lock__.release()
                return

            if not self.__test_connection__()[0] or self.get_last_status().maker_status != MakerStatus.IDLE:
                logger.fatal(f"Machine is not connected ({self.__status__.maker_status}), cannot brew_coffee")
                cb(False)
                self.__jura_lock__.release()
                return

            try:
                self.__update_maker_status__(MakerStatus.BREWING)
                _coffee_bean = max(self.coffee_bean_param[0],
                                   min(self.coffee_bean_param[2], coffee_bean)) // self.coffee_bean_param[3]
                _water_volume = max(self.water_volume_param[0],
                                    min(self.water_volume_param[2], water_volume)) // self.water_volume_param[3]
                if self.jura.set_coffee_param(_coffee_bean, _water_volume):
                    self.__update_last_contact__()
                    if self.jura.write_with_response(self.coffee_button_map[CoffeeMaker.CoffeeType.COFFEE]) == "ok:":
                        self.__update_last_contact__()
                        logger.info(f"Brewing {_coffee_bean} beans {_water_volume} * 5 mL")
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
                                logger.warning(f"Received empty response")
                            except InvalidResponse as e:
                                logger.warning(f"Received invalid response: {e}")

                            if cs is None:
                                logger.warning(f"Received cs == None")
                            else:
                                last_water_sensor_values.append(cs.water_vol)
                                if (time.time() - start_time) < 5 and initial_water_sensor_value is None:
                                    initial_water_sensor_value = cs.water_vol
                                last_water_sensor_values = last_water_sensor_values[1:4]
                                end_detected = last_water_sensor_values[0] != 0 and \
                                               last_water_sensor_values[0] != initial_water_sensor_value and \
                                               all(v == last_water_sensor_values[0] for v in last_water_sensor_values)
                                self.__update_brewing__(
                                    int(last_water_sensor_values[-1] / self.water_sensor_to_water_value))
                        if end_detected:
                            logger.info(f"Coffee was brewed!")
                            logger.warning(f"last water sensor: {last_water_sensor_values}")
                        else:
                            logger.warning(f"Coffee ending could not be detected.")
                        self.__update_maker_status__(MakerStatus.IDLE)
                        cb(True)
                        self.__update_brewing__(0)
                        self.__jura_lock__.release()
                        return
                    else:
                        logger.warning("Could not press button.")
                else:
                    logger.warning("Could not send coffee params.")
            except EmptyResponse:
                logger.fatal(f"Received empty response while trying to brew_coffee")
            except InvalidResponse as e:
                logger.fatal(f"Received invalid response: {e} while trying to brew_coffee")
            cb(False)
            self.__jura_lock__.release()

        self.__brew_thread__ = Thread(target=__exec__)
        self.__brew_thread__.start()

    def reset_coffee_param(self, cb: Callable[[bool], None]):
        """
        BE EXTREMELY CAREFUL WHEN USING THIS FUNCTION AS IT OVERWRITE DIRECTLY TO THE EEPROM!!!!!

        Reset coffee default parameters to actual default

        """
        self.__jura_lock__.acquire()
        if self.__brew_thread__ is not None:
            self.__brew_thread__.join()
            self.__brew_thread__ = None

        def __exec__():
            if not self.__check_maker_versions__():
                cb(False)
                self.__jura_lock__.release()
                return

            if not self.__test_connection__()[0] or self.get_last_status().maker_status != MakerStatus.IDLE:
                logger.fatal(f"Machine is not connected ({self.__status__}), cannot brew_coffee")
                cb(False)
                self.__jura_lock__.release()
                return

            try:
                r = self.jura.set_coffee_param(self.coffee_bean_param[1] // self.coffee_bean_param[3],
                                               self.water_volume_param[1] // self.water_volume_param[3])
                self.__update_last_contact__()
                self.__update_maker_status__(MakerStatus.IDLE)
                cb(r)
                self.__jura_lock__.release()
                return
            except EmptyResponse:
                logger.fatal(f"Received empty response while trying to reset_coffee_param")
            except InvalidResponse as e:
                logger.fatal(f"Received invalid response: {e} while trying to reset_coffee_param")
            cb(False)
            self.__jura_lock__.release()

        self.__brew_thread__ = Thread(target=__exec__)
        self.__brew_thread__.start()

    def stop(self, cb: Callable[[bool], None]):
        self.__jura_lock__.acquire()
        if self.__brew_thread__ is not None:
            self.__brew_thread__.join()
            self.__brew_thread__ = None

        def __exec__():
            if not self.__check_maker_versions__():
                cb(False)
                self.__jura_lock__.release()
                return

            if not self.__test_connection__()[0] or self.get_last_status().maker_status != MakerStatus.IDLE:
                logger.fatal(f"Machine is not connected ({self.__status__}), cannot brew_coffee")
                cb(False)
                self.__jura_lock__.release()
                return

            try:
                r = self.jura.write_with_response(JuraCommand.BUTTON_6) == "ok:"
                self.__update_last_contact__()
                self.__update_maker_status__(MakerStatus.IDLE)
                cb(r)
                self.__jura_lock__.release()
                return
            except EmptyResponse:
                logger.fatal(f"Received empty response while trying to stop")
            except InvalidResponse as e:
                logger.fatal(f"Received invalid response: {e} while trying to stop")
            cb(False)
            self.__jura_lock__.release()

        self.__brew_thread__ = Thread(target=__exec__)
        self.__brew_thread__.start()

    def get_totals_statistics(self, cb: Callable[[Optional[Tuple[int, int, int, int, int, int, int]]], None]):
        self.__jura_lock__.acquire()
        if self.__brew_thread__ is not None:
            self.__brew_thread__.join()
            self.__brew_thread__ = None

        def __exec__():
            if not self.__check_maker_versions__():
                cb(None)
                self.__jura_lock__.release()
                return

            if not self.__test_connection__()[0] or self.get_last_status().maker_status != MakerStatus.IDLE:
                logger.fatal(f"Machine is not connected ({self.__status__}), cannot brew_coffee")
                cb(None)
                self.__jura_lock__.release()
                return

            try:
                self.__update_maker_status__(MakerStatus.DUMPING_STATISTICS)
                r = self.jura.get_totals_statistics()
                self.__update_last_contact__()
                self.__update_maker_status__(MakerStatus.IDLE)
                cb(r)
                self.__jura_lock__.release()
                return
            except EmptyResponse:
                logger.fatal(f"Received empty response while trying to get_totals_statistics")
            except InvalidResponse as e:
                logger.fatal(f"Received invalid response: {e} while trying to get_totals_statistics")
            cb(None)
            self.__jura_lock__.release()

        self.__brew_thread__ = Thread(target=__exec__)
        self.__brew_thread__.start()

from __future__ import annotations

import logging
import time
from enum import IntEnum, Enum
from typing import Optional, overload, Tuple, Callable

from juracoffeemachine.jura import JuraProtocol, JuraCommand, HZ, CS, IC, EmptyResponse, InvalidResponse, Response
from juracoffeemachine.serial import JuraSerial

logger = logging.getLogger(__name__)


class MakerStatus(Enum):
    NOT_CONNECTED = 0
    CONNECTED = 1
    OFF = 2
    DESYNCHRONISED = 3


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

    # min, initial, max, step
    coffee_bean_param = (0, 3, 7, 1)
    water_volume_param = (25, 100, 240, 5)
    water_sensor_to_water_value = 2.18595512820513

    def __init__(self, protocol: JuraProtocol):
        self.jura: JuraProtocol = protocol
        self.type = "ty:EF532M V02.03"
        self.__update_status__(MakerStatus.NOT_CONNECTED)
        response = self.jura.write_with_response(JuraCommand.GET_TYPE)
        assert response == self.type, f"This code was created for 'ty:EF532M V02.03' machine not '{response}'"
        response = self.jura.write_with_response(JuraCommand.GET_LOADER)
        assert response == "tl:BL_RL78 V01.31", f"This code was created for 'tl:BL_RL78 V01.31' machine not '{response}'"
        self.__update_status__(MakerStatus.CONNECTED)
        logger.info("Coffee Maker connected.")

    def __update_status__(self, new_status):
        self.__status__ = (time.time(), new_status)

    def get_last_status(self) -> Tuple[float, MakerStatus]:
        return self.__status__

    def test_and_reconnect(self, _tries=3) -> bool:
        if _tries == 3:
            logger.info(f"Testing coffee maker connection")
        is_invalid = False
        try:
            t = self.jura.write_with_response(JuraCommand.GET_TYPE)
            if t == self.type:
                self.__update_status__(MakerStatus.CONNECTED)
                logger.info("Connection recovered")
                return True
            else:
                logger.info(f"Received invalid response {t} != {self.type}")
                is_invalid = True
        except EmptyResponse:
            logger.info("Received empty response")
            self.__update_status__(MakerStatus.OFF)
        except InvalidResponse as e:
            logger.info(f"Received invalid response {e}")
            is_invalid = True
        finally:
            if is_invalid:
                self.__update_status__(MakerStatus.DESYNCHRONISED)
                if _tries > 0:
                    logger.info(f"Trying to reset buffers/reopened stream")
                    if _tries == 3:
                        self.jura.reset_streams()
                    else:
                        self.jura.reopen_serial()
                    return self.test_and_reconnect(_tries=_tries - 1)
                else:
                    logger.error(f"Reached maximum number of tries")
        return False

    @staticmethod
    def create_from_uart(port: str) -> CoffeeMaker:
        return CoffeeMaker(JuraProtocol(JuraSerial(port), lambda _: None))
        # lambda b: b.dump(os.path.join(os.path.dirname(__file__),
        #                               str(int(time.time()))))))

    @overload
    def ping(self, command: JuraCommand.HZ) -> Optional[HZ]:
        ...

    @overload
    def ping(self, command: JuraCommand.CS) -> Optional[CS]:
        ...

    @overload
    def ping(self, command: JuraCommand.IC) -> Optional[IC]:
        ...

    def ping(self, command: JuraCommand) -> Optional[Response]:
        logger.debug(f"Current status is {self.__status__}")
        try:
            r = self.jura.get_and_parse_message(command)
            self.__update_status__(MakerStatus.CONNECTED)
            return r
        except EmptyResponse:
            logger.debug(f"Received empty response")
            self.test_and_reconnect()
        except InvalidResponse as e:
            logger.debug(f"Received invalid response: {e}")
            self.test_and_reconnect()
        # TODO needs to decide what needs to be done when it recovers the machine from a except

    def brew_coffee(self, coffee_bean: int, water_volume: int, progress_cb: Callable[[int], None]) -> bool:
        """
        BE EXTREMELY CAREFUL WHEN USING THIS FUNCTION AS IT OVERWRITE DIRECTLY TO THE EEPROM!!!!!

        :param coffee_bean: the number of bean (= [jura's gui] - 1)
        :param water_volume: the water volume in mL
        :param progress_cb: callback with an approximation of how much water has flown
        :return: if it is possible and succeeded
        """
        if not self.test_and_reconnect() or self.__status__[1] != MakerStatus.CONNECTED:
            logger.fatal(f"Machine is not connected ({self.__status__}), cannot brew_coffee")
            return False

        try:
            coffee_bean = max(self.coffee_bean_param[0],
                              min(self.coffee_bean_param[2], coffee_bean)) // self.coffee_bean_param[3]
            water_volume = max(self.water_volume_param[0],
                               min(self.water_volume_param[2], water_volume)) // self.water_volume_param[3]
            if self.jura.set_coffee_param(coffee_bean, water_volume):
                if self.jura.write_with_response(self.coffee_button_map[CoffeeMaker.CoffeeType.COFFEE]) == "ok:":
                    logger.info(f"Brewing {coffee_bean} beans {water_volume} * 5 mL")
                    start_time = time.time()
                    end_detected = False
                    last_water_sensor_values = [0, 0, 0]

                    while (time.time() - start_time) < 120 and not end_detected:
                        cs = None
                        try:
                            cs = self.jura.get_and_parse_message(JuraCommand.CS)
                        except EmptyResponse:
                            logger.warning(f"Received empty response")
                        except InvalidResponse as e:
                            logger.warning(f"Received invalid response: {e}")

                        if cs is None:
                            logger.warning(f"Received cs == None")
                        else:
                            last_water_sensor_values.append(cs.water_vol)
                            last_water_sensor_values = last_water_sensor_values[1:4]
                            end_detected = last_water_sensor_values[0] != 0 and \
                                           all(v == last_water_sensor_values[0] for v in last_water_sensor_values)
                            progress_cb(int(last_water_sensor_values[-1] / self.water_sensor_to_water_value))
                    if end_detected:
                        logger.info(f"Coffee was brewed!")
                        logger.warning(f"last water sensor: {last_water_sensor_values}")
                    else:
                        logger.warning(f"Coffee ending could not be detected.")
                    return True
        except EmptyResponse:
            logger.fatal(f"Received empty response while trying to brew_coffee")
        except InvalidResponse as e:
            logger.fatal(f"Received invalid response: {e} while trying to brew_coffee")
        return False

    def reset_coffee_param(self) -> bool:
        """
        BE EXTREMELY CAREFUL WHEN USING THIS FUNCTION AS IT OVERWRITE DIRECTLY TO THE EEPROM!!!!!

        Reset coffee default parameters to actual default

        :return: if it is possible and succeeded
        """
        if not self.test_and_reconnect() or self.__status__[1] != MakerStatus.CONNECTED:
            logger.fatal(f"Machine is not connected ({self.__status__}), cannot reset_coffee_param")
            return False

        try:
            return self.jura.set_coffee_param(self.coffee_bean_param[1] // self.coffee_bean_param[3],
                                              self.water_volume_param[1] // self.water_volume_param[3])
        except EmptyResponse:
            logger.fatal(f"Received empty response while trying to reset_coffee_param")
        except InvalidResponse as e:
            logger.fatal(f"Received invalid response: {e} while trying to reset_coffee_param")
        return False

    def stop(self) -> bool:
        if not self.test_and_reconnect() or self.__status__[1] != MakerStatus.CONNECTED:
            logger.fatal(f"Machine is not connected ({self.__status__}), cannot stop")
            return False

        try:
            return self.jura.write_with_response(JuraCommand.BUTTON_6) == "ok:"
        except EmptyResponse:
            logger.fatal(f"Received empty response while trying to stop")
        except InvalidResponse as e:
            logger.fatal(f"Received invalid response: {e} while trying to stop")
        return False

    def get_totals_statistics(self) -> Optional[Tuple[int, int, int, int, int, int, int]]:
        if not self.test_and_reconnect() or self.__status__[1] != MakerStatus.CONNECTED:
            logger.fatal(f"Machine is not connected ({self.__status__}), cannot get_totals_statistics")
            return None

        try:
            return self.jura.get_totals_statistics()
        except EmptyResponse:
            logger.fatal(f"Received empty response while trying to get_totals_statistics")
        except InvalidResponse as e:
            logger.fatal(f"Received invalid response: {e} while trying to get_totals_statistics")
        return None

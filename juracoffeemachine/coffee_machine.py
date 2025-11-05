from __future__ import annotations

import logging
import time
from enum import IntEnum, Enum
from typing import Optional, overload

from juracoffeemachine.jura import JuraProtocol, JuraCommand, HZ, CS, IC, EmptyResponse, InvalidResponse
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
        self.status = (time.time(), new_status)

    def test_and_reconnect(self, _tries=3) -> bool:
        logger.info("Testing coffee maker connection")
        is_invalid = False
        try:
            t = self.jura.write_with_response(JuraCommand.GET_TYPE)
            if t == self.type:
                self.__update_status__(MakerStatus.CONNECTED)
                return True
            else:
                logger.warning(f"Received invalid response: {t} != {self.type}")
                is_invalid = True
        except EmptyResponse:
            logger.warning("Received empty response")
            self.__update_status__(MakerStatus.OFF)
        except InvalidResponse as e:
            logger.warning(f"Received invalid response: {e}")
            is_invalid = True
        finally:
            if is_invalid:
                self.__update_status__(MakerStatus.DESYNCHRONISED)
                if _tries > 0:
                    logger.warning(f"Trying to reset buffers/reopened stream")
                    if _tries == 3:
                        self.jura.reset_streams()
                    else:
                        self.jura.reopen_serial()
                    return self.test_and_reconnect(_tries=_tries - 1)
                else:
                    logger.warning(f"Reached maximum number of tries")
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
        logger.debug(f"Current status is {self.status}")
        try:
            return self.jura.get_and_parse_message(command)
        except EmptyResponse:
            logger.debug(f"Received empty response")
            self.test_and_reconnect()
        except InvalidResponse as e:
            logger.debug(f"Received invalid response: {e}")
            self.test_and_reconnect()

    def brew_coffee(self, coffee_bean: int, water_volume: int) -> bool:
        """
        BE EXTREMELY CAREFUL WHEN USING THIS FUNCTION AS IT OVERWRITE DIRECTLY TO THE EEPROM!!!!!

        :param coffee_bean: the number of bean (= [jura's gui] - 1)
        :param water_volume: the water volume in mL
        :return: if it is possible and succeeded
        """
        if not self.test_and_reconnect() or self.status[1] != MakerStatus.CONNECTED:
            logger.fatal(f"Machine is not connected ({self.status}), cannot brew_coffee")
            return False

        try:
            coffee_bean = max(self.coffee_bean_param[0],
                              min(self.coffee_bean_param[2], coffee_bean)) // self.coffee_bean_param[3]
            water_volume = max(self.water_volume_param[0],
                               min(self.water_volume_param[2], water_volume)) // self.water_volume_param[3]
            if self.jura.set_coffee_param(coffee_bean, water_volume):
                if self.jura.write_with_response(self.coffee_button_map[CoffeeMaker.CoffeeType.COFFEE]) == "ok:":
                    # TODO use cs when sending water and to detect end
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
        if not self.test_and_reconnect() or self.status[1] != MakerStatus.CONNECTED:
            logger.fatal(f"Machine is not connected ({self.status}), cannot reset_coffee_param")
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
        if not self.test_and_reconnect() or self.status[1] != MakerStatus.CONNECTED:
            logger.fatal(f"Machine is not connected ({self.status}), cannot stop")
            return False

        try:
            return self.jura.write_with_response(JuraCommand.BUTTON_6) == "ok:"
        except EmptyResponse:
            logger.fatal(f"Received empty response while trying to stop")
        except InvalidResponse as e:
            logger.fatal(f"Received invalid response: {e} while trying to stop")
        return False

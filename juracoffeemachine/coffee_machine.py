from __future__ import annotations

import logging
from enum import IntEnum

from juracoffeemachine.jura import JuraProtocol, JuraCommand
from juracoffeemachine.serial import JuraSerial

logger = logging.getLogger(__name__)


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
        self.connection: JuraProtocol = protocol
        response = self.connection.write_with_response(JuraCommand.GET_TYPE, 1.0)
        assert response == "ty:EF532M V02.03", f"This code was created for 'ty:EF532M V02.03' machine not '{response}'"
        response = self.connection.write_with_response(JuraCommand.GET_LOADER, 1.0)
        assert response == "tl:BL_RL78 V01.31", f"This code was created for 'tl:BL_RL78 V01.31' machine not '{response}'"
        logger.info("Coffee Maker connected.")

    @staticmethod
    def create_from_uart(port: str) -> CoffeeMaker:
        return CoffeeMaker(JuraProtocol(JuraSerial(port), lambda _: None))
        # lambda b: b.dump(os.path.join(os.path.dirname(__file__),
        #                               str(int(time.time()))))))

    def __send_command_and_wait_for_acknowledgement__(self, command: str):
        self.connection.write(command)
        result = self.connection.read()
        if result == "ok:":
            return True
        logger.error(f"Receive wrong acknowledgement {result}")
        return False

    def brew_coffee(self, coffee_bean: int, water_volume: int) -> bool:
        """
        BE EXTREMELY CAREFUL WHEN USING THIS FUNCTION AS IT OVERWRITE DIRECTLY TO THE EEPROM!!!!!

        :param coffee_bean: the number of bean (= [jura's gui] - 1)
        :param water_volume: the water volume in mL
        :return: if it is possible and succeeded
        """
        coffee_bean = max(self.coffee_bean_param[0],
                          min(self.coffee_bean_param[2], coffee_bean)) // self.coffee_bean_param[3]
        water_volume = max(self.water_volume_param[0],
                           min(self.water_volume_param[2], water_volume)) // self.water_volume_param[3]
        if self.connection.set_coffee_param(coffee_bean, water_volume):
            if self.__send_command_and_wait_for_acknowledgement__(self.coffee_button_map[CoffeeMaker.CoffeeType.COFFEE]):
                # TODO use cs when sending water and to detect end
                return True
        return False

    def reset_coffee_param(self) -> bool:
        """
        BE EXTREMELY CAREFUL WHEN USING THIS FUNCTION AS IT OVERWRITE DIRECTLY TO THE EEPROM!!!!!

        Reset coffee default parameters to actual default

        :return: if it is possible and succeeded
        """
        return self.connection.set_coffee_param(self.coffee_bean_param[1] // self.coffee_bean_param[3],
                                                self.water_volume_param[1] // self.water_volume_param[3])

    def stop(self) -> bool:
        resp = self.connection.write_with_response(JuraCommand.BUTTON_6)
        return resp == "ok:"

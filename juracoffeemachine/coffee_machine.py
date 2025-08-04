from __future__ import annotations

import logging
import os
import time
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
    water_volume_param = (80, 100, 150, 5)

    def __init__(self, protocol: JuraProtocol):
        self.connection: JuraProtocol = protocol
        response = self.connection.write_with_response(JuraCommand.GET_TYPE, 1.0)
        assert response == "ty:EF532M V02.03", f"This code was created for 'ty:EF532M V02.03' machine not '{response}'"
        response = self.connection.write_with_response(JuraCommand.GET_LOADER, 1.0)
        assert response == "tl:BL_RL78 V01.31", f"This code was created for 'tl:BL_RL78 V01.31' machine not '{response}'"

    @staticmethod
    def create_from_uart(port: str) -> CoffeeMaker:
        return CoffeeMaker(JuraProtocol(JuraSerial(port),
                                        lambda b: b.dump(os.path.join(os.path.dirname(__file__),
                                                                      str(int(time.time()))))))

    def __send_command_and_wait_for_acknowledgement__(self, command: str):
        self.connection.write(command)
        result = self.connection.read()
        if result == "ok:":
            return True
        logger.error(f"Receive wrong acknowledgement {result}")
        return False

    def __reach_value__(self, initial: int, goal: int, step: int):
        logger.info(f"doing {abs(goal - initial) // step} button push")
        to_send = abs(goal - initial) // step
        tries = 3
        while tries > 0 and to_send > 0:
            tries -= 1
            for _ in range(0, to_send):
                logger.info("less" if goal < initial else "more")
                self.__less__() if goal < initial else self.__more__()
                time.sleep(0.1)

            for _ in range(0, to_send):
                if self.connection.read() == "ok:":
                    to_send -= 1

    def brew_coffee(self, coffee: CoffeeType, coffee_bean: int, water_volume: int) -> True:
        coffee_bean = max(self.coffee_bean_param[0], min(self.coffee_bean_param[2], coffee_bean))
        water_volume = max(self.water_volume_param[0], min(self.water_volume_param[2], water_volume))
        if self.__send_command_and_wait_for_acknowledgement__(self.coffee_button_map[coffee]):
            dt = time.time()
            time.sleep(0.6)
            if coffee_bean != self.coffee_bean_param[1]:
                logger.info("sending coffee commands")
                self.__reach_value__(self.coffee_bean_param[1], coffee_bean, self.coffee_bean_param[3])

            # TODO use cs to detect when to send water volume commands?
            dt = time.time() - dt
            if dt < 6:
                logger.info(f"waiting {6 - dt}")
                time.sleep(6 - dt)

            if water_volume != self.water_volume_param[1]:
                logger.info("sending water volume commands")
                self.__reach_value__(self.water_volume_param[1], water_volume, self.water_volume_param[3])

            # TODO use cs to detect end

    def __less__(self):
        """
        A subsequent call to self.connection.read() must be done to receive the acknowledgment
        """
        self.connection.write(JuraCommand.BUTTON_2)

    def __more__(self):
        """
        A subsequent call to self.connection.read() must be done to receive the acknowledgment
        """
        self.connection.write(JuraCommand.BUTTON_5)

    def __stop__(self):
        """
        A subsequent call to self.connection.read() must be done to receive the acknowledgment
        """
        self.connection.write(JuraCommand.BUTTON_6)

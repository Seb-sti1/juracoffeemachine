import logging
from enum import IntEnum, StrEnum

from juracoffeemachine.jura import JuraProtocol, JuraCommand

logger = logging.getLogger(__name__)


class CoffeeMaker:
    class CoffeeType(IntEnum):
        ESPRESSO = 0
        RISTRETTO = 1
        COFFEE = 2
        SPECIAL = 3

    class JuraButton(StrEnum):
        BUTTON_1 = "FA:04\r\n"
        BUTTON_2 = "FA:05\r\n"
        BUTTON_3 = "FA:06\r\n"
        BUTTON_4 = "FA:07\r\n"
        BUTTON_5 = "FA:08\r\n"
        BUTTON_6 = "FA:09\r\n"

    # Mapping coffee type to button
    coffee_button_map = {
        CoffeeType.ESPRESSO: JuraButton.BUTTON_1,
        CoffeeType.RISTRETTO: JuraButton.BUTTON_2,
        CoffeeType.COFFEE: JuraButton.BUTTON_4,
        CoffeeType.SPECIAL: JuraButton.BUTTON_5,
    }

    def __init__(self, protocol: JuraProtocol):
        self.connection = protocol

        response = self.connection.write_decoded_with_response(JuraCommand.GET_TYPE, 1.0)
        logger.info(f"Response: {response}")
        # assert response == "ty:EF532M V02.03", f"This code was created for 'ty:EF532M V02.03' machine not '{response}'"

    def __send_command_and_wait_for_acknowledgement__(self, command: str):
        self.connection.write_decoded(command)
        result = self.connection.read_decoded()
        if result == "ok:":
            return True
        logger.error(f"Receive wrong acknowledgement {result}")
        return False

    def brew_coffee(self, coffee: CoffeeType):
        self.__send_command_and_wait_for_acknowledgement__(self.coffee_button_map[coffee])

    def less(self):
        self.connection.write_decoded(CoffeeMaker.JuraButton.BUTTON_2)

    def more(self):
        self.connection.write_decoded(CoffeeMaker.JuraButton.BUTTON_5)

    def stop(self):
        self.connection.write_decoded(CoffeeMaker.JuraButton.BUTTON_6)

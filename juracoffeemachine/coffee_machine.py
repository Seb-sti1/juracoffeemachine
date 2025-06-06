from enum import IntEnum

class CoffeeMaker:
    class CoffeeType(IntEnum):
        ESPRESSO = 0
        RISTRETTO = 1
        COFFEE = 2
        SPECIAL = 3

    class JuttaButton(IntEnum):
        BUTTON_1 = 1
        BUTTON_2 = 2
        BUTTON_3 = 3
        BUTTON_4 = 4
        BUTTON_5 = 5
        BUTTON_6 = 6

    NUM_PAGES = 1

    # Mapping coffee type to page
    coffee_page_map = {
        CoffeeType.ESPRESSO: 0,
        CoffeeType.RISTRETTO: 0,
        CoffeeType.COFFEE: 0,
        CoffeeType.SPECIAL: 0,
    }

    # Mapping coffee type to button
    coffee_button_map = {
        CoffeeType.ESPRESSO: JuttaButton.BUTTON_1,
        CoffeeType.RISTRETTO: JuttaButton.BUTTON_2,
        CoffeeType.COFFEE: JuttaButton.BUTTON_4,
        CoffeeType.SPECIAL: JuttaButton.BUTTON_5,
    }

    def __init__(self, protocol):
        self.connection = protocol

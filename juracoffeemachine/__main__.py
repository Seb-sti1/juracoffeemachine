import argparse
import logging

from juracoffeemachine.coffee_machine import CoffeeMaker
from juracoffeemachine.jura import JuraProtocol

logger = logging.getLogger(__name__)


def on_press(key, machine: CoffeeMaker):
    try:
        if key.char == '+':
            logger.info("More of something")
            machine.more()
        elif key.char == '-':
            logger.info("Less of something")
            machine.less()
    except AttributeError:
        pass  # special keys like ctrl, alt, etc.


def start_keyboard_listener(machine: CoffeeMaker):
    listener = keyboard.Listener(on_press=lambda key: on_press(key, machine))
    listener.daemon = True
    listener.start()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', default='/dev/ttyUSB0', help='Serial port (default: /dev/ttyUSB0)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable debug output')
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
    logging.getLogger().setLevel(logging.DEBUG if args.verbose else logging.INFO)

    machin = CoffeeMaker(JuraProtocol(args.port))
    machin.brew_coffee(machin.CoffeeType.COFFEE)

    start_keyboard_listener(machin)

    while True:
        result = machin.connection.read_decoded()
        logger.info(f"Response: {result}\n")


if __name__ == "__main__":
    from pynput import keyboard

    main()

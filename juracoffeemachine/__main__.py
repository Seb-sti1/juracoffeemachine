import argparse
import logging
import sys

from juracoffeemachine.coffee_machine import CoffeeMaker

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', default='/dev/ttyUSB0', help='Serial port (default: /dev/ttyUSB0)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable debug output')
    args = parser.parse_args()

    fmt = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s", datefmt='%Y-%m-%d %H:%M:%S')
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, handlers=[console_handler])
    logging.getLogger().setLevel(logging.DEBUG if args.verbose else logging.INFO)

    machin = CoffeeMaker.create_from_uart(args.port)
    machin.brew_coffee(machin.CoffeeType.COFFEE, 3, 100)


if __name__ == "__main__":
    main()

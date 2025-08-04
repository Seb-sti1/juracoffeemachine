import argparse
import logging
import sys
import time
from pathlib import Path

from juracoffeemachine import JuraCommand
from juracoffeemachine.coffee_machine import CoffeeMaker

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('port', default='/dev/ttyUSB0', help='Serial port (default: /dev/ttyUSB0)')
    parser.add_argument('action', choices=["while_hz", "while_cs", "brew_coffee", "eeprom"],
                        help='What should be done')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable debug output')
    args = parser.parse_args()

    fmt = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s", datefmt='%Y-%m-%d %H:%M:%S')
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, handlers=[console_handler])
    logging.getLogger().setLevel(logging.DEBUG if args.verbose else logging.INFO)

    machin = CoffeeMaker.create_from_uart(args.port)
    if args.action == "while_hz":
        while True:
            logger.info(machin.connection.get_and_parse_message(JuraCommand.HZ))
    elif args.action == "while_cs":
        while True:
            logger.info(machin.connection.get_and_parse_message(JuraCommand.CS))
    elif args.action == "brew_coffee":
        machin.brew_coffee(machin.CoffeeType.COFFEE, 2, 100)
    elif args.action == "eeprom":
        machin.connection.dump_eeprom_to_file(Path(f"./eeprom{int(time.time())}.dump"))


if __name__ == "__main__":
    main()

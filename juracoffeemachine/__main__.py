import argparse
import logging
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from juracoffeemachine import JuraCommand
from juracoffeemachine.coffee_machine import CoffeeMaker

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('port', default='/dev/ttyUSB0', help='Serial port (default: /dev/ttyUSB0)')
    parser.add_argument('action', choices=["hz", "cs", "stat",
                                           "while_hz", "while_cs",
                                           "brew_coffee",
                                           "more", "less", "stop",
                                           "eeprom"],
                        help='What should be done')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable debug output')
    args = parser.parse_args()

    fmt = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s", datefmt='%Y-%m-%d %H:%M:%S')
    rotating_handler = RotatingFileHandler(Path("~/coffee/jura.log").expanduser(), maxBytes=10485760, backupCount=10)
    rotating_handler.setFormatter(fmt)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, handlers=[rotating_handler, console_handler])
    logging.getLogger().setLevel(logging.DEBUG if args.verbose else logging.INFO)

    machin = CoffeeMaker.create_from_uart(args.port)
    if args.action == "hz":
        msg = machin.connection.get_and_parse_message(JuraCommand.HZ)
        logger.info(f"{msg.raw}: {msg}")
    elif args.action == "cs":
        msg = machin.connection.get_and_parse_message(JuraCommand.CS)
        logger.info(f"{msg.raw}: {msg}")
    elif args.action == "stat":
        machin.connection.log_statistics()
    elif args.action == "coffee_param":
        q1, q2, v = machin.connection.get_coffee_param()
        logger.info(f"q1 {q1} {int(q1, 16)}")
        logger.info(f"q2 {q2} {int(q2, 16)}")
        logger.info(f"v {v} {int(v, 16)}")
    elif args.action == "while_hz":
        while True:
            msg = machin.connection.get_and_parse_message(JuraCommand.HZ)
            logger.info(f"{msg.raw}: {msg}")
    elif args.action == "while_cs":
        while True:
            msg = machin.connection.get_and_parse_message(JuraCommand.CS)
            logger.info(f"{msg.raw}: {msg}")
    elif args.action == "brew_coffee":
        machin.brew_coffee(machin.CoffeeType.COFFEE, 2, 100)
    elif args.action == "more":
        logger.info("Button acknowledge" if machin.more() else "Sent but not acknowledge")
    elif args.action == "less":
        logger.info("Button acknowledge" if machin.less() else "Sent but not acknowledge")
    elif args.action == "stop":
        logger.info("Button acknowledge" if machin.stop() else "Sent but not acknowledge")
    elif args.action == "eeprom":
        machin.connection.dump_eeprom_to_file(Path(f"./eeprom{int(time.time())}.dump"))
    machin.connection.__serial__.close()


if __name__ == "__main__":
    main()

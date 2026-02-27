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
    parser.add_argument('action', choices=["ty", "hz", "cs", "stat",
                                           "while_hz", "while_cs",
                                           "brew_coffee",
                                           "stop",
                                           "eeprom"],
                        help='The action to perform.')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable debug output.')
    args = parser.parse_args()

    fmt = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s", datefmt='%Y-%m-%d %H:%M:%S')
    rotating_handler = RotatingFileHandler(Path("~/coffee/jura.log").expanduser(), maxBytes=10485760, backupCount=10)
    rotating_handler.setFormatter(fmt)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        handlers=[rotating_handler, console_handler])
    logging.getLogger().setLevel(logging.DEBUG if args.verbose else logging.INFO)

    machin = CoffeeMaker.create_from_uart(args.port)
    if args.action == "ty":
        msg = machin.jura.write_with_response(JuraCommand.GET_TYPE)
        logger.info(f"{msg}")
    if args.action == "hz":
        msg = machin.jura.get_and_parse_message(JuraCommand.HZ)
        logger.info(f"{msg.raw}: {msg}")
    elif args.action == "cs":
        msg = machin.jura.get_and_parse_message(JuraCommand.CS)
        logger.info(f"{msg.raw}: {msg}")
    elif args.action == "ic":
        msg = machin.jura.get_and_parse_message(JuraCommand.IC)
        logger.info(f"{msg.raw}: {msg}")
    elif args.action == "stat":
        machin.jura.log_statistics()
    elif args.action == "coffee_param":
        q, v = machin.jura.get_coffee_param()
        logger.info(f"{q} beans and {v} mL")
    elif args.action == "while_hz":
        while True:
            msg = machin.jura.get_and_parse_message(JuraCommand.HZ)
            logger.info(f"{msg.raw}: {msg}")
    elif args.action == "while_cs":
        while True:
            msg = machin.jura.get_and_parse_message(JuraCommand.CS)
            logger.info(f"{msg.raw}: {msg}")
    elif args.action == "brew_coffee":
        machin.brew_coffee(2, 100, lambda v: logger.info(f"Volume is {v}"))
    elif args.action == "stop":
        logger.info("Button acknowledge" if machin.stop(lambda _: None) else "Sent but not acknowledge")
    elif args.action == "eeprom":
        machin.jura.dump_eeprom_to_file(Path(f"./eeprom{int(time.time())}.dump"))
    machin.jura.__serial__.close()


if __name__ == "__main__":
    main()

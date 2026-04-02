import argparse
import logging
import sys
import threading
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Callable

from juracoffeemachine import JuraCommand
from juracoffeemachine.coffee_machine import CoffeeMaker

logger = logging.getLogger(__name__)


def spin(func: Callable[[], None]):
    is_running = True

    def _exec():
        while is_running:
            try:
                func()
            except Exception as e:
                logger.warning(f"{type(e)}")

    t = threading.Thread(target=_exec)
    t.start()
    input("Press any 'enter' to stop.")
    is_running = False
    t.join()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('port', default='/dev/ttyUSB0', help='Serial port (default: /dev/ttyUSB0)')
    parser.add_argument('action', choices=["ty", "hz", "cs", "stat",
                                           "while_hz", "while_cs", "while_read", "while_ic",
                                           "brew_coffee", "stop", "eeprom", "turn_on"],
                        help='The action to perform.')
    parser.add_argument('address', nargs='?', default="0x0000",
                        help="An address (in [0x0, 0x400[) to read.")
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
    elif args.action == "turn_on":
        machin.turn_on()
    elif args.action == "coffee_param":
        q, v = machin.jura.get_coffee_param()
        logger.info(f"{q} beans and {v} mL")
    elif args.action == "while_hz":
        def _run():
            msg = machin.jura.get_and_parse_message(JuraCommand.HZ)
            logger.info(f"{msg.raw}: {msg}")

        spin(_run)
    elif args.action == "while_cs":
        def _run():
            msg = machin.jura.get_and_parse_message(JuraCommand.CS)
            logger.info(f"{msg.raw}: {msg}")

        spin(_run)
    elif args.action == "while_ic":
        def _run():
            msg = machin.jura.get_and_parse_message(JuraCommand.IC)
            logger.info(f"{msg.raw}: {msg}")

        spin(_run)
    elif args.action == "while_read":
        addr = int(args.address, 16)
        if addr < 0 or addr >= 0x400:
            logger.fatal("Address is outside authorised range [0x0, 0x400[.")
            exit(-1)

        def _run():
            msg = machin.jura.read_eeprom(addr)
            if msg is None:
                logger.info(f"None")
            else:
                logger.info(f"{hex(msg)} = {msg}")

        spin(_run)
    elif args.action == "brew_coffee":
        machin.brew_coffee(2, 100, lambda v: logger.info(f"Volume is {v}"))
    elif args.action == "stop":
        logger.info("Button acknowledge" if machin.jura.write_with_response(JuraCommand.BUTTON_6) == ":ok"
                    else "Sent but not acknowledge")
    elif args.action == "eeprom":
        machin.jura.dump_eeprom_to_file(Path(f"./eeprom{int(time.time())}.dump"))
    machin.jura.__serial__.close()


if __name__ == "__main__":
    main()

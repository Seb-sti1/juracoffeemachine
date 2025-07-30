import argparse
import logging
import os.path
import sys
import time

from juracoffeemachine.coffee_machine import CoffeeMaker
from juracoffeemachine.jura import JuraProtocol, JuraCommand

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

    machin = CoffeeMaker(JuraProtocol(args.port, lambda b: b.dump(os.path.join(__path__, str(int(time.time()))))))
    machin.brew_coffee(machin.CoffeeType.COFFEE, machin.coffee_bean_param[1], machin.water_volume_param[1])


    if False:
        cmd = JuraCommand.CS
        # cmd = JuraCommand.HZ
        while True:
            print(f"{','.join([str(i).ljust(5) for i in machin.connection.get_and_parse_message(cmd)])}")
            time.sleep(0.4)
    else:
        with open(f"./{int(time.time())}.dump", "wb") as f:
            eeprom = machin.connection.dump_eeprom()
            data = int(eeprom, 16)
            f.write(data.to_bytes(len(eeprom) // 2))


if __name__ == "__main__":
    main()

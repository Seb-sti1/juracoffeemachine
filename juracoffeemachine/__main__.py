import argparse
import logging

from juracoffeemachine.jura import JuraProtocol, JuraCommand

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', default='/dev/ttyUSB0', help='Serial port (default: /dev/ttyUSB0)')
    parser.add_argument('--verbose', action='store_true', help='Enable debug output')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
    )
    logging.getLogger().setLevel(logging.DEBUG if args.verbose else logging.INFO)

    p = JuraProtocol(args.port)
    response = p.write_decoded_with_response(JuraCommand.GET_TYPE, 1.0)
    logger.info(f"Response: {response}")

    response = p.write_decoded_with_response(JuraCommand.DEBUG, 1.0)
    logger.info(f"Response: {response}")


    while True:
        result = p.read_decoded(1.0)
        logger.info(f"Response: {result}")


if __name__ == "__main__":
    main()

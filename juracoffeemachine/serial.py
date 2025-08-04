import logging
from pathlib import Path
from typing import Tuple

import serial

logger = logging.getLogger(__name__)


class CircularBuffer:
    def __init__(self, size: int):
        self.size = size
        self.buffer: list[Tuple[bool, str]] = []

    def append(self, is_write: bool, data: bytes):
        self.buffer.append((is_write, data.hex()))
        if len(self.buffer) > self.size:
            self.buffer = self.buffer[1:]

    def dump(self, path: Path):
        f = path.open("r")
        f.write('\n'.join(map(lambda e: f"{e[0]}, {e[1]}", self.buffer)))


class AbstractSerial:
    def __init__(self):
        pass

    def get_debug_buffer(self) -> CircularBuffer:
        raise NotImplemented("This is an abstract method")

    def close(self):
        raise NotImplemented("This is an abstract method")

    def read(self, size=4) -> bytes:
        raise NotImplemented("This is an abstract method")

    def write(self, data: bytes) -> int:
        raise NotImplemented("This is an abstract method")

    def flush(self):
        raise NotImplemented("This is an abstract method")


class JuraSerial(AbstractSerial):
    def __init__(self, device: str, circular_debug_buffer_size: int = 5000):
        super().__init__()
        self.device = device
        self.__serial__ = serial.Serial()
        self.__open_serial__()
        self.buffer = CircularBuffer(circular_debug_buffer_size)

    def __open_serial__(self):
        try:
            self.__serial__.port = self.device
            self.__serial__.baudrate = 9600
            self.__serial__.bytesize = serial.EIGHTBITS
            self.__serial__.parity = serial.PARITY_NONE
            self.__serial__.stopbits = serial.STOPBITS_ONE
            self.__serial__.timeout = 0.2  # corresponds to VTIME=2
            self.__serial__.xonxoff = False
            self.__serial__.rtscts = False
            self.__serial__.dsrdtr = False
            self.__serial__.open()
            self.__serial__.reset_input_buffer()
            self.__serial__.reset_output_buffer()
            logger.info(f"Serial port {self.device} opened and configured")
        except serial.SerialException as e:
            logger.error(f"Failed to open or configure '{self.device}': {e}")
            raise RuntimeError(f"Failed to open or configure '{self.device}': {e}")

    def get_debug_buffer(self) -> CircularBuffer:
        return self.buffer

    def close(self):
        if self.__serial__.is_open:
            self.__serial__.close()
            logger.info(f"Serial port {self.device} closed")

    def read(self, size=4) -> bytes:
        if not self.__serial__.is_open:
            raise RuntimeError("Serial port not open")
        data = self.__serial__.read(size)
        self.buffer.append(False, data)
        return data

    def write(self, data: bytes) -> int:
        if not self.__serial__.is_open:
            raise RuntimeError("Serial port not open")
        count = self.__serial__.write(data)
        self.buffer.append(True, data)
        return count

    def flush(self):
        if self.__serial__.is_open:
            self.__serial__.flush()

import logging
import re
import threading
import time
from enum import StrEnum
from pathlib import Path
from typing import List, Optional, Tuple, Callable

import serial

logger = logging.getLogger(__name__)


class JuraCommand(StrEnum):
    POWER_OFF = "AN:01\r\n"
    TEST_MODE_ON = "AN:20\r\n"
    TEST_MODE_OFF = "AN:21\r\n"

    GET_TYPE = "TY:\r\n"
    GET_LOADER = "TL:\r\n"

    BREW_GROUP_TO_BREWING_POSITION = "FN:22\r\n"
    BREW_GROUP_RESET = "FN:0D\r\n"

    GRINDER_ON = "FN:07\r\n"
    GRINDER_OFF = "FN:08\r\n"
    COFFEE_PRESS_ON = "FN:0B\r\n"
    COFFEE_PRESS_OFF = "FN:0C\r\n"
    COFFEE_WATER_HEATER_ON = "FN:03\r\n"
    COFFEE_WATER_HEATER_OFF = "FN:04\r\n"
    COFFEE_WATER_PUMP_ON = "FN:01\r\n"
    COFFEE_WATER_PUMP_OFF = "FN:02\r\n"

    CS = "CS:\r\n"
    HZ = "HZ:\r\n"
    IC = "IC:\r\n"
    DEBUG = "FN:89\r\n"


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


class JuraProtocol:
    FORMAT_REGEX = {
        JuraCommand.HZ: r"hz:..............,....,....,....,....,....,.,....,......,..",
        JuraCommand.CS: r"cs:...........................................",
        JuraCommand.IC: r"ic:....",
    }

    # Extracted groups are indicated by - or . in examples
    GROUP_REGEX = {
        # hz:.10-0-.000.000,0288,....,....,....,0000,0,....,0.0.-.,12
        # hz:01010110000000,0288,00ED,0107,03E8,0000,0,0017,000100,12
        # UNKNOWNA: first seen will cleaning
        # BOWL_MOVING: flag active at the same time as the coffee bowl moves
        # SLEEPING (extremely probable): 0 = turn on, 1 = sleeping mode
        # BOWL_POS (extremely probable): the position of the bowl containing the grounded coffee
        # WATER_VOL (extremely probable): value*0,4577 ~= water volume in ml
        # HEATER (extremely probable): the value of the heater of the machine
        # WATER_TANK (extremely probable): 0 = water tank present, 1 = water tank absent
        # COFFEE_WASTE (probable): 0 = waste tank full, 1 = waste tank not full
        # DRAINING_TRAY (probable): 0 = draining tray present, 1 = draining tray absent
        # DRAINING_TRAY_FULL (probable): 0 = draining tray not full, 1 = draining tray full
        JuraCommand.HZ: r"^hz:(?P<SLEEPING>.)10(?P<UNKNOWNA>.)0(?P<UNKNOWND>.)(?P<BOWL_MOVING>.)000(?P<UNKNOWNC>.)000,"
                        r"0288,(?P<BOWL_POS>....),(?P<WATER_VOL>....),(?P<HEATER>....),0000,0,(?P<UNKNOWNE>....),"
                        r"0(?P<WATER_TANK>.)0(?P<COFFEE_WASTE>.)(?P<DRAINING_TRAY>.)(?P<DRAINING_TRAY_FULL>.),12$",
        # cs:....00000....---000...---0..000....00...---
        # cs:03770000000ED000000000000006000011C00000000
        # HEATER (extremely probable): the value of the heater of the machine
        # BOWL_POS_2 (unsure): variation are the same as BOWL_POS but maximum value seems different
        # UNKNOWNB: 0-1023, close to UNKNOWNG + UNKNOWNH
        # UNKNOWNF: 0-1023, seen while getting hot water
        # UNKNOWNG: 0-1023, seems very synchronised with WATER_VOL
        # UNKNOWNH: between 0-1023 just before the BOWL_POS moves, could be when grinding coffee beans
        # UNKNOWNI: 6 all the time except after the water finished then 176
        # WATER_VOL (extremely probable): value*0,4577 ~= water volume in ml
        # UNKNOWNK: 0-1023, just before water start flowing and smaller value at the very end
        # UNKNOWNL: 0-1023, at the very end
        JuraCommand.CS: r"^cs:(?P<HEATER>....)00000(?P<BOWL_POS_2>....)(?P<UNKNOWNB>...)(?P<UNKNOWNF>...)"
                        r"(?P<UNKNOWNG>...)(?P<UNKNOWNH>...)0(?P<UNKNOWNI>..)000(?P<WATER_VOL>....)00"
                        r"(?P<UNKNOWNK>...)(?P<UNKNOWNL>...)$",
        # UNKNOWNM: seems an aggregate of multiple value. maybe a OR of multiple flags converted into an int.
        JuraCommand.IC: r"ic:(?P<UNKNOWNM>....)",
    }

    def __init__(self, device: str, unexpected_msg_callback: Callable[[CircularBuffer], None]):
        self.__serial__ = JuraSerial(device)
        self.actionLock = threading.Lock()
        self.unexpected_msg_callback = unexpected_msg_callback

    def get_raw(self, command: JuraCommand) -> Optional[str]:
        return self.write_with_response(command)

    def get_and_parse_message(self, command: JuraCommand, raw: Optional[str] = None) -> Optional[list[int]]:
        raw = raw if raw is not None else self.get_raw(command)
        if raw is None:
            return None
        m = re.match(JuraProtocol.GROUP_REGEX[command], raw)
        if m:
            return list(map(lambda t: int(t, 16), m.groups()))
        else:
            logger.warning(f"Received an unexpected message value {raw}.")
            self.unexpected_msg_callback(self.__serial__.get_debug_buffer())
            return None

    def dump_eeprom(self):
        mem = ""
        address = 0
        while address < 0x400:
            cmd = f"RT:{hex(address)[2:].rjust(4).replace(' ', '0').upper()}\r\n"
            r = self.write_with_response(cmd)
            logger.debug(f"{cmd.strip()} -> {r}")
            if ":" in r:
                mem += r.split(":")[-1]
            else:
                logger.warning(f"Error while fetching {cmd}...")
            address += 16
        return mem

    def dump_eeprom_to_file(self, path: Path):
        with open(path, "wb") as f:
            eeprom = self.dump_eeprom()
            data = int(eeprom, 16)
            f.write(data.to_bytes(len(eeprom) // 2))

    @staticmethod
    def encode(dec_data: int) -> List[int]:
        # 1111 0000 -> 0000 1111:
        tmp = ((dec_data & 0xF0) >> 4) | ((dec_data & 0x0F) << 4)

        # 1100 1100 -> 0011 0011:
        tmp = ((tmp & 0xC0) >> 2) | ((tmp & 0x30) << 2) | ((tmp & 0x0C) >> 2) | ((tmp & 0x03) << 2)

        BASE = 0b01011011

        enc_data = [0] * 4
        enc_data[0] = BASE | ((tmp & 0b10000000) >> 2)
        enc_data[0] |= ((tmp & 0b01000000) >> 4)

        enc_data[1] = BASE | (tmp & 0b00100000)
        enc_data[1] |= ((tmp & 0b00010000) >> 2)

        enc_data[2] = BASE | ((tmp & 0b00001000) << 2)
        enc_data[2] |= (tmp & 0b00000100)

        enc_data[3] = BASE | ((tmp & 0b00000010) << 4)
        enc_data[3] |= ((tmp & 0b00000001) << 2)

        return enc_data

    @staticmethod
    def decode(enc_data: List[int]) -> int:
        B2_MASK = 0b10000000 >> 2
        B5_MASK = 0b10000000 >> 5

        dec_data = 0
        dec_data |= (enc_data[0] & B2_MASK) << 2
        dec_data |= (enc_data[0] & B5_MASK) << 4

        dec_data |= (enc_data[1] & B2_MASK)
        dec_data |= (enc_data[1] & B5_MASK) << 2

        dec_data |= (enc_data[2] & B2_MASK) >> 2
        dec_data |= (enc_data[2] & B5_MASK)

        dec_data |= (enc_data[3] & B2_MASK) >> 4
        dec_data |= (enc_data[3] & B5_MASK) >> 2

        # 1111 0000 -> 0000 1111:
        dec_data = ((dec_data & 0xF0) >> 4) | ((dec_data & 0x0F) << 4)

        # 1100 1100 -> 0011 0011:
        dec_data = ((dec_data & 0xC0) >> 2) | ((dec_data & 0x30) << 2) | ((dec_data & 0x0C) >> 2) | (
                (dec_data & 0x03) << 2)

        return dec_data

    def write(self, data: str) -> bool:
        self.actionLock.acquire()
        try:
            for c in data:
                written = self.__serial__.write(bytes(self.encode(ord(c))))
                self.__serial__.flush()
                time.sleep(0.008)
                if written != 4:
                    return False
            return True
        finally:
            self.actionLock.release()

    def read(self, end_separator: str = "\r\n", timeout: float = 3, wait: float = 0.5) -> str:
        self.actionLock.acquire()
        result = []
        start = time.time()
        while not "".join(result).endswith(end_separator) and (time.time() - start) < timeout:
            buffer = self.__serial__.read(4)
            if len(buffer) == 4:
                decoded = self.decode(list(buffer))
                result.append(chr(decoded))
            else:
                logger.warning(f"Returned too small buffer ({len(buffer)})")
                time.sleep(wait)
        self.actionLock.release()
        return "".join(result).strip()

    def write_with_response(self, data: str, timeout: float = 3) -> Optional[str]:
        if self.write(data):
            return self.read(timeout=timeout)
        return None

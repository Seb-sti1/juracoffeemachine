import logging
import re
import threading
import time
from enum import StrEnum, Enum
from pathlib import Path
from typing import List, Optional, Callable, overload, Tuple, Literal

from juracoffeemachine.response import HZ, CS, IC, Response
from juracoffeemachine.serial import CircularBuffer, AbstractSerial

logger = logging.getLogger(__name__)

RESPONSE_PATTERN = re.compile(r"^[a-zA-Z0-9:, ._]+$")


class EmptyResponse(RuntimeError):
    def __init__(self):
        super()


class InvalidResponse(RuntimeError):
    def __init__(self, content):
        super()
        self.content = content


class JuraAddress(Enum):
    TOT_ESPRESSO = 0x0
    TOT_2_ESPRESSO = 0xE0
    TOT_RISTRETTO = 0x1
    TOT_2_RISTRETTO = 0xE1
    TOT_COFFEE = 0x2
    TOT_2_COFFEE = 0xE2
    TOT_SPECIAL = 0x208
    TOT_HOT_WATER = 0x014

    # quantity of coffee grounds in the tank, will ask to empty it once value is above or equal to 1100 (x044C)
    COFFEE_GROUNDS_TANK = 0x119

    # note that daily is not really daily, it is a value that the user can reset manually
    DAILY_ESPRESSO = 0x180
    # DAILY_2_ESPRESSO = ?
    DAILY_RISTRETTO = 0x181
    # DAILY_2_RISTRETTO = ?
    DAILY_COFFEE = 0x182
    # DAILY_2_COFFEE = ?
    DAILY_SPECIAL = 0x188
    DAILY_HOT_WATER = 0x18D

    # default parameter for brewing a coffee
    PARAM_COFFEE_BEAN_Q = 0xD6
    PARAM_COFFEE_WATER_V = 0x13C


class JuraCommand(StrEnum):
    POWER_OFF = "AN:01"
    TEST_MODE_ON = "AN:20"
    TEST_MODE_OFF = "AN:21"
    DEBUG = "FN:89"

    GET_TYPE = "TY:"
    GET_LOADER = "TL:"

    BREW_GROUP_TO_BREWING_POSITION = "FN:22"
    BREW_GROUP_RESET = "FN:0D"

    GRINDER_ON = "FN:07"
    GRINDER_OFF = "FN:08"
    COFFEE_PRESS_ON = "FN:0B"
    COFFEE_PRESS_OFF = "FN:0C"
    COFFEE_WATER_HEATER_ON = "FN:03"
    COFFEE_WATER_HEATER_OFF = "FN:04"
    COFFEE_WATER_PUMP_ON = "FN:01"
    COFFEE_WATER_PUMP_OFF = "FN:02"

    BUTTON_1 = "FA:04"
    BUTTON_2 = "FA:05"
    BUTTON_3 = "FA:06"
    BUTTON_4 = "FA:07"
    BUTTON_5 = "FA:08"
    BUTTON_6 = "FA:09"

    # read from eeprom. address is 2 bytes hex in uppercase. last address is 0x3FF.
    RE = "RE:"  # read 2 bytes from eeprom
    RT = "RT:"  # read 32 bytes from eeprom
    WE = "WE:"  # write 2 bytes to eeprom. format is WE:AAAA,DDDD where A is the address, D is the data

    CS = "CS:"
    HZ = "HZ:"
    IC = "IC:"


class JuraProtocol:
    RESPONSE = {
        JuraCommand.HZ: HZ,
        JuraCommand.CS: CS,
        JuraCommand.IC: IC,
    }

    # min, initial, max, step
    coffee_param = (1, 4, 8, 1)
    water_param = (25, 100, 240, 5)
    water_sensor_to_water_value = 2.18595512820513
    pump_speed = 4.0  # mL/s

    def __init__(self, s: AbstractSerial, unexpected_msg_callback: Callable[[CircularBuffer], None]):
        self.__serial__ = s
        self.actionLock = threading.Lock()
        self.unexpected_msg_callback = unexpected_msg_callback

    def reopen_serial(self):
        self.__serial__.reopen()

    def reset_streams(self):
        self.__serial__.reset_streams()

    @overload
    def get_and_parse_message(self, command: Literal[JuraCommand.HZ], raw: Optional[str] = None) -> Optional[HZ]:
        ...

    @overload
    def get_and_parse_message(self, command: Literal[JuraCommand.CS], raw: Optional[str] = None) -> Optional[CS]:
        ...

    @overload
    def get_and_parse_message(self, command: Literal[JuraCommand.IC], raw: Optional[str] = None) -> Optional[IC]:
        ...

    def get_and_parse_message(self, command: JuraCommand, raw: Optional[str] = None) -> Optional[Response]:
        raw = raw if raw is not None else self.write_with_response(command)
        if raw is None:
            return None

        if JuraProtocol.RESPONSE[command].check_format(raw):
            if not JuraProtocol.RESPONSE[command].check_static(raw):
                logger.fatal(f"Unexpected value changed '{raw}'.")
                self.unexpected_msg_callback(self.__serial__.get_debug_buffer())
            return JuraProtocol.RESPONSE[command](raw)
        else:
            logger.fatal(f"Message does not respect format '{raw}'.")
            self.unexpected_msg_callback(self.__serial__.get_debug_buffer())
            return None

    def log_statistics(self):
        for a in JuraAddress:
            logger.info(f"{a.name}: {self.read_eeprom(int(a.value))}")

    def get_totals_statistics(self) -> Tuple[Optional[int], Optional[int], Optional[int],
    Optional[int], Optional[int], Optional[int], Optional[int]]:
        r = []

        for a in [JuraAddress.TOT_ESPRESSO, JuraAddress.TOT_2_ESPRESSO,
                  JuraAddress.TOT_RISTRETTO, JuraAddress.TOT_2_RISTRETTO,
                  JuraAddress.TOT_COFFEE, JuraAddress.TOT_2_COFFEE,
                  JuraAddress.TOT_SPECIAL]:
            read = self.read_eeprom(int(a.value))
            r.append(None if read is None else read)
        return tuple(r)

    def __get_raw_coffee_param__(self) -> Tuple[Optional[int], Optional[int]]:
        return (self.read_eeprom(int(JuraAddress.PARAM_COFFEE_BEAN_Q.value)),
                self.read_eeprom(int(JuraAddress.PARAM_COFFEE_WATER_V.value)))

    def get_coffee_param(self) -> Tuple[Optional[int], Optional[int]]:
        """
        :return: (number of coffee bean as per jura's gui, water volume in mL*)
        """
        raw = self.__get_raw_coffee_param__()
        return (None if raw[0] is None else raw[0] >> 4 + 1,
                None if raw[1] is None else raw[1] * 5)

    def set_coffee_param(self, coffee_bean: int, water_volume: int) -> bool:
        """
        BE EXTREMELY CAREFUL WHEN USING THIS FUNCTION AS IT OVERWRITE DIRECTLY TO THE EEPROM!!!!!

        :param coffee_bean: the quantity of coffee (number of beans as per jura's gui)
        :param water_volume: the water volume in mL
        :return: if it is possible and succeeded
        """
        if coffee_bean < self.coffee_param[0] or coffee_bean > self.coffee_param[2]:
            return False
        if water_volume < self.water_param[0] or water_volume > self.water_param[2]:
            return False
        current_q, current_v = self.__get_raw_coffee_param__()
        if current_q is None:
            logger.error(f"current_q is None")
            return False
        new_q = (current_q & 0b1111111100001111) | (((coffee_bean // self.coffee_param[3]) - 1) << 4)
        new_v = (water_volume // self.water_param[3]) & 0b0000000011111111
        if current_q == new_q and current_v == new_v:
            return True
        elif current_q == new_q:
            return self.write_eeprom(int(JuraAddress.PARAM_COFFEE_WATER_V.value), new_v)
        elif current_v == new_v:
            return self.write_eeprom(int(JuraAddress.PARAM_COFFEE_BEAN_Q.value), new_q)
        else:
            return (self.write_eeprom(int(JuraAddress.PARAM_COFFEE_BEAN_Q.value), new_q) and
                    self.write_eeprom(int(JuraAddress.PARAM_COFFEE_WATER_V.value), new_v))

    @staticmethod
    def __int_to_hex_str__(value: int) -> str:
        return hex(value)[2:].rjust(4).replace(' ', '0').upper()

    def write_eeprom(self, address: int, data: int) -> bool:
        """
        BE EXTREMELY CAREFUL WHEN USING THIS FUNCTION AS IT OVERWRITE DIRECTLY TO THE EEPROM!!!!!

        :param address: where to write data
        :param data: the data to write to the eeprom
        :return: if it is possible and succeeded
        """
        if address < 0 or address >= 0x400:
            return False
        if data < 0 or data >= 0x10000:
            return False
        address_str = self.__int_to_hex_str__(address)
        data_str = self.__int_to_hex_str__(data)
        cmd = f"{JuraCommand.WE}{address_str},{data_str}"
        r = self.write_with_response(cmd)
        return r == "ok:"

    def read_eeprom(self, address: int, use_rt: bool = False) -> Optional[int]:
        address_str = self.__int_to_hex_str__(address)
        prefix = JuraCommand.RT if use_rt else JuraCommand.RE
        cmd = f"{prefix}{address_str}"
        r = self.write_with_response(cmd)
        if r is None or not r.startswith(prefix.lower()):
            return None
        try:
            return int(r.replace(prefix.lower(), ''), 16)
        except ValueError:
            return None

    def dump_eeprom(self) -> int:
        mem = 0
        for address in range(0, 0x400, 16):
            r = None
            for _ in range(3):
                r = self.read_eeprom(address, True)
                if r is not None:
                    break
            logger.info(f"{hex(address).ljust(6)}: {hex(r) if r is not None else r}")
            if r is None:
                r = 0
            mem |= r << (address * 16)
        return mem

    def dump_eeprom_to_file(self, path: Path):
        with open(path, "wb") as f:
            eeprom = self.dump_eeprom()
            f.write(eeprom.to_bytes(0x800))

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

    def write(self, data: str, end_separator: str = "\r\n") -> bool:
        self.actionLock.acquire()
        try:
            encoded_data = bytes([d for c in data + end_separator for d in self.encode(ord(c))])
            written = self.__serial__.write(encoded_data)
            return written == len(encoded_data)
        finally:
            self.actionLock.release()

    def read(self, end_separator: str = "\r\n", timeout: float = 3, wait: float = 0.5) -> str:
        self.actionLock.acquire()
        result = []
        buffer = []
        empty = True
        start = time.time()
        while not "".join(result).endswith(end_separator) and (time.time() - start) < timeout:
            # always try and read chunk of 4 bytes
            # as this is required to decode one char
            buffer += self.__serial__.read(4 - len(buffer))
            empty = len(buffer) == 0 and empty
            if len(buffer) == 4:
                decoded = self.decode(buffer)
                result.append(chr(decoded))
                buffer = []
            else:
                time.sleep(wait)
        self.actionLock.release()
        if empty:
            raise EmptyResponse()
        r = "".join(result).strip()
        if not RESPONSE_PATTERN.fullmatch(r):
            raise InvalidResponse(r)
        return r

    def write_with_response(self, data: str, timeout: float = 3) -> Optional[str]:
        if self.write(data):
            return self.read(timeout=timeout)
        return None

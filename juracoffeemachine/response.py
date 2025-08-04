import re


class Response:

    def __init__(self, raw: str):
        self.raw = raw

    @staticmethod
    def check_format(data: str) -> bool:
        raise NotImplemented("This is abstract")

    @staticmethod
    def check_static(data: str) -> bool:
        raise NotImplemented("This is abstract")

    @staticmethod
    def __check__(data: str, regex: str) -> bool:
        return re.match(regex, data) is not None

    def __repr__(self):
        return self.__str__()


class HZ(Response):
    # Extracted groups are indicated by - or . in examples
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
    FORMAT = r"^hz:..............,....,....,....,....,....,.,....,......,..$"
    STATIC_VALUE = r"^hz:.10.0..000.000,0288,....,....,....,0000,0,....,0.0...,12$"
    GROUPS = (r"^hz:(?P<SLEEPING>.)..(?P<UNKNOWNA>.).(?P<UNKNOWND>.)(?P<BOWL_MOVING>.)...(?P<UNKNOWNC>.)...,"
              r"....,(?P<BOWL_POS>....),(?P<WATER_VOL>....),(?P<HEATER>....),....,.,(?P<UNKNOWNE>....),"
              r".(?P<WATER_TANK>.).(?P<COFFEE_WASTE>.)(?P<DRAINING_TRAY>.)(?P<DRAINING_TRAY_FULL>.),..$")

    def __init__(self, data: str):
        super().__init__(data)
        m = re.match(HZ.GROUPS, data)
        assert m is not None
        group = m.groupdict()

        self.is_sleeping = group["SLEEPING"] == "1"
        self.is_bowl_moving = group["BOWL_MOVING"] == "0"
        self.bowl_pos = int(group["BOWL_POS"], 16)
        self.water_vol = int(group["WATER_VOL"], 16)
        self.heater = int(group["HEATER"], 16)
        self.is_water_tank_present = group["WATER_TANK"] == "0"
        self.is_coffee_waste_full = group["COFFEE_WASTE"] == "0"
        self.is_draining_tray_present = group["DRAINING_TRAY"] == "0"
        self.is_draining_tray_full = group["DRAINING_TRAY_FULL"] == "1"
        self.unknown_a = group["UNKNOWNA"] == "1"
        self.unknown_d = group["UNKNOWND"] == "1"
        self.unknown_c = group["UNKNOWNC"] == "1"
        self.unknown_e = int(group["UNKNOWNE"], 16)

    @staticmethod
    def check_format(data: str) -> bool:
        return Response.__check__(data, HZ.FORMAT)

    @staticmethod
    def check_static(data: str) -> bool:
        return Response.__check__(data, HZ.STATIC_VALUE)

    def __str__(self):
        return (f"{self.is_sleeping}, {self.is_bowl_moving}, {self.bowl_pos}, {self.water_vol}, {self.heater},"
                f" {self.is_water_tank_present}, {self.is_coffee_waste_full}, {self.is_draining_tray_present},"
                f" {self.is_draining_tray_full}, {self.unknown_a}, {self.unknown_d}, {self.unknown_c}, {self.unknown_e}")


class CS(Response):
    # Extracted groups are indicated by - or . in examples
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
    FORMAT = r"^cs:...........................................$"
    STATIC_VALUE = r"^cs:....00000.......000......0..000....00......$"
    GROUPS = (r"^cs:(?P<HEATER>....)00000(?P<BOWL_POS_2>....)(?P<UNKNOWNB>...)(?P<UNKNOWNF>...)"
              r"(?P<UNKNOWNG>...)(?P<UNKNOWNH>...)0(?P<UNKNOWNI>..)000(?P<WATER_VOL>....)00"
              r"(?P<UNKNOWNK>...)(?P<UNKNOWNL>...)$")

    def __init__(self, data: str):
        super().__init__(data)
        m = re.match(CS.GROUPS, data)
        assert m is not None
        group = m.groupdict()

        self.heater = int(group["HEATER"], 16)
        self.bowl_pos_2 = int(group["BOWL_POS_2"], 16)
        self.water_vol = int(group["WATER_VOL"], 16)
        self.unknown_b = int(group["UNKNOWNB"], 16)
        self.unknown_f = int(group["UNKNOWNF"], 16)
        self.unknown_g = int(group["UNKNOWNG"], 16)
        self.unknown_h = int(group["UNKNOWNH"], 16)
        self.unknown_i = int(group["UNKNOWNI"], 16)
        self.unknown_k = int(group["UNKNOWNK"], 16)
        self.unknown_l = int(group["UNKNOWNL"], 16)

    @staticmethod
    def check_format(data: str) -> bool:
        return Response.__check__(data, CS.FORMAT)

    @staticmethod
    def check_static(data: str) -> bool:
        return Response.__check__(data, CS.STATIC_VALUE)

    def __str__(self):
        return (f"{self.heater}, {self.bowl_pos_2}, {self.water_vol}, {self.unknown_b}, {self.unknown_f},"
                f" {self.unknown_g}, {self.unknown_h}, {self.unknown_i}, {self.unknown_k}, {self.unknown_l}")


class IC(Response):
    # Extracted groups are indicated by - or . in examples
    # ic:1720
    # ic:....

    # UNKNOWNM: seems an aggregate of multiple value. maybe a OR of multiple flags converted into an int.
    FORMAT = r"^ic:....$"
    STATIC_VALUE = r"^ic:....$"
    GROUPS = r"^ic:(?P<UNKNOWNM>....)$"

    def __init__(self, data: str):
        super().__init__(data)
        m = re.match(IC.GROUPS, data)
        assert m is not None
        group = m.groupdict()

        self.unknown_m = group["UNKNOWNM"]

    @staticmethod
    def check_format(data: str) -> bool:
        return Response.__check__(data, IC.FORMAT)

    @staticmethod
    def check_static(data: str) -> bool:
        return Response.__check__(data, IC.STATIC_VALUE)

    def __str__(self):
        return f"{self.unknown_m}"
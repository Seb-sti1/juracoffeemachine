import pytest

from juracoffeemachine import JuraProtocol, JuraCommand, CS, HZ, IC
from test_jura import ValidSerial


def encode_str(data) -> list[int]:
    encoded = []
    for c in data + "\r\n":
        encoded += JuraProtocol.encode(ord(c))  # tested in test_jura.py
    return encoded


def test_valid_hz():
    t = ValidSerial()
    t.read_buffer = encode_str("hz:01010110000000,0288,00ED,0107,03E8,0000,0,0017,000100,12")

    def callback():
        assert False

    p = JuraProtocol(t, unexpected_msg_callback=lambda c: callback())
    hz = p.get_and_parse_message(JuraCommand.HZ)
    assert isinstance(hz, HZ)
    assert t.read_index == len(t.read_buffer)

    assert not hz.is_sleeping
    assert not hz.is_bowl_moving
    assert hz.bowl_pos == 237
    assert hz.water_vol == 263
    assert hz.heater == 1000
    assert hz.is_water_tank_present
    assert hz.is_draining_tray_present
    assert not hz.is_draining_tray_full


def test_wrong_static_hz():
    t = ValidSerial()
    t.read_buffer = encode_str("hz:00010110000000,0288,00ED,0107,03E8,0000,0,0017,000100,13")
    callback_called = [False]

    def callback(_):
        callback_called[0] = True

    p = JuraProtocol(t, unexpected_msg_callback=lambda c: callback(c))
    hz = p.get_and_parse_message(JuraCommand.HZ)
    assert isinstance(hz, HZ)
    assert callback_called[0]
    assert t.read_index == len(t.read_buffer)

    assert not hz.is_sleeping
    assert not hz.is_bowl_moving
    assert hz.bowl_pos == 237
    assert hz.water_vol == 263
    assert hz.heater == 1000
    assert hz.is_water_tank_present
    assert hz.is_draining_tray_present
    assert not hz.is_draining_tray_full


@pytest.mark.parametrize(
    "hz_msg",
    [
        "hz:01010110000000,0288,00ED,0107,03E8,0000,0,",
        "hz:00010110000000,0288,00ED,0107,03E8,000,0,0017,000100,12",
        "hz:010101100000000288,00ED,0107,03E8,0000,0,0017,000100,12"
    ],
)
def test_wrong_format_hz(hz_msg):
    t = ValidSerial()
    t.read_buffer = encode_str(hz_msg)
    callback_called = [False]

    def callback(_):
        callback_called[0] = True

    p = JuraProtocol(t, unexpected_msg_callback=lambda c: callback(c))
    hz = p.get_and_parse_message(JuraCommand.HZ)
    assert hz is None
    assert callback_called[0]
    assert t.read_index == len(t.read_buffer)


def test_valid_cs():
    t = ValidSerial()
    t.read_buffer = encode_str("cs:03770000000ED000000000000006000011C00000000")

    def callback():
        assert False

    p = JuraProtocol(t, unexpected_msg_callback=lambda c: callback())
    cs = p.get_and_parse_message(JuraCommand.CS)
    assert isinstance(cs, CS)
    assert t.read_index == len(t.read_buffer)

    assert cs.bowl_pos_2 == 237
    assert cs.water_vol == 284
    assert cs.heater == 887
    assert not cs.is_water_tank_empty


def test_wrong_static_cs():
    t = ValidSerial()
    t.read_buffer = encode_str("cs:0377000FF00ED000000000000006000011C00000000")
    callback_called = [False]

    def callback(_):
        callback_called[0] = True

    p = JuraProtocol(t, unexpected_msg_callback=lambda c: callback(c))
    cs = p.get_and_parse_message(JuraCommand.CS)
    assert isinstance(cs, CS)
    assert callback_called[0]
    assert t.read_index == len(t.read_buffer)

    assert cs.bowl_pos_2 == 237
    assert cs.water_vol == 284
    assert cs.heater == 887
    assert not cs.is_water_tank_empty


@pytest.mark.parametrize(
    "cs_msg",
    [
        "cs:03770000000ED000000000000006000011C0000",
    ],
)
def test_wrong_format_cs(cs_msg):
    t = ValidSerial()
    t.read_buffer = encode_str(cs_msg)
    callback_called = [False]

    def callback(_):
        callback_called[0] = True

    p = JuraProtocol(t, unexpected_msg_callback=lambda c: callback(c))
    cs = p.get_and_parse_message(JuraCommand.CS)
    assert cs is None
    assert callback_called[0]
    assert t.read_index == len(t.read_buffer)


def test_valid_ic():
    t = ValidSerial()
    t.read_buffer = encode_str("ic:1706")

    def callback():
        assert False

    p = JuraProtocol(t, unexpected_msg_callback=lambda c: callback())
    ic = p.get_and_parse_message(JuraCommand.IC)
    assert isinstance(ic, IC)
    assert t.read_index == len(t.read_buffer)

    assert ic.unknown_m == "1706"

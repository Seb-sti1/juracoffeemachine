import time

from juracoffeemachine import JuraProtocol, CoffeeMaker, JuraCommand
from tests.test_jura import ValidSerial
from tests.test_response import encode_str


def init_seq_coffee_brew(t: ValidSerial) -> list[int]:
    write_buffer = encode_str("TY:")
    t.read_buffer = encode_str("ty:EF532M V02.03")
    write_buffer += encode_str("TL:")
    t.read_buffer += encode_str("tl:BL_RL78 V01.31")
    write_buffer += encode_str("TY:")
    t.read_buffer += encode_str("ty:EF532M V02.03")
    return write_buffer


def test_brew_coffee():
    t = ValidSerial()
    write_buffer = init_seq_coffee_brew(t)
    write_buffer += encode_str("RE:00D6")
    t.read_buffer += encode_str("re:0031")
    write_buffer += encode_str("RE:013C")
    t.read_buffer += encode_str("re:0014")
    write_buffer += encode_str("WE:00D6,0011")
    t.read_buffer += encode_str("ok:")
    write_buffer += encode_str("WE:013C,0012")
    t.read_buffer += encode_str("ok:")
    write_buffer += encode_str(JuraCommand.BUTTON_4)
    t.read_buffer += encode_str("ok:")
    write_buffer += encode_str("CS:")
    t.read_buffer += encode_str("cs:03770000000ED000000000000006000011C00000000")
    write_buffer += encode_str("CS:")
    t.read_buffer += encode_str("cs:03770000000ED000000000000006000011C00000000")
    write_buffer += encode_str("CS:")
    t.read_buffer += encode_str("cs:03770000000ED000000000000006000011C00000000")

    def callback():
        assert False

    result = [False]

    def _cb(_b):
        result[0] = True

    p = JuraProtocol(t, unexpected_msg_callback=lambda c: callback())
    m = CoffeeMaker(p)
    m.brew_coffee((CoffeeMaker.coffee_bean_param[1] - 2),
                  (CoffeeMaker.water_volume_param[1] - CoffeeMaker.water_volume_param[3] * 2),
                  _cb)

    while not result[0]:
        time.sleep(1)

    assert t.read_index == len(t.read_buffer)
    assert t.write_buffer == write_buffer


def test_reset_coffee_param_valid():
    t = ValidSerial()
    write_buffer = init_seq_coffee_brew(t)
    write_buffer += encode_str("RE:00D6")
    t.read_buffer += encode_str("re:0041")
    write_buffer += encode_str("RE:013C")
    t.read_buffer += encode_str("re:0015")
    write_buffer += encode_str("WE:00D6,0031")
    t.read_buffer += encode_str("ok:")
    write_buffer += encode_str("WE:013C,0014")
    t.read_buffer += encode_str("ok:")

    def callback():
        assert False

    result = [False]

    def _cb(_b):
        result[0] = True

    p = JuraProtocol(t, unexpected_msg_callback=lambda c: callback())
    m = CoffeeMaker(p)
    m.reset_coffee_param(_cb)

    while not result[0]:
        time.sleep(1)

    assert t.read_index == len(t.read_buffer)
    assert t.write_buffer == write_buffer


def test_brew_then_reset():
    t = ValidSerial()
    write_buffer = init_seq_coffee_brew(t)
    write_buffer += encode_str("RE:00D6")
    t.read_buffer += encode_str("re:0031")
    write_buffer += encode_str("RE:013C")
    t.read_buffer += encode_str("re:0014")
    write_buffer += encode_str("WE:00D6,0011")
    t.read_buffer += encode_str("ok:")
    write_buffer += encode_str("WE:013C,0012")
    t.read_buffer += encode_str("ok:")
    write_buffer += encode_str(JuraCommand.BUTTON_4)
    t.read_buffer += encode_str("ok:")
    write_buffer += encode_str("CS:")
    t.read_buffer += encode_str("cs:03770000000ED000000000000006000011C00000000")
    write_buffer += encode_str("CS:")
    t.read_buffer += encode_str("cs:03770000000ED000000000000006000011C00000000")
    write_buffer += encode_str("CS:")
    t.read_buffer += encode_str("cs:03770000000ED000000000000006000011C00000000")
    write_buffer += encode_str("TY:")
    t.read_buffer += encode_str("ty:EF532M V02.03")
    write_buffer += encode_str("RE:00D6")
    t.read_buffer += encode_str("re:0041")
    write_buffer += encode_str("RE:013C")
    t.read_buffer += encode_str("re:0015")
    write_buffer += encode_str("WE:00D6,0031")
    t.read_buffer += encode_str("ok:")
    write_buffer += encode_str("WE:013C,0014")
    t.read_buffer += encode_str("ok:")

    def callback():
        assert False

    result = [False]

    def _cb(_b):
        result[0] = True

    p = JuraProtocol(t, unexpected_msg_callback=lambda c: callback())
    m = CoffeeMaker(p)
    m.brew_coffee((CoffeeMaker.coffee_bean_param[1] - 2),
                  (CoffeeMaker.water_volume_param[1] - CoffeeMaker.water_volume_param[3] * 2),
                  _cb)
    m.reset_coffee_param(_cb)

    while not result[0]:
        time.sleep(1)

    assert t.read_index == len(t.read_buffer)
    assert t.write_buffer == write_buffer


import pytest

from juracoffeemachine import JuraProtocol, CoffeeMaker, JuraCommand
from tests.test_jura import ValidSerial
from tests.test_response import encode_str


# TODO repare tests here

def test_init_valid():
    t = ValidSerial()
    write_buffer = []
    # t.read_buffer = encode_str("ty:EF532M V02.03")
    # t.read_buffer += encode_str("tl:BL_RL78 V01.31")
    # write_buffer += encode_str("TY:")
    # write_buffer += encode_str("TL:")

    def callback():
        assert False

    p = JuraProtocol(t, unexpected_msg_callback=lambda c: callback())
    m = CoffeeMaker(p)

    assert t.read_index == len(t.read_buffer)
    assert t.write_buffer == write_buffer


@pytest.mark.skip(reason="Requires modification to account for cs monitoring")
def test_brew_no_mods_valid():
    t = ValidSerial()
    write_buffer = encode_str("TY:")
    t.read_buffer = encode_str("ty:EF532M V02.03")
    write_buffer += encode_str("TL:")
    t.read_buffer += encode_str("tl:BL_RL78 V01.31")
    write_buffer += encode_str("TY:")
    t.read_buffer += encode_str("ty:EF532M V02.03")
    write_buffer += encode_str("RE:00D6")
    t.read_buffer += encode_str("re:0031")
    write_buffer += encode_str("RE:013C")
    t.read_buffer += encode_str("re:0014")
    write_buffer += encode_str(JuraCommand.BUTTON_4)
    t.read_buffer += encode_str("ok:")

    def callback():
        assert False

    p = JuraProtocol(t, unexpected_msg_callback=lambda c: callback())
    m = CoffeeMaker(p)
    m.brew_coffee(CoffeeMaker.coffee_bean_param[1],
                  CoffeeMaker.water_volume_param[1])

    assert t.read_index == len(t.read_buffer)
    assert t.write_buffer == write_buffer


def init_seq_coffee_brew(t: ValidSerial) -> list[int]:
    write_buffer = encode_str("TY:")
    t.read_buffer = encode_str("ty:EF532M V02.03")
    write_buffer += encode_str("TL:")
    t.read_buffer += encode_str("tl:BL_RL78 V01.31")
    write_buffer += encode_str("TY:")
    t.read_buffer += encode_str("ty:EF532M V02.03")
    write_buffer += encode_str("RE:00D6")
    t.read_buffer += encode_str("re:0031")
    write_buffer += encode_str("RE:013C")
    t.read_buffer += encode_str("re:0014")
    return write_buffer


@pytest.mark.skip(reason="Requires modification to account for cs monitoring")
def test_brew_more_coffee_valid():
    t = ValidSerial()
    write_buffer = init_seq_coffee_brew(t)
    write_buffer += encode_str("WE:00D6,0051")
    t.read_buffer += encode_str("ok:")
    write_buffer += encode_str(JuraCommand.BUTTON_4)
    t.read_buffer += encode_str("ok:")

    def callback():
        assert False

    p = JuraProtocol(t, unexpected_msg_callback=lambda c: callback())
    m = CoffeeMaker(p)
    m.brew_coffee(CoffeeMaker.coffee_bean_param[1] + 2,
                  CoffeeMaker.water_volume_param[1])

    assert t.read_index == len(t.read_buffer)
    assert t.write_buffer == write_buffer


@pytest.mark.skip(reason="Requires modification to account for cs monitoring")
def test_brew_less_water_valid():
    t = ValidSerial()
    write_buffer = init_seq_coffee_brew(t)
    write_buffer += encode_str("WE:013C,0016")
    t.read_buffer += encode_str("ok:")
    write_buffer += encode_str(JuraCommand.BUTTON_4)
    t.read_buffer += encode_str("ok:")

    def callback():
        assert False

    p = JuraProtocol(t, unexpected_msg_callback=lambda c: callback())
    m = CoffeeMaker(p)
    m.brew_coffee(CoffeeMaker.coffee_bean_param[1],
                  CoffeeMaker.water_volume_param[1] + CoffeeMaker.water_volume_param[3] * 2)

    assert t.read_index == len(t.read_buffer)
    assert t.write_buffer == write_buffer


@pytest.mark.skip(reason="Requires modification to account for cs monitoring")
def test_brew_less_coffee_and_water_valid():
    t = ValidSerial()
    write_buffer = init_seq_coffee_brew(t)
    write_buffer += encode_str("WE:00D6,0011")
    t.read_buffer += encode_str("ok:")
    write_buffer += encode_str("WE:013C,0012")
    t.read_buffer += encode_str("ok:")
    write_buffer += encode_str(JuraCommand.BUTTON_4)
    t.read_buffer += encode_str("ok:")

    def callback():
        assert False

    p = JuraProtocol(t, unexpected_msg_callback=lambda c: callback())
    m = CoffeeMaker(p)
    m.brew_coffee(CoffeeMaker.coffee_bean_param[1] - 2,
                  CoffeeMaker.water_volume_param[1] - CoffeeMaker.water_volume_param[3] * 2)

    assert t.read_index == len(t.read_buffer)
    assert t.write_buffer == write_buffer


@pytest.mark.asyncio
async def test_reset_coffee_param_valid():
    t = ValidSerial()
    # write_buffer = encode_str("TY:")
    # t.read_buffer = encode_str("ty:EF532M V02.03")
    # write_buffer += encode_str("TL:")
    # t.read_buffer += encode_str("tl:BL_RL78 V01.31")
    write_buffer = encode_str("TY:")
    t.read_buffer = encode_str("ty:EF532M V02.03")
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

    p = JuraProtocol(t, unexpected_msg_callback=lambda c: callback())
    m = CoffeeMaker(p)
    await m.reset_coffee_param()

    assert t.read_index == len(t.read_buffer)
    assert t.write_buffer == write_buffer

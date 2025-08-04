from juracoffeemachine import JuraProtocol, CoffeeMaker, JuraCommand
from tests.test_jura import ValidSerial
from tests.test_response import encode_str


def test_init_valid():
    t = ValidSerial()
    t.read_buffer = encode_str("ty:EF532M V02.03")
    t.read_buffer += encode_str("tl:BL_RL78 V01.31")
    write_buffer = encode_str("TY:")
    write_buffer += encode_str("TL:")

    def callback():
        assert False

    p = JuraProtocol(t, unexpected_msg_callback=lambda c: callback())
    m = CoffeeMaker(p)

    assert t.read_index == len(t.read_buffer)
    assert t.write_buffer == write_buffer


def test_brew_no_mods_valid():
    t = ValidSerial()
    t.read_buffer = encode_str("ty:EF532M V02.03")
    t.read_buffer += encode_str("tl:BL_RL78 V01.31")
    t.read_buffer += encode_str("ok:")
    write_buffer = encode_str("TY:")
    write_buffer += encode_str("TL:")
    write_buffer += encode_str(JuraCommand.BUTTON_4)

    def callback():
        assert False

    p = JuraProtocol(t, unexpected_msg_callback=lambda c: callback())
    m = CoffeeMaker(p)
    m.brew_coffee(CoffeeMaker.CoffeeType.COFFEE,
                  CoffeeMaker.coffee_bean_param[1],
                  CoffeeMaker.water_volume_param[1])

    assert t.read_index == len(t.read_buffer)
    assert t.write_buffer == write_buffer


def test_brew_less_watter_valid():
    t = ValidSerial()
    t.read_buffer = encode_str("ty:EF532M V02.03")
    t.read_buffer += encode_str("tl:BL_RL78 V01.31")
    t.read_buffer += encode_str("ok:")
    t.read_buffer += encode_str("ok:")
    t.read_buffer += encode_str("ok:")
    write_buffer = encode_str("TY:")
    write_buffer += encode_str("TL:")
    write_buffer += encode_str(JuraCommand.BUTTON_4)
    write_buffer += encode_str(JuraCommand.BUTTON_5)
    write_buffer += encode_str(JuraCommand.BUTTON_5)

    def callback():
        assert False

    p = JuraProtocol(t, unexpected_msg_callback=lambda c: callback())
    m = CoffeeMaker(p)
    m.brew_coffee(CoffeeMaker.CoffeeType.COFFEE,
                  CoffeeMaker.coffee_bean_param[1] + 2,
                  CoffeeMaker.water_volume_param[1])

    assert t.read_index == len(t.read_buffer)
    assert t.write_buffer == write_buffer


def test_brew_more_coffee_valid():
    t = ValidSerial()
    t.read_buffer = encode_str("ty:EF532M V02.03")
    t.read_buffer += encode_str("tl:BL_RL78 V01.31")
    t.read_buffer += encode_str("ok:")
    t.read_buffer += encode_str("ok:")
    t.read_buffer += encode_str("ok:")
    write_buffer = encode_str("TY:")
    write_buffer += encode_str("TL:")
    write_buffer += encode_str(JuraCommand.BUTTON_4)
    write_buffer += encode_str(JuraCommand.BUTTON_2)
    write_buffer += encode_str(JuraCommand.BUTTON_2)

    def callback():
        assert False

    p = JuraProtocol(t, unexpected_msg_callback=lambda c: callback())
    m = CoffeeMaker(p)
    m.brew_coffee(CoffeeMaker.CoffeeType.COFFEE,
                  CoffeeMaker.coffee_bean_param[1],
                  CoffeeMaker.water_volume_param[1] - CoffeeMaker.water_volume_param[3] * 2)

    assert t.read_index == len(t.read_buffer)
    assert t.write_buffer == write_buffer

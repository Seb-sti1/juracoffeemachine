from threading import Event
from typing import Optional, Tuple

import pytest

from juracoffeemachine import JuraProtocol, CoffeeMaker, JuraCommand, HZ, Response, CS, CoffeeStatistics, \
    CoffeeMakerResult, CoffeeType


class MockProtocol(JuraProtocol):

    def __init__(self):
        pass

    def write_with_response(self, data: str, timeout: float = 3) -> Optional[str]:
        pass

    def get_and_parse_message(self, command: JuraCommand, raw: Optional[str] = None) -> Optional[Response]:
        pass

    def set_coffee_param(self, coffee_bean: int, water_volume: int) -> bool:
        pass

    def read_eeprom(self, address: int, use_rt: bool = False) -> Optional[int]:
        pass

    def reopen_serial(self):
        pass

    def reset_streams(self):
        pass


@pytest.mark.parametrize(
    ("coffee_bean", "water_volume", "hz", "grounds", "result"),
    [
        (1, 50, HZ("hz:01010110000000,0288,00ED,0000,03E8,0000,0,0017,000100,12"), 1000, CoffeeMakerResult.OK),
        (4, 25, HZ("hz:01010110000000,0288,00ED,0000,03E8,0000,0,0017,000100,12"), 1000, CoffeeMakerResult.OK),
        (4, 100, HZ("hz:01010110000000,0288,00ED,0000,03E8,0000,0,0017,000100,12"), 1000, CoffeeMakerResult.OK),
        (3, 110, HZ("hz:01010110000000,0288,00ED,0000,03E8,0000,0,0017,000100,12"), 1000, CoffeeMakerResult.OK),
        (3, 110, HZ("hz:01010110000000,0288,00ED,0000,03E8,0000,0,0017,000100,12"), None,
         CoffeeMakerResult.CANNOT_FETCH_GROUNDS_TANK),
        (3, 110, None, 1000,
         CoffeeMakerResult.CANNOT_FETCH_HZ),
        (3, 110, HZ("hz:01010110000000,0288,00ED,0000,03E8,0000,0,0017,000100,12"), 1100,
         CoffeeMakerResult.GROUNDS_TANK_FULL),
        (3, 110, HZ("hz:11010110000000,0288,00ED,0000,03E8,0000,0,0017,000100,12"), 1000,
         CoffeeMakerResult.SLEEPING),
        (3, 110, HZ("hz:01010110000000,0288,00ED,0000,03E8,0000,0,0017,000101,12"), 1000,
         CoffeeMakerResult.DRAINING_TRAY_FULL),
        (3, 110, HZ("hz:01010110000000,0288,00ED,0000,03E8,0000,0,0017,000110,12"), 1000,
         CoffeeMakerResult.DRAINING_TRAY_MISSING),
        (3, 110, HZ("hz:01010110000000,0288,00ED,0000,03E8,0000,0,0017,010100,12"), 1000,
         CoffeeMakerResult.WATER_TANK_MISSING),
    ],
)
def test_brew_coffee(mocker,
                     coffee_bean, water_volume,
                     hz, grounds,
                     result):
    p = MockProtocol()

    set_coffee_param_mock = mocker.patch.object(p, "set_coffee_param")
    write_with_response_mock = mocker.patch.object(p, "write_with_response")
    get_and_parse_message_mock = mocker.patch.object(p, "get_and_parse_message")
    read_eeprom_mock = mocker.patch.object(p, "read_eeprom")

    write_with_response_mock.side_effect = [
        CoffeeMaker.type,
        CoffeeMaker.bootloader,
        "ok:"
    ]

    get_and_parse_message_mock.side_effect = [
        hz,
        hz,
        CS("cs:03770000000ED000000000000006000000000000000"),
        CS("cs:03770000000ED000000000000006000011C00000000"),
        CS("cs:03770000000ED000000000000006000011C00000000"),
        CS("cs:03770000000ED000000000000006000011C00000000"),
    ]

    read_eeprom_mock.side_effect = [
        grounds
    ]

    set_coffee_param_mock.side_effect = [
        True
    ]

    done = Event()
    callback_result = [None]

    def _callback(result):
        callback_result[0] = result
        done.set()

    maker = CoffeeMaker(p, None)
    maker.brew_coffee(coffee_bean, water_volume, _callback)

    done.wait(timeout=100)
    assert callback_result[0] == result
    write_with_response_mock.assert_any_call(JuraCommand.GET_TYPE)
    write_with_response_mock.assert_any_call(JuraCommand.GET_LOADER)

    if result == CoffeeMakerResult.OK:
        set_coffee_param_mock.assert_called_once_with(coffee_bean, water_volume)
        write_with_response_mock.assert_any_call(CoffeeMaker.coffee_button_map[CoffeeType.COFFEE])
        get_and_parse_message_mock.assert_any_call(JuraCommand.CS)
    else:
        set_coffee_param_mock.assert_not_called()
        assert not any(call == call(CoffeeMaker.coffee_button_map[CoffeeType.COFFEE])
                       for call in write_with_response_mock.call_args_list)

@pytest.mark.parametrize(
    ("hz", "grounds", "result"),
    [
        (HZ("hz:01010110000000,0288,00ED,0107,03E8,0000,0,0017,000100,12"), 1000, CoffeeMakerResult.OK),
        (HZ("hz:01010110000000,0288,00ED,0107,03E8,0000,0,0017,000100,12"), 1000, CoffeeMakerResult.OK),
        (HZ("hz:01010110000000,0288,00ED,0107,03E8,0000,0,0017,000100,12"), 1000, CoffeeMakerResult.OK),
        (HZ("hz:01010110000000,0288,00ED,0107,03E8,0000,0,0017,000100,12"), 1000, CoffeeMakerResult.OK),
        (HZ("hz:01010110000000,0288,00ED,0107,03E8,0000,0,0017,000100,12"), None,
        CoffeeMakerResult.CANNOT_FETCH_GROUNDS_TANK),
        (None, 1000,
        CoffeeMakerResult.CANNOT_FETCH_HZ),
        (HZ("hz:01010110000000,0288,00ED,0107,03E8,0000,0,0017,000100,12"), 1100,
        CoffeeMakerResult.GROUNDS_TANK_FULL),
        (HZ("hz:11010110000000,0288,00ED,0107,03E8,0000,0,0017,000100,12"), 1000,
        CoffeeMakerResult.SLEEPING),
        (HZ("hz:01010110000000,0288,00ED,0107,03E8,0000,0,0017,000101,12"), 1000,
        CoffeeMakerResult.DRAINING_TRAY_FULL),
        (HZ("hz:01010110000000,0288,00ED,0107,03E8,0000,0,0017,000110,12"), 1000,
        CoffeeMakerResult.DRAINING_TRAY_MISSING),
        (HZ("hz:01010110000000,0288,00ED,0107,03E8,0000,0,0017,010100,12"), 1000,
        CoffeeMakerResult.WATER_TANK_MISSING),
    ],
)
def test_can_brew(mocker,
                  hz, grounds,
                  result):
    p = MockProtocol()

    write_with_response_mock = mocker.patch.object(p, "write_with_response")
    get_and_parse_message_mock = mocker.patch.object(p, "get_and_parse_message")
    read_eeprom_mock = mocker.patch.object(p, "read_eeprom")

    write_with_response_mock.side_effect = [CoffeeMaker.type,
                                            CoffeeMaker.bootloader]
    get_and_parse_message_mock.side_effect = [hz]
    read_eeprom_mock.side_effect = [grounds]

    done = Event()
    callback_result = [None]

    def _callback(result):
        callback_result[0] = result
        done.set()

    maker = CoffeeMaker(p, None)
    maker.can_brew(_callback)

    done.wait(timeout=100)
    assert callback_result[0] == result
    write_with_response_mock.assert_any_call(JuraCommand.GET_TYPE)
    write_with_response_mock.assert_any_call(JuraCommand.GET_LOADER)


def test_reset_coffee_param(mocker):
    p = MockProtocol()

    write_with_response_mock = mocker.patch.object(p, "write_with_response")
    write_with_response_mock.side_effect = [CoffeeMaker.type,
                                            CoffeeMaker.bootloader]
    set_coffee_param_mock = mocker.patch.object(p, "set_coffee_param", return_value=True)

    done = Event()
    callback_result = [None]

    def _callback(result):
        callback_result[0] = result
        done.set()

    maker = CoffeeMaker(p, None)
    maker.reset_coffee_param(_callback)

    done.wait(timeout=100)
    assert callback_result[0] == True
    write_with_response_mock.assert_any_call(JuraCommand.GET_TYPE)
    write_with_response_mock.assert_any_call(JuraCommand.GET_LOADER)
    set_coffee_param_mock.assert_called_once_with(JuraProtocol.coffee_param[1], JuraProtocol.water_param[1])


@pytest.mark.parametrize(
    ("values",),
    [
        ((1, 2, 3, 4, 5, 6, 7),),
        ((1, None, 3, None, 5, 6, 7),),
    ],
)
def test_totals_statistics(mocker, values: Tuple[Optional[int], ...]):
    p = MockProtocol()

    write_with_response_mock = mocker.patch.object(p, "write_with_response")
    write_with_response_mock.side_effect = [CoffeeMaker.type,
                                            CoffeeMaker.bootloader]
    read_eeprom_mock = mocker.patch.object(p, "read_eeprom")
    read_eeprom_mock.side_effect = values

    done = Event()
    callback_result = [None]

    def _callback(result):
        callback_result[0] = result
        done.set()

    maker = CoffeeMaker(p, None)
    maker.get_totals_statistics(_callback)

    done.wait(timeout=100)
    assert callback_result[0] == CoffeeStatistics(*values)
    write_with_response_mock.assert_any_call(JuraCommand.GET_TYPE)
    write_with_response_mock.assert_any_call(JuraCommand.GET_LOADER)


@pytest.mark.parametrize(
    ("responses", "result_first_call", "result_second_call", "jura_version_verified"),
    [
        ((CoffeeMaker.type, CoffeeMaker.bootloader, CoffeeMaker.type), True, True, True),
        ((None, None, None,
          None, None, None), False, False, False),
        ((None, None, None,
          CoffeeMaker.type, CoffeeMaker.bootloader), False, True, True),
    ],
)
def test_check_connection(mocker, responses, result_first_call, result_second_call, jura_version_verified):
    p = MockProtocol()

    write_with_response_mock = mocker.patch.object(p, "write_with_response")
    write_with_response_mock.side_effect = responses

    maker = CoffeeMaker(p, None)
    assert maker.__check_connection__() == result_first_call
    assert maker.__check_connection__() == result_second_call
    assert maker.jura_version_verified == jura_version_verified

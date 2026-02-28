import pytest

from juracoffeemachine import CircularBuffer, AbstractSerial, JuraProtocol, JuraCommand


def decode(data: list[int]) -> str:
    decoded = []
    for i in range(0, len(data), 4):
        decoded += chr(JuraProtocol.decode(data[i: i + 4]))
    return ''.join(decoded)


class ValidSerial(AbstractSerial):
    def __init__(self):
        super().__init__()
        self.read_index = 0
        self.read_buffer: list[int] = []
        self.write_buffer = []

    def get_debug_buffer(self) -> CircularBuffer:
        return CircularBuffer(10)

    def close(self):
        pass

    def read(self, size=4) -> bytes:
        r = self.read_buffer[self.read_index:self.read_index + size]
        self.read_index += size
        # print(f"read: {decode(r)}")
        return bytes(r)

    def write(self, data: bytes) -> int:
        written = list(data)
        self.write_buffer += list(written)
        # print(f"wrote: {decode(written)}")
        return len(written)

    def flush(self):
        pass


@pytest.mark.parametrize(
    "value,encoded",
    [
        (0, [91, 91, 91, 91]),
        (228, [91, 95, 123, 127]),
        (255, [127, 127, 127, 127]),
    ],
)
def test_encode(value, encoded):
    assert JuraProtocol.encode(value) == encoded


@pytest.mark.parametrize(
    "value,encoded",
    [
        ([91, 91, 91, 91], 0),
        ([91, 95, 123, 127], 228),
        ([127, 127, 127, 127], 255),
    ],
)
def test_decode(value, encoded):
    assert JuraProtocol.decode(value) == encoded


def test_write():
    t = ValidSerial()
    p = JuraProtocol(t, unexpected_msg_callback=lambda c: None)

    p.write("TY:")
    assert t.write_buffer == [91, 95, 95, 95, 95, 123, 95, 95, 123, 123, 127, 91, 95, 127, 91, 91, 123, 123, 91, 91]


def test_read():
    t = ValidSerial()
    t.read_buffer = [91, 95, 127, 95, 95, 123, 127, 95, 123, 123, 127, 91, 95, 95, 91, 95, 123, 95, 91, 95, 95, 95, 127,
                     91, 127, 91, 127, 91, 123, 91, 127, 91, 95, 127, 91, 95, 91, 91, 123, 91, 123, 95, 95, 95, 91, 91,
                     127, 91, 123, 91, 127, 91, 123, 127, 123, 91, 91, 91, 127, 91, 127, 91, 127, 91, 95, 127, 91, 91,
                     123, 123, 91, 91, 91, 95, 95, 95, 95, 123, 95, 95, 123, 123, 127, 91, 95, 127, 91, 91, 123, 123,
                     91, 91]
    p = JuraProtocol(t, unexpected_msg_callback=lambda c: None)

    assert p.read() == "ty:EF532M V02.03"


def test_write_with_response():
    t = ValidSerial()
    p = JuraProtocol(t, unexpected_msg_callback=lambda c: None)
    t.read_buffer = [127, 127, 123, 95, 127, 123, 123, 95, 123, 123, 127, 91, 95, 127, 91, 91, 123, 123, 91, 91]

    resp = p.write_with_response(JuraCommand.BUTTON_1)
    assert t.write_buffer == [123, 95, 91, 95, 95, 91, 91, 95, 123, 123, 127, 91, 91, 91, 127, 91, 91, 95, 127, 91,
                              95, 127, 91, 91, 123, 123, 91, 91]
    assert resp == "ok:"


def test_read_eeprom():
    t = ValidSerial()
    p = JuraProtocol(t, unexpected_msg_callback=lambda c: None)
    t.read_buffer = [123, 91, 127, 95, 95, 95, 123, 95, 123, 123, 127, 91, 95, 95, 91, 95, 95, 91, 91, 95, 95, 95, 91,
                     95, 95, 91, 91, 95, 95, 127, 91, 91, 123, 123, 91, 91]

    resp = p.read_eeprom(0x2a3)

    assert t.write_buffer == [123, 91, 95, 95, 95, 95, 91, 95, 123, 123, 127, 91, 91, 91, 127, 91, 123, 91, 127, 91, 95,
                              91, 91, 95, 127, 91, 127, 91, 95, 127, 91, 91, 123, 123, 91, 91]
    assert resp == int("EAEA", 16)

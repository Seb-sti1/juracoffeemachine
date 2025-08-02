This small python package makes it possible to brew coffee with a Jura E6 machin.

It is _(will be)_ used in app that tracks how many coffees each employee takes.
Therefore, it aims for high reliability and low maintenance.

> [!NOTE]
> This code was tested on a Jura responding `ty:EF532M V02.03` `TY:` and `tl:BL_RL78 V01.31` to `TL:`.

## Installation

_WIP_

## Usage

For the wiring, please look at the
diagram [here](https://github.com/Jutta-Proto/serial-snooper?tab=readme-ov-file#hardware).
Don't forget that the TX/RX of the controller should be connected to the RX/TX of the machin.

To brew a coffee `python -m juracoffeemachine --port /dev/ttyUSB0`, then while the coffee machine
is running (there is no safety regarding this for now), press +/- to increase/decrease coffee beans/water.

## API Example

The minimal example to brew a coffee is as follows:

```python
from juracoffeemachine.coffee_machine import CoffeeMaker
from juracoffeemachine.jura import JuraProtocol

machin = CoffeeMaker(JuraProtocol("/dev/ttyUSB0"))
machin.brew_coffee(machin.CoffeeType.COFFEE)
```

## Jura's protocol

If you're only interested in the protocol itself and which information can be retrieved, check out:

- [encode](juracoffeemachine/jura.py), [decode](juracoffeemachine/jura.py): functions to send message to the jura
- [JuraCommand](juracoffeemachine/jura.py): the list of message that is used in this package
- [GROUP_REGEX](juracoffeemachine/jura.py): part of the signification of the response from the jura

## Acknowledgments, contributions & license

### Acknowledgments

Other work exists to try and control Jura coffee machines.
All the protocol used in this project was decoded by [COM8](https://github.com/COM8) in his
project [protocol-cpp](https://github.com/Jutta-Proto/protocol-cpp) (see also the
organisation [JuttaProto](https://github.com/Jutta-Proto)).
[Juramote](https://6xq.net/juramote/), [q42](https://blog.q42.nl/hacking-the-coffee-machine-5802172b17c1/),
[at.ua](https://protocol-jura.at.ua/index/commands_for_coffeemaker/0-5) was also of
great help to extract relevant information from the Jura.

### Contributions

All contribution are welcomed, submit an issue for bug reports/feature requests (or open a pull request if you
already implemented the feature).

### License

See [LICENSE](LICENSE)
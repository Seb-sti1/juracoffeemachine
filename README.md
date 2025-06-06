This small python package makes it possible to brew coffee with a Jura E6 machin.

**All the protocol used in this project was decoded by [COM8](https://github.com/COM8) in his
project [protocol-cpp](https://github.com/Jutta-Proto/protocol-cpp) (see also the
organisation [JuttaProto](https://github.com/Jutta-Proto)).**

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

## Contributions

All contribution are welcomed, submit an issue for bug reports/feature requests (or open a pull request if you
already implemented the feature).

## License

Copyright (C) 2025 Seb-sti1

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>.

See [LICENSE](LICENSE)
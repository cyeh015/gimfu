# gimfu

A toolkit for generating future scenarios in AUTOUGH2.

[![PyPI - Version](https://img.shields.io/pypi/v/gimfu.svg)](https://pypi.org/project/gimfu)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/gimfu.svg)](https://pypi.org/project/gimfu)

-----

## Table of Contents

- [Installation](#installation)
- [Commands](#Commands)
- [License](#license)
- [Developer](#Developer)

## Installation

```console
pip install -U gimfu
```

## Commands

### Make Scenario

To build a scenario from a `.cfg` and its parts (.geners):

```console
make_scenarios make_scenarios_sXXX.cfg
```

This will generate a folder with the scenario name.  Use `run_all_models.bat` for Windows or `./run_all_models.sh`  for Linux/MacOS.

### Convert SAVE file to INCON file

```console
save2incon a.save b.incon
```

NOTE this command is used during the scenario run.

## License

`gimfu` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.

## Developer

To bump version, create a tag, eg. `v0.1.0`

PyPI token is expected in ~/.pypirc

Publish to PyPI:

```console
hatch build
hatch publish
```

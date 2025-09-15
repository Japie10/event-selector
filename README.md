# Event Selector

A modern desktop tool for managing hardware/firmware event masks and capture-masks.

## Features

- Dual format support (mk1 and mk2)
- Modern PyQt5 GUI with tabs and real-time filtering
- Tri-state selection with undo/redo
- Comprehensive validation and error reporting
- Session management with autosave
- Cross-platform support (primary: RHEL8+)

## Installation

```bash
pip install event-selector
```

Or for RHEL8+:
```bash
sudo dnf install event-selector-*.rpm
```

## Usage

### GUI Mode
```bash
event-selector-gui [yaml_file]
```

### CLI Mode (minimal)
```bash
event-selector --help
event-selector --version
event-selector --debug DEBUG_LEVEL
```

## Development

### Setup
```bash
pip install -e .[dev]
pre-commit install
```

### Testing
```bash
pytest
```

### Building
```bash
python -m build
```

## License

MIT

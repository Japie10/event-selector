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

## Architecture

Event Selector follows Clean Architecture principles:

- **Presentation Layer**: Qt GUI with MVVM pattern
- **Application Layer**: Use cases and orchestration via Facade
- **Domain Layer**: Core business logic and entities
- **Infrastructure**: Technical concerns (logging, config, persistence)

### Key Design Patterns

1. **MVVM**: Separates UI from business logic
2. **Command Pattern**: Undo/redo support
3. **Facade Pattern**: Simplified application interface
4. **Strategy Pattern**: Format-specific operations
5. **Repository Pattern**: Session persistence

### File Organization

Each layer has clear boundaries:
- Controllers: < 200 lines
- View Models: < 100 lines
- Views: < 200 lines
- Commands: < 50 lines

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

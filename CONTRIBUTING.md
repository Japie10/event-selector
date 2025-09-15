# Contributing to Event Selector

## Development Setup

1. Clone the repository
2. Install development dependencies:
   ```bash
   pip install -e .[dev]
   ```
3. Install pre-commit hooks:
   ```bash
   pre-commit install
   ```

## Code Style

- Use ruff for linting and formatting
- Type hints required (checked by mypy)
- Docstrings for all public functions/classes
- Test coverage must be ≥90%

## Testing

Run tests with:
```bash
pytest
```

## Building

### Python Package
```bash
python -m build
```

### RPM Package
```bash
scripts/build_rpm.sh
```

## Definition of Done

- [ ] Code formatted and linted
- [ ] Type hints added and checked
- [ ] Tests written (≥90% coverage)
- [ ] Documentation updated
- [ ] CI pipeline green
- [ ] Code reviewed and approved

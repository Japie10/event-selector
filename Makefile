.PHONY: help install install-dev test test-fast test-all lint type-check format clean build docs serve-docs

help:  ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install the package
	pip install -e .

install-dev:  ## Install the package with development dependencies
	pip install -e .[dev,docs]
	pre-commit install

test:  ## Run tests with coverage
	pytest

test-fast:  ## Run tests in parallel without coverage
	pytest -n auto --no-cov

test-all:  ## Run tests with tox for all Python versions
	tox

lint:  ## Run linting checks
	ruff check src tests
	ruff format --check src tests

type-check:  ## Run type checking
	mypy src/event_selector

format:  ## Format code
	ruff check --fix src tests
	ruff format src tests

clean:  ## Clean build artifacts
	rm -rf build dist *.egg-info
	rm -rf .pytest_cache .ruff_cache .mypy_cache .tox
	rm -rf htmlcov coverage.xml .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build:  ## Build distribution packages
	python -m build

docs:  ## Build documentation
	mkdocs build

serve-docs:  ## Serve documentation locally
	mkdocs serve

rpm:  ## Build RPM package
	scripts/build_rpm.sh

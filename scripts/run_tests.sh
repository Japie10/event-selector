#!/bin/bash
# Convenience script for running tests

set -e
echo "Running Event Selector tests..."
pytest tests/ -v --cov=event_selector --cov-report=term-missing

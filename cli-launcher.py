#!/usr/bin/env python3
"""Event Selector CLI launcher script.

This script serves as the main entry point for the event-selector command.
It can be installed as a console script via setuptools.
"""

import sys
from event_selector.cli.app import main

if __name__ == "__main__":
    main()

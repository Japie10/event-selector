"""Common path utilities."""

import sys
from pathlib import Path

def get_app_data_dir() -> Path:
    """Get application data directory."""
    if sys.platform == "win32":
        return Path.home() / "AppData" / "Local" / "EventSelector"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Event Selector"
    else:
        return Path.home() / ".local" / "share" / "event-selector"

def get_config_dir() -> Path:
    """Get configuration directory."""
    if sys.platform == "win32":
        return Path.home() / "AppData" / "Roaming" / "EventSelector"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Event Selector"
    else:
        return Path.home() / ".config" / "event-selector"

def get_log_dir() -> Path:
    """Get log directory."""
    if sys.platform == "win32":
        return Path.home() / "AppData" / "Local" / "EventSelector" / "logs"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Logs" / "EventSelector"
    else:
        return Path.home() / ".local" / "state" / "event-selector"
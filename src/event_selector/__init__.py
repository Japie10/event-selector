"""Event Selector - Hardware/Firmware Event Mask Management Tool."""

try:
    from event_selector._version import version as __version__
except ImportError:
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]


# src/event_selector/utils/__init__.py
"""Utilities package for Event Selector."""

from event_selector.utils.logging import (
    setup_logging,
    get_logger,
    log_debug,
    log_info,
    log_warning,
    log_error,
    log_critical
)
from event_selector.utils.config import (
    Config,
    get_config
)
from event_selector.utils.autosave import (
    Autosave,
    get_autosave
)

__all__ = [
    "setup_logging",
    "get_logger",
    "log_debug",
    "log_info",
    "log_warning",
    "log_error",
    "log_critical",
    "Config",
    "get_config",
    "Autosave",
    "get_autosave"
]
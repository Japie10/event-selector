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
from event_selector.utils.paths import (  # NEW EXPORTS
    get_app_data_dir,
    get_config_dir,
    get_log_dir
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
    "get_autosave",
    "get_app_data_dir",
    "get_config_dir",
    "get_log_dir",
]
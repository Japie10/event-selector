"""Configuration management for Event Selector."""

import json
import sys
from pathlib import Path
from typing import Dict, Any

from event_selector.utils.logging import get_logger
from event_selector.utils.paths import get_config_dir

logger = get_logger(__name__)


class Config:
    """Configuration manager for Event Selector."""

    DEFAULT_CONFIG = {
        "accent_color": "#007ACC",
        "row_density": "comfortable",
        "log_level": "INFO",
        "restore_on_start": True,
        "scan_dir_on_start": True,
        "default_mode": "mask",
        "mk2_hide_28_31": True,
        "autosave_debounce_ms": 5000,
        "max_problem_entries": 200,
        "confirm_overwrite_on_export": True
    }

    def __init__(self):
        """Initialize config manager."""
        self.config_path = self._get_config_path()
        self.config = self._load_config()

    def _get_config_path(self) -> Path:
        """Get configuration file path.

        Returns:
            Path to config file
        """
        config_dir = get_config_dir()
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "config.json"

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file.

        Returns:
            Configuration dictionary
        """
        config = self.DEFAULT_CONFIG.copy()

        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    user_config = json.load(f)
                    config.update(user_config)
                    logger.info(f"Loaded config from {self.config_path}")
            except Exception as e:
                logger.error(f"Failed to load config: {e}")

        return config

    def save(self) -> None:
        """Save configuration to file."""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
                logger.info(f"Saved config to {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value
        """
        return self.config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set configuration value.

        Args:
            key: Configuration key
            value: Configuration value
        """
        self.config[key] = value

    def update(self, updates: Dict[str, Any]) -> None:
        """Update multiple configuration values.

        Args:
            updates: Dictionary of updates
        """
        self.config.update(updates)


def get_config() -> Config:
    """Get global config instance.

    Returns:
        Config instance
    """
    if not hasattr(get_config, '_instance'):
        get_config._instance = Config()
    return get_config._instance
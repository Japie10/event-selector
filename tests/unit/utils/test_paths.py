"""Tests for path utilities."""

import pytest
import sys
from unittest.mock import patch
from pathlib import Path

from event_selector.utils.paths import (
    get_app_data_dir,
    get_config_dir,
    get_log_dir
)


class TestPaths:
    """Test path utility functions."""
    
    @patch('sys.platform', 'win32')
    def test_windows_paths(self):
        """Test Windows path generation."""
        home = Path.home()
        
        assert get_app_data_dir() == home / "AppData" / "Local" / "EventSelector"
        assert get_config_dir() == home / "AppData" / "Roaming" / "EventSelector"
        assert get_log_dir() == home / "AppData" / "Local" / "EventSelector" / "logs"
    
    @patch('sys.platform', 'darwin')
    def test_macos_paths(self):
        """Test macOS path generation."""
        home = Path.home()
        
        assert get_app_data_dir() == home / "Library" / "Application Support" / "Event Selector"
        assert get_config_dir() == home / "Library" / "Application Support" / "Event Selector"
        assert get_log_dir() == home / "Library" / "Logs" / "EventSelector"
    
    @patch('sys.platform', 'linux')
    def test_linux_paths(self):
        """Test Linux path generation."""
        home = Path.home()
        
        assert get_app_data_dir() == home / ".local" / "share" / "event-selector"
        assert get_config_dir() == home / ".config" / "event-selector"
        assert get_log_dir() == home / ".local" / "state" / "event-selector"
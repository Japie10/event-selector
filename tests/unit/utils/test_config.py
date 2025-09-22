"""Tests for configuration management."""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from event_selector.utils.config import Config, get_config


class TestConfig:
    """Test Config class."""
    
    def test_default_config(self):
        """Test default configuration values."""
        with patch('event_selector.utils.config.get_config_dir') as mock_dir:
            mock_dir.return_value = Path(tempfile.gettempdir())
            
            config = Config()
            
            assert config.get("accent_color") == "#007ACC"
            assert config.get("row_density") == "comfortable"
            assert config.get("log_level") == "INFO"
            assert config.get("restore_on_start") is True
            assert config.get("default_mode") == "mask"
            assert config.get("mk2_hide_28_31") is True
            assert config.get("max_problem_entries") == 200
    
    def test_load_user_config(self, tmp_path):
        """Test loading user configuration."""
        config_file = tmp_path / "config.json"
        user_config = {
            "accent_color": "#FF0000",
            "log_level": "DEBUG",
            "new_setting": "custom_value"
        }
        config_file.write_text(json.dumps(user_config))
        
        with patch('event_selector.utils.config.get_config_dir') as mock_dir:
            mock_dir.return_value = tmp_path
            
            config = Config()
            
            # User settings override defaults
            assert config.get("accent_color") == "#FF0000"
            assert config.get("log_level") == "DEBUG"
            
            # New settings are added
            assert config.get("new_setting") == "custom_value"
            
            # Other defaults remain
            assert config.get("row_density") == "comfortable"
    
    def test_save_config(self, tmp_path):
        """Test saving configuration."""
        with patch('event_selector.utils.config.get_config_dir') as mock_dir:
            mock_dir.return_value = tmp_path
            
            config = Config()
            config.set("test_key", "test_value")
            config.save()
            
            # Verify file was created
            config_file = tmp_path / "config.json"
            assert config_file.exists()
            
            # Verify content
            saved_data = json.loads(config_file.read_text())
            assert saved_data["test_key"] == "test_value"
    
    def test_update_multiple(self, tmp_path):
        """Test updating multiple config values."""
        with patch('event_selector.utils.config.get_config_dir') as mock_dir:
            mock_dir.return_value = tmp_path
            
            config = Config()
            updates = {
                "accent_color": "#00FF00",
                "log_level": "WARNING",
                "custom_key": "custom_value"
            }
            config.update(updates)
            
            assert config.get("accent_color") == "#00FF00"
            assert config.get("log_level") == "WARNING"
            assert config.get("custom_key") == "custom_value"
    
    def test_get_config_singleton(self):
        """Test get_config returns singleton."""
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2
    
    def test_invalid_config_file(self, tmp_path):
        """Test handling of invalid config file."""
        config_file = tmp_path / "config.json"
        config_file.write_text("INVALID JSON {{{")
        
        with patch('event_selector.utils.config.get_config_dir') as mock_dir:
            mock_dir.return_value = tmp_path
            
            # Should fall back to defaults
            config = Config()
            assert config.get("accent_color") == "#007ACC"  # Default value
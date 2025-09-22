"""Tests for autosave functionality."""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime

from event_selector.utils.autosave import Autosave, get_autosave
from event_selector.core.models import SessionState, MaskMode


class TestAutosave:
    """Test Autosave class."""
    
    def test_save_session(self, tmp_path):
        """Test saving session state."""
        with patch('event_selector.utils.autosave.get_app_data_dir') as mock_dir:
            mock_dir.return_value = tmp_path
            
            autosave = Autosave()
            
            # Create session
            session = SessionState()
            session.open_files = ["file1.yaml", "file2.yaml"]
            session.active_tab = 1
            session.window_geometry = {"x": 100, "y": 200, "width": 800, "height": 600}
            session.current_mode = MaskMode.TRIGGER
            
            # Save
            result = autosave.save_session(session)
            assert result is True
            
            # Verify file exists
            autosave_file = tmp_path / "autosave.json"
            assert autosave_file.exists()
            
            # Verify content
            saved_data = json.loads(autosave_file.read_text())
            assert saved_data["open_files"] == ["file1.yaml", "file2.yaml"]
            assert saved_data["active_tab"] == 1
            assert saved_data["current_mode"] == "trigger"
            assert saved_data["window_geometry"]["x"] == 100
    
    def test_load_session(self, tmp_path):
        """Test loading session state."""
        with patch('event_selector.utils.autosave.get_app_data_dir') as mock_dir:
            mock_dir.return_value = tmp_path
            
            # Create autosave file
            autosave_data = {
                "version": "1.0",
                "timestamp": datetime.now().isoformat(),
                "open_files": ["test.yaml"],
                "active_tab": 0,
                "active_subtab": 2,
                "current_mode": "mask",
                "window_geometry": {"x": 50, "y": 50, "width": 1024, "height": 768},
                "mask_states": {"test.yaml": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]},
                "trigger_states": {"test.yaml": [0] * 12},
                "scroll_positions": {},
                "dock_states": {"problems_dock": True}
            }
            
            autosave_file = tmp_path / "autosave.json"
            autosave_file.write_text(json.dumps(autosave_data))
            
            autosave = Autosave()
            session = autosave.load_session()
            
            assert session is not None
            assert session.open_files == ["test.yaml"]
            assert session.active_tab == 0
            assert session.current_mode == MaskMode.MASK
            assert session.window_geometry["width"] == 1024
            assert len(session.mask_states["test.yaml"]) == 12
    
    def test_load_nonexistent_session(self, tmp_path):
        """Test loading when no autosave exists."""
        with patch('event_selector.utils.autosave.get_app_data_dir') as mock_dir:
            mock_dir.return_value = tmp_path
            
            autosave = Autosave()
            session = autosave.load_session()
            
            assert session is None
    
    def test_delete_session(self, tmp_path):
        """Test deleting autosave."""
        with patch('event_selector.utils.autosave.get_app_data_dir') as mock_dir:
            mock_dir.return_value = tmp_path
            
            # Create file
            autosave_file = tmp_path / "autosave.json"
            autosave_file.write_text("{}")
            
            autosave = Autosave()
            autosave.delete_session()
            
            assert not autosave_file.exists()
    
    def test_has_session(self, tmp_path):
        """Test checking for session existence."""
        with patch('event_selector.utils.autosave.get_app_data_dir') as mock_dir:
            mock_dir.return_value = tmp_path
            
            autosave = Autosave()
            assert not autosave.has_session()
            
            # Create file
            autosave_file = tmp_path / "autosave.json"
            autosave_file.write_text("{}")
            
            assert autosave.has_session()
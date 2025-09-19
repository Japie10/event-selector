"""Autosave functionality for Event Selector."""

import json
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime

from event_selector.core.models import SessionState, MaskMode
from event_selector.utils.logging import get_logger

logger = get_logger(__name__)


class Autosave:
    """Autosave manager for session state."""

    def __init__(self):
        """Initialize autosave manager."""
        self.autosave_path = self._get_autosave_path()

    def _get_autosave_path(self) -> Path:
        """Get autosave file path.

        Returns:
            Path to autosave file
        """
        if sys.platform == "win32":
            data_dir = Path.home() / "AppData" / "Local" / "EventSelector"
        elif sys.platform == "darwin":
            data_dir = Path.home() / "Library" / "Application Support" / "Event Selector"
        else:
            data_dir = Path.home() / ".local" / "share" / "event-selector"

        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir / "autosave.json"

    def save_session(self, session: SessionState) -> bool:
        """Save session state to file.

        Args:
            session: Session state to save

        Returns:
            True if successful
        """
        try:
            # Convert session to dict
            session_dict = {
                "version": "1.0",
                "timestamp": datetime.now().isoformat(),
                "open_files": session.open_files,
                "active_tab": session.active_tab,
                "active_subtab": session.active_subtab,
                "scroll_positions": session.scroll_positions,
                "window_geometry": session.window_geometry,
                "dock_states": session.dock_states,
                "mask_states": session.mask_states,
                "trigger_states": session.trigger_states,
                "current_mode": session.current_mode.value
            }

            # Write atomically using temporary file
            temp_file = self.autosave_path.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(session_dict, f, indent=2)

            temp_file.replace(self.autosave_path)
            logger.debug(f"Saved session to {self.autosave_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to save session: {e}")
            return False

    def load_session(self) -> Optional[SessionState]:
        """Load session state from file.

        Returns:
            SessionState object or None if not found/invalid
        """
        if not self.autosave_path.exists():
            return None

        try:
            with open(self.autosave_path, 'r') as f:
                session_dict = json.load(f)

            # Create SessionState from dict
            session = SessionState()
            session.open_files = session_dict.get("open_files", [])
            session.active_tab = session_dict.get("active_tab")
            session.active_subtab = session_dict.get("active_subtab")
            session.scroll_positions = session_dict.get("scroll_positions", {})
            session.window_geometry = session_dict.get("window_geometry")
            session.dock_states = session_dict.get("dock_states", {})
            session.mask_states = session_dict.get("mask_states", {})
            session.trigger_states = session_dict.get("trigger_states", {})

            mode_str = session_dict.get("current_mode", "mask")
            session.current_mode = MaskMode(mode_str)

            logger.info(f"Loaded session from {self.autosave_path}")
            return session

        except Exception as e:
            logger.error(f"Failed to load session: {e}")
            return None

    def delete_session(self) -> None:
        """Delete saved session file."""
        if self.autosave_path.exists():
            try:
                self.autosave_path.unlink()
                logger.info("Deleted autosave file")
            except Exception as e:
                logger.error(f"Failed to delete autosave: {e}")

    def has_session(self) -> bool:
        """Check if autosave session exists.

        Returns:
            True if session file exists
        """
        return self.autosave_path.exists()


def get_autosave() -> Autosave:
    """Get global autosave instance.

    Returns:
        Autosave instance
    """
    if not hasattr(get_autosave, '_instance'):
        get_autosave._instance = Autosave()
    return get_autosave._instance
"""Session manager for saving and restoring application state."""

from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
import json
from datetime import datetime

from event_selector.infrastructure.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SessionState:
    """Container for session state."""

    # File state
    open_files: List[str] = field(default_factory=list)
    active_tab: int = 0
    current_mode: str = "mask"  # "mask" or "trigger"

    # Window state
    window_geometry: Dict[str, int] = field(default_factory=dict)
    dock_states: Dict[str, bool] = field(default_factory=dict)

    # Mask states (project_id -> list of 32-bit values)
    mask_states: Dict[str, List[int]] = field(default_factory=dict)
    trigger_states: Dict[str, List[int]] = field(default_factory=dict)

    # Metadata
    timestamp: Optional[str] = None
    version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionState':
        """Create from dictionary."""
        return cls(**data)


class SessionManager:
    """Manages session persistence."""

    def __init__(self, session_file: Optional[Path] = None):
        """Initialize session manager.

        Args:
            session_file: Path to session file (default: .local/autosave.json)
        """
        if session_file is None:
            # Default to .local directory in current working directory
            session_file = Path.cwd() / ".local" / "autosave.json"

        self.session_file = session_file
        self.session_file.parent.mkdir(parents=True, exist_ok=True)

    def save_session(self, session: SessionState) -> None:
        """Save session state to file.

        Args:
            session: Session state to save
        """
        try:
            # Add timestamp
            session.timestamp = datetime.now().isoformat()

            # Convert to JSON
            data = session.to_dict()

            # Write atomically
            temp_file = self.session_file.with_suffix('.tmp')

            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)

            # Atomic rename
            temp_file.replace(self.session_file)

            logger.debug(f"Saved session to {self.session_file}")

        except Exception as e:
            logger.error(f"Failed to save session: {e}")
            # Don't raise - autosave failure shouldn't crash app

    def load_session(self) -> Optional[SessionState]:
        """Load session state from file.

        Returns:
            SessionState or None if no session exists
        """
        if not self.session_file.exists():
            logger.debug("No session file found")
            return None

        try:
            with open(self.session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            session = SessionState.from_dict(data)
            logger.info(f"Loaded session from {self.session_file}")
            return session

        except Exception as e:
            logger.error(f"Failed to load session: {e}")
            return None

    def clear_session(self) -> None:
        """Delete the session file."""
        if self.session_file.exists():
            try:
                self.session_file.unlink()
                logger.info("Cleared session file")
            except Exception as e:
                logger.error(f"Failed to clear session: {e}")

    def add_open_file(self, file_path: str) -> None:
        """Add a file to the current session.

        Args:
            file_path: Path to file
        """
        session = self.load_session() or SessionState()

        if file_path not in session.open_files:
            session.open_files.append(file_path)
            self.save_session(session)

    def remove_open_file(self, file_path: str) -> None:
        """Remove a file from the current session.

        Args:
            file_path: Path to file
        """
        session = self.load_session()
        if session and file_path in session.open_files:
            session.open_files.remove(file_path)

            # Also remove associated mask states
            if file_path in session.mask_states:
                del session.mask_states[file_path]
            if file_path in session.trigger_states:
                del session.trigger_states[file_path]

            self.save_session(session)


# Global singleton instance
_session_manager: Optional[SessionManager] = None


def get_session_manager(session_file: Optional[Path] = None) -> SessionManager:
    """Get the global session manager instance.

    Args:
        session_file: Optional custom session file path

    Returns:
        SessionManager instance
    """
    global _session_manager

    if _session_manager is None:
        _session_manager = SessionManager(session_file)

    return _session_manager

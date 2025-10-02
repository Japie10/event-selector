"""Session management and autosave functionality."""

import json
import platform
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, asdict, field

from event_selector.shared.types import MaskMode


@dataclass
class SessionState:
    """Represents a saved session state."""
    # File state
    open_files: List[str] = field(default_factory=list)
    active_tab: Optional[int] = None
    active_subtab: Optional[int] = None
    
    # UI state
    window_geometry: Optional[Dict[str, int]] = None
    dock_states: Dict[str, bool] = field(default_factory=dict)
    scroll_positions: Dict[str, int] = field(default_factory=dict)
    
    # Mask states (file -> mask values)
    mask_states: Dict[str, List[int]] = field(default_factory=dict)
    trigger_states: Dict[str, List[int]] = field(default_factory=dict)
    current_mode: str = "mask"
    
    # Metadata
    version: str = "1.0"
    timestamp: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['timestamp'] = datetime.now().isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionState':
        """Create from dictionary."""
        # Filter out unknown keys
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {
            k: v for k, v in data.items() 
            if k in valid_fields
        }
        return cls(**filtered_data)


class SessionManager:
    """Manages session persistence and autosave."""
    
    def __init__(self):
        """Initialize session manager."""
        self._autosave_path = self._get_autosave_path()
        self._current_session: Optional[SessionState] = None
    
    def _get_autosave_path(self) -> Path:
        """Get platform-specific autosave file path.
        
        Returns:
            Path to autosave file
        """
        system = platform.system()
        
        if system == "Windows":
            base = Path.home() / "AppData" / "Local"
            data_dir = base / "EventSelector"
        elif system == "Darwin":  # macOS
            base = Path.home() / "Library" / "Application Support"
            data_dir = base / "Event Selector"
        else:  # Linux and others
            base = Path.home() / ".local" / "state"
            data_dir = base / "event-selector"
        
        # Ensure directory exists
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
            # Convert to dict
            data = session.to_dict()
            
            # Write atomically
            temp_file = self._autosave_path.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            # Replace original
            temp_file.replace(self._autosave_path)
            
            self._current_session = session
            return True
            
        except Exception as e:
            print(f"Error saving session: {e}")
            return False
    
    def load_session(self) -> Optional[SessionState]:
        """Load session state from file.
        
        Returns:
            SessionState if successful, None otherwise
        """
        if not self._autosave_path.exists():
            return None
        
        try:
            with open(self._autosave_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            session = SessionState.from_dict(data)
            self._current_session = session
            return session
            
        except Exception as e:
            print(f"Error loading session: {e}")
            return None
    
    def delete_session(self) -> None:
        """Delete the autosave file."""
        try:
            if self._autosave_path.exists():
                self._autosave_path.unlink()
            self._current_session = None
        except Exception as e:
            print(f"Error deleting session: {e}")
    
    def has_session(self) -> bool:
        """Check if an autosave session exists.
        
        Returns:
            True if autosave file exists
        """
        return self._autosave_path.exists()
    
    def get_session_info(self) -> Optional[Dict[str, Any]]:
        """Get basic information about saved session without full load.
        
        Returns:
            Dictionary with session info, or None
        """
        if not self._autosave_path.exists():
            return None
        
        try:
            with open(self._autosave_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            return {
                'timestamp': data.get('timestamp'),
                'file_count': len(data.get('open_files', [])),
                'open_files': data.get('open_files', [])
            }
            
        except Exception:
            return None
    
    def update_window_geometry(self, geometry: Dict[str, int]) -> None:
        """Update just the window geometry in current session.
        
        Args:
            geometry: Window geometry dict (x, y, width, height)
        """
        if self._current_session:
            self._current_session.window_geometry = geometry
            self.save_session(self._current_session)
    
    def update_mask_state(self, 
                         file_path: str,
                         mask_values: List[int],
                         mode: MaskMode) -> None:
        """Update mask state for a file.
        
        Args:
            file_path: Path to YAML file
            mask_values: Current mask values
            mode: Mask or trigger mode
        """
        if self._current_session:
            if mode == MaskMode.MASK:
                self._current_session.mask_states[file_path] = mask_values
            else:
                self._current_session.trigger_states[file_path] = mask_values
            self.save_session(self._current_session)
    
    def add_open_file(self, file_path: str) -> None:
        """Add a file to the open files list.
        
        Args:
            file_path: Path to file
        """
        if self._current_session:
            if file_path not in self._current_session.open_files:
                self._current_session.open_files.append(file_path)
                self.save_session(self._current_session)
    
    def remove_open_file(self, file_path: str) -> None:
        """Remove a file from the open files list.
        
        Args:
            file_path: Path to file
        """
        if self._current_session:
            if file_path in self._current_session.open_files:
                self._current_session.open_files.remove(file_path)
                # Also remove mask states
                self._current_session.mask_states.pop(file_path, None)
                self._current_session.trigger_states.pop(file_path, None)
                self.save_session(self._current_session)


# Global session manager
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get the global session manager.
    
    Returns:
        SessionManager instance
    """
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager

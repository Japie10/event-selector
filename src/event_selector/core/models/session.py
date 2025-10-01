"""Session state models.

This module contains models for session persistence (autosave/restore).
"""

from typing import Optional, Dict, List
from pydantic import Field

from .base import StrictModel
from .constants import MaskMode


# =====================
# Session State Model
# =====================

class SessionState(StrictModel):
    """Session state for autosave/restore.
    
    Captures the complete state of the application including:
    - Open files
    - Active tabs and subtabs
    - Window geometry
    - Dock states
    - Mask and trigger selections
    """
    
    # File state
    open_files: List[str] = Field(
        default_factory=list,
        description="List of open YAML file paths"
    )
    active_tab: Optional[int] = Field(
        None,
        description="Index of active tab"
    )
    active_subtab: Optional[int] = Field(
        None,
        description="Index of active subtab within active tab"
    )
    
    # UI state
    scroll_positions: Dict[str, int] = Field(
        default_factory=dict,
        description="Scroll positions by tab identifier"
    )
    window_geometry: Optional[Dict[str, int]] = Field(
        None,
        description="Window position and size (x, y, width, height)"
    )
    dock_states: Dict[str, bool] = Field(
        default_factory=dict,
        description="Visibility state of dock widgets"
    )
    
    # Mask state
    mask_states: Dict[str, List[int]] = Field(
        default_factory=dict,
        description="Mask values by file path"
    )
    trigger_states: Dict[str, List[int]] = Field(
        default_factory=dict,
        description="Trigger values by file path"
    )
    current_mode: MaskMode = Field(
        default=MaskMode.EVENT,
        description="Current mode (mask or trigger)"
    )

    # ========================================
    # File management methods
    # ========================================
    
    def add_file(self, filepath: str) -> None:
        """Add a file to the session.
        
        Args:
            filepath: Path to add
        """
        if filepath not in self.open_files:
            self.open_files.append(filepath)

    def remove_file(self, filepath: str) -> None:
        """Remove a file from the session.
        
        Also cleans up related state (mask/trigger states).
        
        Args:
            filepath: Path to remove
        """
        if filepath in self.open_files:
            self.open_files.remove(filepath)
            
            # Clean up related state
            self.mask_states.pop(filepath, None)
            self.trigger_states.pop(filepath, None)
            self.scroll_positions.pop(filepath, None)
    
    def has_file(self, filepath: str) -> bool:
        """Check if file is in session.
        
        Args:
            filepath: Path to check
            
        Returns:
            True if file is in session
        """
        return filepath in self.open_files
    
    def clear_files(self) -> None:
        """Remove all files from session."""
        self.open_files.clear()
        self.mask_states.clear()
        self.trigger_states.clear()
        self.scroll_positions.clear()
    
    # ========================================
    # State management methods
    # ========================================
    
    def get_mask_state(self, filepath: str) -> Optional[List[int]]:
        """Get mask state for a file.
        
        Args:
            filepath: File path
            
        Returns:
            Mask state if exists, None otherwise
        """
        return self.mask_states.get(filepath)
    
    def set_mask_state(self, filepath: str, mask: List[int]) -> None:
        """Set mask state for a file.
        
        Args:
            filepath: File path
            mask: Mask values
        """
        self.mask_states[filepath] = mask
    
    def get_trigger_state(self, filepath: str) -> Optional[List[int]]:
        """Get trigger state for a file.
        
        Args:
            filepath: File path
            
        Returns:
            Trigger state if exists, None otherwise
        """
        return self.trigger_states.get(filepath)
    
    def set_trigger_state(self, filepath: str, trigger: List[int]) -> None:
        """Set trigger state for a file.
        
        Args:
            filepath: File path
            trigger: Trigger values
        """
        self.trigger_states[filepath] = trigger
    
    def get_scroll_position(self, identifier: str) -> int:
        """Get scroll position for a tab.
        
        Args:
            identifier: Tab identifier
            
        Returns:
            Scroll position (0 if not set)
        """
        return self.scroll_positions.get(identifier, 0)
    
    def set_scroll_position(self, identifier: str, position: int) -> None:
        """Set scroll position for a tab.
        
        Args:
            identifier: Tab identifier
            position: Scroll position
        """
        self.scroll_positions[identifier] = position
    
    def is_dock_visible(self, dock_name: str) -> bool:
        """Check if a dock widget is visible.
        
        Args:
            dock_name: Dock widget name
            
        Returns:
            True if visible (default True if not set)
        """
        return self.dock_states.get(dock_name, True)
    
    def set_dock_visible(self, dock_name: str, visible: bool) -> None:
        """Set dock widget visibility.
        
        Args:
            dock_name: Dock widget name
            visible: Visibility state
        """
        self.dock_states[dock_name] = visible
    
    # ========================================
    # Utility methods
    # ========================================
    
    def get_file_count(self) -> int:
        """Get number of open files.
        
        Returns:
            Number of open files
        """
        return len(self.open_files)
    
    def is_empty(self) -> bool:
        """Check if session has no open files.
        
        Returns:
            True if no files open
        """
        return len(self.open_files) == 0
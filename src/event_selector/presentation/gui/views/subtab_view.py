"""Subtab view - displays events for a single subtab."""

from typing import Optional

from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtCore import pyqtSignal

from event_selector.presentation.gui.widgets.subtab_toolbar import SubtabToolbar
from event_selector.presentation.gui.widgets.event_table import EventTable
from event_selector.application.base import SubtabContext
from event_selector.shared.types import MaskMode
from event_selector.infrastructure.logging import get_logger

logger = get_logger(__name__)


class SubtabView(QWidget):
    """View for a single subtab with its own toolbar."""
    
    # Signals for communicating with controller
    event_toggled = pyqtSignal(str)  # event_key
    
    def __init__(
        self, 
        project_id: str,
        subtab_name: str,
        subtab_index: int,
        parent: Optional[QWidget] = None
    ):
        """Initialize subtab view.
        
        Args:
            project_id: Project identifier
            subtab_name: Name of this subtab
            subtab_index: Index of this subtab (for tab switching)
            parent: Parent widget
        """
        super().__init__(parent)
        logger.trace(f"Starting {__name__}...")
        
        self.project_id = project_id
        self.subtab_name = subtab_name
        self.subtab_index = subtab_index
        
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Setup subtab UI."""
        logger.trace(f"Starting {__name__}...")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Add toolbar at top
        self.toolbar = SubtabToolbar(self.subtab_name)
        layout.addWidget(self.toolbar)
        
        # Add event table
        self.event_table = EventTable()
        layout.addWidget(self.event_table)
        
        # Connect toolbar signals (these will be connected to controller)
        # See next step for controller connections
    
    def get_context(self) -> SubtabContext:
        """Get subtab context for commands.
        
        Returns:
            SubtabContext with this subtab's information
        """
        logger.trace(f"Starting {__name__}...")
        return SubtabContext(
            project_id=self.project_id,
            subtab_name=self.subtab_name,
            subtab_index=self.subtab_index
        )
    
    def update_undo_redo_state(
        self, 
        can_undo: bool, 
        can_redo: bool,
        undo_desc: Optional[str] = None,
        redo_desc: Optional[str] = None
    ) -> None:
        """Update undo/redo button states.
        
        Args:
            can_undo: Whether undo is available
            can_redo: Whether redo is available
            undo_desc: Description of undo command
            redo_desc: Description of redo command
        """
        logger.trace(f"Starting {__name__}...")
        self.toolbar.update_undo_state(can_undo, undo_desc)
        self.toolbar.update_redo_state(can_redo, redo_desc)
    
    def update_event_counter(self, selected: int, total: int) -> None:
        """Update the event counter display.
        
        Args:
            selected: Number of selected events
            total: Total number of events
        """
        logger.trace(f"Starting {__name__}...")
        self.toolbar.update_counter(selected, total)
    
    def refresh_from_model(self, view_model, current_mode: MaskMode) -> None:
        """Refresh display from view model.
        
        Args:
            view_model: SubtabViewModel with event data
            current_mode: Current mask mode
        """
        logger.trace(f"Starting {__name__}...")
        # Update event table
        self.event_table.set_events(view_model.events, current_mode)
        
        # Update counter
        selected = sum(1 for e in view_model.events if e.is_selected(current_mode))
        total = len(view_model.events)
        self.update_event_counter(selected, total)
        
        # Update special selection button states
        has_errors = any('error' in e.info.lower() for e in view_model.events)
        has_syncs = any(
            any(term in e.info.lower() for term in ['sync', 'sbs', 'sws', 'ebs'])
            for e in view_model.events
        )
        self.toolbar.set_has_errors(has_errors)
        self.toolbar.set_has_syncs(has_syncs)

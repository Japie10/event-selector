"""Subtab view - UPDATED with integrated toolbar."""

from typing import Optional

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QShortcut
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QKeySequence

from event_selector.presentation.gui.view_models.project_vm import SubtabViewModel
from event_selector.presentation.gui.widgets.event_table import EventTable
from event_selector.presentation.gui.widgets.subtab_toolbar import SubtabToolbar
from event_selector.shared.types import EventKey


class SubtabView(QWidget):
    """View for a single subtab with integrated toolbar."""

    # Signals
    event_toggled = pyqtSignal(str)  # EventKey as string
    undo_requested = pyqtSignal()
    redo_requested = pyqtSignal()
    select_all_requested = pyqtSignal()
    clear_all_requested = pyqtSignal()
    select_errors_requested = pyqtSignal()
    select_syncs_requested = pyqtSignal()

    def __init__(self, 
                 view_model: SubtabViewModel,
                 parent=None):
        """Initialize subtab view.

        Args:
            view_model: Subtab view model
            parent: Parent widget
        """
        super().__init__(parent)

        self.view_model = view_model
        self._init_ui()
        self._setup_shortcuts()

    def _init_ui(self):
        """Initialize UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar at top
        self.toolbar = SubtabToolbar(self)
        self.toolbar.undo_clicked.connect(self.undo_requested.emit)
        self.toolbar.redo_clicked.connect(self.redo_requested.emit)
        self.toolbar.select_all_clicked.connect(self.select_all_requested.emit)
        self.toolbar.clear_all_clicked.connect(self.clear_all_requested.emit)
        self.toolbar.select_errors_clicked.connect(self.select_errors_requested.emit)
        self.toolbar.select_syncs_clicked.connect(self.select_syncs_requested.emit)
        layout.addWidget(self.toolbar)

        # Event table below toolbar
        self.table = EventTable()
        self.table.event_toggled.connect(self._on_event_toggled)
        layout.addWidget(self.table)

        # Initial population
        self.refresh()

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts for this subtab."""
        # Undo/Redo
        QShortcut(QKeySequence.Undo, self, self.undo_requested.emit)
        QShortcut(QKeySequence.Redo, self, self.redo_requested.emit)
        
        # Select All
        QShortcut(QKeySequence.SelectAll, self, self.select_all_requested.emit)
        
        # Clear All (Ctrl+Shift+A)
        QShortcut(QKeySequence("Ctrl+Shift+A"), self, self.clear_all_requested.emit)
        
        # Select Errors (Ctrl+E)
        QShortcut(QKeySequence("Ctrl+E"), self, self.select_errors_requested.emit)
        
        # Select Syncs (Ctrl+S) - Note: might conflict with Save, consider changing
        QShortcut(QKeySequence("Ctrl+Shift+S"), self, self.select_syncs_requested.emit)

    def _on_event_toggled(self, event_key: str):
        """Handle event toggle from table.

        Args:
            event_key: Event key that was toggled
        """
        # Update view model locally for immediate UI feedback
        for event in self.view_model.events:
            if str(event.key) == event_key:
                event.is_checked = not event.is_checked
                break

        # Update toolbar counter
        self._update_toolbar_state()

        # Propagate to parent
        self.event_toggled.emit(event_key)

    def refresh(self):
        """Refresh table and toolbar from view model."""
        self.table.set_events(self.view_model.events)
        self._update_toolbar_state()

    def _update_toolbar_state(self):
        """Update toolbar button states based on view model."""
        # Update counter
        checked = self.view_model.count_checked()
        total = len(self.view_model.events)
        self.toolbar.update_counter(checked, total)
        
        # Update selection buttons
        has_errors = len(self.view_model.get_error_events()) > 0
        has_syncs = len(self.view_model.get_sync_events()) > 0
        self.toolbar.update_selection_buttons(has_errors, has_syncs)

    def update_undo_redo_state(self, can_undo: bool, can_redo: bool,
                               undo_desc: str = None, redo_desc: str = None):
        """Update undo/redo button states.
        
        Args:
            can_undo: Whether undo is available
            can_redo: Whether redo is available
            undo_desc: Description of undo action
            redo_desc: Description of redo action
        """
        self.toolbar.update_undo_redo_state(can_undo, can_redo, undo_desc, redo_desc)

    def get_view_model(self) -> SubtabViewModel:
        """Get the view model.

        Returns:
            SubtabViewModel instance
        """
        return self.view_model

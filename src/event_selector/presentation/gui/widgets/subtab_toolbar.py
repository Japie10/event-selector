"""Subtab toolbar with per-subtab undo/redo controls."""

from typing import Optional

from PyQt5.QtWidgets import (
    QToolBar, QAction, QLabel, QWidget, QHBoxLayout
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QKeySequence

from event_selector.infrastructure.logging import get_logger

logger = get_logger(__name__)


class SubtabToolbar(QToolBar):
    """Toolbar for subtab with undo/redo and selection controls.
    
    Each subtab has its own toolbar with:
    - Undo/Redo buttons
    - Select All / Clear All buttons
    - Select Errors / Select Syncs buttons (if applicable)
    - Event counter (e.g., "5 / 128 selected")
    
    Signals:
        undo_clicked: Emitted when undo button clicked
        redo_clicked: Emitted when redo button clicked
        select_all_clicked: Emitted when select all button clicked
        clear_all_clicked: Emitted when clear all button clicked
        select_errors_clicked: Emitted when select errors button clicked
        select_syncs_clicked: Emitted when select syncs button clicked
    """
    
    # Signals
    undo_clicked = pyqtSignal()
    redo_clicked = pyqtSignal()
    select_all_clicked = pyqtSignal()
    clear_all_clicked = pyqtSignal()
    select_errors_clicked = pyqtSignal()
    select_syncs_clicked = pyqtSignal()
    
    def __init__(self, subtab_name: str, parent: Optional[QWidget] = None):
        """Initialize subtab toolbar.
        
        Args:
            subtab_name: Name of the subtab
            parent: Parent widget
        """
        super().__init__(f"{subtab_name} Controls", parent)
        
        self.subtab_name = subtab_name
        self._has_errors = False
        self._has_syncs = False
        
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Setup toolbar UI."""
        # Make toolbar non-movable and non-floatable
        self.setMovable(False)
        self.setFloatable(False)
        
        # Undo action
        self.undo_action = QAction("↶ Undo", self)
        self.undo_action.setShortcut(QKeySequence.Undo)
        self.undo_action.setEnabled(False)
        self.undo_action.triggered.connect(self.undo_clicked.emit)
        self.addAction(self.undo_action)
        
        # Redo action
        self.redo_action = QAction("↷ Redo", self)
        self.redo_action.setShortcut(QKeySequence.Redo)
        self.redo_action.setEnabled(False)
        self.redo_action.triggered.connect(self.redo_clicked.emit)
        self.addAction(self.redo_action)
        
        self.addSeparator()
        
        # Select All action
        self.select_all_action = QAction("Select All", self)
        self.select_all_action.setShortcut(QKeySequence.SelectAll)
        self.select_all_action.triggered.connect(self.select_all_clicked.emit)
        self.addAction(self.select_all_action)
        
        # Clear All action
        self.clear_all_action = QAction("Clear All", self)
        self.clear_all_action.setShortcut(QKeySequence("Ctrl+Shift+A"))
        self.clear_all_action.triggered.connect(self.clear_all_clicked.emit)
        self.addAction(self.clear_all_action)
        
        self.addSeparator()
        
        # Select Errors action
        self.select_errors_action = QAction("Select Errors", self)
        self.select_errors_action.setShortcut(QKeySequence("Ctrl+E"))
        self.select_errors_action.setEnabled(False)  # Disabled until errors exist
        self.select_errors_action.triggered.connect(self.select_errors_clicked.emit)
        self.addAction(self.select_errors_action)
        
        # Select Syncs action
        self.select_syncs_action = QAction("Select Syncs", self)
        self.select_syncs_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.select_syncs_action.setEnabled(False)  # Disabled until syncs exist
        self.select_syncs_action.triggered.connect(self.select_syncs_clicked.emit)
        self.addAction(self.select_syncs_action)
        
        self.addSeparator()
        
        # Event counter label
        self.counter_label = QLabel("0 / 0 selected")
        self.counter_label.setStyleSheet("padding: 0 10px;")
        self.addWidget(self.counter_label)
    
    def update_undo_state(self, can_undo: bool, description: Optional[str] = None) -> None:
        """Update undo button state.
        
        Args:
            can_undo: Whether undo is available
            description: Optional description for tooltip
        """
        self.undo_action.setEnabled(can_undo)
        
        if can_undo and description:
            self.undo_action.setToolTip(f"Undo: {description}")
        else:
            self.undo_action.setToolTip("Undo (Ctrl+Z)")
    
    def update_redo_state(self, can_redo: bool, description: Optional[str] = None) -> None:
        """Update redo button state.
        
        Args:
            can_redo: Whether redo is available
            description: Optional description for tooltip
        """
        self.redo_action.setEnabled(can_redo)
        
        if can_redo and description:
            self.redo_action.setToolTip(f"Redo: {description}")
        else:
            self.redo_action.setToolTip("Redo (Ctrl+Y)")
    
    def update_counter(self, selected: int, total: int) -> None:
        """Update event counter display.
        
        Args:
            selected: Number of selected events
            total: Total number of events
        """
        self.counter_label.setText(f"{selected} / {total} selected")
    
    def set_has_errors(self, has_errors: bool) -> None:
        """Enable/disable Select Errors button.
        
        Args:
            has_errors: Whether this subtab has error events
        """
        self._has_errors = has_errors
        self.select_errors_action.setEnabled(has_errors)
    
    def set_has_syncs(self, has_syncs: bool) -> None:
        """Enable/disable Select Syncs button.
        
        Args:
            has_syncs: Whether this subtab has sync events
        """
        self._has_syncs = has_syncs
        self.select_syncs_action.setEnabled(has_syncs)

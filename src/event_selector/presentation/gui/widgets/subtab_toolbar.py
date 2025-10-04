"""Subtab toolbar - Per-subtab controls for selection and undo/redo."""

from typing import TYPE_CHECKING

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QToolButton, QLabel
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QIcon

if TYPE_CHECKING:
    from event_selector.presentation.gui.views.subtab_view import SubtabView


class SubtabToolbar(QWidget):
    """Toolbar with per-subtab controls.
    
    Contains:
    - Undo/Redo buttons
    - Select All / Clear All
    - Select Errors
    - Select Syncs
    - Checked event counter
    """
    
    # Signals
    undo_clicked = pyqtSignal()
    redo_clicked = pyqtSignal()
    select_all_clicked = pyqtSignal()
    clear_all_clicked = pyqtSignal()
    select_errors_clicked = pyqtSignal()
    select_syncs_clicked = pyqtSignal()
    
    def __init__(self, parent: 'SubtabView' = None):
        """Initialize subtab toolbar.
        
        Args:
            parent: Parent SubtabView
        """
        super().__init__(parent)
        self.subtab_view = parent
        self._init_ui()
    
    def _init_ui(self):
        """Initialize UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(5)
        
        # Undo/Redo group
        self.undo_btn = self._create_button("↶", "Undo (Ctrl+Z)")
        self.undo_btn.clicked.connect(self.undo_clicked.emit)
        layout.addWidget(self.undo_btn)
        
        self.redo_btn = self._create_button("↷", "Redo (Ctrl+Y)")
        self.redo_btn.clicked.connect(self.redo_clicked.emit)
        layout.addWidget(self.redo_btn)
        
        # Separator
        layout.addWidget(self._create_separator())
        
        # Selection group
        self.select_all_btn = self._create_button("Select All", "Select all events (Ctrl+A)")
        self.select_all_btn.clicked.connect(self.select_all_clicked.emit)
        layout.addWidget(self.select_all_btn)
        
        self.clear_all_btn = self._create_button("Clear All", "Clear all events (Ctrl+Shift+A)")
        self.clear_all_btn.clicked.connect(self.clear_all_clicked.emit)
        layout.addWidget(self.clear_all_btn)
        
        # Separator
        layout.addWidget(self._create_separator())
        
        # Special selections
        self.select_errors_btn = self._create_button("Errors", "Select all error events (Ctrl+E)")
        self.select_errors_btn.clicked.connect(self.select_errors_clicked.emit)
        layout.addWidget(self.select_errors_btn)
        
        self.select_syncs_btn = self._create_button("Syncs", "Select all sync events (Ctrl+S)")
        self.select_syncs_btn.clicked.connect(self.select_syncs_clicked.emit)
        layout.addWidget(self.select_syncs_btn)
        
        # Separator
        layout.addWidget(self._create_separator())
        
        # Event counter
        self.counter_label = QLabel("0 / 0 selected")
        self.counter_label.setStyleSheet("padding: 0 5px; font-weight: bold;")
        layout.addWidget(self.counter_label)
        
        # Stretch to push everything left
        layout.addStretch()
        
        # Style the toolbar
        self.setStyleSheet("""
            QWidget {
                background-color: #f8f8f8;
                border-bottom: 1px solid #ddd;
            }
            QToolButton {
                padding: 4px 8px;
                border: 1px solid #ccc;
                border-radius: 3px;
                background-color: white;
            }
            QToolButton:hover {
                background-color: #e7f3ff;
                border-color: #007ACC;
            }
            QToolButton:pressed {
                background-color: #cce4ff;
            }
            QToolButton:disabled {
                color: #999;
                background-color: #f0f0f0;
                border-color: #ddd;
            }
        """)
    
    def _create_button(self, text: str, tooltip: str) -> QToolButton:
        """Create a toolbar button.
        
        Args:
            text: Button text
            tooltip: Tooltip text
            
        Returns:
            QToolButton instance
        """
        btn = QToolButton()
        btn.setText(text)
        btn.setToolTip(tooltip)
        return btn
    
    def _create_separator(self) -> QWidget:
        """Create a vertical separator.
        
        Returns:
            Separator widget
        """
        separator = QWidget()
        separator.setFixedWidth(1)
        separator.setStyleSheet("background-color: #ccc;")
        return separator
    
    def update_counter(self, checked: int, total: int):
        """Update the event counter.
        
        Args:
            checked: Number of checked events
            total: Total number of events
        """
        self.counter_label.setText(f"{checked} / {total} selected")
    
    def update_undo_redo_state(self, can_undo: bool, can_redo: bool, 
                               undo_desc: str = None, redo_desc: str = None):
        """Update undo/redo button states.
        
        Args:
            can_undo: Whether undo is available
            can_redo: Whether redo is available
            undo_desc: Description of undo action
            redo_desc: Description of redo action
        """
        self.undo_btn.setEnabled(can_undo)
        self.redo_btn.setEnabled(can_redo)
        
        # Update tooltips with descriptions
        if can_undo and undo_desc:
            self.undo_btn.setToolTip(f"Undo: {undo_desc} (Ctrl+Z)")
        else:
            self.undo_btn.setToolTip("Undo (Ctrl+Z)")
        
        if can_redo and redo_desc:
            self.redo_btn.setToolTip(f"Redo: {redo_desc} (Ctrl+Y)")
        else:
            self.redo_btn.setToolTip("Redo (Ctrl+Y)")
    
    def update_selection_buttons(self, has_errors: bool, has_syncs: bool):
        """Update selection button states based on available events.
        
        Args:
            has_errors: Whether there are error events
            has_syncs: Whether there are sync events
        """
        self.select_errors_btn.setEnabled(has_errors)
        self.select_syncs_btn.setEnabled(has_syncs)

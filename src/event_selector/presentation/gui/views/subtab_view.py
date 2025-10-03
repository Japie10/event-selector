"""Subtab view - displays events in a table."""

from typing import Optional

from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtCore import pyqtSignal

from event_selector.presentation.gui.view_models.project_vm import SubtabViewModel
from event_selector.presentation.gui.widgets.event_table import EventTable
from event_selector.shared.types import EventKey


class SubtabView(QWidget):
    """View for a single subtab - displays event table."""

    # Signals
    event_toggled = pyqtSignal(str)  # EventKey as string

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

    def _init_ui(self):
        """Initialize UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Event table
        self.table = EventTable()
        self.table.event_toggled.connect(self._on_event_toggled)
        layout.addWidget(self.table)

        # Populate table
        self.refresh()

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

        # Propagate to parent
        self.event_toggled.emit(event_key)

    def refresh(self):
        """Refresh table from view model."""
        self.table.set_events(self.view_model.events)

    def get_view_model(self) -> SubtabViewModel:
        """Get the view model.

        Returns:
            SubtabViewModel instance
        """
        return self.view_model

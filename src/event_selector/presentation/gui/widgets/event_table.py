"""Event table widget - displays event rows."""

from typing import List

from PyQt5.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, 
    QCheckBox, QWidget, QHBoxLayout, QAbstractItemView
)
from PyQt5.QtCore import Qt, pyqtSignal

from event_selector.presentation.gui.view_models.project_vm import EventRowViewModel


class EventTable(QTableWidget):
    """Table widget for displaying events."""

    # Signals
    event_toggled = pyqtSignal(str)  # EventKey as string

    def __init__(self, parent=None):
        """Initialize event table.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        self._setup_table()
        self._event_rows = []

    def _setup_table(self):
        """Setup table structure and appearance."""
        # Columns
        self.setColumnCount(6)
        self.setHorizontalHeaderLabels([
            "State", "ID/Addr", "Bit", "Source", "Description", "Info"
        ])

        # Appearance
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)

        # Header
        header = self.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # State
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # ID/Addr
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Bit
        header.setSectionResizeMode(3, QHeaderView.Interactive)       # Source
        header.setSectionResizeMode(4, QHeaderView.Stretch)           # Description
        header.setSectionResizeMode(5, QHeaderView.Interactive)       # Info

        # Vertical header
        self.verticalHeader().setDefaultSectionSize(24)
        self.verticalHeader().setVisible(False)

        # Enable tooltips
        self.setMouseTracking(True)

    def set_events(self, events: List[EventRowViewModel]):
        """Set events to display in table.

        Args:
            events: List of event view models
        """
        self._event_rows = events
        self._populate_table()

    def _populate_table(self):
        """Populate table with event rows."""
        # Block signals during population
        self.blockSignals(True)

        # Clear existing rows
        self.setRowCount(0)

        # Add rows
        for event in self._event_rows:
            self._add_event_row(event)

        # Unblock signals
        self.blockSignals(False)

    def _add_event_row(self, event: EventRowViewModel):
        """Add a single event row.

        Args:
            event: Event view model
        """
        row = self.rowCount()
        self.insertRow(row)

        # State checkbox (column 0)
        checkbox_widget = self._create_checkbox_widget(event)
        self.setCellWidget(row, 0, checkbox_widget)

        # ID/Address (column 1)
        self._set_readonly_item(row, 1, event.id_or_addr)

        # Bit (column 2)
        self._set_readonly_item(row, 2, str(event.bit))

        # Source (column 3)
        self._set_readonly_item(row, 3, event.source)

        # Description (column 4)
        desc_item = self._set_readonly_item(row, 4, event.description)
        if len(event.description) > 50:
            desc_item.setToolTip(event.description)

        # Info (column 5)
        info_item = self._set_readonly_item(row, 5, event.info)
        if len(event.info) > 30:
            info_item.setToolTip(event.info)

        # Highlight errors and syncs
        if event.is_error:
            self._highlight_row(row, "#ffe6e6")  # Light red
        elif event.is_sync:
            self._highlight_row(row, "#e6f3ff")  # Light blue

    def _create_checkbox_widget(self, event: EventRowViewModel) -> QWidget:
        """Create centered checkbox widget.

        Args:
            event: Event view model

        Returns:
            Widget containing centered checkbox
        """
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignCenter)

        checkbox = QCheckBox()
        checkbox.setChecked(event.is_checked)

        # Store event key in checkbox for later retrieval
        checkbox.setProperty("event_key", str(event.key))

        checkbox.stateChanged.connect(
            lambda state, key=str(event.key): self.event_toggled.emit(key)
        )

        layout.addWidget(checkbox)
        return widget

    def _set_readonly_item(self, row: int, col: int, text: str) -> QTableWidgetItem:
        """Set a readonly table item.

        Args:
            row: Row index
            col: Column index
            text: Item text

        Returns:
            Created QTableWidgetItem
        """
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        self.setItem(row, col, item)
        return item

    def _highlight_row(self, row: int, color: str):
        """Highlight a row with a background color.

        Args:
            row: Row index
            color: Background color (hex or name)
        """
        from PyQt5.QtGui import QColor

        bg_color = QColor(color)
        for col in range(1, self.columnCount()):  # Skip checkbox column
            item = self.item(row, col)
            if item:
                item.setBackground(bg_color)

    def update_event_state(self, event_key: str, is_checked: bool):
        """Update the checked state of an event.

        Args:
            event_key: Event key
            is_checked: New checked state
        """
        # Find and update the checkbox
        for row in range(self.rowCount()):
            checkbox_widget = self.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox and checkbox.property("event_key") == event_key:
                    checkbox.blockSignals(True)
                    checkbox.setChecked(is_checked)
                    checkbox.blockSignals(False)
                    break

    def get_checked_events(self) -> List[str]:
        """Get list of checked event keys.

        Returns:
            List of event keys (as strings)
        """
        checked = []
        for row in range(self.rowCount()):
            checkbox_widget = self.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    event_key = checkbox.property("event_key")
                    if event_key:
                        checked.append(event_key)
        return checked

    def select_all_events(self):
        """Check all event checkboxes."""
        for row in range(self.rowCount()):
            checkbox_widget = self.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox and not checkbox.isChecked():
                    checkbox.setChecked(True)

    def clear_all_events(self):
        """Uncheck all event checkboxes."""
        for row in range(self.rowCount()):
            checkbox_widget = self.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    checkbox.setChecked(False)

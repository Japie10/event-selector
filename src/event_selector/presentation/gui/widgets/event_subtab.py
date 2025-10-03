"""Event tab widget for displaying event format data."""

from typing import Optional, Dict, Any, List
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
    QPushButton, QMessageBox, QAbstractItemView
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

from event_selector.domain.models.base import Project
from event_selector.application.facades.event_selector_facade import EventSelectorFacade
from event_selector.shared.types import MaskMode, FormatType, EventKey


class EventSubtab(QWidget):
    """Widget for a single subtab showing events."""

    # Signals
    selection_changed = pyqtSignal()

    def __init__(self, 
                 name: str,
                 events: Dict[EventKey, Any],
                 project: Project,
                 subtab_id: int,
                 parent=None):
        """Initialize subtab.

        Args:
            name: Subtab name
            events: Events for this subtab
            project: Parent project
            subtab_id: Subtab identifier
            parent: Parent widget
        """
        super().__init__(parent)

        self.name = name
        self.events = events
        self.project = project
        self.subtab_id = subtab_id
        self.current_mode = MaskMode.MASK

        self._init_ui()
        self._populate_table()

    def _init_ui(self):
        """Initialize UI."""
        layout = QVBoxLayout(self)

        # Table widget
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "State", "ID/Addr", "Bit", "Event Source", "Description", "Info"
        ])

        # Configure table
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)

        # Connect signals
        self.table.itemChanged.connect(self._on_item_changed)

        layout.addWidget(self.table)

    def _populate_table(self):
        """Populate table with events."""
        # Clear table
        self.table.setRowCount(0)

        # Add events
        for key, event in self.events.items():
            row = self.table.rowCount()
            self.table.insertRow(row)

            # Get coordinate
            coord = event.get_coordinate()

            # State checkbox
            checkbox = QCheckBox()
            checkbox.setChecked(self._is_bit_set(coord.id, coord.bit))
            checkbox.stateChanged.connect(
                lambda state, k=key: self._toggle_event(k, state)
            )
            self.table.setCellWidget(row, 0, checkbox)

            # ID/Address
            if hasattr(event, 'address'):  # MK1
                self.table.setItem(row, 1, QTableWidgetItem(event.address.hex))
            else:  # MK2
                self.table.setItem(row, 1, QTableWidgetItem(f"{coord.id:02X}"))

            # Bit
            self.table.setItem(row, 2, QTableWidgetItem(str(coord.bit)))

            # Event source
            self.table.setItem(row, 3, QTableWidgetItem(event.info.source))

            # Description
            self.table.setItem(row, 4, QTableWidgetItem(event.info.description))

            # Info
            self.table.setItem(row, 5, QTableWidgetItem(event.info.info))

            # Make read-only except checkbox
            for col in range(1, 6):
                item = self.table.item(row, col)
                if item:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)

    def _is_bit_set(self, id_num: int, bit: int) -> bool:
        """Check if a bit is set in current mask."""
        mask_data = (self.project.event_mask if self.current_mode == MaskMode.MASK 
                    else self.project.capture_mask)
        return mask_data.get_bit(id_num, bit)

    def _toggle_event(self, event_key: EventKey, state: int):
        """Toggle event state."""
        # This will be handled by parent tab to use commands
        self.parent().toggle_event(event_key)

    def set_mode(self, mode: MaskMode):
        """Set the current mode."""
        self.current_mode = mode
        self.refresh()

    def refresh(self):
        """Refresh the display."""
        # Update checkboxes
        for row in range(self.table.rowCount()):
            checkbox = self.table.cellWidget(row, 0)
            if checkbox:
                # Get ID and bit from table
                id_item = self.table.item(row, 1)
                bit_item = self.table.item(row, 2)
                if id_item and bit_item:
                    try:
                        # Parse ID (handle both hex and decimal)
                        id_text = id_item.text()
                        if id_text.startswith('0x'):
                            # This is an address, need to map to ID
                            # For now, just skip
                            continue
                        else:
                            id_num = int(id_text, 16)
                        bit = int(bit_item.text())

                        # Update checkbox state
                        checkbox.blockSignals(True)
                        checkbox.setChecked(self._is_bit_set(id_num, bit))
                        checkbox.blockSignals(False)
                    except (ValueError, AttributeError):
                        pass

    def select_all(self):
        """Select all events."""
        for row in range(self.table.rowCount()):
            checkbox = self.table.cellWidget(row, 0)
            if checkbox and not checkbox.isChecked():
                checkbox.setChecked(True)

    def clear_all(self):
        """Clear all events."""
        for row in range(self.table.rowCount()):
            checkbox = self.table.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                checkbox.setChecked(False)

    def get_selected_keys(self) -> List[EventKey]:
        """Get list of selected event keys."""
        selected = []
        # Implementation depends on tracking event keys with rows
        return selected


class EventTab(QWidget):
    """Tab widget for a complete project."""

    # Signals
    status_message = pyqtSignal(str)

    def __init__(self, 
                 project: Project,
                 project_id: str,
                 facade: EventSelectorFacade,
                 parent=None):
        """Initialize event tab.

        Args:
            project: Project to display
            project_id: Project identifier
            facade: Application facade
            parent: Parent widget
        """
        super().__init__(parent)

        self.project = project
        self.project_id = project_id
        self.facade = facade
        self.current_mode = MaskMode.MASK

        self._init_ui()
        self._create_subtabs()

    def _init_ui(self):
        """Initialize UI."""
        layout = QVBoxLayout(self)

        # Sources banner if present
        if self.project.format.sources:
            sources_label = QLabel()
            sources_text = "These events are used for: " + ", ".join(
                s.name for s in self.project.format.sources
            )
            sources_label.setText(sources_text)
            sources_label.setStyleSheet("QLabel { background-color: #f0f0f0; padding: 5px; }")
            layout.addWidget(sources_label)

        # Subtab widget
        self.subtab_widget = QTabWidget()
        layout.addWidget(self.subtab_widget)

    def _create_subtabs(self):
        """Create subtabs based on format."""
        subtab_config = self.project.format.get_subtab_config()

        if self.project.format.format_type == FormatType.MK1:
            # Fixed subtabs for MK1
            from event_selector.domain.models.mk1 import Mk1Format
            mk1_format = self.project.format

            for subtab_info in subtab_config['subtabs']:
                name = subtab_info['name']
                # Get events for this subtab
                events = mk1_format.get_events_by_subtab(name)

                # Create subtab widget
                subtab = EventSubtab(name, events, self.project, 
                                   subtab_info['ids'][0], self)
                self.subtab_widget.addTab(subtab, name)

        elif self.project.format.format_type == FormatType.MK2:
            # Dynamic subtabs for MK2
            from event_selector.domain.models.mk2 import Mk2Format
            mk2_format = self.project.format

            for subtab_info in subtab_config['subtabs']:
                name = subtab_info['name']
                id_num = subtab_info['id']

                # Get events for this ID
                events = mk2_format.get_events_by_id(id_num)

                # Create subtab widget
                subtab = EventSubtab(name, events, self.project, id_num, self)
                self.subtab_widget.addTab(subtab, name)

    def toggle_event(self, event_key: EventKey):
        """Toggle an event using command pattern."""
        self.facade.toggle_event(self.project_id, event_key, self.current_mode)
        self.refresh()
        self.status_message.emit(f"Toggled {event_key}")

    def undo(self):
        """Undo last operation."""
        description = self.facade.undo(self.project_id)
        if description:
            self.refresh()
            self.status_message.emit(f"Undone: {description}")
        else:
            self.status_message.emit("Nothing to undo")

    def redo(self):
        """Redo last undone operation."""
        description = self.facade.redo(self.project_id)
        if description:
            self.refresh()
            self.status_message.emit(f"Redone: {description}")
        else:
            self.status_message.emit("Nothing to redo")

    def select_all(self):
        """Select all in current subtab."""
        current_subtab = self.subtab_widget.currentWidget()
        if isinstance(current_subtab, EventSubtab):
            subtab_name = current_subtab.name
            self.facade.select_all_events(self.project_id, self.current_mode, subtab_name)
            self.refresh()
            self.status_message.emit(f"Selected all in {subtab_name}")

    def clear_all(self):
        """Clear all in current subtab."""
        current_subtab = self.subtab_widget.currentWidget()
        if isinstance(current_subtab, EventSubtab):
            subtab_name = current_subtab.name
            self.facade.clear_all_events(self.project_id, self.current_mode, subtab_name)
            self.refresh()
            self.status_message.emit(f"Cleared all in {subtab_name}")

    def select_errors(self):
        """Select all error events."""
        error_keys = self.facade.select_errors(self.project_id, self.current_mode)
        if error_keys:
            self.facade.toggle_events(self.project_id, error_keys, self.current_mode)
            self.refresh()
            self.status_message.emit(f"Selected {len(error_keys)} error events")
        else:
            self.status_message.emit("No error events found")

    def select_syncs(self):
        """Select all sync events."""
        sync_keys = self.facade.select_syncs(self.project_id, self.current_mode)
        if sync_keys:
            self.facade.toggle_events(self.project_id, sync_keys, self.current_mode)
            self.refresh()
            self.status_message.emit(f"Selected {len(sync_keys)} sync events")
        else:
            self.status_message.emit("No sync events found")

    def set_mode(self, mode: MaskMode):
        """Set the current mode."""
        self.current_mode = mode
        for i in range(self.subtab_widget.count()):
            widget = self.subtab_widget.widget(i)
            if isinstance(widget, EventSubtab):
                widget.set_mode(mode)

    def refresh(self):
        """Refresh all subtabs."""
        for i in range(self.subtab_widget.count()):
            widget = self.subtab_widget.widget(i)
            if isinstance(widget, EventSubtab):
                widget.refresh()"""Event tab widget for displaying event format data."""

"""Event tab widget for displaying and editing events.

This module implements the tab widget that displays events from a YAML file
with tri-state checkboxes, filtering, and undo/redo support.
"""

from pathlib import Path
from typing import Optional, Dict, List, Any, Union
import re

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QTableWidget, 
    QTableWidgetItem, QHeaderView, QLabel, QLineEdit, QPushButton,
    QCheckBox, QUndoStack, QUndoCommand, QAbstractItemView,
    QStyledItemDelegate, QStyleOptionButton, QStyle, QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal, QRect, QModelIndex, QEvent
from PyQt5.QtGui import QPainter

import numpy as np

from event_selector.core.models import (
    FormatType, MaskMode, Mk1Format, Mk2Format, 
    EventMk1, EventMk2, MaskData
)


class TriStateCheckBox(QCheckBox):
    """Tri-state checkbox for event selection."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTristate(True)

    def nextCheckState(self):
        """Override to control state transitions."""
        if self.checkState() == Qt.Unchecked:
            self.setCheckState(Qt.Checked)
        elif self.checkState() == Qt.Checked:
            self.setCheckState(Qt.PartiallyChecked)
        else:
            self.setCheckState(Qt.Unchecked)


class CheckBoxDelegate(QStyledItemDelegate):
    """Delegate for rendering tri-state checkboxes in table."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.checkboxes = {}  # Store checkbox states

    def createEditor(self, parent, option, index):
        """Create checkbox editor."""
        checkbox = TriStateCheckBox(parent)
        checkbox.setStyleSheet("margin-left: 15px;")  # Center in cell
        return checkbox

    def setEditorData(self, editor, index):
        """Set checkbox state from model."""
        state = index.data(Qt.UserRole)
        if state is not None:
            editor.setCheckState(state)

    def setModelData(self, editor, model, index):
        """Save checkbox state to model."""
        model.setData(index, editor.checkState(), Qt.UserRole)
        model.setData(index, "", Qt.DisplayRole)  # Clear text

    def paint(self, painter, option, index):
        """Paint checkbox in cell."""
        # Get checkbox state
        state = index.data(Qt.UserRole)
        if state is None:
            state = Qt.Unchecked

        # Create checkbox style option
        checkbox_option = QStyleOptionButton()
        checkbox_option.state |= QStyle.State_Enabled

        if state == Qt.Checked:
            checkbox_option.state |= QStyle.State_On
        elif state == Qt.PartiallyChecked:
            checkbox_option.state |= QStyle.State_NoChange
        else:
            checkbox_option.state |= QStyle.State_Off

        # Calculate checkbox position (centered)
        checkbox_size = QApplication.style().subElementRect(
            QStyle.SE_CheckBoxIndicator, checkbox_option
        ).size()

        x = option.rect.x() + (option.rect.width() - checkbox_size.width()) // 2
        y = option.rect.y() + (option.rect.height() - checkbox_size.height()) // 2

        checkbox_option.rect = QRect(x, y, checkbox_size.width(), checkbox_size.height())

        # Draw checkbox
        QApplication.style().drawControl(QStyle.CE_CheckBox, checkbox_option, painter)

    def editorEvent(self, event, model, option, index):
        """Handle mouse clicks on checkbox."""
        if event.type() == QEvent.MouseButtonRelease:
            # Toggle checkbox state
            current_state = index.data(Qt.UserRole)
            if current_state == Qt.Unchecked:
                new_state = Qt.Checked
            elif current_state == Qt.Checked:
                new_state = Qt.PartiallyChecked
            else:
                new_state = Qt.Unchecked

            model.setData(index, new_state, Qt.UserRole)
            return True
        return False


class ToggleEventCommand(QUndoCommand):
    """Undo command for toggling event selection."""

    def __init__(self, table, row, old_state, new_state, description="Toggle event"):
        super().__init__(description)
        self.table = table
        self.row = row
        self.old_state = old_state
        self.new_state = new_state

    def redo(self):
        """Apply the toggle."""
        item = self.table.item(self.row, 0)
        if item:
            item.setData(Qt.UserRole, self.new_state)

    def undo(self):
        """Revert the toggle."""
        item = self.table.item(self.row, 0)
        if item:
            item.setData(Qt.UserRole, self.old_state)


class BulkToggleCommand(QUndoCommand):
    """Undo command for bulk toggle operations."""

    def __init__(self, table, changes, description="Bulk toggle"):
        super().__init__(description)
        self.table = table
        self.changes = changes  # List of (row, old_state, new_state)

    def redo(self):
        """Apply all toggles."""
        for row, _, new_state in self.changes:
            item = self.table.item(row, 0)
            if item:
                item.setData(Qt.UserRole, new_state)

    def undo(self):
        """Revert all toggles."""
        for row, old_state, _ in self.changes:
            item = self.table.item(row, 0)
            if item:
                item.setData(Qt.UserRole, old_state)


class EventSubTab(QWidget):
    """Widget for a single subtab showing events for specific IDs."""

    selection_changed = pyqtSignal()

    def __init__(self, name: str, events: Dict, format_type: FormatType, parent=None):
        super().__init__(parent)
        self.name = name
        self.events = events
        self.format_type = format_type
        self.undo_stack = QUndoStack(self)
        self._setup_ui()
        self._populate_table()

    def _setup_ui(self):
        """Setup subtab UI."""
        layout = QVBoxLayout(self)

        # Filter bar
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter:"))

        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Type to filter events...")
        self.filter_input.textChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.filter_input)

        self.clear_filter_button = QPushButton("Clear")
        self.clear_filter_button.clicked.connect(self._clear_filter)
        filter_layout.addWidget(self.clear_filter_button)

        layout.addLayout(filter_layout)

        # Event table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "State", "ID/Addr", "Bit", "Event Source", "Description", "Info"
        ])

        # Set checkbox delegate for first column
        self.checkbox_delegate = CheckBoxDelegate()
        self.table.setItemDelegate(self.checkbox_delegate)

        # Configure table
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        # Set column widths
        header = self.table.horizontalHeader()
        header.resizeSection(0, 60)  # State column
        header.resizeSection(1, 80)  # ID/Addr
        header.resizeSection(2, 50)  # Bit
        header.setStretchLastSection(True)

        # Connect signals
        self.table.itemClicked.connect(self._on_item_clicked)

        layout.addWidget(self.table)

    def _populate_table(self):
        """Populate table with events."""
        # Calculate number of rows based on format
        if self.format_type == FormatType.MK1:
            # Show 128 rows (4 IDs × 32 bits) for each subtab
            num_rows = 128
        else:  # MK2
            # Show 28 rows (bits 0-27) for each ID
            num_rows = 28

        self.table.setRowCount(num_rows)

        # Fill table with events or empty rows
        row = 0
        for key, event in sorted(self.events.items()):
            if row >= num_rows:
                break

            # State checkbox (column 0)
            state_item = QTableWidgetItem()
            state_item.setData(Qt.UserRole, Qt.Unchecked)  # Initial state
            self.table.setItem(row, 0, state_item)

            # ID/Address (column 1)
            if isinstance(event, EventMk1):
                self.table.setItem(row, 1, QTableWidgetItem(event.address))
                self.table.setItem(row, 2, QTableWidgetItem(str(event.bit)))
            else:  # EventMk2
                self.table.setItem(row, 1, QTableWidgetItem(f"ID {event.id:X}"))
                self.table.setItem(row, 2, QTableWidgetItem(str(event.bit)))

            # Event source (column 3)
            self.table.setItem(row, 3, QTableWidgetItem(event.event_source))

            # Description (column 4)
            self.table.setItem(row, 4, QTableWidgetItem(event.description))

            # Info (column 5)
            self.table.setItem(row, 5, QTableWidgetItem(event.info))

            row += 1

        # Fill remaining rows with empty entries
        while row < num_rows:
            # Empty state checkbox
            state_item = QTableWidgetItem()
            state_item.setData(Qt.UserRole, Qt.Unchecked)
            state_item.setFlags(state_item.flags() & ~Qt.ItemIsEnabled)
            self.table.setItem(row, 0, state_item)

            # Disabled empty cells
            for col in range(1, 6):
                item = QTableWidgetItem("")
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                self.table.setItem(row, col, item)

            row += 1

    def _on_item_clicked(self, item):
        """Handle item click."""
        if item.column() == 0:  # Checkbox column
            # Handle through delegate
            pass

        self.selection_changed.emit()

    def _apply_filter(self, text: str):
        """Apply filter to table rows."""
        if not text:
            # Show all rows
            for row in range(self.table.rowCount()):
                self.table.setRowHidden(row, False)
            return

        # Hide rows that don't match filter
        text_lower = text.lower()
        for row in range(self.table.rowCount()):
            # Check all columns except checkbox
            match = False
            for col in range(1, self.table.columnCount()):
                item = self.table.item(row, col)
                if item and text_lower in item.text().lower():
                    match = True
                    break
            self.table.setRowHidden(row, not match)

    def _clear_filter(self):
        """Clear filter input."""
        self.filter_input.clear()

    def get_mask_array(self) -> np.ndarray:
        """Get mask array from current selections."""
        if self.format_type == FormatType.MK1:
            mask = np.zeros(4, dtype=np.uint32)  # 4 IDs per subtab
        else:
            mask = np.zeros(1, dtype=np.uint32)  # 1 ID per subtab

        for row in range(self.table.rowCount()):
            state_item = self.table.item(row, 0)
            if state_item and state_item.data(Qt.UserRole) == Qt.Checked:
                # Calculate which bit to set
                if self.format_type == FormatType.MK1:
                    # Map row to ID and bit
                    id_offset = row // 32
                    bit = row % 32
                    mask[id_offset] |= (1 << bit)
                else:  # MK2
                    # Row directly maps to bit (0-27)
                    if row < 28:
                        mask[0] |= (1 << row)

        return mask

    def set_mask_array(self, mask: np.ndarray):
        """Set selections from mask array."""
        for row in range(self.table.rowCount()):
            state_item = self.table.item(row, 0)
            if not state_item:
                continue

            # Check if bit is set in mask
            is_set = False
            if self.format_type == FormatType.MK1:
                id_offset = row // 32
                bit = row % 32
                if id_offset < len(mask):
                    is_set = bool(mask[id_offset] & (1 << bit))
            else:  # MK2
                if row < 28 and len(mask) > 0:
                    is_set = bool(mask[0] & (1 << row))

            state_item.setData(Qt.UserRole, Qt.Checked if is_set else Qt.Unchecked)


class EventTab(QWidget):
    """Main tab widget for a YAML file."""

    selection_changed = pyqtSignal()
    events_modified = pyqtSignal()

    def __init__(self, format_obj: Union[Mk1Format, Mk2Format], 
                 filepath: Path, mode: MaskMode, parent=None):
        super().__init__(parent)
        self.format_obj = format_obj
        self.filepath = filepath
        self.mode = mode
        self.subtabs = {}
        self.unsaved_changes = False
        self._setup_ui()
        self._create_subtabs()

    def _setup_ui(self):
        """Setup main tab UI."""
        layout = QVBoxLayout(self)

        # Sources banner (if present)
        if hasattr(self.format_obj, 'sources') and self.format_obj.sources:
            sources_text = "These events are used for: " + ", ".join(
                s.name for s in self.format_obj.sources
            )
            sources_label = QLabel(sources_text)
            sources_label.setStyleSheet("background-color: #f0f0f0; padding: 5px;")
            layout.addWidget(sources_label)

        # Subtabs
        self.subtab_widget = QTabWidget()
        layout.addWidget(self.subtab_widget)

    def _create_subtabs(self):
        """Create subtabs based on format."""
        if isinstance(self.format_obj, Mk1Format):
            # Create fixed subtabs for MK1
            for subtab_name in ["Data", "Network", "Application"]:
                events = self.format_obj.get_subtab_events(subtab_name)
                subtab = EventSubTab(subtab_name, events, FormatType.MK1, self)
                subtab.selection_changed.connect(self.selection_changed.emit)
                self.subtab_widget.addTab(subtab, subtab_name)
                self.subtabs[subtab_name] = subtab

        else:  # Mk2Format
            # Create subtab for each ID
            for id_num in range(16):
                events = self.format_obj.get_id_events(id_num)
                name = self.format_obj.get_id_name(id_num)
                subtab = EventSubTab(name, events, FormatType.MK2, self)
                subtab.selection_changed.connect(self.selection_changed.emit)
                self.subtab_widget.addTab(subtab, name)
                self.subtabs[name] = subtab

    def get_current_mask(self) -> np.ndarray:
        """Get current mask array."""
        if isinstance(self.format_obj, Mk1Format):
            mask = np.zeros(12, dtype=np.uint32)

            # Map subtabs to ID ranges
            mapping = {
                "Data": [0, 1, 2, 3],
                "Network": [4, 5, 6, 7],
                "Application": [8, 9, 10, 11]
            }

            for subtab_name, ids in mapping.items():
                if subtab_name in self.subtabs:
                    subtab_mask = self.subtabs[subtab_name].get_mask_array()
                    for i, id_num in enumerate(ids):
                        if i < len(subtab_mask):
                            mask[id_num] = subtab_mask[i]

        else:  # Mk2Format
            mask = np.zeros(16, dtype=np.uint32)
            for i, subtab in enumerate(self.subtabs.values()):
                if i < 16:
                    subtab_mask = subtab.get_mask_array()
                    if len(subtab_mask) > 0:
                        mask[i] = subtab_mask[0]

        return mask

    def apply_mask(self, mask_data: MaskData):
        """Apply imported mask data."""
        mask = mask_data.to_numpy()

        if isinstance(self.format_obj, Mk1Format):
            # Map to subtabs
            mapping = {
                "Data": mask[0:4],
                "Network": mask[4:8],
                "Application": mask[8:12]
            }

            for subtab_name, subtab_mask in mapping.items():
                if subtab_name in self.subtabs:
                    self.subtabs[subtab_name].set_mask_array(subtab_mask)

        else:  # Mk2Format
            for i, subtab in enumerate(self.subtabs.values()):
                if i < len(mask):
                    subtab.set_mask_array(mask[i:i+1])

        self.unsaved_changes = True
        self.events_modified.emit()

    def export_mask(self, filepath: str, mode: MaskMode):
        """Export current mask to file."""
        from event_selector.core.exporter import Exporter

        mask = self.get_current_mask()
        exporter = Exporter(format_obj=self.format_obj)

        # Determine if Format B should be used
        format_b = isinstance(self.format_obj, Mk2Format) and self.format_obj.base_address

        exporter.export_to_file(
            filepath=filepath,
            mask_array=mask,
            mode=mode,
            format_b=format_b,
            base_address=self.format_obj.base_address if format_b else None,
            yaml_file=self.filepath.name,
            include_metadata=True
        )

    def set_mode(self, mode: MaskMode):
        """Set mask mode."""
        self.mode = mode
        # Mode affects which mask array is used but display remains the same

    def has_unsaved_changes(self) -> bool:
        """Check if there are unsaved changes."""
        return self.unsaved_changes

    def save_changes(self):
        """Save changes (placeholder for actual save logic)."""
        self.unsaved_changes = False

    def get_event_count(self) -> int:
        """Get total event count."""
        count = 0
        for subtab in self.subtabs.values():
            count += len(subtab.events)
        return count

    def get_selection_count(self) -> int:
        """Get selected event count."""
        count = 0
        for subtab in self.subtabs.values():
            for row in range(subtab.table.rowCount()):
                item = subtab.table.item(row, 0)
                if item and item.data(Qt.UserRole) == Qt.Checked:
                    count += 1
        return count

    def select_all(self):
        """Select all events in current subtab."""
        current_subtab = self.subtab_widget.currentWidget()
        if current_subtab:
            changes = []
            for row in range(current_subtab.table.rowCount()):
                item = current_subtab.table.item(row, 0)
                if item and item.flags() & Qt.ItemIsEnabled:
                    old_state = item.data(Qt.UserRole)
                    if old_state != Qt.Checked:
                        changes.append((row, old_state, Qt.Checked))

            if changes:
                command = BulkToggleCommand(current_subtab.table, changes, "Select all")
                current_subtab.undo_stack.push(command)
                self.selection_changed.emit()

    def select_none(self):
        """Deselect all events in current subtab."""
        current_subtab = self.subtab_widget.currentWidget()
        if current_subtab:
            changes = []
            for row in range(current_subtab.table.rowCount()):
                item = current_subtab.table.item(row, 0)
                if item and item.flags() & Qt.ItemIsEnabled:
                    old_state = item.data(Qt.UserRole)
                    if old_state != Qt.Unchecked:
                        changes.append((row, old_state, Qt.Unchecked))

            if changes:
                command = BulkToggleCommand(current_subtab.table, changes, "Deselect all")
                current_subtab.undo_stack.push(command)
                self.selection_changed.emit()

    def select_by_info(self, pattern: str) -> int:
        """Select events where info contains pattern."""
        current_subtab = self.subtab_widget.currentWidget()
        if not current_subtab:
            return 0

        count = 0
        changes = []
        pattern_lower = pattern.lower()

        for row in range(current_subtab.table.rowCount()):
            info_item = current_subtab.table.item(row, 5)  # Info column
            state_item = current_subtab.table.item(row, 0)

            if info_item and state_item and (state_item.flags() & Qt.ItemIsEnabled):
                if pattern_lower in info_item.text().lower():
                    old_state = state_item.data(Qt.UserRole)
                    if old_state != Qt.Checked:
                        changes.append((row, old_state, Qt.Checked))
                        count += 1

        if changes:
            command = BulkToggleCommand(current_subtab.table, changes, f"Select {pattern}")
            current_subtab.undo_stack.push(command)
            self.selection_changed.emit()

        return count

    def unselect_by_info(self, pattern: str) -> int:
        """Unselect events where info contains pattern."""
        current_subtab = self.subtab_widget.currentWidget()
        if not current_subtab:
            return 0

        count = 0
        changes = []
        pattern_lower = pattern.lower()

        for row in range(current_subtab.table.rowCount()):
            info_item = current_subtab.table.item(row, 5)
            state_item = current_subtab.table.item(row, 0)

            if info_item and state_item and (state_item.flags() & Qt.ItemIsEnabled):
                if pattern_lower in info_item.text().lower():
                    old_state = state_item.data(Qt.UserRole)
                    if old_state == Qt.Checked:
                        changes.append((row, old_state, Qt.Unchecked))
                        count += 1

        if changes:
            command = BulkToggleCommand(current_subtab.table, changes, f"Unselect {pattern}")
            current_subtab.undo_stack.push(command)
            self.selection_changed.emit()

        return count

    def select_by_info_regex(self, regex_pattern: str) -> int:
        """Select events where info matches regex."""
        current_subtab = self.subtab_widget.currentWidget()
        if not current_subtab:
            return 0

        try:
            pattern = re.compile(regex_pattern, re.IGNORECASE)
        except re.error:
            return 0

        count = 0
        changes = []

        for row in range(current_subtab.table.rowCount()):
            info_item = current_subtab.table.item(row, 5)
            state_item = current_subtab.table.item(row, 0)

            if info_item and state_item and (state_item.flags() & Qt.ItemIsEnabled):
                if pattern.search(info_item.text()):
                    old_state = state_item.data(Qt.UserRole)
                    if old_state != Qt.Checked:
                        changes.append((row, old_state, Qt.Checked))
                        count += 1

        if changes:
            command = BulkToggleCommand(current_subtab.table, changes, "Select syncs")
            current_subtab.undo_stack.push(command)
            self.selection_changed.emit()

        return count

    def unselect_by_info_regex(self, regex_pattern: str) -> int:
        """Unselect events where info matches regex."""
        current_subtab = self.subtab_widget.currentWidget()
        if not current_subtab:
            return 0

        try:
            pattern = re.compile(regex_pattern, re.IGNORECASE)
        except re.error:
            return 0

        count = 0
        changes = []

        for row in range(current_subtab.table.rowCount()):
            info_item = current_subtab.table.item(row, 5)
            state_item = current_subtab.table.item(row, 0)

            if info_item and state_item and (state_item.flags() & Qt.ItemIsEnabled):
                if pattern.search(info_item.text()):
                    old_state = state_item.data(Qt.UserRole)
                    if old_state == Qt.Checked:
                        changes.append((row, old_state, Qt.Unchecked))
                        count += 1

        if changes:
            command = BulkToggleCommand(current_subtab.table, changes, "Unselect syncs")
            current_subtab.undo_stack.push(command)
            self.selection_changed.emit()

        return count

    def can_undo(self) -> bool:
        """Check if undo is available."""
        current_subtab = self.subtab_widget.currentWidget()
        return current_subtab and current_subtab.undo_stack.canUndo()

    def can_redo(self) -> bool:
        """Check if redo is available."""
        current_subtab = self.subtab_widget.currentWidget()
        return current_subtab and current_subtab.undo_stack.canRedo()

    def undo(self):
        """Undo last action in current subtab."""
        current_subtab = self.subtab_widget.currentWidget()
        if current_subtab:
            current_subtab.undo_stack.undo()
            self.selection_changed.emit()

    def redo(self):
        """Redo last undone action in current subtab."""
        current_subtab = self.subtab_widget.currentWidget()
        if current_subtab:
            current_subtab.undo_stack.redo()
            self.selection_changed.emit()

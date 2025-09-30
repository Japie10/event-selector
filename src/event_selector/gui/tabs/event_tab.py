"""Event tab widget for displaying and editing events.

This module implements the tab widget that displays events from a YAML file
with tri-state checkboxes, filtering, and undo/redo support.
"""

from pathlib import Path
from typing import Optional, Dict, List, Any, TypeAlias
import re

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QTableWidget, 
    QTableWidgetItem, QHeaderView, QLabel, QLineEdit, QPushButton,
    QCheckBox, QUndoStack, QUndoCommand, QAbstractItemView,
    QStyledItemDelegate, QStyleOptionButton, QStyle, QApplication,
    QStyleOptionViewItem, QTabBar, QStyleOptionTab
)

from PyQt5.QtCore import Qt, pyqtSignal, QRect, QModelIndex, QEvent, QPoint
from PyQt5.QtGui import QPainter

import numpy as np

from event_selector.core.models import (
    FormatType, MaskMode, Mk1Format, Mk2Format, 
    EventMk1, EventMk2, MaskData
)
from event_selector.utils.logging import get_logger

logger = get_logger(__name__)

FormatObject: TypeAlias = Mk1Format | Mk2Format


class editorEven(QCheckBox):
    """Tri-state checkbox for header that reflects and controls all rows."""
    
    state_changed = pyqtSignal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        logger.trace("Start")
        self.setTristate(True)
        self.stateChanged.connect(self.on_state_changed)

    def on_state_changed(self, state):
        """Emit custom signal when state changes."""
        logger.trace("Start")
        self.state_changed.emit(state)
    
    def update_from_rows(self, checked_count: int, total_count: int):
        """Update header checkbox based on row selections."""
        logger.trace("Start")
        if total_count == 0:
            self.setCheckState(Qt.Unchecked)
        elif checked_count == 0:
            self.setCheckState(Qt.Unchecked)
        elif checked_count == total_count:
            self.setCheckState(Qt.Checked)
        else:
            self.setCheckState(Qt.PartiallyChecked)

class CheckBoxDelegate(QStyledItemDelegate):
    """Delegate for rendering checkboxes in the first column."""

    def __init__(self, parent=None):
        super().__init__(parent)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        """Paint checkbox in cell."""
        if index.column() == 0:
            # Get the checkbox state from the item
            state = index.data(Qt.UserRole)
            if state is None:
                state = Qt.Unchecked

            # Create checkbox style option
            checkbox_option = QStyleOptionButton()
            checkbox_option.rect = self.get_checkbox_rect(option.rect)

            # Set the checkbox state
            if state == Qt.Checked:
                checkbox_option.state = QStyle.State_On | QStyle.State_Enabled
            else:
                checkbox_option.state = QStyle.State_Off | QStyle.State_Enabled

            # Add hover effect when row is selected or hovered
            if option.state & QStyle.State_Selected:
                checkbox_option.state |= QStyle.State_MouseOver

            # Check if item is enabled
            if not (index.flags() & Qt.ItemIsEnabled):
                checkbox_option.state &= ~QStyle.State_Enabled

            # Draw the checkbox
            QApplication.style().drawControl(QStyle.CE_CheckBox, checkbox_option, painter)
        else:
            super().paint(painter, option, index)

    def get_checkbox_rect(self, cell_rect: QRect) -> QRect:
        """Calculate checkbox position (centered in cell)."""
        checkbox_size = QApplication.style().pixelMetric(QStyle.PM_IndicatorWidth)
        x = cell_rect.center().x() - checkbox_size // 2
        y = cell_rect.center().y() - checkbox_size // 2
        return QRect(x, y, checkbox_size, checkbox_size)

class ToggleCommand(QUndoCommand):
    """Undo command for single checkbox toggle."""

    def __init__(self, table, row, old_state, new_state, parent_widget=None):
        super().__init__(f"Toggle row {row}")
        logger.trace("Start")
        self.table = table
        self.row = row
        self.old_state = old_state
        self.new_state = new_state
        self.parent_widget = parent_widget  # Add this line

    def redo(self):
        """Apply the toggle."""
        logger.trace("Start")
        item = self.table.item(self.row, 0)
        if item:
            item.setData(Qt.UserRole, self.new_state)
            # Force repaint
            self.table.viewport().update()
            # Update header if parent widget available
            if self.parent_widget and hasattr(self.parent_widget, '_update_header_checkbox'):
                self.parent_widget._update_header_checkbox()

    def undo(self):
        """Revert the toggle."""
        logger.trace("Start")
        item = self.table.item(self.row, 0)
        if item:
            item.setData(Qt.UserRole, self.old_state)
            # Force repaint
            self.table.viewport().update()
            # Update header if parent widget available
            if self.parent_widget and hasattr(self.parent_widget, '_update_header_checkbox'):
                self.parent_widget._update_header_checkbox()

class BulkToggleCommand(QUndoCommand):
    """Undo command for bulk toggle operations."""

    def __init__(self, table, changes, description="Bulk toggle", parent_widget=None):
        super().__init__(description)
        logger.trace("Start")
        self.table = table
        self.changes = changes
        self.parent_widget = parent_widget

    def redo(self):
        """Apply all toggles."""
        logger.trace("Start")
        for row, _, new_state in self.changes:
            item = self.table.item(row, 0)
            if item:
                item.setData(Qt.UserRole, new_state)
        # Force repaint
        self.table.viewport().update()
        # Update header if parent widget available
        if self.parent_widget and hasattr(self.parent_widget, '_update_header_checkbox'):
            self.parent_widget._update_header_checkbox()

    def undo(self):
        """Revert all toggles."""
        logger.trace("Start")
        for row, old_state, _ in self.changes:
            item = self.table.item(row, 0)
            if item:
                item.setData(Qt.UserRole, old_state)
        # Force repaint
        self.table.viewport().update()
        # Update header if parent widget available
        if self.parent_widget and hasattr(self.parent_widget, '_update_header_checkbox'):
            self.parent_widget._update_header_checkbox()

class EventSubTab(QWidget):
    """Widget for a single subtab showing events for specific IDs."""

    selection_changed = pyqtSignal()

    def __init__(self, name: str, events: Dict, format_type: FormatType, parent=None):
        super().__init__(parent)
        logger.trace("Start")
        self.name = name
        self.events = events
        self.format_type = format_type
        self.undo_stack = QUndoStack(self)
        self.undo_stack.setUndoLimit(200)  # Set maximum undo levels per spec
        
        # emit selection_changed when undo stack changes
        self.undo_stack.canUndoChanged.connect(lambda: self.selection_changed.emit())
        self.undo_stack.canRedoChanged.connect(lambda: self.selection_changed.emit())        

        self.header_checkbox = None
        self._setup_ui()
        self._populate_table()

    def _setup_ui(self):
        """Setup subtab UI with row click handling."""
        logger.trace("Start")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Filter bar
        filter_layout = QHBoxLayout()
        filter_label = QLabel("Filter:")
        filter_label.setStyleSheet("font-weight: bold;")
        filter_layout.addWidget(filter_label)

        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Type to filter events...")
        self.filter_input.setClearButtonEnabled(True)
        self.filter_input.textChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.filter_input)

        self.clear_filter_button = QPushButton("Clear Filter")
        self.clear_filter_button.setEnabled(False)
        self.clear_filter_button.clicked.connect(self._clear_filter)
        filter_layout.addWidget(self.clear_filter_button)
        
        # Enable/disable clear button based on filter text
        self.filter_input.textChanged.connect(
            lambda text: self.clear_filter_button.setEnabled(bool(text))
        )

        layout.addLayout(filter_layout)

        # Event table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "State", "ID/Addr", "Bit", "Event Source", "Description", "Info"
        ])

        # Hide row numbers (vertical header)
        self.table.verticalHeader().setVisible(False)
        
        # Set default row height (reduced from default ~30 to 22 pixels)
        self.table.verticalHeader().setDefaultSectionSize(22)
        
        # Set minimum row height to prevent them from being too small
        self.table.verticalHeader().setMinimumSectionSize(20)
    
        # Make row height fixed (prevents resizing)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)

        # Enable mouse tracking for hover effects
        self.table.setMouseTracking(True)

        # Install event filter to capture Space key
        self.table.installEventFilter(self)

        # Create tri-state header checkbox
        self.header_checkbox = editorEven()
        self.header_checkbox.state_changed.connect(self._on_header_state_changed)
        
        # Configure header
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header_item = QTableWidgetItem()
        self.table.setHorizontalHeaderItem(0, header_item)
        
        # Position header checkbox
        self.header_checkbox.setParent(header.viewport())
        checkbox_x = (40 - self.header_checkbox.sizeHint().width()) // 2 - 1
        self.header_checkbox.move(checkbox_x, 3)

        # Set checkbox delegate for painting only
        self.checkbox_delegate = CheckBoxDelegate()
        self.table.setItemDelegateForColumn(0, self.checkbox_delegate)

        # Configure table behavior
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setGridStyle(Qt.SolidLine)
        
        # Style for better visual feedback
        self.table.setStyleSheet("""
            QTableWidget {
                gridline-color: #d0d0d0;
            }
            QTableWidget::item {
                padding: 0px;
                margin: 0px;
            }
            QTableWidget::item:selected {
                background-color: rgba(51, 153, 255, 40);
            }
            QTableWidget::item:hover {
                background-color: rgba(0, 0, 0, 10);
            }
        """)

        # Set column widths
        header.resizeSection(0, 40)   # State column
        header.resizeSection(1, 80)  # ID/Addr
        header.resizeSection(2, 50)   # Bit
        header.resizeSection(3, 250)  # Event Source
        header.resizeSection(4, 700)  # Description
        header.setStretchLastSection(True)  # Info stretches

        # Add tooltips to header
        self.table.horizontalHeaderItem(0).setToolTip("Click rows to toggle selection")
        self.table.horizontalHeaderItem(1).setToolTip("Event ID or Address")
        self.table.horizontalHeaderItem(2).setToolTip("Bit number")

        # Connect row click handler - clicking ANYWHERE on the row toggles checkbox
        self.table.itemClicked.connect(self._on_row_clicked)
        
        # Connect selection change for visual feedback
        self.table.itemSelectionChanged.connect(self._on_selection_changed)

        layout.addWidget(self.table)

    def _populate_table(self):
        """Populate table with events."""
        logger.trace("Start")
        
        # Calculate number of rows based on format
        if self.format_type == FormatType.MK1:
            num_rows = 128
        else:  # MK2
            num_rows = 28

        self.table.setRowCount(num_rows)

        # Temporarily disable signals during population
        self.table.blockSignals(True)

        # Fill table with events
        row = 0
        for key, event in sorted(self.events.items()):
            if row >= num_rows:
                break
                
            # For MK2, skip bits 28-31
            if self.format_type == FormatType.MK2 and hasattr(event, 'bit'):
                if event.bit > 27:
                    logger.warning(f"Skipping MK2 event with bit {event.bit} > 27")
                    continue

            # State checkbox (column 0)
            state_item = QTableWidgetItem()
            state_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            state_item.setData(Qt.UserRole, Qt.Unchecked)
            state_item.setText("")
            self.table.setItem(row, 0, state_item)

            # ID/Address (column 1)
            if self.format_type == FormatType.MK1:
                addr_item = QTableWidgetItem(event.address)
                addr_item.setToolTip(f"Address: {event.address}")
                self.table.setItem(row, 1, addr_item)
                
                bit_item = QTableWidgetItem(str(event.bit))
                self.table.setItem(row, 2, bit_item)
            else:  # EventMk2
                addr_text = f"0x{event.id:01X}{event.bit:02X}"
                addr_item = QTableWidgetItem(addr_text)
                addr_item.setToolTip(f"ID: 0x{event.id:01X}, Bit: {event.bit}")
                self.table.setItem(row, 1, addr_item)
                
                bit_item = QTableWidgetItem(str(event.bit))
                self.table.setItem(row, 2, bit_item)

            # Event source (column 3)
            source_item = QTableWidgetItem(event.event_source)
            if len(event.event_source) > 20:
                source_item.setToolTip(event.event_source)
            self.table.setItem(row, 3, source_item)

            # Description (column 4)
            desc_item = QTableWidgetItem(event.description)
            if len(event.description) > 30:
                desc_item.setToolTip(event.description)
            self.table.setItem(row, 4, desc_item)

            # Info (column 5)
            info_item = QTableWidgetItem(event.info)
            if len(event.info) > 30:
                info_item.setToolTip(event.info)
            self.table.setItem(row, 5, info_item)

            row += 1

        # Fill remaining rows with empty disabled entries
        while row < num_rows:
            state_item = QTableWidgetItem()
            state_item.setData(Qt.UserRole, Qt.Unchecked)
            state_item.setFlags(Qt.NoItemFlags)
            state_item.setText("")
            self.table.setItem(row, 0, state_item)

            for col in range(1, 6):
                item = QTableWidgetItem("")
                item.setFlags(Qt.NoItemFlags)
                self.table.setItem(row, col, item)

            row += 1

        # Re-enable signals
        self.table.blockSignals(False)

        # Update header checkbox state
        self._update_header_checkbox()

    def _on_header_state_changed(self, state):
        """Handle header checkbox state change."""
        logger.trace("Start")
        
        if state == Qt.PartiallyChecked:
            return
        
        # Collect changes for undo
        changes = []
        new_state = Qt.Checked if state == Qt.Checked else Qt.Unchecked
        
        for row in range(self.table.rowCount()):
            if self.table.isRowHidden(row):
                continue
            
            item = self.table.item(row, 0)
            if item and (item.flags() & Qt.ItemIsEnabled):
                old_state = item.data(Qt.UserRole)
                if old_state != new_state:
                    changes.append((row, old_state, new_state))
        
        if changes:
            description = "Select all" if new_state == Qt.Checked else "Deselect all"
            command = BulkToggleCommand(self.table, changes, description, self)
            self.undo_stack.push(command)
            self._update_header_checkbox()
            self.selection_changed.emit()

    def _update_header_checkbox(self):
        """Update header checkbox based on row states."""
        logger.trace("Start")
        if not self.header_checkbox:
            return

        checked_count = 0
        total_count = 0

        for row in range(self.table.rowCount()):
            if self.table.isRowHidden(row):
                continue

            item = self.table.item(row, 0)
            if item and (item.flags() & Qt.ItemIsEnabled):
                total_count += 1
                state = item.data(Qt.UserRole)
                if state == Qt.Checked:
                    checked_count += 1

        self.header_checkbox.blockSignals(True)
        self.header_checkbox.update_from_rows(checked_count, total_count)
        self.header_checkbox.blockSignals(False)

    def _apply_filter(self, text: str):
        """Apply filter to table rows."""
        logger.trace("Start")
        if not text:
            # Show all rows
            for row in range(self.table.rowCount()):
                self.table.setRowHidden(row, False)
        else:
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

        # Update header checkbox after filtering
        self._update_header_checkbox()

    def _on_row_clicked(self, item):
        """Handle clicking anywhere on a row to toggle its checkbox."""
        logger.trace("Start")
        
        # Get the checkbox item for this row
        row = item.row()
        checkbox_item = self.table.item(row, 0)
        
        # Check if row is enabled
        if not checkbox_item or not (checkbox_item.flags() & Qt.ItemIsEnabled):
            return
        
        # Get current state
        old_state = checkbox_item.data(Qt.UserRole)
        
        # Toggle state
        new_state = Qt.Checked if old_state != Qt.Checked else Qt.Unchecked
        
        # Create undo command
        command = ToggleCommand(self.table, row, old_state, new_state, self)
        self.undo_stack.push(command)
        
        # Update header checkbox
        self._update_header_checkbox()
        
        # Emit selection changed
        self.selection_changed.emit()

    def _on_selection_changed(self):
        """Keep visual selection in sync with checkbox states."""
        # This prevents selection from getting out of sync
        pass

    def _clear_filter(self):
        """Clear filter input."""
        logger.trace("Start")
        self.filter_input.clear()

    def get_mask_array(self) -> np.ndarray:
        """Get mask array from current selections."""
        logger.trace("Start")
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
        logger.trace("Start")
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

        # Update header after setting mask
        self._update_header_checkbox()

    def eventFilter(self, obj, event):
        """Filter events from the table widget to handle Space key."""
        if obj == self.table and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Space:
                logger.trace("Space key pressed")
                
                # Get the current row (where keyboard focus is)
                current_row = self.table.currentRow()
                logger.trace(f"Current row: {current_row}")
                
                if current_row >= 0:
                    checkbox_item = self.table.item(current_row, 0)
                    
                    # Check if row is enabled
                    if checkbox_item and (checkbox_item.flags() & Qt.ItemIsEnabled):
                        # Get current state and toggle it
                        old_state = checkbox_item.data(Qt.UserRole)
                        new_state = Qt.Checked if old_state != Qt.Checked else Qt.Unchecked
                        
                        logger.trace(f"Toggling row {current_row}: {old_state} -> {new_state}")
                        
                        # Create undo command for single row
                        command = ToggleCommand(self.table, current_row, old_state, new_state, self)
                        self.undo_stack.push(command)
                        
                        # Update header checkbox
                        self._update_header_checkbox()
                        
                        # Emit selection changed
                        self.selection_changed.emit()
                
                # Always consume Space key events to prevent default behavior
                return True
        
        # Pass all other events to the base class
        return super().eventFilter(obj, event)

class EventTab(QWidget):
    """Main tab widget for a YAML file."""

    selection_changed = pyqtSignal()
    events_modified = pyqtSignal()

    def __init__(self, format_obj: FormatObject, yaml_file: Path,parent=None):
        super().__init__(parent)
        self.filepath = yaml_file
        self.format_obj = format_obj
        self.format_type = format_obj.format_type

        self.subtabs = {}
        self.mode = MaskMode.MASK
        self.unsaved_changes = False
        self._setup_ui()
        self._create_subtabs()
        logger.trace("Connect subtabs")

        # Connect selection changed signals
        for subtab in self.subtabs.values():
            subtab.selection_changed.connect(self._on_selection_changed)
        
        self.subtab_widget.currentChanged.connect(lambda: self.selection_changed.emit())

        # Initialize separate storage for mask and trigger modes
        size = 12 if self.format_type == FormatType.MK1 else 16
        self.mask_array = np.zeros(size, dtype=np.uint32)  # Event-Mask storage
        self.trigger_array = np.zeros(size, dtype=np.uint32)  # Capture-Mask storage

    def _setup_ui(self):
        """Setup main tab UI."""
        logger.trace("Start")
        layout = QVBoxLayout(self)

        # Sources banner (if applicable)
        if hasattr(self.format_obj, 'sources') and self.format_obj.sources:
            sources_label = QLabel(f"These events are used for: {', '.join(e.name for e in self.format_obj.sources)}")
            sources_label.setStyleSheet("QLabel { background-color: #f0f0f0; padding: 5px; }")
            layout.addWidget(sources_label)

        # Subtab widget
        self.subtab_widget = QTabWidget()
        self.subtab_widget.tabBar().setElideMode(Qt.ElideRight)
        self.subtab_widget.tabBar().setExpanding(False)
        layout.addWidget(self.subtab_widget)

    def _create_subtabs(self):
        """Create subtabs based on format type."""
        logger.trace("Start")
        if self.format_type == FormatType.MK1:
            # Create three subtabs for mk1
            subtab_names = ["Data", "Network", "Application"]
            for i, name in enumerate(subtab_names):
                # Filter events for this subtab (4 IDs per subtab)
                subtab_events = {}
                for key, event in self.format_obj.events.items():
                    if self.format_type == FormatType.MK1:
                        # Determine which subtab based on ID
                        event_id = int(event.address[2:], 16) >> 5  # Extract ID from address
                        if i * 4 <= event_id < (i + 1) * 4:
                            subtab_events[key] = event
                
                subtab = EventSubTab(name, subtab_events, self.format_type, self)
                self.subtabs[name] = subtab
                self.subtab_widget.addTab(subtab, name)
                self.subtab_widget.setTabToolTip(i, name)
        else:  # MK2
            # Create one subtab per ID
            for id_num in range(16):
                # Filter events for this ID
                subtab_events = {}
                for key, event in self.format_obj.events.items():
                    if isinstance(event, EventMk2) and event.id == id_num:
                        subtab_events[key] = event

                # Determine subtab name
                if hasattr(self.format_obj, 'id_names') and id_num in self.format_obj.id_names:
                    name = f"0x{id_num:01X}: {self.format_obj.id_names[id_num]})"
                else:
                    name = f"ID 0x{id_num:01X}"

                subtab = EventSubTab(name, subtab_events, self.format_type, self)
                self.subtabs[name] = subtab
                self.subtab_widget.addTab(subtab, name)
                self.subtab_widget.setTabToolTip(id_num, name)

    def _on_selection_changed(self):
        """Handle selection change in any subtab."""
        logger.trace("Start")
        self.unsaved_changes = True
        self.selection_changed.emit()


    def get_current_mask(self) -> np.ndarray:
        """Get current mask array."""
        if self.format_type == FormatType.MK1:
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
        """Set the mask mode (Event-Mask or Capture-Mask)."""
        logger.trace("Start")
        
        # Save current checkbox states to the current mode's array
        if self.mode == MaskMode.MASK:
            self.mask_array = self.get_current_mask()
        else:
            self.trigger_array = self.get_current_mask()
        
        # Switch mode
        self.mode = mode
        
        # Load checkbox states from the target mode's array
        if self.mode == MaskMode.MASK:
            self._apply_mask_to_checkboxes(self.mask_array)
        else:
            self._apply_mask_to_checkboxes(self.trigger_array)

    def _apply_mask_to_checkboxes(self, mask: np.ndarray):
        """Apply mask array to all subtab checkboxes."""
        if isinstance(self.format_obj, Mk1Format):
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

    def has_unsaved_changes(self) -> bool:
        """Check if there are unsaved changes."""
        return self.unsaved_changes

    def get_current_subtab(self) -> Optional[EventSubTab]:
        """Get the currently active subtab."""
        logger.trace("Start")
        return self.subtab_widget.currentWidget()

    def save_changes(self):
        """Save changes (placeholder for actual save logic)."""
        logger.trace("Start")
        self.unsaved_changes = False

    def get_event_count(self) -> int:
        """Get total event count."""
        logger.trace("Start")
        count = 0
        for subtab in self.subtabs.values():
            count += len(subtab.events)
        return count

    def get_selection_count(self) -> int:
        """Get selected event count."""
        logger.trace("Start")
        count = 0
        for subtab in self.subtabs.values():
            for row in range(subtab.table.rowCount()):
                item = subtab.table.item(row, 0)
                if item and item.data(Qt.UserRole) == Qt.Checked:
                    count += 1
        return count

    def select_all(self):
        """Select all events in current subtab."""
        logger.trace("Start")
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
                command = BulkToggleCommand(current_subtab.table, changes, "Select all", current_subtab)
                current_subtab.undo_stack.push(command)
                self.selection_changed.emit()

    def select_none(self):
        """Deselect all events in current subtab."""
        logger.trace("Start")
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
                command = BulkToggleCommand(current_subtab.table, changes, "Deselect all", current_subtab)
                current_subtab.undo_stack.push(command)
                self.selection_changed.emit()

    def select_by_info(self, pattern: str) -> int:
        """Select events where info contains pattern."""
        logger.trace("Start")
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
            command = BulkToggleCommand(current_subtab.table, changes, f"Select {pattern}", current_subtab)
            current_subtab.undo_stack.push(command)
            self.selection_changed.emit()

        return count

    def unselect_by_info(self, pattern: str) -> int:
        """Unselect events where info contains pattern."""
        logger.trace("Start")
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
            command = BulkToggleCommand(current_subtab.table, changes, f"Unselect {pattern}", current_subtab)
            current_subtab.undo_stack.push(command)
            self.selection_changed.emit()

        return count

    def select_by_info_regex(self, regex_pattern: str) -> int:
        """Select events where info matches regex."""
        logger.trace("Start")
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
            command = BulkToggleCommand(current_subtab.table, changes, "Select syncs", current_subtab)
            current_subtab.undo_stack.push(command)
            self.selection_changed.emit()

        return count

    def unselect_by_info_regex(self, regex_pattern: str) -> int:
        """Unselect events where info matches regex."""
        logger.trace("Start")
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
            command = BulkToggleCommand(current_subtab.table, changes, "Unselect syncs", current_subtab)
            current_subtab.undo_stack.push(command)
            self.selection_changed.emit()

        return count

    def can_undo(self) -> bool:
        """Check if undo is available."""
        logger.trace("Start")
        current_subtab = self.subtab_widget.currentWidget()
        return current_subtab and current_subtab.undo_stack.canUndo()

    def can_redo(self) -> bool:
        """Check if redo is available."""
        logger.trace("Start")
        current_subtab = self.subtab_widget.currentWidget()
        return current_subtab and current_subtab.undo_stack.canRedo()

    def undo(self):
        """Undo last action in current subtab."""
        logger.trace("Start")
        current_subtab = self.subtab_widget.currentWidget()
        if current_subtab:
            current_subtab.undo_stack.undo()
            self.selection_changed.emit()

    def redo(self):
        """Redo last undone action in current subtab."""
        logger.trace("Start")
        current_subtab = self.subtab_widget.currentWidget()
        if current_subtab:
            current_subtab.undo_stack.redo()
            self.selection_changed.emit()

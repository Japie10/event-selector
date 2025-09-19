"""Problems dock widget for displaying validation issues and log messages.

This module implements the dock widget that displays validation errors,
warnings, and log messages in a table format.
"""

from typing import Optional, List
from datetime import datetime
from collections import deque

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QLabel, QComboBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QColor, QBrush

from event_selector.core.models import (
    ValidationResult, ValidationLevel, ValidationCode, ValidationIssue
)


class ProblemsDock(QWidget):
    """Dock widget for displaying problems and validation issues."""

    problem_selected = pyqtSignal(str, int)  # file, line

    def __init__(self, parent=None):
        super().__init__(parent)
        self.max_entries = 200
        self.problems = deque(maxlen=self.max_entries)
        self._setup_ui()
        self._setup_timer()

    def _setup_ui(self):
        """Setup the problems dock UI."""
        layout = QVBoxLayout(self)

        # Control bar
        control_layout = QHBoxLayout()

        # Filter combo
        control_layout.addWidget(QLabel("Show:"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All", "Errors", "Warnings", "Info"])
        self.filter_combo.currentTextChanged.connect(self._apply_filter)
        control_layout.addWidget(self.filter_combo)

        control_layout.addStretch()

        # Clear button
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self._clear_problems)
        control_layout.addWidget(self.clear_button)

        layout.addLayout(control_layout)

        # Problems table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Level", "Code", "Location", "Message", "Time"
        ])

        # Configure table
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSortingEnabled(True)

        # Set column widths
        header = self.table.horizontalHeader()
        header.resizeSection(0, 70)   # Level
        header.resizeSection(1, 150)  # Code
        header.resizeSection(2, 200)  # Location
        header.setSectionResizeMode(3, QHeaderView.Stretch)  # Message
        header.resizeSection(4, 100)  # Time

        # Connect signals
        self.table.itemDoubleClicked.connect(self._on_item_double_clicked)

        layout.addWidget(self.table)

        # Status bar
        self.status_label = QLabel("0 problems")
        layout.addWidget(self.status_label)

    def _setup_timer(self):
        """Setup timer for log monitoring."""
        self.log_timer = QTimer()
        self.log_timer.timeout.connect(self._check_logs)
        self.log_timer.start(1000)  # Check every second

    def add_validation_result(self, result: ValidationResult, source: str):
        """Add validation result to problems list.

        Args:
            result: ValidationResult object
            source: Source file or identifier
        """
        for issue in result.issues:
            self._add_problem(
                level=issue.level,
                code=issue.code,
                location=issue.location or source,
                message=issue.message,
                details=issue.details
            )

        self._update_display()

    def add_error(self, message: str, location: Optional[str] = None):
        """Add an error message.

        Args:
            message: Error message
            location: Optional location
        """
        self._add_problem(
            level=ValidationLevel.ERROR,
            code=ValidationCode.KEY_FORMAT,
            location=location or "unknown",
            message=message
        )
        self._update_display()

    def add_warning(self, message: str, location: Optional[str] = None):
        """Add a warning message.

        Args:
            message: Warning message
            location: Optional location
        """
        self._add_problem(
            level=ValidationLevel.WARNING,
            code=ValidationCode.KEY_FORMAT,
            location=location or "unknown",
            message=message
        )
        self._update_display()

    def add_info(self, message: str, location: Optional[str] = None):
        """Add an info message.

        Args:
            message: Info message
            location: Optional location
        """
        self._add_problem(
            level=ValidationLevel.INFO,
            code=ValidationCode.KEY_FORMAT,
            location=location or "unknown",
            message=message
        )
        self._update_display()

    def _add_problem(self, level: ValidationLevel, code: ValidationCode,
                     location: str, message: str, details: Optional[dict] = None):
        """Add a problem to the internal list.

        Args:
            level: Problem severity level
            code: Problem code
            location: Problem location
            message: Problem message
            details: Optional additional details
        """
        problem = {
            'level': level,
            'code': code,
            'location': location,
            'message': message,
            'details': details,
            'time': datetime.now()
        }
        self.problems.append(problem)

    def _update_display(self):
        """Update the table display with current problems."""
        # Store current filter
        current_filter = self.filter_combo.currentText()

        # Clear table
        self.table.setRowCount(0)

        # Add filtered problems
        visible_count = 0
        for problem in self.problems:
            # Apply filter
            if current_filter != "All":
                if current_filter == "Errors" and problem['level'] != ValidationLevel.ERROR:
                    continue
                elif current_filter == "Warnings" and problem['level'] != ValidationLevel.WARNING:
                    continue
                elif current_filter == "Info" and problem['level'] != ValidationLevel.INFO:
                    continue

            # Add row
            row = self.table.rowCount()
            self.table.insertRow(row)
            visible_count += 1

            # Level column with color
            level_item = QTableWidgetItem(problem['level'].value)
            if problem['level'] == ValidationLevel.ERROR:
                level_item.setForeground(QBrush(QColor(255, 0, 0)))  # Red
            elif problem['level'] == ValidationLevel.WARNING:
                level_item.setForeground(QBrush(QColor(255, 165, 0)))  # Orange
            else:
                level_item.setForeground(QBrush(QColor(0, 100, 200)))  # Blue
            self.table.setItem(row, 0, level_item)

            # Code column
            self.table.setItem(row, 1, QTableWidgetItem(problem['code'].value))

            # Location column
            self.table.setItem(row, 2, QTableWidgetItem(problem['location']))

            # Message column
            self.table.setItem(row, 3, QTableWidgetItem(problem['message']))

            # Time column
            time_str = problem['time'].strftime("%H:%M:%S")
            self.table.setItem(row, 4, QTableWidgetItem(time_str))

            # Store details in user data if available
            if problem['details']:
                self.table.item(row, 3).setData(Qt.UserRole, problem['details'])

        # Update status
        self._update_status(visible_count)

    def _update_status(self, visible_count: int):
        """Update status label.

        Args:
            visible_count: Number of visible problems
        """
        # Count by level
        error_count = sum(1 for p in self.problems if p['level'] == ValidationLevel.ERROR)
        warning_count = sum(1 for p in self.problems if p['level'] == ValidationLevel.WARNING)
        info_count = sum(1 for p in self.problems if p['level'] == ValidationLevel.INFO)

        # Format status text
        parts = []
        if error_count > 0:
            parts.append(f"{error_count} error{'s' if error_count != 1 else ''}")
        if warning_count > 0:
            parts.append(f"{warning_count} warning{'s' if warning_count != 1 else ''}")
        if info_count > 0:
            parts.append(f"{info_count} info")

        if parts:
            status_text = ", ".join(parts)
            if visible_count < len(self.problems):
                status_text += f" ({visible_count} shown)"
        else:
            status_text = "No problems"

        self.status_label.setText(status_text)

    def _apply_filter(self, filter_text: str):
        """Apply filter to problems display.

        Args:
            filter_text: Filter selection
        """
        self._update_display()

    def _clear_problems(self):
        """Clear all problems."""
        self.problems.clear()
        self._update_display()

    def _on_item_double_clicked(self, item):
        """Handle double-click on problem item.

        Args:
            item: Clicked table item
        """
        row = item.row()
        location_item = self.table.item(row, 2)
        if location_item:
            location = location_item.text()
            # Try to extract file and line number
            if ':' in location:
                parts = location.rsplit(':', 1)
                if len(parts) == 2:
                    file_path = parts[0]
                    try:
                        line_num = int(parts[1])
                        self.problem_selected.emit(file_path, line_num)
                    except ValueError:
                        self.problem_selected.emit(location, 0)
                else:
                    self.problem_selected.emit(location, 0)
            else:
                self.problem_selected.emit(location, 0)

    def _check_logs(self):
        """Check for new log entries (placeholder for log monitoring)."""
        # This would integrate with the logging system to capture
        # WARN/ERROR level messages
        pass

    def get_problem_count(self) -> tuple[int, int, int]:
        """Get problem counts by level.

        Returns:
            Tuple of (error_count, warning_count, info_count)
        """
        error_count = sum(1 for p in self.problems if p['level'] == ValidationLevel.ERROR)
        warning_count = sum(1 for p in self.problems if p['level'] == ValidationLevel.WARNING)
        info_count = sum(1 for p in self.problems if p['level'] == ValidationLevel.INFO)
        return error_count, warning_count, info_count

    def has_errors(self) -> bool:
        """Check if there are any errors.

        Returns:
            True if there are errors
        """
        return any(p['level'] == ValidationLevel.ERROR for p in self.problems)

    def has_warnings(self) -> bool:
        """Check if there are any warnings.

        Returns:
            True if there are warnings
        """
        return any(p['level'] == ValidationLevel.WARNING for p in self.problems)
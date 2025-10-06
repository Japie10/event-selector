"""Problems dock widget for displaying validation errors and warnings."""

from typing import List, Optional, Dict
from datetime import datetime

from PyQt5.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QHBoxLayout, QLabel
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QBrush

from event_selector.domain.interfaces.format_strategy import (
    ValidationResult, ValidationIssue, ValidationLevel
)
from event_selector.infrastructure.logging import get_logger

logger = get_logger(__name__)


class ProblemsDock(QDockWidget):
    """Dock widget for displaying validation problems and log entries.
    
    Displays:
    - Validation errors and warnings from YAML parsing
    - Last 200 WARN/ERROR log entries
    - Clickable rows to jump to relevant locations
    
    Signals:
        problem_clicked: Emitted when user clicks a problem row
    """
    
    # Signals
    problem_clicked = pyqtSignal(str, str)  # (location, message)
    
    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize problems dock.
        
        Args:
            parent: Parent widget
        """
        super().__init__("Problems", parent)
        
        self._problems: List[Dict] = []
        self._max_log_entries = 200
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup dock UI."""
        # Create main widget
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Toolbar with controls
        toolbar_layout = QHBoxLayout()
        
        self.problem_count_label = QLabel("No problems")
        toolbar_layout.addWidget(self.problem_count_label)
        
        toolbar_layout.addStretch()
        
        self.clear_button = QPushButton("Clear All")
        self.clear_button.clicked.connect(self.clear_problems)
        toolbar_layout.addWidget(self.clear_button)
        
        layout.addLayout(toolbar_layout)
        
        # Problems table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([
            "Level", "Message", "Location", "Suggestion"
        ])
        
        # Configure table
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        
        # Set column widths
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Level
        header.setSectionResizeMode(1, QHeaderView.Stretch)           # Message
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Location
        header.setSectionResizeMode(3, QHeaderView.Stretch)           # Suggestion
        
        # Connect signals
        self.table.itemDoubleClicked.connect(self._on_item_double_clicked)
        
        layout.addWidget(self.table)
        
        self.setWidget(widget)
        
        # Dock properties
        self.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)
        self.setFeatures(
            QDockWidget.DockWidgetClosable | 
            QDockWidget.DockWidgetMovable
        )
    
    def add_validation_result(self, validation: ValidationResult) -> None:
        """Add validation issues to the problems list.
        
        Args:
            validation: ValidationResult containing issues
        """
        # Add errors
        for issue in validation.get_errors():
            self._add_problem(
                level="ERROR",
                message=issue.message,
                location=self._format_location(issue),
                suggestion=self._format_suggestion(issue),
                timestamp=datetime.now()
            )
        
        # Add warnings
        for issue in validation.get_warnings():
            self._add_problem(
                level="WARNING",
                message=issue.message,
                location=self._format_location(issue),
                suggestion=self._format_suggestion(issue),
                timestamp=datetime.now()
            )
        
        self._refresh_display()
        
        # Auto-show dock if there are errors
        if validation.has_errors:
            self.show()
            self.raise_()
    
    def add_log_entry(self, level: str, message: str, location: str = "") -> None:
        """Add a log entry to the problems list.
        
        Only WARN and ERROR level entries are added.
        
        Args:
            level: Log level (ERROR, WARNING, etc.)
            message: Log message
            location: Optional location information
        """
        if level.upper() not in ["ERROR", "WARNING", "WARN"]:
            return
        
        # Normalize WARN to WARNING
        if level.upper() == "WARN":
            level = "WARNING"
        
        self._add_problem(
            level=level.upper(),
            message=message,
            location=location,
            suggestion="",
            timestamp=datetime.now()
        )
        
        self._refresh_display()
    
    def _add_problem(
        self, 
        level: str, 
        message: str, 
        location: str,
        suggestion: str,
        timestamp: datetime
    ) -> None:
        """Add a problem to the internal list.
        
        Args:
            level: ERROR or WARNING
            message: Problem message
            location: Location where problem occurred
            suggestion: Suggestion for fixing
            timestamp: When problem occurred
        """
        problem = {
            'level': level,
            'message': message,
            'location': location,
            'suggestion': suggestion,
            'timestamp': timestamp
        }
        
        self._problems.append(problem)
        
        # Limit to max entries
        if len(self._problems) > self._max_log_entries:
            self._problems = self._problems[-self._max_log_entries:]
    
    def _refresh_display(self) -> None:
        """Refresh the table display."""
        # Clear table
        self.table.setRowCount(0)
        
        # Count problems by level
        error_count = sum(1 for p in self._problems if p['level'] == 'ERROR')
        warning_count = sum(1 for p in self._problems if p['level'] == 'WARNING')
        
        # Update count label
        if error_count > 0 or warning_count > 0:
            parts = []
            if error_count > 0:
                parts.append(f"{error_count} error{'s' if error_count != 1 else ''}")
            if warning_count > 0:
                parts.append(f"{warning_count} warning{'s' if warning_count != 1 else ''}")
            self.problem_count_label.setText(", ".join(parts))
        else:
            self.problem_count_label.setText("No problems")
        
        # Populate table (newest first)
        for idx, problem in enumerate(reversed(self._problems)):
            row = idx
            self.table.insertRow(row)
            
            # Level column
            level_item = QTableWidgetItem(problem['level'])
            if problem['level'] == 'ERROR':
                level_item.setForeground(QBrush(QColor(220, 50, 50)))
                level_item.setBackground(QBrush(QColor(255, 240, 240)))
            else:  # WARNING
                level_item.setForeground(QBrush(QColor(200, 130, 0)))
                level_item.setBackground(QBrush(QColor(255, 250, 230)))
            self.table.setItem(row, 0, level_item)
            
            # Message column
            message_item = QTableWidgetItem(problem['message'])
            self.table.setItem(row, 1, message_item)
            
            # Location column
            location_item = QTableWidgetItem(problem['location'])
            self.table.setItem(row, 2, location_item)
            
            # Suggestion column
            suggestion_item = QTableWidgetItem(problem['suggestion'])
            suggestion_item.setForeground(QBrush(QColor(100, 100, 100)))
            self.table.setItem(row, 3, suggestion_item)
        
        # Auto-resize rows to content
        self.table.resizeRowsToContents()
    
    def clear_problems(self) -> None:
        """Clear all problems from the list."""
        self._problems.clear()
        self._refresh_display()
        logger.debug("Cleared problems dock")
    
    def _on_item_double_clicked(self, item: QTableWidgetItem) -> None:
        """Handle double-click on table item.
        
        Args:
            item: Clicked table item
        """
        row = item.row()
        
        # Get location and message from this row
        location_item = self.table.item(row, 2)
        message_item = self.table.item(row, 1)
        
        if location_item and message_item:
            location = location_item.text()
            message = message_item.text()
            
            if location:
                self.problem_clicked.emit(location, message)
                logger.debug(f"Problem clicked: {location}")
    
    def _format_location(self, issue: ValidationIssue) -> str:
        """Format location information from validation issue.
        
        Args:
            issue: Validation issue
            
        Returns:
            Formatted location string
        """
        if not issue.details:
            return ""
        
        parts = []
        
        # Extract common location fields
        if 'file' in issue.details:
            parts.append(issue.details['file'])
        
        if 'line' in issue.details:
            parts.append(f"line {issue.details['line']}")
        
        if 'key' in issue.details:
            parts.append(f"key: {issue.details['key']}")
        
        if 'id' in issue.details:
            parts.append(f"ID: {issue.details['id']}")
        
        if 'subtab' in issue.details:
            parts.append(f"subtab: {issue.details['subtab']}")
        
        return ", ".join(parts) if parts else ""
    
    def _format_suggestion(self, issue: ValidationIssue) -> str:
        """Format suggestion from validation issue.
        
        Args:
            issue: Validation issue
            
        Returns:
            Formatted suggestion string
        """
        if not issue.details or 'suggestion' not in issue.details:
            return ""
        
        return issue.details['suggestion']
    
    def get_problem_count(self) -> tuple[int, int]:
        """Get count of errors and warnings.
        
        Returns:
            Tuple of (error_count, warning_count)
        """
        error_count = sum(1 for p in self._problems if p['level'] == 'ERROR')
        warning_count = sum(1 for p in self._problems if p['level'] == 'WARNING')
        return error_count, warning_count
    
    def has_errors(self) -> bool:
        """Check if there are any errors.
        
        Returns:
            True if errors exist
        """
        return any(p['level'] == 'ERROR' for p in self._problems)
    
    def has_warnings(self) -> bool:
        """Check if there are any warnings.
        
        Returns:
            True if warnings exist
        """
        return any(p['level'] == 'WARNING' for p in self._problems)


class ProblemsLogHandler:
    """Log handler that feeds entries to the problems dock.
    
    This can be used to connect Loguru to the problems dock.
    """
    
    def __init__(self, problems_dock: ProblemsDock):
        """Initialize log handler.
        
        Args:
            problems_dock: Problems dock to send entries to
        """
        self.problems_dock = problems_dock
    
    def __call__(self, message):
        """Handle log message.
        
        Args:
            message: Loguru log message
        """
        record = message.record
        level = record['level'].name
        text = record['message']
        
        # Extract location if available
        location = ""
        if 'file' in record:
            location = f"{record['file'].name}:{record['line']}"
        
        self.problems_dock.add_log_entry(level, text, location)

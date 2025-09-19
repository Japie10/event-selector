"""Filter widget for event table."""

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QLabel, QPushButton
from PyQt5.QtCore import pyqtSignal, QTimer

class FilterWidget(QWidget):
    """Real-time filter widget for event tables."""
    
    filter_changed = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.debounce_timer = QTimer()
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.timeout.connect(self._emit_filter)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        layout.addWidget(QLabel("Filter:"))
        
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Type to filter...")
        self.filter_input.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.filter_input)
        
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_filter)
        layout.addWidget(self.clear_button)
    
    def _on_text_changed(self):
        """Start debounce timer on text change."""
        self.debounce_timer.stop()
        self.debounce_timer.start(300)  # 300ms debounce
    
    def _emit_filter(self):
        """Emit filter signal after debounce."""
        self.filter_changed.emit(self.filter_input.text())
    
    def clear_filter(self):
        """Clear the filter."""
        self.filter_input.clear()
    
    def get_filter_text(self) -> str:
        """Get current filter text."""
        return self.filter_input.text()
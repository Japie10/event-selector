"""Dialog for associating mask files with YAML definitions."""

from pathlib import Path
from typing import Optional

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QDialogButtonBox, QComboBox
)
from PyQt5.QtCore import Qt

class FileAssociationDialog(QDialog):
    """Dialog for associating mask files with YAML definitions."""
    
    def __init__(self, mask_file: Path, yaml_suggestions: list = None, parent=None):
        super().__init__(parent)
        self.mask_file = mask_file
        self.yaml_suggestions = yaml_suggestions or []
        self.selected_yaml = None
        
        self.setWindowTitle("Associate YAML File")
        self.setModal(True)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Info
        info_label = QLabel(
            f"Select the YAML definition file for mask:\n{self.mask_file.name}"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Suggestions combo
        if self.yaml_suggestions:
            layout.addWidget(QLabel("Suggested files:"))
            self.suggestion_combo = QComboBox()
            for yaml_file in self.yaml_suggestions:
                self.suggestion_combo.addItem(str(yaml_file))
            layout.addWidget(self.suggestion_combo)
        
        # Manual selection
        manual_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Select YAML file...")
        manual_layout.addWidget(self.path_input)
        
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._browse_yaml)
        manual_layout.addWidget(browse_button)
        
        layout.addLayout(manual_layout)
        
        # Dialog buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def _browse_yaml(self):
        """Browse for YAML file."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Select YAML Definition",
            str(self.mask_file.parent),
            "YAML Files (*.yaml *.yml);;All Files (*.*)"
        )
        if filepath:
            self.path_input.setText(filepath)
    
    def _on_accept(self):
        """Handle accept action."""
        if self.path_input.text():
            self.selected_yaml = Path(self.path_input.text())
        elif hasattr(self, 'suggestion_combo') and self.suggestion_combo.currentText():
            self.selected_yaml = Path(self.suggestion_combo.currentText())
        
        if self.selected_yaml and self.selected_yaml.exists():
            self.accept()
        else:
            # Show error
            pass
    
    def get_yaml_path(self) -> Optional[Path]:
        """Get selected YAML path."""
        return self.selected_yaml
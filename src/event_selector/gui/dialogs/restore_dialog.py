"""Restore dialog for session restoration.

This module implements the dialog for restoring previous sessions.
"""

from pathlib import Path
from typing import Optional, List

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QPushButton, QDialogButtonBox, QCheckBox, QGroupBox
)
from PyQt5.QtCore import Qt, pyqtSignal

from event_selector.core.models import SessionState


class RestoreDialog(QDialog):
    """Dialog for restoring previous session."""

    files_selected = pyqtSignal(list)  # List of files to restore

    def __init__(self, session: SessionState, parent=None):
        super().__init__(parent)
        self.session = session
        self.setWindowTitle("Restore Previous Session")
        self.setModal(True)
        self.resize(500, 400)
        self._setup_ui()

    def _setup_ui(self):
        """Setup dialog UI."""
        layout = QVBoxLayout(self)

        # Info label
        info_label = QLabel(
            "Your previous session was found. "
            "Select which files you want to restore:"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Files group
        files_group = QGroupBox("Files from Previous Session")
        files_layout = QVBoxLayout(files_group)

        # File list
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.MultiSelection)

        # Add files from session
        for filepath in self.session.open_files:
            path = Path(filepath)
            if path.exists():
                self.file_list.addItem(str(filepath))
            else:
                # Show missing files in red
                item = self.file_list.addItem(f"{filepath} (missing)")
                item.setForeground(Qt.red)
                item.setFlags(item.flags() & ~Qt.ItemIsSelectable)

        # Select all by default
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item.flags() & Qt.ItemIsSelectable:
                item.setSelected(True)

        files_layout.addWidget(self.file_list)

        # Select all/none buttons
        button_layout = QHBoxLayout()

        select_all_button = QPushButton("Select All")
        select_all_button.clicked.connect(self._select_all)
        button_layout.addWidget(select_all_button)

        select_none_button = QPushButton("Select None")
        select_none_button.clicked.connect(self._select_none)
        button_layout.addWidget(select_none_button)

        button_layout.addStretch()
        files_layout.addLayout(button_layout)

        layout.addWidget(files_group)

        # Options
        self.restore_window_checkbox = QCheckBox("Restore window position and size")
        self.restore_window_checkbox.setChecked(True)
        layout.addWidget(self.restore_window_checkbox)

        self.restore_state_checkbox = QCheckBox("Restore mask/trigger states")
        self.restore_state_checkbox.setChecked(True)
        layout.addWidget(self.restore_state_checkbox)

        # Dialog buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _select_all(self):
        """Select all available files."""
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item.flags() & Qt.ItemIsSelectable:
                item.setSelected(True)

    def _select_none(self):
        """Deselect all files."""
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            item.setSelected(False)

    def _on_accept(self):
        """Handle accept action."""
        # Get selected files
        selected_files = []
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item.isSelected():
                filepath = item.text()
                # Remove "(missing)" suffix if present
                if filepath.endswith(" (missing)"):
                    continue
                selected_files.append(filepath)

        if selected_files:
            self.files_selected.emit(selected_files)

        self.accept()

    def should_restore_window(self) -> bool:
        """Check if window state should be restored.

        Returns:
            True if window state should be restored
        """
        return self.restore_window_checkbox.isChecked()

    def should_restore_states(self) -> bool:
        """Check if mask/trigger states should be restored.

        Returns:
            True if states should be restored
        """
        return self.restore_state_checkbox.isChecked()
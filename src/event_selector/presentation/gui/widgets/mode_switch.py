"""Mode switch widget for toggling between Event Mask and Capture Mask."""

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QRadioButton, QButtonGroup, QLabel
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QFont

from event_selector.shared.types import MaskMode


class ModeSwitchWidget(QWidget):
    """Widget for switching between Event Mask and Capture Mask modes."""

    # Signal emitted when mode changes (emits mode value string)
    mode_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        """Initialize mode switch widget."""
        super().__init__(parent)

        self.current_mode = MaskMode.EVENT  # Default to EVENT mode
        self._init_ui()

    def _init_ui(self):
        """Initialize UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        # Mode label
        label = QLabel("Mode:")
        label.setFont(QFont("", 10, QFont.Bold))
        layout.addWidget(label)

        # Radio button group
        self.button_group = QButtonGroup(self)

        # Event Mask radio (default)
        self.event_mask_radio = QRadioButton("Event Mask")
        self.event_mask_radio.setChecked(True)  # Default checked
        self.event_mask_radio.setToolTip("Edit Event Mask")
        self.button_group.addButton(self.event_mask_radio, 0)
        layout.addWidget(self.event_mask_radio)

        # Capture Mask radio
        self.capture_mask_radio = QRadioButton("Capture Mask")
        self.capture_mask_radio.setToolTip("Edit Capture Mask")
        self.button_group.addButton(self.capture_mask_radio, 1)
        layout.addWidget(self.capture_mask_radio)

        # Add stretch to push everything left
        layout.addStretch()

        # Connect signals
        self.button_group.buttonClicked.connect(self._on_mode_changed)

        # Style the widget
        self.setStyleSheet("""
            QWidget {
                background-color: #f5f5f5;
                border-bottom: 1px solid #ddd;
            }
            QRadioButton {
                padding: 5px 10px;
                font-size: 10pt;
            }
            QRadioButton:checked {
                font-weight: bold;
                color: #007ACC;
            }
        """)

    def _on_mode_changed(self, button):
        """Handle mode change.

        Args:
            button: The clicked button
        """
        if button == self.event_mask_radio:
            self.current_mode = MaskMode.EVENT
            self.mode_changed.emit(MaskMode.EVENT.value)  # Emit "event"
        else:
            self.current_mode = MaskMode.CAPTURE
            self.mode_changed.emit(MaskMode.CAPTURE.value)  # Emit "capture"

    def set_mode(self, mode: MaskMode):
        """Set the current mode programmatically.

        Args:
            mode: The mode to set (MaskMode.EVENT or MaskMode.CAPTURE)
        """
        if mode == MaskMode.EVENT:
            self.event_mask_radio.setChecked(True)
        else:
            self.capture_mask_radio.setChecked(True)

        self.current_mode = mode

    def get_mode(self) -> MaskMode:
        """Get the current mode.

        Returns:
            Current MaskMode (EVENT or CAPTURE)
        """
        return self.current_mode

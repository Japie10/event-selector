"""Integration tests for main window."""

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication
from PyQt5.QtTest import QTest

from event_selector.gui.main_window import MainWindow


@pytest.fixture
def qapp(qtbot):
    """Provide Qt application."""
    return QApplication.instance()


class TestMainWindow:
    """Test MainWindow basic functionality."""
    
    def test_window_creation(self, qtbot):
        """Test main window can be created."""
        window = MainWindow()
        qtbot.addWidget(window)
        
        assert window.windowTitle() == "Event Selector"
        assert window.width() >= 1200
        assert window.height() >= 800
    
    def test_initial_state(self, qtbot):
        """Test initial window state."""
        window = MainWindow()
        qtbot.addWidget(window)
        
        # Check mode is set to MASK
        assert window.current_mode.value == "mask"
        assert window.mask_button.isChecked()
        
        # Check menus exist
        assert window.menuBar() is not None
        
        # Check status bar exists
        assert window.statusBar() is not None
    
    def test_mode_switching(self, qtbot):
        """Test switching between mask and trigger modes."""
        window = MainWindow()
        qtbot.addWidget(window)
        
        # Switch to trigger mode
        qtbot.mouseClick(window.trigger_button, Qt.LeftButton)
        assert window.current_mode.value == "trigger"
        
        # Switch back to mask mode
        qtbot.mouseClick(window.mask_button, Qt.LeftButton)
        assert window.current_mode.value == "mask"
    
    @pytest.mark.parametrize("action_name", [
        "open_yaml_action",
        "import_mask_action",
        "export_mask_action",
        "export_trigger_action"
    ])
    def test_actions_exist(self, qtbot, action_name):
        """Test that menu actions exist."""
        window = MainWindow()
        qtbot.addWidget(window)
        
        assert hasattr(window, action_name)
        action = getattr(window, action_name)
        assert action is not None
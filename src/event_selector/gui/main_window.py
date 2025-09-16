"""Main application window for Event Selector.

This module implements the main PyQt5 window with tabs, menus,
status bar, and dock widgets.
"""

import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
from enum import Enum

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QMenuBar, QMenu, QAction, QStatusBar, QToolBar,
    QDockWidget, QFileDialog, QMessageBox, QButtonGroup,
    QPushButton, QLabel, QSplitter, QActionGroup
)
from PyQt5.QtCore import Qt, QSettings, QTimer, pyqtSignal, QSize
from PyQt5.QtGui import QIcon, QKeySequence, QCloseEvent

from event_selector.core.models import (
    FormatType, MaskMode, Mk1Format, Mk2Format, SessionState
)
from event_selector.core.parser import parse_yaml_file
from event_selector.core.importer import import_mask_file, find_associated_yaml
from event_selector.core.exporter import Exporter
from event_selector.gui.tabs.event_tab import EventTab
from event_selector.gui.widgets.problems_dock import ProblemsDock
from event_selector.gui.dialogs.restore_dialog import RestoreDialog

# Try to import version
try:
    from event_selector import __version__
except ImportError:
    __version__ = "0.0.0+unknown"


class MainWindow(QMainWindow):
    """Main application window."""

    # Signals
    mode_changed = pyqtSignal(MaskMode)
    file_loaded = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize main window.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        self.setWindowTitle("Event Selector")
        self.resize(1200, 800)

        # State
        self.open_tabs: Dict[str, EventTab] = {}
        self.current_mode = MaskMode.MASK
        self.session_state = SessionState()
        self.autosave_timer = QTimer()
        self.autosave_timer.timeout.connect(self._autosave_session)

        # Settings
        self.settings = QSettings("EventSelector", "EventSelector")

        # Setup UI
        self._setup_ui()
        self._setup_menus()
        self._setup_toolbar()
        self._setup_dock_widgets()
        self._setup_statusbar()

        # Restore state
        self._restore_window_state()

        # Check for startup actions
        self._check_startup_actions()

    def _setup_ui(self) -> None:
        """Setup main UI components."""
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Mode selector
        mode_widget = self._create_mode_selector()
        layout.addWidget(mode_widget)

        # Tab widget for YAML files
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self._close_tab)
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tab_widget)

        # Show welcome message if no tabs
        if self.tab_widget.count() == 0:
            self._show_welcome_tab()

    def _create_mode_selector(self) -> QWidget:
        """Create mode selector widget.

        Returns:
            Mode selector widget
        """
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)

        # Mode label
        layout.addWidget(QLabel("Mode:"))

        # Mode buttons
        self.mask_button = QPushButton("Event-Mask")
        self.mask_button.setCheckable(True)
        self.mask_button.setChecked(True)

        self.trigger_button = QPushButton("Capture-Mask")
        self.trigger_button.setCheckable(True)

        # Button group for exclusive selection
        self.mode_group = QButtonGroup()
        self.mode_group.addButton(self.mask_button, 0)
        self.mode_group.addButton(self.trigger_button, 1)
        self.mode_group.buttonClicked.connect(self._on_mode_changed)

        layout.addWidget(self.mask_button)
        layout.addWidget(self.trigger_button)
        layout.addStretch()

        # Current file label
        self.current_file_label = QLabel("No file loaded")
        layout.addWidget(self.current_file_label)

        return widget

    def _setup_menus(self) -> None:
        """Setup menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        self.open_yaml_action = QAction("&Open YAML...", self)
        self.open_yaml_action.setShortcut(QKeySequence.Open)
        self.open_yaml_action.triggered.connect(self._open_yaml_file)
        file_menu.addAction(self.open_yaml_action)

        self.import_mask_action = QAction("&Import Mask...", self)
        self.import_mask_action.setShortcut(QKeySequence("Ctrl+I"))
        self.import_mask_action.triggered.connect(self._import_mask_file)
        file_menu.addAction(self.import_mask_action)

        file_menu.addSeparator()

        self.export_mask_action = QAction("&Export Mask...", self)
        self.export_mask_action.setShortcut(QKeySequence("Ctrl+E"))
        self.export_mask_action.triggered.connect(self._export_mask)
        self.export_mask_action.setEnabled(False)
        file_menu.addAction(self.export_mask_action)

        self.export_trigger_action = QAction("Export &Trigger...", self)
        self.export_trigger_action.setShortcut(QKeySequence("Ctrl+T"))
        self.export_trigger_action.triggered.connect(self._export_trigger)
        self.export_trigger_action.setEnabled(False)
        file_menu.addAction(self.export_trigger_action)

        file_menu.addSeparator()

        self.close_tab_action = QAction("&Close Tab", self)
        self.close_tab_action.setShortcut(QKeySequence("Ctrl+W"))
        self.close_tab_action.triggered.connect(self._close_current_tab)
        self.close_tab_action.setEnabled(False)
        file_menu.addAction(self.close_tab_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit menu
        edit_menu = menubar.addMenu("&Edit")

        self.undo_action = QAction("&Undo", self)
        self.undo_action.setShortcut(QKeySequence.Undo)
        self.undo_action.triggered.connect(self._undo)
        self.undo_action.setEnabled(False)
        edit_menu.addAction(self.undo_action)

        self.redo_action = QAction("&Redo", self)
        self.redo_action.setShortcut(QKeySequence.Redo)
        self.redo_action.triggered.connect(self._redo)
        self.redo_action.setEnabled(False)
        edit_menu.addAction(self.redo_action)

        edit_menu.addSeparator()

        self.select_all_action = QAction("Select &All", self)
        self.select_all_action.setShortcut(QKeySequence.SelectAll)
        self.select_all_action.triggered.connect(self._select_all)
        self.select_all_action.setEnabled(False)
        edit_menu.addAction(self.select_all_action)

        self.select_none_action = QAction("Select &None", self)
        self.select_none_action.setShortcut(QKeySequence("Ctrl+D"))
        self.select_none_action.triggered.connect(self._select_none)
        self.select_none_action.setEnabled(False)
        edit_menu.addAction(self.select_none_action)

        edit_menu.addSeparator()

        # Selection macros submenu
        selection_menu = edit_menu.addMenu("Selection &Macros")

        self.select_errors_action = QAction("Select All &Errors", self)
        self.select_errors_action.triggered.connect(self._select_all_errors)
        self.select_errors_action.setEnabled(False)
        selection_menu.addAction(self.select_errors_action)

        self.unselect_errors_action = QAction("&Unselect All Errors", self)
        self.unselect_errors_action.triggered.connect(self._unselect_all_errors)
        self.unselect_errors_action.setEnabled(False)
        selection_menu.addAction(self.unselect_errors_action)

        selection_menu.addSeparator()

        self.select_syncs_action = QAction("Select All &Syncs", self)
        self.select_syncs_action.triggered.connect(self._select_all_syncs)
        self.select_syncs_action.setEnabled(False)
        selection_menu.addAction(self.select_syncs_action)

        self.unselect_syncs_action = QAction("U&nselect All Syncs", self)
        self.unselect_syncs_action.triggered.connect(self._unselect_all_syncs)
        self.unselect_syncs_action.setEnabled(False)
        selection_menu.addAction(self.unselect_syncs_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        self.problems_dock_action = QAction("&Problems Dock", self)
        self.problems_dock_action.setCheckable(True)
        self.problems_dock_action.setChecked(True)
        view_menu.addAction(self.problems_dock_action)

        view_menu.addSeparator()

        self.compact_view_action = QAction("&Compact View", self)
        self.compact_view_action.setCheckable(True)
        view_menu.addAction(self.compact_view_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

        about_qt_action = QAction("About &Qt", self)
        about_qt_action.triggered.connect(QApplication.aboutQt)
        help_menu.addAction(about_qt_action)

    def _setup_toolbar(self) -> None:
        """Setup toolbar."""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setObjectName("MainToolbar")
        self.addToolBar(toolbar)

        # Add common actions
        toolbar.addAction(self.open_yaml_action)
        toolbar.addAction(self.import_mask_action)
        toolbar.addSeparator()
        toolbar.addAction(self.export_mask_action)
        toolbar.addAction(self.export_trigger_action)
        toolbar.addSeparator()
        toolbar.addAction(self.undo_action)
        toolbar.addAction(self.redo_action)

    def _setup_dock_widgets(self) -> None:
        """Setup dock widgets."""
        # Problems dock
        self.problems_dock = ProblemsDock()
        self.problems_dock_widget = QDockWidget("Problems", self)
        self.problems_dock_widget.setObjectName("ProblemsDock")
        self.problems_dock_widget.setWidget(self.problems_dock)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.problems_dock_widget)

        # Connect visibility action
        self.problems_dock_action.toggled.connect(self.problems_dock_widget.setVisible)
        self.problems_dock_widget.visibilityChanged.connect(
            lambda visible: self.problems_dock_action.setChecked(visible)
        )

    def _setup_statusbar(self) -> None:
        """Setup status bar."""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)

        # Permanent widgets
        self.event_count_label = QLabel("Events: 0")
        self.statusbar.addPermanentWidget(self.event_count_label)

        self.selection_count_label = QLabel("Selected: 0")
        self.statusbar.addPermanentWidget(self.selection_count_label)

        # Show ready message
        self.statusbar.showMessage("Ready", 2000)

    def _show_welcome_tab(self) -> None:
        """Show welcome tab when no files are loaded."""
        welcome_widget = QWidget()
        layout = QVBoxLayout(welcome_widget)
        layout.setAlignment(Qt.AlignCenter)

        welcome_label = QLabel(
            "<h2>Welcome to Event Selector</h2>"
            "<p>To get started:</p>"
            "<ul>"
            "<li>Open a YAML file (Ctrl+O)</li>"
            "<li>Import an existing mask (Ctrl+I)</li>"
            "<li>Or drag and drop files here</li>"
            "</ul>"
        )
        welcome_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(welcome_label)

        self.tab_widget.addTab(welcome_widget, "Welcome")

    def _open_yaml_file(self) -> None:
        """Open YAML file dialog."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Open YAML File",
            str(Path.home()),
            "YAML Files (*.yaml *.yml);;All Files (*.*)"
        )

        if filepath:
            self.load_yaml_file(filepath)

    def load_yaml_file(self, filepath: str) -> None:
        """Load YAML file.

        Args:
            filepath: Path to YAML file
        """
        filepath = Path(filepath)

        # Check if already open
        if str(filepath) in self.open_tabs:
            # Switch to existing tab
            for i in range(self.tab_widget.count()):
                if self.tab_widget.widget(i) == self.open_tabs[str(filepath)]:
                    self.tab_widget.setCurrentIndex(i)
                    return

        try:
            # Parse YAML
            format_obj, validation = parse_yaml_file(filepath)

            # Show validation issues
            if validation.has_errors or validation.has_warnings:
                self.problems_dock.add_validation_result(validation, str(filepath))

            # Create tab
            event_tab = EventTab(format_obj, filepath, self.current_mode)
            event_tab.selection_changed.connect(self._update_selection_count)
            event_tab.events_modified.connect(self._on_events_modified)

            # Remove welcome tab if present
            if self.tab_widget.count() == 1 and self.tab_widget.tabText(0) == "Welcome":
                self.tab_widget.removeTab(0)

            # Add tab
            index = self.tab_widget.addTab(event_tab, filepath.name)
            self.tab_widget.setCurrentIndex(index)
            self.tab_widget.setTabToolTip(index, str(filepath))

            # Store reference
            self.open_tabs[str(filepath)] = event_tab
            self.session_state.add_file(str(filepath))

            # Update UI
            self._update_ui_state()
            self.statusbar.showMessage(f"Loaded {filepath.name}", 2000)
            self.file_loaded.emit(str(filepath))

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Loading File",
                f"Failed to load {filepath.name}:\n{str(e)}"
            )
            self.problems_dock.add_error(f"Failed to load {filepath}: {e}")

    def _import_mask_file(self) -> None:
        """Import mask file dialog."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Import Mask File",
            str(Path.home()),
            "Text Files (*.txt);;All Files (*.*)"
        )

        if not filepath:
            return

        try:
            # Import mask
            mask_data, validation = import_mask_file(filepath)

            # Show validation issues
            if validation.has_errors or validation.has_warnings:
                self.problems_dock.add_validation_result(validation, filepath)

            # Try to find associated YAML
            yaml_path = find_associated_yaml(filepath)

            if not yaml_path:
                # Ask user to select YAML
                yaml_path, _ = QFileDialog.getOpenFileName(
                    self,
                    "Select Associated YAML File",
                    str(Path(filepath).parent),
                    "YAML Files (*.yaml *.yml);;All Files (*.*)"
                )

            if yaml_path:
                # Load YAML first
                self.load_yaml_file(str(yaml_path))

                # Apply mask to current tab
                current_tab = self.tab_widget.currentWidget()
                if isinstance(current_tab, EventTab):
                    current_tab.apply_mask(mask_data)
                    self.statusbar.showMessage(f"Imported mask from {Path(filepath).name}", 2000)

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Importing Mask",
                f"Failed to import mask:\n{str(e)}"
            )

    def _export_mask(self) -> None:
        """Export current mask."""
        self._export_current(MaskMode.MASK)

    def _export_trigger(self) -> None:
        """Export current trigger."""
        self._export_current(MaskMode.TRIGGER)

    def _export_current(self, mode: MaskMode) -> None:
        """Export current tab's mask/trigger.

        Args:
            mode: Export mode (mask or trigger)
        """
        current_tab = self.tab_widget.currentWidget()
        if not isinstance(current_tab, EventTab):
            return

        # Get export filepath
        default_name = f"{Path(current_tab.filepath).stem}_{mode.value}.txt"
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            f"Export {mode.value.title()}",
            default_name,
            "Text Files (*.txt);;All Files (*.*)"
        )

        if not filepath:
            return

        try:
            current_tab.export_mask(filepath, mode)
            self.statusbar.showMessage(f"Exported {mode.value} to {Path(filepath).name}", 2000)
        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Error",
                f"Failed to export {mode.value}:\n{str(e)}"
            )

    def _close_tab(self, index: int) -> None:
        """Close tab at index.

        Args:
            index: Tab index to close
        """
        widget = self.tab_widget.widget(index)
        if isinstance(widget, EventTab):
            # Check for unsaved changes
            if widget.has_unsaved_changes():
                reply = QMessageBox.question(
                    self,
                    "Unsaved Changes",
                    f"Save changes to {widget.filepath.name}?",
                    QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
                )

                if reply == QMessageBox.Cancel:
                    return
                elif reply == QMessageBox.Save:
                    widget.save_changes()

            # Remove from tracking
            filepath = str(widget.filepath)
            if filepath in self.open_tabs:
                del self.open_tabs[filepath]
                self.session_state.remove_file(filepath)

        # Remove tab
        self.tab_widget.removeTab(index)

        # Show welcome if no tabs left
        if self.tab_widget.count() == 0:
            self._show_welcome_tab()

        self._update_ui_state()

    def _close_current_tab(self) -> None:
        """Close current tab."""
        index = self.tab_widget.currentIndex()
        if index >= 0:
            self._close_tab(index)

    def _on_tab_changed(self, index: int) -> None:
        """Handle tab change.

        Args:
            index: New tab index
        """
        self._update_ui_state()

        # Update current file label
        if index >= 0:
            widget = self.tab_widget.widget(index)
            if isinstance(widget, EventTab):
                self.current_file_label.setText(widget.filepath.name)
                self._update_event_count(widget)
                self._update_selection_count()
            else:
                self.current_file_label.setText("No file loaded")

    def _on_mode_changed(self) -> None:
        """Handle mode change."""
        if self.mask_button.isChecked():
            self.current_mode = MaskMode.MASK
        else:
            self.current_mode = MaskMode.TRIGGER

        # Update all tabs
        for tab in self.open_tabs.values():
            tab.set_mode(self.current_mode)

        self.mode_changed.emit(self.current_mode)
        self.statusbar.showMessage(f"Switched to {self.current_mode.value} mode", 2000)

    def _on_events_modified(self) -> None:
        """Handle events modification."""
        sender = self.sender()
        if isinstance(sender, EventTab):
            self._update_event_count(sender)

    def _update_ui_state(self) -> None:
        """Update UI state based on current tab."""
        has_tab = self.tab_widget.count() > 0 and self.tab_widget.tabText(0) != "Welcome"
        current_tab = self.tab_widget.currentWidget()
        is_event_tab = isinstance(current_tab, EventTab)

        # File actions
        self.export_mask_action.setEnabled(is_event_tab)
        self.export_trigger_action.setEnabled(is_event_tab)
        self.close_tab_action.setEnabled(has_tab)

        # Edit actions
        if is_event_tab:
            self.undo_action.setEnabled(current_tab.can_undo())
            self.redo_action.setEnabled(current_tab.can_redo())
            self.select_all_action.setEnabled(True)
            self.select_none_action.setEnabled(True)
            self.select_errors_action.setEnabled(True)
            self.unselect_errors_action.setEnabled(True)
            self.select_syncs_action.setEnabled(True)
            self.unselect_syncs_action.setEnabled(True)
        else:
            self.undo_action.setEnabled(False)
            self.redo_action.setEnabled(False)
            self.select_all_action.setEnabled(False)
            self.select_none_action.setEnabled(False)
            self.select_errors_action.setEnabled(False)
            self.unselect_errors_action.setEnabled(False)
            self.select_syncs_action.setEnabled(False)
            self.unselect_syncs_action.setEnabled(False)

    def _update_event_count(self, tab: EventTab) -> None:
        """Update event count in status bar.

        Args:
            tab: Event tab
        """
        count = tab.get_event_count()
        self.event_count_label.setText(f"Events: {count}")

    def _update_selection_count(self) -> None:
        """Update selection count in status bar."""
        current_tab = self.tab_widget.currentWidget()
        if isinstance(current_tab, EventTab):
            count = current_tab.get_selection_count()
            self.selection_count_label.setText(f"Selected: {count}")
        else:
            self.selection_count_label.setText("Selected: 0")

    # Edit menu actions
    def _undo(self) -> None:
        """Undo last action."""
        current_tab = self.tab_widget.currentWidget()
        if isinstance(current_tab, EventTab):
            current_tab.undo()
            self._update_ui_state()

    def _redo(self) -> None:
        """Redo last undone action."""
        current_tab = self.tab_widget.currentWidget()
        if isinstance(current_tab, EventTab):
            current_tab.redo()
            self._update_ui_state()

    def _select_all(self) -> None:
        """Select all events in current tab."""
        current_tab = self.tab_widget.currentWidget()
        if isinstance(current_tab, EventTab):
            current_tab.select_all()

    def _select_none(self) -> None:
        """Deselect all events in current tab."""
        current_tab = self.tab_widget.currentWidget()
        if isinstance(current_tab, EventTab):
            current_tab.select_none()

    def _select_all_errors(self) -> None:
        """Select all error events."""
        current_tab = self.tab_widget.currentWidget()
        if isinstance(current_tab, EventTab):
            count = current_tab.select_by_info("error")
            self.statusbar.showMessage(f"Selected {count} error events", 2000)

    def _unselect_all_errors(self) -> None:
        """Unselect all error events."""
        current_tab = self.tab_widget.currentWidget()
        if isinstance(current_tab, EventTab):
            count = current_tab.unselect_by_info("error")
            self.statusbar.showMessage(f"Unselected {count} error events", 2000)

    def _select_all_syncs(self) -> None:
        """Select all sync events."""
        current_tab = self.tab_widget.currentWidget()
        if isinstance(current_tab, EventTab):
            count = current_tab.select_by_info_regex(r"(sync|sbs|sws|ebs)")
            self.statusbar.showMessage(f"Selected {count} sync events", 2000)

    def _unselect_all_syncs(self) -> None:
        """Unselect all sync events."""
        current_tab = self.tab_widget.currentWidget()
        if isinstance(current_tab, EventTab):
            count = current_tab.unselect_by_info_regex(r"(sync|sbs|sws|ebs)")
            self.statusbar.showMessage(f"Unselected {count} sync events", 2000)

    def _show_about(self) -> None:
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About Event Selector",
            f"<h3>Event Selector</h3>"
            f"<p>Version {__version__}</p>"
            f"<p>Hardware/Firmware Event Mask Management Tool</p>"
            f"<p>© 2025</p>"
        )

    def _restore_window_state(self) -> None:
        """Restore window state from settings."""
        # Window geometry
        geometry = self.settings.value("window/geometry")
        if geometry:
            self.restoreGeometry(geometry)

        # Window state
        state = self.settings.value("window/state")
        if state:
            self.restoreState(state)

        # Dock visibility
        problems_visible = self.settings.value("docks/problems_visible", True, type=bool)
        self.problems_dock_widget.setVisible(problems_visible)
        self.problems_dock_action.setChecked(problems_visible)

    def _save_window_state(self) -> None:
        """Save window state to settings."""
        self.settings.setValue("window/geometry", self.saveGeometry())
        self.settings.setValue("window/state", self.saveState())
        self.settings.setValue("docks/problems_visible", self.problems_dock_widget.isVisible())

    def _check_startup_actions(self) -> None:
        """Check for startup actions (restore session, scan directory, etc)."""
        # Check for command line arguments
        args = QApplication.arguments()
        if len(args) > 1:
            # Load files from command line
            for arg in args[1:]:
                if arg.endswith(('.yaml', '.yml')):
                    self.load_yaml_file(arg)
                elif arg.endswith('.txt'):
                    # Try to import as mask
                    pass
            return

        # Check for session restore
        restore_on_start = self.settings.value("restore_on_start", True, type=bool)
        if restore_on_start:
            self._try_restore_session()
        else:
            # Check for files in current directory
            self._scan_current_directory()

    def _try_restore_session(self) -> None:
        """Try to restore previous session."""
        # TODO: Implement session restore
        pass

    def _scan_current_directory(self) -> None:
        """Scan current directory for mask/YAML files."""
        current_dir = Path.cwd()

        # Look for YAML files
        yaml_files = list(current_dir.glob("*.yaml")) + list(current_dir.glob("*.yml"))

        # Look for mask files
        mask_files = list(current_dir.glob("*mask*.txt")) + list(current_dir.glob("*trigger*.txt"))

        if yaml_files or mask_files:
            reply = QMessageBox.question(
                self,
                "Files Found",
                f"Found {len(yaml_files)} YAML and {len(mask_files)} mask files in current directory.\n"
                "Would you like to load them?",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                for yaml_file in yaml_files:
                    self.load_yaml_file(str(yaml_file))

    def _autosave_session(self) -> None:
        """Autosave current session."""
        # TODO: Implement autosave
        pass

    def closeEvent(self, event: QCloseEvent) -> None:
        """Handle window close event.

        Args:
            event: Close event
        """
        # Check for unsaved changes
        unsaved_tabs = []
        for tab in self.open_tabs.values():
            if tab.has_unsaved_changes():
                unsaved_tabs.append(tab)

        if unsaved_tabs:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                f"You have unsaved changes in {len(unsaved_tabs)} tab(s).\n"
                "Do you want to save them before closing?",
                QMessageBox.SaveAll | QMessageBox.Discard | QMessageBox.Cancel
            )

            if reply == QMessageBox.Cancel:
                event.ignore()
                return
            elif reply == QMessageBox.SaveAll:
                for tab in unsaved_tabs:
                    tab.save_changes()

        # Save window state
        self._save_window_state()

        # Save session
        self._autosave_session()

        event.accept()


def main() -> None:
    """Main entry point for GUI application."""
    app = QApplication(sys.argv)
    app.setOrganizationName("EventSelector")
    app.setApplicationName("Event Selector")

    # Set application style
    app.setStyle("Fusion")

    # Create and show main window
    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
"""Main window for Event Selector GUI."""

import sys
from pathlib import Path
from typing import Optional, Dict, Any, List

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QVBoxLayout, QHBoxLayout,
    QWidget, QMenuBar, QMenu, QAction, QToolBar, QStatusBar,
    QMessageBox, QFileDialog, QDockWidget, QSplitter
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QSettings
from PyQt5.QtGui import QKeySequence, QIcon

from event_selector.application.facades.event_selector_facade import EventSelectorFacade
from event_selector.infrastructure.config.config_manager import get_config_manager
from event_selector.infrastructure.persistence.session_manager import (
    get_session_manager, SessionState
)
from event_selector.presentation.gui.widgets.event_tab import EventTab
from event_selector.presentation.gui.widgets.problems_dock import ProblemsDock
from event_selector.presentation.gui.widgets.mode_switch import ModeSwitchWidget
from event_selector.shared.types import MaskMode


class MainWindow(QMainWindow):
    """Main application window."""
    
    # Signals
    project_loaded = pyqtSignal(str)  # Path to loaded project
    mode_changed = pyqtSignal(str)    # New mode
    
    def __init__(self, facade: Optional[EventSelectorFacade] = None):
        """Initialize main window.
        
        Args:
            facade: Application facade (creates one if None)
        """
        super().__init__()
        
        self.facade = facade or EventSelectorFacade()
        self.config_manager = get_config_manager()
        self.session_manager = get_session_manager()
        
        # Track open projects
        self.projects: Dict[str, Any] = {}
        self.tabs: Dict[str, EventTab] = {}
        
        # Current mode
        self.current_mode = MaskMode.MASK
        
        # Initialize UI
        self._init_ui()
        self._setup_menus()
        self._setup_toolbar()
        self._setup_statusbar()
        self._setup_docks()
        
        # Setup autosave timer
        self._setup_autosave()
        
        # Restore session if configured
        if self.config_manager.get('restore_on_start'):
            self._restore_session()
    
    def _init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Event Selector")
        self.setGeometry(100, 100, 1400, 900)
        
        # Central widget with tab widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Mode switch widget
        self.mode_switch = ModeSwitchWidget()
        self.mode_switch.mode_changed.connect(self._on_mode_changed)
        layout.addWidget(self.mode_switch)
        
        # Tab widget for projects
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self._close_tab)
        layout.addWidget(self.tab_widget)
        
        # Apply theme
        self._apply_theme()
    
    def _setup_menus(self):
        """Setup menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        self.open_action = QAction("&Open YAML...", self)
        self.open_action.setShortcut(QKeySequence.Open)
        self.open_action.triggered.connect(self._open_yaml)
        file_menu.addAction(self.open_action)
        
        self.import_mask_action = QAction("Import &Mask...", self)
        self.import_mask_action.triggered.connect(self._import_mask)
        file_menu.addAction(self.import_mask_action)
        
        self.import_trigger_action = QAction("Import &Trigger...", self)
        self.import_trigger_action.triggered.connect(self._import_trigger)
        file_menu.addAction(self.import_trigger_action)
        
        file_menu.addSeparator()
        
        self.export_mask_action = QAction("Export Mask...", self)
        self.export_mask_action.setShortcut(QKeySequence("Ctrl+Shift+E"))
        self.export_mask_action.triggered.connect(self._export_mask)
        file_menu.addAction(self.export_mask_action)
        
        self.export_trigger_action = QAction("Export Trigger...", self)
        self.export_trigger_action.triggered.connect(self._export_trigger)
        file_menu.addAction(self.export_trigger_action)
        
        self.export_both_action = QAction("Export Both...", self)
        self.export_both_action.triggered.connect(self._export_both)
        file_menu.addAction(self.export_both_action)
        
        file_menu.addSeparator()
        
        self.exit_action = QAction("E&xit", self)
        self.exit_action.setShortcut(QKeySequence.Quit)
        self.exit_action.triggered.connect(self.close)
        file_menu.addAction(self.exit_action)
        
        # Edit menu
        edit_menu = menubar.addMenu("&Edit")
        
        self.undo_action = QAction("&Undo", self)
        self.undo_action.setShortcut(QKeySequence.Undo)
        self.undo_action.triggered.connect(self._undo)
        edit_menu.addAction(self.undo_action)
        
        self.redo_action = QAction("&Redo", self)
        self.redo_action.setShortcut(QKeySequence.Redo)
        self.redo_action.triggered.connect(self._redo)
        edit_menu.addAction(self.redo_action)
        
        edit_menu.addSeparator()
        
        self.select_all_action = QAction("Select &All", self)
        self.select_all_action.setShortcut(QKeySequence.SelectAll)
        self.select_all_action.triggered.connect(self._select_all)
        edit_menu.addAction(self.select_all_action)
        
        self.clear_all_action = QAction("&Clear All", self)
        self.clear_all_action.triggered.connect(self._clear_all)
        edit_menu.addAction(self.clear_all_action)
        
        edit_menu.addSeparator()
        
        # Selection macros submenu
        macros_menu = edit_menu.addMenu("Selection &Macros")
        
        self.select_errors_action = QAction("Select All &Errors", self)
        self.select_errors_action.triggered.connect(self._select_errors)
        macros_menu.addAction(self.select_errors_action)
        
        self.select_syncs_action = QAction("Select All &Syncs", self)
        self.select_syncs_action.triggered.connect(self._select_syncs)
        macros_menu.addAction(self.select_syncs_action)
        
        # View menu
        view_menu = menubar.addMenu("&View")
        
        self.problems_dock_action = QAction("&Problems Dock", self)
        self.problems_dock_action.setCheckable(True)
        self.problems_dock_action.setChecked(True)
        self.problems_dock_action.triggered.connect(self._toggle_problems_dock)
        view_menu.addAction(self.problems_dock_action)
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        
        self.about_action = QAction("&About", self)
        self.about_action.triggered.connect(self._show_about)
        help_menu.addAction(self.about_action)
    
    def _setup_toolbar(self):
        """Setup toolbar."""
        toolbar = self.addToolBar("Main")
        toolbar.setMovable(False)
        
        # Add common actions
        toolbar.addAction(self.open_action)
        toolbar.addSeparator()
        toolbar.addAction(self.undo_action)
        toolbar.addAction(self.redo_action)
        toolbar.addSeparator()
        toolbar.addAction(self.export_mask_action)
        toolbar.addAction(self.export_trigger_action)
    
    def _setup_statusbar(self):
        """Setup status bar."""
        self.statusbar = self.statusBar()
        self.statusbar.showMessage("Ready")
    
    def _setup_docks(self):
        """Setup dock widgets."""
        # Problems dock
        self.problems_dock = QDockWidget("Problems", self)
        self.problems_widget = ProblemsDock()
        self.problems_dock.setWidget(self.problems_widget)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.problems_dock)
    
    def _setup_autosave(self):
        """Setup autosave timer."""
        self.autosave_timer = QTimer()
        self.autosave_timer.timeout.connect(self._autosave)
        
        # Get debounce time from config
        interval = self.config_manager.get('autosave_debounce_ms', 1000)
        self.autosave_timer.setInterval(interval)
        self.autosave_timer.start()
    
    def _apply_theme(self):
        """Apply application theme."""
        # This would apply the configured accent color and theme
        # For now, using default Qt theme
        pass
    
    # ==================
    # File Operations
    # ==================
    
    def load_project(self, yaml_path: Path):
        """Load a project from YAML file.
        
        Args:
            yaml_path: Path to YAML file
        """
        try:
            # Check if already loaded
            project_id = str(yaml_path)
            if project_id in self.projects:
                # Switch to existing tab
                for i in range(self.tab_widget.count()):
                    if self.tab_widget.widget(i).project_id == project_id:
                        self.tab_widget.setCurrentIndex(i)
                        return
            
            # Load project
            project, validation = self.facade.load_project(yaml_path)
            
            # Show validation issues in problems dock
            if validation.has_errors or validation.has_warnings:
                self.problems_widget.add_validation_result(validation)
            
            if validation.has_errors:
                QMessageBox.warning(
                    self,
                    "Validation Errors",
                    f"Project loaded with errors. Check Problems dock for details."
                )
            
            # Create tab for project
            tab = EventTab(project, project_id, self.facade)
            tab.status_message.connect(self.statusbar.showMessage)
            
            # Add to tab widget
            tab_name = yaml_path.stem
            index = self.tab_widget.addTab(tab, tab_name)
            self.tab_widget.setCurrentIndex(index)
            
            # Track project
            self.projects[project_id] = project
            self.tabs[project_id] = tab
            
            # Update session
            self.session_manager.add_open_file(project_id)
            
            # Emit signal
            self.project_loaded.emit(project_id)
            
            self.statusbar.showMessage(f"Loaded: {yaml_path.name}")
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Load Error",
                f"Failed to load project:\n{e}"
            )
    
    def _open_yaml(self):
        """Open YAML file dialog."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open YAML Event Definition",
            "",
            "YAML Files (*.yaml *.yml);;All Files (*.*)"
        )
        
        if file_path:
            self.load_project(Path(file_path))
    
    def _import_mask(self):
        """Import mask file."""
        current_tab = self._get_current_tab()
        if not current_tab:
            return
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Mask File",
            "",
            "Text Files (*.txt);;All Files (*.*)"
        )
        
        if file_path:
            try:
                result = self.facade.import_mask(
                    current_tab.project,
                    Path(file_path),
                    MaskMode.MASK
                )
                
                if result.has_errors:
                    self.problems_widget.add_validation_result(result)
                    QMessageBox.warning(self, "Import Errors", "Import completed with errors")
                else:
                    current_tab.refresh()
                    self.statusbar.showMessage("Mask imported successfully")
                    
            except Exception as e:
                QMessageBox.critical(self, "Import Error", str(e))
    
    def _import_trigger(self):
        """Import trigger file."""
        current_tab = self._get_current_tab()
        if not current_tab:
            return
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Trigger File",
            "",
            "Text Files (*.txt);;All Files (*.*)"
        )
        
        if file_path:
            try:
                result = self.facade.import_mask(
                    current_tab.project,
                    Path(file_path),
                    MaskMode.TRIGGER
                )
                
                if result.has_errors:
                    self.problems_widget.add_validation_result(result)
                    QMessageBox.warning(self, "Import Errors", "Import completed with errors")
                else:
                    current_tab.refresh()
                    self.statusbar.showMessage("Trigger imported successfully")
                    
            except Exception as e:
                QMessageBox.critical(self, "Import Error", str(e))
    
    def _export_mask(self):
        """Export mask file."""
        current_tab = self._get_current_tab()
        if not current_tab:
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Mask File",
            "mask.txt",
            "Text Files (*.txt);;All Files (*.*)"
        )
        
        if file_path:
            try:
                self.facade.export_mask(
                    current_tab.project,
                    Path(file_path),
                    MaskMode.MASK
                )
                self.statusbar.showMessage(f"Mask exported to {Path(file_path).name}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))
    
    def _export_trigger(self):
        """Export trigger file."""
        current_tab = self._get_current_tab()
        if not current_tab:
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Trigger File",
            "trigger.txt",
            "Text Files (*.txt);;All Files (*.*)"
        )
        
        if file_path:
            try:
                self.facade.export_mask(
                    current_tab.project,
                    Path(file_path),
                    MaskMode.TRIGGER
                )
                self.statusbar.showMessage(f"Trigger exported to {Path(file_path).name}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))
    
    def _export_both(self):
        """Export both mask and trigger files."""
        current_tab = self._get_current_tab()
        if not current_tab:
            return
        
        # Get base name
        base_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Mask and Trigger Files (base name)",
            "output",
            "Text Files (*.txt);;All Files (*.*)"
        )
        
        if base_path:
            try:
                base = Path(base_path).with_suffix('')
                mask_path = base.with_name(f"{base.name}_mask.txt")
                trigger_path = base.with_name(f"{base.name}_trigger.txt")
                
                self.facade.export_both_masks(
                    current_tab.project,
                    mask_path,
                    trigger_path
                )
                
                self.statusbar.showMessage(f"Exported mask and trigger files")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))
    
    # ==================
    # Edit Operations
    # ==================
    
    def _undo(self):
        """Undo last operation."""
        current_tab = self._get_current_tab()
        if current_tab:
            current_tab.undo()
    
    def _redo(self):
        """Redo last undone operation."""
        current_tab = self._get_current_tab()
        if current_tab:
            current_tab.redo()
    
    def _select_all(self):
        """Select all events in current subtab."""
        current_tab = self._get_current_tab()
        if current_tab:
            current_tab.select_all()
    
    def _clear_all(self):
        """Clear all events in current subtab."""
        current_tab = self._get_current_tab()
        if current_tab:
            current_tab.clear_all()
    
    def _select_errors(self):
        """Select all error events."""
        current_tab = self._get_current_tab()
        if current_tab:
            current_tab.select_errors()
    
    def _select_syncs(self):
        """Select all sync events."""
        current_tab = self._get_current_tab()
        if current_tab:
            current_tab.select_syncs()
    
    # ==================
    # View Operations
    # ==================
    
    def _toggle_problems_dock(self):
        """Toggle problems dock visibility."""
        if self.problems_dock.isVisible():
            self.problems_dock.hide()
        else:
            self.problems_dock.show()
    
    def _show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About Event Selector",
            "Event Selector v1.0.0\n\n"
            "Hardware/Firmware Event Mask Management Tool\n\n"
            "Built with clean architecture for maintainability and extensibility."
        )
    
    # ==================
    # Helper Methods
    # ==================
    
    def _get_current_tab(self) -> Optional[EventTab]:
        """Get the current active tab."""
        widget = self.tab_widget.currentWidget()
        if isinstance(widget, EventTab):
            return widget
        return None
    
    def _close_tab(self, index: int):
        """Close a tab.
        
        Args:
            index: Tab index to close
        """
        widget = self.tab_widget.widget(index)
        if isinstance(widget, EventTab):
            # Remove from tracking
            project_id = widget.project_id
            self.projects.pop(project_id, None)
            self.tabs.pop(project_id, None)
            self.facade.close_project(project_id)
            self.session_manager.remove_open_file(project_id)
        
        self.tab_widget.removeTab(index)
    
    def _on_mode_changed(self, mode: str):
        """Handle mode change.
        
        Args:
            mode: New mode (mask or trigger)
        """
        self.current_mode = MaskMode(mode)
        
        # Update all tabs
        for tab in self.tabs.values():
            tab.set_mode(self.current_mode)
        
        self.mode_changed.emit(mode)
    
    def _autosave(self):
        """Perform autosave."""
        if not self.projects:
            return
        
        # Build session state
        session = SessionState()
        session.open_files = list(self.projects.keys())
        session.current_mode = self.current_mode.value
        session.active_tab = self.tab_widget.currentIndex()
        
        # Save window geometry
        geometry = self.geometry()
        session.window_geometry = {
            'x': geometry.x(),
            'y': geometry.y(),
            'width': geometry.width(),
            'height': geometry.height()
        }
        
        # Save dock states
        session.dock_states['problems'] = self.problems_dock.isVisible()
        
        # Save mask states
        for project_id, project in self.projects.items():
            session.mask_states[project_id] = project.event_mask.data.tolist()
            session.trigger_states[project_id] = project.capture_mask.data.tolist()
        
        # Save session
        self.session_manager.save_session(session)
    
    def _restore_session(self):
        """Restore previous session."""
        session = self.session_manager.load_session()
        if not session:
            return
        
        # Check if should restore
        if session.open_files:
            reply = QMessageBox.question(
                self,
                "Restore Session",
                f"Restore previous session with {len(session.open_files)} file(s)?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            
            if reply != QMessageBox.Yes:
                return
        
        # Restore files
        for file_path in session.open_files:
            path = Path(file_path)
            if path.exists():
                try:
                    self.load_project(path)
                    
                    # Restore mask states if available
                    project_id = str(path)
                    if project_id in self.projects:
                        project = self.projects[project_id]
                        
                        if project_id in session.mask_states:
                            mask_values = session.mask_states[project_id]
                            project.event_mask.data[:] = mask_values[:len(project.event_mask.data)]
                        
                        if project_id in session.trigger_states:
                            trigger_values = session.trigger_states[project_id]
                            project.capture_mask.data[:] = trigger_values[:len(project.capture_mask.data)]
                        
                        # Refresh tab
                        if project_id in self.tabs:
                            self.tabs[project_id].refresh()
                            
                except Exception as e:
                    print(f"Failed to restore {file_path}: {e}")
            else:
                self.problems_widget.add_problem(
                    "WARNING",
                    f"File not found: {file_path}",
                    location=file_path
                )
        
        # Restore window geometry
        if session.window_geometry:
            self.setGeometry(
                session.window_geometry.get('x', 100),
                session.window_geometry.get('y', 100),
                session.window_geometry.get('width', 1400),
                session.window_geometry.get('height', 900)
            )
        
        # Restore mode
        if session.current_mode:
            self.current_mode = MaskMode(session.current_mode)
            self.mode_switch.set_mode(self.current_mode)
        
        # Restore active tab
        if session.active_tab is not None and session.active_tab < self.tab_widget.count():
            self.tab_widget.setCurrentIndex(session.active_tab)
    
    def closeEvent(self, event):
        """Handle window close event."""
        # Perform final autosave
        self._autosave()
        
        # Accept close
        event.accept()


def launch_gui(debug_level: Optional[str] = None) -> int:
    """Launch the GUI application.
    
    Args:
        debug_level: Optional debug level for logging
        
    Returns:
        Exit code
    """
    app = QApplication(sys.argv)
    app.setApplicationName("Event Selector")
    app.setOrganizationName("EventSelector")
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    # Check for mask/trigger files in current directory
    if window.config_manager.get('scan_dir_on_start'):
        _check_current_directory(window)
    
    return app.exec_()


def _check_current_directory(window: MainWindow):
    """Check current directory for mask/trigger files.
    
    Args:
        window: Main window instance
    """
    from pathlib import Path
    
    current_dir = Path.cwd()
    
    # Look for YAML files
    yaml_files = list(current_dir.glob("*.yaml")) + list(current_dir.glob("*.yml"))
    
    # Look for mask/trigger files
    mask_files = [f for f in current_dir.glob("*.txt") 
                  if 'mask' in f.name.lower() or 'trigger' in f.name.lower()]
    
    if yaml_files or mask_files:
        message = "Found files in current directory:\n"
        if yaml_files:
            message += f"\n{len(yaml_files)} YAML file(s)"
        if mask_files:
            message += f"\n{len(mask_files)} mask/trigger file(s)"
        message += "\n\nWould you like to load them?"
        
        reply = QMessageBox.question(
            window,
            "Files Detected",
            message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Load YAML files
            for yaml_file in yaml_files[:5]:  # Limit to 5 files
                window.load_project(yaml_file)

"""Lean main window - coordination only, no business logic."""

from pathlib import Path
from typing import Optional

from PyQt5.QtWidgets import QMainWindow, QTabWidget, QVBoxLayout, QWidget
from PyQt5.QtCore import Qt, QTimer, pyqtSignal

from event_selector.application.facades.event_selector_facade import EventSelectorFacade
from event_selector.infrastructure.config.config_manager import get_config_manager
from event_selector.infrastructure.persistence.session_manager import get_session_manager
from event_selector.presentation.gui.controllers.project_controller import ProjectController
from event_selector.presentation.gui.controllers.menu_controller import MenuController
from event_selector.presentation.gui.controllers.toolbar_controller import ToolbarController
from event_selector.presentation.gui.views.project_view import ProjectView
from event_selector.presentation.gui.widgets.mode_switch import ModeSwitchWidget
from event_selector.presentation.gui.widgets.problems_dock import ProblemsDock
from event_selector.shared.types import MaskMode
from event_selector.infrastructure.logging import get_logger

logger = get_logger(__name__)

class MainWindow(QMainWindow):
    """Main application window - coordination only."""

    # Signals
    project_loaded = pyqtSignal(str)
    mode_changed = pyqtSignal(str)

    def __init__(self, facade: Optional[EventSelectorFacade] = None):
        """Initialize main window.

        Args:
            facade: Application facade
        """
        super().__init__()

        # Dependencies
        self.facade = facade or EventSelectorFacade()
        self.config_manager = get_config_manager()
        self.session_manager = get_session_manager()

        # Controllers
        self.project_controller = ProjectController(self.facade, self)
        self.menu_controller = MenuController(self, self.project_controller)
        self.toolbar_controller = ToolbarController(self, self.project_controller)

        # State
        self.project_views = {}
        self.current_mode = MaskMode.MASK

        # Initialize UI
        self._setup_ui()
        self._setup_problems_dock()
        self._setup_autosave()

        # Restore session
        if self.config_manager.get('restore_on_start'):
            self.project_controller.restore_session()

    def _setup_ui(self):
        """Setup user interface."""
        self.setWindowTitle("Event Selector")
        self.setGeometry(100, 100, 1400, 900)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        # Mode switch
        self.mode_switch = ModeSwitchWidget()
        self.mode_switch.mode_changed.connect(self._on_mode_changed)
        layout.addWidget(self.mode_switch)

        # Tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self._close_tab)
        layout.addWidget(self.tab_widget)

        # Setup menus and toolbars
        self.menu_controller.setup_menus()
        self.toolbar_controller.setup_toolbar()

        # Status bar
        self.statusBar().showMessage("Ready")

        # Problems dock
        self._setup_problems_dock()

    def _setup_problems_dock(self):
        """Setup problems dock widget."""
        # Create problems dock
        self.problems_dock = ProblemsDock(self)
        
        # Add to main window (bottom by default)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.problems_dock)
        
        # Connect signal for jumping to problems
        self.problems_dock.problem_clicked.connect(self._on_problem_clicked)
        
        # Initially hidden (shows automatically when problems occur)
        self.problems_dock.hide()
        
        logger.debug("Problems dock initialized")

    def _setup_autosave(self):
        """Setup autosave timer."""
        self.autosave_timer = QTimer()
        self.autosave_timer.timeout.connect(self.project_controller.autosave)
        interval = self.config_manager.get('autosave_debounce_ms', 1000)
        self.autosave_timer.setInterval(interval)
        self.autosave_timer.start()

    def add_project_view(self, project_id: str, view: ProjectView):
        """Add a project view as a new tab.

        Args:
            project_id: Project identifier
            view: Project view widget
        """
        view.status_message.connect(self.statusBar().showMessage)

        tab_name = Path(project_id).stem
        index = self.tab_widget.addTab(view, tab_name)
        self.tab_widget.setCurrentIndex(index)

        self.project_views[project_id] = view
        self.project_loaded.emit(project_id)

    def remove_project_view(self, project_id: str):
        """Remove a project view.

        Args:
            project_id: Project identifier
        """
        if project_id in self.project_views:
            view = self.project_views.pop(project_id)
            index = self.tab_widget.indexOf(view)
            if index >= 0:
                self.tab_widget.removeTab(index)

    def get_current_project_view(self) -> Optional[ProjectView]:
        """Get the currently active project view.

        Returns:
            Current ProjectView or None
        """
        widget = self.tab_widget.currentWidget()
        if isinstance(widget, ProjectView):
            return widget
        return None

    def _close_tab(self, index: int):
        """Handle tab close request.

        Args:
            index: Tab index to close
        """
        widget = self.tab_widget.widget(index)
        if isinstance(widget, ProjectView):
            self.project_controller.close_project(widget.project_id)

    def _on_mode_changed(self, mode: MaskMode):
        """Handle mode switch.
        
        Args:
            mode: New mask mode
        """
        self.current_mode = mode
        
        # Update all open projects
        for project_id, project_view in self.project_views.items():
            project_view.set_mode(mode)

    def closeEvent(self, event):
        """Handle window close event.

        Args:
            event: Close event
        """
        self.project_controller.autosave()
        event.accept()

    def show_problems_dock(self):
        """Show the problems dock."""
        self.problems_dock.show()
        self.problems_dock.raise_()

    def hide_problems_dock(self):
        """Hide the problems dock."""
        self.problems_dock.hide()

    def toggle_problems_dock(self):
        """Toggle problems dock visibility."""
        if self.problems_dock.isVisible():
            self.hide_problems_dock()
        else:
            self.show_problems_dock()
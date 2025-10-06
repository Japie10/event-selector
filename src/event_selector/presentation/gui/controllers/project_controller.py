"""Controller for project-level operations."""

from pathlib import Path
from typing import Optional, TYPE_CHECKING

from PyQt5.QtWidgets import QMessageBox, QFileDialog

from event_selector.application.facades.event_selector_facade import EventSelectorFacade
from event_selector.presentation.gui.views.project_view import ProjectView
from event_selector.presentation.gui.view_models.project_vm import ProjectViewModel
from event_selector.infrastructure.persistence.session_manager import SessionState
from event_selector.shared.types import MaskMode
from event_selector.infrastructure.logging import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from event_selector.presentation.gui.main_window import MainWindow
from event_selector.infrastructure.logging import get_logger

logger = get_logger(__name__)

class ProjectController:
    """Handles project lifecycle operations."""

    def __init__(self, facade: EventSelectorFacade, main_window: 'MainWindow'):
        """Initialize controller.

        Args:
            facade: Application facade
            main_window: Main window reference
        """
        self.facade = facade
        self.window = main_window

    def open_project_dialog(self):
        """Show dialog to open YAML file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self.window,
            "Open YAML Event Definition",
            "",
            "YAML Files (*.yaml *.yml);;All Files (*.*)"
        )

        if file_path:
            self.load_project(Path(file_path))

    def load_project(self, yaml_path: Path):
        """Load a project from YAML file.

        Args:
            yaml_path: Path to YAML file
        """
        project_id = str(yaml_path)

        # Check if already open
        if project_id in self.window.project_views:
            self._switch_to_existing_project(project_id)
            return

        try:
            # Load through facade
            project, validation = self.facade.load_project(yaml_path)

            # Show validation issues
            if validation.has_errors or validation.has_warnings:
                self.window.problems_widget.add_validation_result(validation)

            if validation.has_errors:
                QMessageBox.warning(
                    self.window,
                    "Validation Errors",
                    "Project loaded with errors. Check Problems dock for details."
                )

            # Create view model
            view_model = ProjectViewModel.from_project(project, project_id)

            # Create view
            project_view = ProjectView(view_model, self.facade)

            # Add to window
            self.window.add_project_view(project_id, project_view)

            # Update session
            self.window.session_manager.add_open_file(project_id)

            self.window.statusBar().showMessage(f"Loaded: {yaml_path.name}")

        except Exception as e:
            QMessageBox.critical(
                self.window,
                "Load Error",
                f"Failed to load project:\n{e}"
            )

    def close_project(self, project_id: str):
        """Close a project.

        Args:
            project_id: Project identifier
        """
        # Close in facade
        self.facade.close_project(project_id)

        # Remove from window
        self.window.remove_project_view(project_id)

        # Update session
        self.window.session_manager.remove_open_file(project_id)

    def autosave(self):
        """Perform autosave of current state."""
        if not self.window.project_views:
            return

        session = self._build_session_state()
        self.window.session_manager.save_session(session)

    def restore_session(self):
        """Restore previous session."""
        session = self.window.session_manager.load_session()
        if not session or not session.open_files:
            return

        # Ask user
        reply = QMessageBox.question(
            self.window,
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
                    self._restore_project_state(file_path, session)
                except Exception as e:
                    self.window.problems_widget.add_problem(
                        "ERROR",
                        f"Failed to restore {file_path}: {e}"
                    )
            else:
                self.window.problems_widget.add_problem(
                    "WARNING",
                    f"File not found: {file_path}",
                    location=file_path
                )

        # Restore window state
        self._restore_window_state(session)

    def _switch_to_existing_project(self, project_id: str):
        """Switch to already open project.

        Args:
            project_id: Project identifier
        """
        view = self.window.project_views.get(project_id)
        if view:
            index = self.window.tab_widget.indexOf(view)
            if index >= 0:
                self.window.tab_widget.setCurrentIndex(index)

    def _build_session_state(self) -> SessionState:
        """Build session state from current window.

        Returns:
            SessionState object
        """
        session = SessionState()

        # File state
        session.open_files = list(self.window.project_views.keys())
        session.active_tab = self.window.tab_widget.currentIndex()
        session.current_mode = self.window.current_mode.value

        # Window geometry
        geometry = self.window.geometry()
        session.window_geometry = {
            'x': geometry.x(),
            'y': geometry.y(),
            'width': geometry.width(),
            'height': geometry.height()
        }

        # Dock states
        session.dock_states['problems'] = self.window.problems_dock.isVisible()

        # Mask states from facade
        for project_id in session.open_files:
            try:
                project = self.facade.get_project(project_id)
                session.event_mask_states[project_id] = project.event_mask.data.tolist()
                session.capture_mask_states[project_id] = project.capture_mask.data.tolist()
            except:
                pass

        return session

    def _restore_project_state(self, project_id: str, session: SessionState):
        """Restore project state from session.

        Args:
            project_id: Project identifier
            session: Session state
        """
        try:
            project = self.facade.get_project(project_id)
            view = self.window.project_views.get(project_id)

            # Restore mask states
            if project_id in session.event_mask_states:
                event_mask_values = session.event_mask_states[project_id]
                project.event_mask.data[:] = event_mask_values[:len(project.event_mask.data)]

            if project_id in session.capture_mask_states:
                capture_mask_values = session.capture_mask_states[project_id]
                project.capture_mask.data[:] = capture_mask_values[:len(project.capture_mask.data)]

            # Refresh view
            if view:
                view.refresh()

        except Exception as e:
            logger.error(f"Failed to restore state for {project_id}: {e}")

    def _restore_window_state(self, session: SessionState):
        """Restore window state from session.

        Args:
            session: Session state
        """
        # Window geometry
        if session.window_geometry:
            self.window.setGeometry(
                session.window_geometry.get('x', 100),
                session.window_geometry.get('y', 100),
                session.window_geometry.get('width', 1400),
                session.window_geometry.get('height', 900)
            )

        # Mode
        if session.current_mode:
            mode = MaskMode(session.current_mode)
            self.window.mode_switch.set_mode(mode)
            self.window.current_mode = mode

        # Active tab
        if session.active_tab is not None:
            if session.active_tab < self.window.tab_widget.count():
                self.window.tab_widget.setCurrentIndex(session.active_tab)

"""Controller for toolbar operations."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from event_selector.presentation.gui.main_window import MainWindow
    from event_selector.presentation.gui.controllers.project_controller import ProjectController


class ToolbarController:
    """Handles toolbar creation and management."""

    def __init__(self, main_window: 'MainWindow', project_controller: 'ProjectController'):
        """Initialize toolbar controller.

        Args:
            main_window: Main window reference
            project_controller: Project controller
        """
        self.window = main_window
        self.project_controller = project_controller

    def setup_toolbar(self):
        """Setup toolbar with common actions."""
        toolbar = self.window.addToolBar("Main")
        toolbar.setMovable(False)

        # Get actions from menu controller
        menu_controller = self.window.menu_controller

        # Add common actions
        if 'open' in menu_controller.actions:
            toolbar.addAction(menu_controller.actions['open'])

        toolbar.addSeparator()

        if 'undo' in menu_controller.actions:
            toolbar.addAction(menu_controller.actions['undo'])
        if 'redo' in menu_controller.actions:
            toolbar.addAction(menu_controller.actions['redo'])

        toolbar.addSeparator()

        if 'export_event_mask' in menu_controller.actions:
            toolbar.addAction(menu_controller.actions['export_event_mask'])
        if 'export_capture_mask' in menu_controller.actions:
            toolbar.addAction(menu_controller.actions['export_capture_mask'])

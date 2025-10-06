"""Menu controller with complete import/export implementations."""

from typing import TYPE_CHECKING
from pathlib import Path

from PyQt5.QtWidgets import QAction, QMessageBox, QFileDialog
from PyQt5.QtGui import QKeySequence

from event_selector.shared.types import MaskMode

if TYPE_CHECKING:
    from event_selector.presentation.gui.main_window import MainWindow
    from event_selector.presentation.gui.controllers.project_controller import ProjectController
from event_selector.infrastructure.logging import get_logger

logger = get_logger(__name__)

class MenuController:
    """Handles menu creation and actions - COMPLETE VERSION."""

    def __init__(self, main_window: 'MainWindow', project_controller: 'ProjectController'):
        """Initialize menu controller."""
        logger.trace(f"Starting {__name__}...")
        self.window = main_window
        self.project_controller = project_controller
        self.actions = {}

    def setup_menus(self):
        """Setup all menus."""
        logger.trace(f"Starting {__name__}...")
        menubar = self.window.menuBar()

        self._setup_file_menu(menubar)
        self._setup_edit_menu(menubar)
        self._setup_view_menu(menubar)
        self._setup_help_menu(menubar)

    def _setup_file_menu(self, menubar):
        """Setup File menu."""
        logger.trace(f"Starting {__name__}...")
        file_menu = menubar.addMenu("&File")

        # Open
        self.actions['open'] = QAction("&Open YAML...", self.window)
        self.actions['open'].setShortcut(QKeySequence.Open)
        self.actions['open'].triggered.connect(
            self.project_controller.open_project_dialog
        )
        file_menu.addAction(self.actions['open'])

        # Import
        self.actions['import_event_mask'] = QAction("Import &Event Mask...", self.window)
        self.actions['import_event_mask'].triggered.connect(self._import_event_mask)
        file_menu.addAction(self.actions['import_event_mask'])

        self.actions['import_capture_mask'] = QAction("Import &Capture Mask...", self.window)
        self.actions['import_capture_mask'].triggered.connect(self._import_capture_mask)
        file_menu.addAction(self.actions['import_capture_mask'])

        file_menu.addSeparator()

        # Export
        self.actions['export_event_mask'] = QAction("Export Event Mask...", self.window)
        self.actions['export_event_mask'].setShortcut(QKeySequence("Ctrl+Shift+E"))
        self.actions['export_event_mask'].triggered.connect(self._export_event_mask)
        file_menu.addAction(self.actions['export_event_mask'])

        self.actions['export_capture_mask'] = QAction("Export Capture Mask...", self.window)
        self.actions['export_capture_mask'].triggered.connect(self._export_capture_mask)
        file_menu.addAction(self.actions['export_capture_mask'])

        self.actions['export_both'] = QAction("Export Both...", self.window)
        self.actions['export_both'].triggered.connect(self._export_both)
        file_menu.addAction(self.actions['export_both'])

        file_menu.addSeparator()

        # Exit
        self.actions['exit'] = QAction("E&xit", self.window)
        self.actions['exit'].setShortcut(QKeySequence.Quit)
        self.actions['exit'].triggered.connect(self.window.close)
        file_menu.addAction(self.actions['exit'])

    def _setup_edit_menu(self, menubar):
        """Setup Edit menu."""
        logger.trace(f"Starting {__name__}...")
        edit_menu = menubar.addMenu("&Edit")

        # Undo/Redo
        self.actions['undo'] = QAction("&Undo", self.window)
        self.actions['undo'].setShortcut(QKeySequence.Undo)
        self.actions['undo'].triggered.connect(self._undo)
        edit_menu.addAction(self.actions['undo'])

        self.actions['redo'] = QAction("&Redo", self.window)
        self.actions['redo'].setShortcut(QKeySequence.Redo)
        self.actions['redo'].triggered.connect(self._redo)
        edit_menu.addAction(self.actions['redo'])

        edit_menu.addSeparator()

        # Selection
        self.actions['select_all'] = QAction("Select &All", self.window)
        self.actions['select_all'].setShortcut(QKeySequence.SelectAll)
        self.actions['select_all'].triggered.connect(self._select_all)
        edit_menu.addAction(self.actions['select_all'])

        self.actions['clear_all'] = QAction("&Clear All", self.window)
        self.actions['clear_all'].setShortcut(QKeySequence("Ctrl+Shift+A"))
        self.actions['clear_all'].triggered.connect(self._clear_all)
        edit_menu.addAction(self.actions['clear_all'])

        edit_menu.addSeparator()

        # Special selections
        self.actions['select_errors'] = QAction("Select &Errors", self.window)
        self.actions['select_errors'].setShortcut(QKeySequence("Ctrl+E"))
        self.actions['select_errors'].triggered.connect(self._select_errors)
        edit_menu.addAction(self.actions['select_errors'])

        self.actions['select_syncs'] = QAction("Select &Syncs", self.window)
        self.actions['select_syncs'].setShortcut(QKeySequence("Ctrl+S"))
        self.actions['select_syncs'].triggered.connect(self._select_syncs)
        edit_menu.addAction(self.actions['select_syncs'])

    def _setup_view_menu(self, menubar):
        """Setup View menu."""
        logger.trace(f"Starting {__name__}...")
        view_menu = menubar.addMenu("&View")

        # Problems dock
        self.actions['toggle_problems'] = QAction("&Problems", self.window)
        self.actions['toggle_problems'].setCheckable(True)
        self.actions['toggle_problems'].setChecked(False)
        self.actions['toggle_problems'].triggered.connect(self._toggle_problems_dock)
        view_menu.addAction(self.actions['toggle_problems'])

    def _setup_help_menu(self, menubar):
        """Setup Help menu."""
        logger.trace(f"Starting {__name__}...")
        help_menu = menubar.addMenu("&Help")

        # About
        self.actions['about'] = QAction("&About", self.window)
        self.actions['about'].triggered.connect(self._show_about)
        help_menu.addAction(self.actions['about'])

    # Action handlers
    def _import_event_mask(self):
        """Import event mask file."""
        logger.trace(f"Starting {__name__}...")
        view = self.window.get_current_project_view()
        if not view:
            QMessageBox.warning(
                self.window,
                "No Project",
                "Please open a YAML file first."
            )
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self.window,
            "Import Event Mask File",
            "",
            "Event Mask Files (*.txt);;All Files (*.*)"
        )

        if file_path:
            try:
                view.import_event_mask(Path(file_path))
            except Exception as e:
                QMessageBox.critical(
                    self.window,
                    "Import Error",
                    f"Failed to import event mask:\n{e}"
                )

    def _import_capture_mask(self):
        """Import capture mask file."""
        logger.trace(f"Starting {__name__}...")
        view = self.window.get_current_project_view()
        if not view:
            QMessageBox.warning(
                self.window,
                "No Project",
                "Please open a YAML file first."
            )
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self.window,
            "Import Capture Mask File",
            "",
            "Capture Mask Files (*.txt);;All Files (*.*)"
        )

        if file_path:
            try:
                view.import_capture_mask(Path(file_path))
            except Exception as e:
                QMessageBox.critical(
                    self.window,
                    "Import Error",
                    f"Failed to import capture mask:\n{e}"
                )

    def _export_event_mask(self):
        """Export event mask file."""
        logger.trace(f"Starting {__name__}...")
        view = self.window.get_current_project_view()
        if not view:
            QMessageBox.warning(
                self.window,
                "No Project",
                "Please open a YAML file first."
            )
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self.window,
            "Export Event Mask File",
            "event_mask.txt",
            "Event Mask Files (*.txt);;All Files (*.*)"
        )

        if file_path:
            try:
                view.export_event_mask(Path(file_path))
            except Exception as e:
                QMessageBox.critical(
                    self.window,
                    "Export Error",
                    f"Failed to export event mask:\n{e}"
                )

    def _export_capture_mask(self):
        """Export capture mask file."""
        logger.trace(f"Starting {__name__}...")
        view = self.window.get_current_project_view()
        if not view:
            QMessageBox.warning(
                self.window,
                "No Project",
                "Please open a YAML file first."
            )
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self.window,
            "Export Capture Mask File",
            "capture_mask.txt",
            "Capture Mask Files (*.txt);;All Files (*.*)"
        )

        if file_path:
            try:
                view.export_capture_mask(Path(file_path))
            except Exception as e:
                QMessageBox.critical(
                    self.window,
                    "Export Error",
                    f"Failed to export capture mask:\n{e}"
                )

    def _export_both(self):
        """Export both mask and capture mask files."""
        logger.trace(f"Starting {__name__}...")
        view = self.window.get_current_project_view()
        if not view:
            QMessageBox.warning(
                self.window,
                "No Project",
                "Please open a YAML file first."
            )
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self.window,
            "Export Base Filename",
            "event_masks",
            "All Files (*.*)"
        )

        if file_path:
            try:
                view.export_both(Path(file_path))
            except Exception as e:
                QMessageBox.critical(
                    self.window,
                    "Export Error",
                    f"Failed to export files:\n{e}"
                )

    def _undo(self):
        """Undo last operation."""
        logger.trace(f"Starting {__name__}...")
        view = self.window.get_current_project_view()
        if view:
            view.undo()

    def _redo(self):
        """Redo last operation."""
        logger.trace(f"Starting {__name__}...")
        view = self.window.get_current_project_view()
        if view:
            view.redo()

    def _select_all(self):
        """Select all events."""
        logger.trace(f"Starting {__name__}...")
        view = self.window.get_current_project_view()
        if view:
            view.select_all()

    def _clear_all(self):
        """Clear all events."""
        logger.trace(f"Starting {__name__}...")
        view = self.window.get_current_project_view()
        if view:
            view.clear_all()

    def _select_errors(self):
        """Select all error events."""
        logger.trace(f"Starting {__name__}...")
        view = self.window.get_current_project_view()
        if view:
            view.select_errors()

    def _select_syncs(self):
        """Select all sync events."""
        logger.trace(f"Starting {__name__}...")
        view = self.window.get_current_project_view()
        if view:
            view.select_syncs()

    def _toggle_problems_dock(self):
        """Toggle problems dock visibility."""
        logger.trace(f"Starting {__name__}...")
        self.window.toggle_problems_dock()
        
        # Update checked state
        self.actions['toggle_problems'].setChecked(
            self.window.problems_dock.isVisible()
    )

    def _show_about(self):
        """Show about dialog."""
        logger.trace(f"Starting {__name__}...")
        try:
            from event_selector._version import version
        except ImportError:
            version = "Unknown"

        QMessageBox.about(
            self.window,
            "About Event Selector",
            f"Event Selector v{version}\n\n"
            "Hardware/Firmware Event Mask Management Tool\n\n"
            "Built with clean architecture for maintainability.\n\n"
            "© 2025"
        )

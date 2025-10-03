"""Project view - coordinates subtabs and operations."""

from pathlib import Path
from typing import Optional

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QLabel, QMessageBox
)
from PyQt5.QtCore import pyqtSignal

from event_selector.application.facades.event_selector_facade import EventSelectorFacade
from event_selector.presentation.gui.view_models.project_vm import ProjectViewModel
from event_selector.presentation.gui.views.subtab_view import SubtabView
from event_selector.shared.types import MaskMode, EventKey


class ProjectView(QWidget):
    """View for a single project - coordination only."""

    # Signals
    status_message = pyqtSignal(str)

    def __init__(self, 
                 view_model: ProjectViewModel,
                 facade: EventSelectorFacade,
                 parent=None):
        """Initialize project view.

        Args:
            view_model: Project view model
            facade: Application facade
            parent: Parent widget
        """
        super().__init__(parent)

        self.view_model = view_model
        self.facade = facade
        self.project_id = view_model.project_id

        self.subtab_views = []

        self._init_ui()

    def _init_ui(self):
        """Initialize UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Sources banner
        if self.view_model.sources:
            sources_text = "These events are used for: " + ", ".join(
                self.view_model.sources
            )
            label = QLabel(sources_text)
            label.setStyleSheet(
                "QLabel { background-color: #f0f0f0; padding: 5px; }"
            )
            layout.addWidget(label)

        # Subtab widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # Create subtab views
        for subtab_vm in self.view_model.subtabs:
            subtab_view = SubtabView(subtab_vm, self)
            subtab_view.event_toggled.connect(self._on_event_toggled)

            self.tab_widget.addTab(subtab_view, subtab_vm.name)
            self.subtab_views.append(subtab_view)

    # Event Operations
    def _on_event_toggled(self, event_key: EventKey):
        """Handle event toggle from subtab.

        Args:
            event_key: Event key that was toggled
        """
        mode = self.view_model.current_mode
        self.facade.toggle_event(self.project_id, event_key, mode)

        # Update view model
        project = self.facade.get_project(self.project_id)
        self.view_model.refresh_from_project(project)

        # Refresh views
        self.refresh()
        self.status_message.emit(f"Toggled {event_key}")

    def undo(self):
        """Undo last operation."""
        description = self.facade.undo(self.project_id)
        if description:
            # Refresh view model from project
            project = self.facade.get_project(self.project_id)
            self.view_model.refresh_from_project(project)
            self.refresh()
            self.status_message.emit(f"Undone: {description}")
        else:
            self.status_message.emit("Nothing to undo")

    def redo(self):
        """Redo last undone operation."""
        description = self.facade.redo(self.project_id)
        if description:
            project = self.facade.get_project(self.project_id)
            self.view_model.refresh_from_project(project)
            self.refresh()
            self.status_message.emit(f"Redone: {description}")
        else:
            self.status_message.emit("Nothing to redo")

    # Bulk Operations
    def select_all(self):
        """Select all events in current subtab."""
        current_view = self._get_current_subtab_view()
        if current_view:
            subtab_name = current_view.view_model.name
            self.facade.select_all_events(
                self.project_id, 
                self.view_model.current_mode,
                subtab_name
            )
            project = self.facade.get_project(self.project_id)
            self.view_model.refresh_from_project(project)
            self.refresh()
            self.status_message.emit(f"Selected all in {subtab_name}")

    def clear_all(self):
        """Clear all events in current subtab."""
        current_view = self._get_current_subtab_view()
        if current_view:
            subtab_name = current_view.view_model.name
            self.facade.clear_all_events(
                self.project_id,
                self.view_model.current_mode,
                subtab_name
            )
            project = self.facade.get_project(self.project_id)
            self.view_model.refresh_from_project(project)
            self.refresh()
            self.status_message.emit(f"Cleared all in {subtab_name}")

    def select_errors(self):
        """Select all error events."""
        current_view = self._get_current_subtab_view()
        if current_view:
            error_events = current_view.view_model.get_error_events()
            if error_events:
                # Filter to only those that are NOT checked
                to_toggle = [e.key for e in error_events if not e.is_checked]

                if to_toggle:
                    self.facade.toggle_events(
                        self.project_id,
                        to_toggle,  # Only toggle the unchecked ones
                        self.view_model.current_mode
                    )
                    project = self.facade.get_project(self.project_id)
                    self.view_model.refresh_from_project(project)
                    self.refresh()
                    self.status_message.emit(
                        f"Selected {len(to_toggle)} error events"
                    )
                else:
                    self.status_message.emit("All error events already selected")
            else:
                self.status_message.emit("No error events found")

    def select_syncs(self):
        """Select all sync events."""
        current_view = self._get_current_subtab_view()
        if current_view:
            sync_events = current_view.view_model.get_sync_events()
            if sync_events:
                # Only toggle unchecked sync events
                to_toggle = [e.key for e in sync_events if not e.is_checked]

                if to_toggle:
                    self.facade.toggle_events(
                        self.project_id,
                        to_toggle,
                        self.view_model.current_mode
                    )
                    project = self.facade.get_project(self.project_id)
                    self.view_model.refresh_from_project(project)
                    self.refresh()
                    self.status_message.emit(
                        f"Selected {len(to_toggle)} sync events"
                    )
                else:
                    self.status_message.emit("All sync events already selected")
            else:
                self.status_message.emit("No sync events found")

    # Import/Export Operations
    def import_mask(self, file_path: Path):
        """Import mask file.

        Args:
            file_path: Path to mask file
        """
        try:
            result = self.facade.import_mask(
                self.project_id,
                file_path,
                MaskMode.MASK
            )

            if result.has_errors:
                QMessageBox.warning(
                    self,
                    "Import Errors",
                    "Import completed with errors. Check Problems dock."
                )

            project = self.facade.get_project(self.project_id)
            self.view_model.refresh_from_project(project)
            self.refresh()
            self.status_message.emit("Mask imported successfully")

        except Exception as e:
            QMessageBox.critical(self, "Import Error", str(e))

    def import_trigger(self, file_path: Path):
        """Import trigger file.

        Args:
            file_path: Path to trigger file
        """
        try:
            result = self.facade.import_mask(
                self.project_id,
                file_path,
                MaskMode.TRIGGER
            )

            if result.has_errors:
                QMessageBox.warning(
                    self,
                    "Import Errors",
                    "Import completed with errors. Check Problems dock."
                )

            project = self.facade.get_project(self.project_id)
            self.view_model.refresh_from_project(project)
            self.refresh()
            self.status_message.emit("Trigger imported successfully")

        except Exception as e:
            QMessageBox.critical(self, "Import Error", str(e))

    def export_mask(self, file_path: Path):
        """Export mask file.

        Args:
            file_path: Output file path
        """
        try:
            self.facade.export_mask(
                self.project_id,
                file_path,
                MaskMode.MASK
            )
            self.status_message.emit(f"Mask exported to {file_path.name}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def export_trigger(self, file_path: Path):
        """Export trigger file.

        Args:
            file_path: Output file path
        """
        try:
            self.facade.export_mask(
                self.project_id,
                file_path,
                MaskMode.TRIGGER
            )
            self.status_message.emit(f"Trigger exported to {file_path.name}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def export_both(self, base_path: Path):
        """Export both mask and trigger files.

        Args:
            base_path: Base path for output files
        """
        try:
            base = base_path.with_suffix('')
            mask_path = base.with_name(f"{base.name}_mask.txt")
            trigger_path = base.with_name(f"{base.name}_trigger.txt")

            self.facade.export_both_masks(
                self.project_id,
                mask_path,
                trigger_path
            )

            self.status_message.emit("Exported mask and trigger files")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    # Mode Management
    def set_mode(self, mode: MaskMode):
        """Set the current mode.

        Args:
            mode: New mask mode
        """
        self.view_model.current_mode = mode

        # Refresh from project with new mode
        project = self.facade.get_project(self.project_id)
        self.view_model.refresh_from_project(project)

        # Refresh all subtab views
        self.refresh()

    def refresh(self):
        """Refresh all subtab views from view model."""
        for subtab_view in self.subtab_views:
            subtab_view.refresh()

    # Helper Methods
    def _get_current_subtab_view(self) -> Optional[SubtabView]:
        """Get the currently active subtab view.

        Returns:
            Current SubtabView or None
        """
        widget = self.tab_widget.currentWidget()
        if isinstance(widget, SubtabView):
            return widget
        return None

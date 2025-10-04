"""Project view - UPDATED to connect subtab toolbar signals."""

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
from event_selector.infrastructure.logging import get_logger

logger = get_logger(__name__)


class ProjectView(QWidget):
    """View for a single project - coordinates subtabs."""

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
        self.tab_widget.currentChanged.connect(self._on_subtab_changed)
        layout.addWidget(self.tab_widget)

        # Create subtab views with toolbars
        for subtab_vm in self.view_model.subtabs:
            subtab_view = SubtabView(subtab_vm, self)
            
            # Connect all subtab signals
            subtab_view.event_toggled.connect(self._on_event_toggled)
            subtab_view.undo_requested.connect(self.undo)
            subtab_view.redo_requested.connect(self.redo)
            subtab_view.select_all_requested.connect(self.select_all)
            subtab_view.clear_all_requested.connect(self.clear_all)
            subtab_view.select_errors_requested.connect(self.select_errors)
            subtab_view.select_syncs_requested.connect(self.select_syncs)

            self.tab_widget.addTab(subtab_view, subtab_vm.name)
            self.subtab_views.append(subtab_view)
        
        # Update undo/redo state for initial subtab
        if self.subtab_views:
            self._update_current_subtab_undo_state()

    def _on_subtab_changed(self, index: int):
        """Handle subtab change.
        
        Args:
            index: New subtab index
        """
        if 0 <= index < len(self.subtab_views):
            subtab_view = self.subtab_views[index]
            subtab_name = subtab_view.view_model.name
            
            # Notify facade of active subtab change
            self.facade.set_active_subtab(self.project_id, subtab_name)
            
            # Update undo/redo state for new subtab
            self._update_current_subtab_undo_state()
            
            logger.debug(f"Active subtab changed to: {subtab_name}")

    def _update_current_subtab_undo_state(self):
        """Update undo/redo state for current subtab."""
        current_view = self._get_current_subtab_view()
        if not current_view:
            return
        
        subtab_name = current_view.view_model.name
        
        # Get undo/redo state from facade
        can_undo = self.facade.can_undo(self.project_id, subtab_name)
        can_redo = self.facade.can_redo(self.project_id, subtab_name)
        undo_desc = self.facade.get_undo_description(self.project_id, subtab_name)
        redo_desc = self.facade.get_redo_description(self.project_id, subtab_name)
        
        # Update current subtab toolbar
        current_view.update_undo_redo_state(can_undo, can_redo, undo_desc, redo_desc)

    # Event Operations
    def _on_event_toggled(self, event_key: EventKey):
        """Handle event toggle from subtab."""
        current_view = self._get_current_subtab_view()
        if not current_view:
            return
        
        subtab_name = current_view.view_model.name
        mode = self.view_model.current_mode
        
        self.facade.toggle_event(self.project_id, event_key, mode, subtab_name)

        # Update view model
        project = self.facade.get_project(self.project_id)
        self.view_model.refresh_from_project(project)

        # Refresh current subtab
        current_view.refresh()
        
        # Update undo/redo state
        self._update_current_subtab_undo_state()
        
        self.status_message.emit(f"Toggled {event_key}")

    def undo(self):
        """Undo last operation in current subtab."""
        result = self.facade.undo(self.project_id)
        if result:
            description, subtab_name = result
            
            # Switch to target subtab if different
            self._switch_to_subtab(subtab_name)
            
            # Refresh view
            project = self.facade.get_project(self.project_id)
            self.view_model.refresh_from_project(project)
            self.refresh()
            
            # Update undo/redo state
            self._update_current_subtab_undo_state()
            
            self.status_message.emit(f"Undone: {description}")
        else:
            self.status_message.emit("Nothing to undo")

    def redo(self):
        """Redo last undone operation in current subtab."""
        result = self.facade.redo(self.project_id)
        if result:
            description, subtab_name = result
            
            # Switch to target subtab if different
            self._switch_to_subtab(subtab_name)
            
            # Refresh view
            project = self.facade.get_project(self.project_id)
            self.view_model.refresh_from_project(project)
            self.refresh()
            
            # Update undo/redo state
            self._update_current_subtab_undo_state()
            
            self.status_message.emit(f"Redone: {description}")
        else:
            self.status_message.emit("Nothing to redo")

    def _switch_to_subtab(self, subtab_name: str):
        """Switch to a specific subtab.
        
        Args:
            subtab_name: Name of subtab to switch to
        """
        for i, subtab_view in enumerate(self.subtab_views):
            if subtab_view.view_model.name == subtab_name:
                if self.tab_widget.currentIndex() != i:
                    self.tab_widget.setCurrentIndex(i)
                    logger.info(f"Switched to subtab '{subtab_name}'")
                break

    # Bulk Operations (work on current subtab)
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
            current_view.refresh()
            self._update_current_subtab_undo_state()
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
            current_view.refresh()
            self._update_current_subtab_undo_state()
            self.status_message.emit(f"Cleared all in {subtab_name}")

    def select_errors(self):
        """Select all error events in current subtab."""
        current_view = self._get_current_subtab_view()
        if current_view:
            error_events = current_view.view_model.get_error_events()
            if error_events:
                to_toggle = [e.key for e in error_events if not e.is_checked]

                if to_toggle:
                    subtab_name = current_view.view_model.name
                    self.facade.toggle_events(
                        self.project_id,
                        to_toggle,
                        self.view_model.current_mode,
                        subtab_name
                    )
                    project = self.facade.get_project(self.project_id)
                    self.view_model.refresh_from_project(project)
                    current_view.refresh()
                    self._update_current_subtab_undo_state()
                    self.status_message.emit(
                        f"Selected {len(to_toggle)} error events"
                    )
                else:
                    self.status_message.emit("All error events already selected")
            else:
                self.status_message.emit("No error events found")

    def select_syncs(self):
        """Select all sync events in current subtab."""
        current_view = self._get_current_subtab_view()
        if current_view:
            sync_events = current_view.view_model.get_sync_events()
            if sync_events:
                to_toggle = [e.key for e in sync_events if not e.is_checked]

                if to_toggle:
                    subtab_name = current_view.view_model.name
                    self.facade.toggle_events(
                        self.project_id,
                        to_toggle,
                        self.view_model.current_mode,
                        subtab_name
                    )
                    project = self.facade.get_project(self.project_id)
                    self.view_model.refresh_from_project(project)
                    current_view.refresh()
                    self._update_current_subtab_undo_state()
                    self.status_message.emit(
                        f"Selected {len(to_toggle)} sync events"
                    )
                else:
                    self.status_message.emit("All sync events already selected")
            else:
                self.status_message.emit("No sync events found")

    # Global Operations (work across all subtabs) - will be called from menu
    def select_all_errors_globally(self):
        """Select all error events across ALL subtabs."""
        total_selected = 0
        
        for subtab_view in self.subtab_views:
            error_events = subtab_view.view_model.get_error_events()
            to_toggle = [e.key for e in error_events if not e.is_checked]
            
            if to_toggle:
                subtab_name = subtab_view.view_model.name
                self.facade.toggle_events(
                    self.project_id,
                    to_toggle,
                    self.view_model.current_mode,
                    subtab_name
                )
                total_selected += len(to_toggle)
        
        if total_selected > 0:
            project = self.facade.get_project(self.project_id)
            self.view_model.refresh_from_project(project)
            self.refresh()
            self.status_message.emit(
                f"Selected {total_selected} error events across all tabs"
            )
        else:
            self.status_message.emit("All error events already selected")

    # Import/Export Operations
    def import_mask(self, file_path: Path):
        """Import mask file."""
        try:
            validation = self.facade.import_mask(
                self.project_id,
                file_path,
                MaskMode.EVENT
            )
            
            project = self.facade.get_project(self.project_id)
            self.view_model.refresh_from_project(project)
            self.refresh()
            
            if validation.has_warnings or validation.has_errors:
                msg = "Mask imported with issues:\n\n"
                for issue in validation.get_all_issues():
                    msg += f"{issue.level.value}: {issue.message}\n"
                QMessageBox.warning(self, "Import Warnings", msg)
            else:
                self.status_message.emit(f"Mask imported from {file_path.name}")
                
        except Exception as e:
            raise

    def import_capture(self, file_path: Path):
        """Import capture mask file."""
        try:
            validation = self.facade.import_mask(
                self.project_id,
                file_path,
                MaskMode.CAPTURE
            )
            
            project = self.facade.get_project(self.project_id)
            self.view_model.refresh_from_project(project)
            self.refresh()
            
            if validation.has_warnings or validation.has_errors:
                msg = "Capture mask imported with issues:\n\n"
                for issue in validation.get_all_issues():
                    msg += f"{issue.level.value}: {issue.message}\n"
                QMessageBox.warning(self, "Import Warnings", msg)
            else:
                self.status_message.emit(f"Capture mask imported from {file_path.name}")
                
        except Exception as e:
            raise

    def export_mask(self, file_path: Path):
        """Export event mask file."""
        try:
            self.facade.export_mask(
                self.project_id,
                file_path,
                MaskMode.EVENT
            )
            self.status_message.emit(f"Event mask exported to {file_path.name}")
        except Exception as e:
            raise

    def export_capture(self, file_path: Path):
        """Export capture mask file."""
        try:
            self.facade.export_mask(
                self.project_id,
                file_path,
                MaskMode.CAPTURE
            )
            self.status_message.emit(f"Capture mask exported to {file_path.name}")
        except Exception as e:
            raise

    def export_both(self, base_path: Path):
        """Export both mask files."""
        try:
            base = base_path.with_suffix('')
            mask_path = base.with_name(f"{base.name}_event.txt")
            capture_path = base.with_name(f"{base.name}_capture.txt")

            self.facade.export_both_masks(
                self.project_id,
                mask_path,
                capture_path
            )

            self.status_message.emit("Exported event and capture mask files")
        except Exception as e:
            raise

    # Mode Management
    def set_mode(self, mode: MaskMode):
        """Set the current mode."""
        self.view_model.current_mode = mode

        project = self.facade.get_project(self.project_id)
        self.view_model.refresh_from_project(project)

        self.refresh()

    def refresh(self):
        """Refresh all subtab views from view model."""
        for subtab_view in self.subtab_views:
            subtab_view.refresh()

    # Helper Methods
    def _get_current_subtab_view(self) -> Optional[SubtabView]:
        """Get the currently active subtab view."""
        widget = self.tab_widget.currentWidget()
        if isinstance(widget, SubtabView):
            return widget
        return None

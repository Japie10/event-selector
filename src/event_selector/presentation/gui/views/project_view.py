"""Project view - coordinates subtabs with per-subtab undo/redo."""

from pathlib import Path
from typing import Optional, Dict

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QMessageBox
from PyQt5.QtCore import pyqtSignal

from event_selector.application.facades.event_selector_facade import EventSelectorFacade
from event_selector.application.base import SubtabContext
from event_selector.presentation.gui.view_models.project_vm import ProjectViewModel
from event_selector.presentation.gui.views.subtab_view import SubtabView
from event_selector.shared.types import MaskMode, EventKey
from event_selector.infrastructure.logging import get_logger

logger = get_logger(__name__)


class ProjectView(QWidget):
    """View for a single project - coordinates subtabs with independent undo/redo."""

    # Signals
    status_message = pyqtSignal(str)
    tab_switch_requested = pyqtSignal(int)  # NEW: for auto tab switching

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
        logger.trace(f"Starting {__name__}...")

        self.view_model = view_model
        self.facade = facade
        self.project_id = view_model.project_id
        self.subtab_views: Dict[str, SubtabView] = {}
        self.current_mode = MaskMode.EVENT

        self._init_ui()
        self._setup_tab_switch_callback()

    def _init_ui(self):
        """Initialize UI."""
        logger.trace(f"Starting {__name__}...")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create tab widget for subtabs
        self.tab_widget = QTabWidget()
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tab_widget)

        # Create a subtab view for each subtab in the view model
        for idx, subtab_vm in enumerate(self.view_model.subtabs):
            subtab_view = SubtabView(
                project_id=self.project_id,
                subtab_name=subtab_vm.name,
                subtab_index=idx,
                parent=self
            )
            
            # Store reference
            self.subtab_views[subtab_vm.name] = subtab_view
            
            # Connect toolbar signals to handlers
            self._connect_subtab_signals(subtab_view)
            
            # Add to tab widget
            self.tab_widget.addTab(subtab_view, subtab_vm.name)
            
            # Initial refresh
            subtab_view.refresh_from_model(subtab_vm, self.current_mode)
            
            # Update initial undo/redo state
            self._update_subtab_undo_redo_state(subtab_vm.name)

    def _setup_tab_switch_callback(self):
        """Setup callback for auto tab switching on undo/redo."""
        logger.trace(f"Starting {__name__}...")
        def switch_callback(subtab_name: str, subtab_index: int):
            """Called when undo/redo needs to switch tabs."""
            logger.debug(f"Auto-switching to subtab: {subtab_name} (index {subtab_index})")
            self.tab_widget.setCurrentIndex(subtab_index)
        
        self.facade.set_tab_switch_callback(self.project_id, switch_callback)

    def _connect_subtab_signals(self, subtab_view: SubtabView):
        """Connect subtab toolbar signals to command handlers.
        
        Args:
            subtab_view: The subtab view to connect
        """
        logger.trace(f"Starting {__name__}...")
        toolbar = subtab_view.toolbar
        
        # Undo/Redo
        toolbar.undo_clicked.connect(
            lambda: self._handle_undo(subtab_view)
        )
        toolbar.redo_clicked.connect(
            lambda: self._handle_redo(subtab_view)
        )
        
        # Selection operations
        toolbar.select_all_clicked.connect(
            lambda: self._handle_select_all(subtab_view)
        )
        toolbar.clear_all_clicked.connect(
            lambda: self._handle_clear_all(subtab_view)
        )
        toolbar.select_errors_clicked.connect(
            lambda: self._handle_select_errors(subtab_view)
        )
        toolbar.select_syncs_clicked.connect(
            lambda: self._handle_select_syncs(subtab_view)
        )
        
        # Event toggling
        subtab_view.event_toggled.connect(
            lambda event_key: self._handle_event_toggle(subtab_view, event_key)
        )

    def _handle_undo(self, subtab_view: SubtabView):
        """Handle undo button click.
        
        Args:
            subtab_view: The subtab where undo was clicked
        """
        logger.trace(f"Starting {__name__}...")
        context = subtab_view.get_context()
        
        try:
            description = self.facade.undo(self.project_id, context)
            
            if description:
                self.status_message.emit(f"Undone: {description}")
                
                # Refresh all subtabs (the command may have affected this or another subtab)
                self._refresh_all_subtabs()
                
                # Update undo/redo states for all subtabs
                self._update_all_undo_redo_states()
            else:
                self.status_message.emit("Nothing to undo")
                
        except Exception as e:
            logger.error(f"Undo failed: {e}", exc_info=True)
            QMessageBox.warning(self, "Undo Failed", str(e))

    def _handle_redo(self, subtab_view: SubtabView):
        """Handle redo button click.
        
        Args:
            subtab_view: The subtab where redo was clicked
        """
        logger.trace(f"Starting {__name__}...")
        context = subtab_view.get_context()
        
        try:
            description = self.facade.redo(self.project_id, context)
            
            if description:
                self.status_message.emit(f"Redone: {description}")
                self._refresh_all_subtabs()
                self._update_all_undo_redo_states()
            else:
                self.status_message.emit("Nothing to redo")
                
        except Exception as e:
            logger.error(f"Redo failed: {e}", exc_info=True)
            QMessageBox.warning(self, "Redo Failed", str(e))

    def _handle_select_all(self, subtab_view: SubtabView):
        """Handle select all button click.
        
        Args:
            subtab_view: The subtab where select all was clicked
        """
        logger.trace(f"Starting {__name__}...")
        context = subtab_view.get_context()
        
        try:
            self.facade.select_all_events(
                self.project_id, 
                self.current_mode, 
                context
            )
            
            self.status_message.emit(f"Selected all events in {subtab_view.subtab_name}")
            self._refresh_subtab(subtab_view.subtab_name)
            self._update_subtab_undo_redo_state(subtab_view.subtab_name)
            
        except Exception as e:
            logger.error(f"Select all failed: {e}", exc_info=True)
            QMessageBox.warning(self, "Select All Failed", str(e))

    def _handle_clear_all(self, subtab_view: SubtabView):
        """Handle clear all button click.
        
        Args:
            subtab_view: The subtab where clear all was clicked
        """
        logger.trace(f"Starting {__name__}...")
        context = subtab_view.get_context()
        
        try:
            self.facade.clear_all_events(
                self.project_id, 
                self.current_mode, 
                context
            )
            
            self.status_message.emit(f"Cleared all events in {subtab_view.subtab_name}")
            self._refresh_subtab(subtab_view.subtab_name)
            self._update_subtab_undo_redo_state(subtab_view.subtab_name)
            
        except Exception as e:
            logger.error(f"Clear all failed: {e}", exc_info=True)
            QMessageBox.warning(self, "Clear All Failed", str(e))

    def _handle_select_errors(self, subtab_view: SubtabView):
        """Handle select errors button click.
        
        Args:
            subtab_view: The subtab where select errors was clicked
        """
        logger.trace(f"Starting {__name__}...")
        # TODO: Implement SelectErrorsCommand
        self.status_message.emit("Select errors not yet implemented")

    def _handle_select_syncs(self, subtab_view: SubtabView):
        """Handle select syncs button click.
        
        Args:
            subtab_view: The subtab where select syncs was clicked
        """
        logger.trace(f"Starting {__name__}...")
        # TODO: Implement SelectSyncsCommand
        self.status_message.emit("Select syncs not yet implemented")

    def _handle_event_toggle(self, subtab_view: SubtabView, event_key: EventKey):
        """Handle event toggle from table.
        
        Args:
            subtab_view: The subtab where event was toggled
            event_key: Key of the toggled event
        """
        logger.trace(f"Starting {__name__}...")
        context = subtab_view.get_context()
        
        try:
            self.facade.toggle_event(
                self.project_id,
                event_key,
                self.current_mode,
                context
            )
            
            # Refresh just this subtab
            self._refresh_subtab(subtab_view.subtab_name)
            self._update_subtab_undo_redo_state(subtab_view.subtab_name)
            
        except Exception as e:
            logger.error(f"Toggle event failed: {e}", exc_info=True)

    def _on_tab_changed(self, index: int):
        """Handle tab change.
        
        Args:
            index: New tab index
        """
        logger.trace(f"Starting {__name__}...")
        if index >= 0 and index < len(self.view_model.subtabs):
            subtab_name = self.view_model.subtabs[index].name
            logger.debug(f"Switched to subtab: {subtab_name}")
            
            # Update undo/redo state for the new current tab
            self._update_subtab_undo_redo_state(subtab_name)

    def _refresh_subtab(self, subtab_name: str):
        """Refresh a single subtab from the domain model.
        
        Args:
            subtab_name: Name of subtab to refresh
        """
        logger.trace(f"Starting {__name__}...")
        if subtab_name not in self.subtab_views:
            return
        
        # Get updated view model for this subtab
        subtab_vm = next(
            (st for st in self.view_model.subtabs if st.name == subtab_name),
            None
        )
        
        if subtab_vm:
            self.subtab_views[subtab_name].refresh_from_model(
                subtab_vm, 
                self.current_mode
            )

    def _refresh_all_subtabs(self):
        """Refresh all subtabs from the domain model."""
        logger.trace(f"Starting {__name__}...")
        for subtab_vm in self.view_model.subtabs:
            self._refresh_subtab(subtab_vm.name)

    def _update_subtab_undo_redo_state(self, subtab_name: str):
        """Update undo/redo button states for a subtab.
        
        Args:
            subtab_name: Name of subtab to update
        """
        logger.trace(f"Starting {__name__}...")
        if subtab_name not in self.subtab_views:
            return
        
        subtab_view = self.subtab_views[subtab_name]
        
        # Get undo/redo availability and descriptions
        can_undo = self.facade.can_undo(self.project_id, subtab_name)
        can_redo = self.facade.can_redo(self.project_id, subtab_name)
        
        undo_desc = self.facade.get_undo_description(self.project_id, subtab_name)
        redo_desc = self.facade.get_redo_description(self.project_id, subtab_name)
        
        # Update the toolbar
        subtab_view.update_undo_redo_state(
            can_undo, can_redo, undo_desc, redo_desc
        )

    def _update_all_undo_redo_states(self):
        """Update undo/redo states for all subtabs."""
        logger.trace(f"Starting {__name__}...")
        for subtab_vm in self.view_model.subtabs:
            self._update_subtab_undo_redo_state(subtab_vm.name)

    def set_mode(self, mode: MaskMode):
        """Change the active mask mode.
        
        Args:
            mode: New mask mode (EVENT or CAPTURE)
        """
        logger.trace(f"Starting {__name__}...")
        if mode != self.current_mode:
            self.current_mode = mode
            self._refresh_all_subtabs()
            self.status_message.emit(f"Switched to {mode.value} mode")

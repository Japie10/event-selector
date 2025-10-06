"""Event Selector Facade - Application layer interface."""

from pathlib import Path
from typing import Dict, List, Optional, Tuple, Callable

from event_selector.application.commands.base import (
    Command, CommandStack, MacroCommand, SubtabCommandStack, SubtabContext
)
from event_selector.application.commands.toggle_event import ToggleEventCommand
from event_selector.application.commands.bulk_operations import (
    SelectAllCommand, ClearAllCommand
)
from event_selector.domain.models.base import Project
from event_selector.domain.interfaces.format_strategy import ValidationResult
from event_selector.infrastructure.parser.yaml_parser import YamlParser
from event_selector.infrastructure.export.mask_exporter import MaskExporter
from event_selector.infrastructure.import.mask_importer import MaskImporter
from event_selector.shared.types import EventKey, MaskMode
from event_selector.infrastructure.logging import get_logger

logger = get_logger(__name__)


class EventSelectorFacade:
    """Main application facade with per-subtab undo/redo support."""

    def __init__(self):
        self._projects: Dict[str, Project] = {}
        
        self._subtab_stacks: Dict[str, SubtabCommandStack] = {}
        
        self._parser = YamlParser()
        self._exporter = MaskExporter()
        self._importer = MaskImporter()

    def load_project(self, yaml_path: Path) -> Tuple[Project, ValidationResult]:
        """Load a project from YAML file.
        
        Args:
            yaml_path: Path to YAML file
            
        Returns:
            Tuple of (Project instance, ValidationResult)
        """
        project_id = str(yaml_path)
        
        # Parse YAML
        project, validation = self._parser.parse_file(yaml_path)
        
        # Store project
        self._projects[project_id] = project
        
        # Initialize subtab command stack for this project
        self._subtab_stacks[project_id] = SubtabCommandStack(max_size_per_subtab=100)
        
        logger.info(f"Loaded project: {yaml_path}")
        return project, validation

    def set_tab_switch_callback(
        self, 
        project_id: str, 
        callback: Callable[[str, int], None]
    ) -> None:
        """Set callback for auto tab switching.
        
        Args:
            project_id: Project identifier
            callback: Function that switches tabs (subtab_name, subtab_index)
        """
        if project_id in self._subtab_stacks:
            self._subtab_stacks[project_id].set_tab_switch_callback(callback)

    def get_project(self, project_id: str) -> Project:
        """Get a project by ID.
        
        Args:
            project_id: Project identifier
            
        Returns:
            Project instance
            
        Raises:
            KeyError: If project not found
        """
        if project_id not in self._projects:
            raise KeyError(f"Project not found: {project_id}")
        return self._projects[project_id]

    def toggle_event(
        self, 
        project_id: str, 
        event_key: EventKey, 
        mode: MaskMode,
        context: SubtabContext
    ) -> None:
        """Toggle a single event.
        
        Args:
            project_id: Project identifier
            event_key: Event key to toggle
            mode: Mask mode (EVENT or CAPTURE)
            context: Subtab context for undo/redo
        """
        project = self.get_project(project_id)
        command = ToggleEventCommand(project, event_key, mode)

        stack = self._get_subtab_stack(project_id)
        stack.push(command, context)
        
        logger.debug(f"Toggled event {event_key} in {context.subtab_name}")

    def toggle_events(
        self, 
        project_id: str, 
        event_keys: List[EventKey], 
        mode: MaskMode,
        context: SubtabContext
    ) -> None:
        """Toggle multiple events as one operation.
        
        Args:
            project_id: Project identifier
            event_keys: List of event keys to toggle
            mode: Mask mode (EVENT or CAPTURE)
            context: Subtab context for undo/redo
        """
        project = self.get_project(project_id)
        commands = [
            ToggleEventCommand(project, key, mode) 
            for key in event_keys
        ]
        macro = MacroCommand(commands, f"Toggle {len(event_keys)} events")

        stack = self._get_subtab_stack(project_id)
        stack.push(macro, context)
        
        logger.debug(f"Toggled {len(event_keys)} events in {context.subtab_name}")

    def select_all_events(
        self, 
        project_id: str, 
        mode: MaskMode, 
        context: SubtabContext
    ) -> None:
        """Select all events in a subtab.
        
        Args:
            project_id: Project identifier
            mode: Mask mode (EVENT or CAPTURE)
            context: Subtab context for undo/redo
        """
        project = self.get_project(project_id)
        command = SelectAllCommand(project, mode, context.subtab_name)

        stack = self._get_subtab_stack(project_id)
        stack.push(command, context)
        
        logger.debug(f"Selected all events in {context.subtab_name}")

    def clear_all_events(
        self, 
        project_id: str, 
        mode: MaskMode, 
        context: SubtabContext
    ) -> None:
        """Clear all events in a subtab.
        
        Args:
            project_id: Project identifier
            mode: Mask mode (EVENT or CAPTURE)
            context: Subtab context for undo/redo
        """
        project = self.get_project(project_id)
        command = ClearAllCommand(project, mode, context.subtab_name)

        stack = self._get_subtab_stack(project_id)
        stack.push(command, context)
        
        logger.debug(f"Cleared all events in {context.subtab_name}")

    def undo(
        self, 
        project_id: str, 
        context: SubtabContext
    ) -> Optional[str]:
        """Undo last operation in current subtab.
        
        May auto-switch tabs if last operation was in a different subtab.
        
        Args:
            project_id: Project identifier
            context: Current subtab context
            
        Returns:
            Description of undone command, or None if nothing to undo
        """
        stack = self._get_subtab_stack(project_id)
        command = stack.undo(context.subtab_name, context)
        
        if command:
            description = command.get_description()
            logger.debug(f"Undone: {description}")
            return description
        return None

    def redo(
        self, 
        project_id: str, 
        context: SubtabContext
    ) -> Optional[str]:
        """Redo last undone operation in current subtab.
        
        Args:
            project_id: Project identifier
            context: Current subtab context
            
        Returns:
            Description of redone command, or None if nothing to redo
        """
        stack = self._get_subtab_stack(project_id)
        command = stack.redo(context.subtab_name, context)
        
        if command:
            description = command.get_description()
            logger.debug(f"Redone: {description}")
            return description
        return None

    def can_undo(self, project_id: str, subtab_name: str) -> bool:
        """Check if undo is available for a subtab.
        
        Args:
            project_id: Project identifier
            subtab_name: Name of the subtab
            
        Returns:
            True if undo is available
        """
        stack = self._get_subtab_stack(project_id)
        return stack.can_undo(subtab_name)

    def can_redo(self, project_id: str, subtab_name: str) -> bool:
        """Check if redo is available for a subtab.
        
        Args:
            project_id: Project identifier
            subtab_name: Name of the subtab
            
        Returns:
            True if redo is available
        """
        stack = self._get_subtab_stack(project_id)
        return stack.can_redo(subtab_name)

    def get_undo_description(self, project_id: str, subtab_name: str) -> Optional[str]:
        """Get description of command that would be undone.
        
        Args:
            project_id: Project identifier
            subtab_name: Name of the subtab
            
        Returns:
            Description string or None
        """
        stack = self._get_subtab_stack(project_id)
        return stack.get_undo_description(subtab_name)

    def get_redo_description(self, project_id: str, subtab_name: str) -> Optional[str]:
        """Get description of command that would be redone.
        
        Args:
            project_id: Project identifier
            subtab_name: Name of the subtab
            
        Returns:
            Description string or None
        """
        stack = self._get_subtab_stack(project_id)
        return stack.get_redo_description(subtab_name)

    def _get_subtab_stack(self, project_id: str) -> SubtabCommandStack:
        """Get or create subtab command stack for project.
        
        Args:
            project_id: Project identifier
            
        Returns:
            SubtabCommandStack instance
        """
        if project_id not in self._subtab_stacks:
            self._subtab_stacks[project_id] = SubtabCommandStack(max_size_per_subtab=100)
        return self._subtab_stacks[project_id]

    def import_mask(self, project_id: str, file_path: Path, mode: MaskMode) -> ValidationResult:
        """Import mask from file."""
        project = self.get_project(project_id)
        mask_data = self._importer.import_file(file_path)

        # Update project mask
        if mode == MaskMode.MASK:
            project.event_mask.data[:] = mask_data.data
        else:
            project.capture_mask.data[:] = mask_data.data

        return self._importer.validation_result

    def export_mask(self, project_id: str, file_path: Path, mode: MaskMode):
        """Export mask to file."""
        project = self.get_project(project_id)
        mask_data = project.get_active_mask(mode)

        self._exporter.export_file(
            mask_data,
            file_path,
            include_metadata=True,
            yaml_file=project.yaml_path
        )

    def export_both_masks(self, project_id: str, mask_path: Path, trigger_path: Path):
        """Export both event mask and capture mask."""
        self.export_mask(project_id, mask_path, MaskMode.EVENT)
        self.export_mask(project_id, trigger_path, MaskMode.CAPTURE)

    def _get_command_stack(self, project_id: str) -> CommandStack:
        """Get or create command stack for project."""
        if project_id not in self._command_stacks:
            self._command_stacks[project_id] = CommandStack(max_size=100)
        return self._command_stacks[project_id]

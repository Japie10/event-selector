from event_selector.application.commands.toggle_event import ToggleEventCommand
from event_selector.application.commands.bulk_operations import (
    SelectAllCommand, ClearAllCommand
)
from event_selector.domain.models.base import Project
from event_selector.domain.interfaces.format_strategy import ValidationResult
from event_selector.application.base import Command, CommandStack, MacroCommand
from event_selector.infrastructure.parser.yaml_parser import YamlParser
from event_selector.infrastructure.export.mask_exporter import MaskExporter
from event_selector.infrastructure.import.mask_importer import MaskImporter

class EventSelectorFacade:
    """Main application facade."""

    def __init__(self):
        self._projects: Dict[str, Project] = {}
        self._command_stacks: Dict[str, CommandStack] = {}
        self._parser = YamlParser()
        self._exporter = MaskExporter()
        self._importer = MaskImporter()

    def get_project(self, project_id: str) -> Project:
        """Get a project by ID."""
        if project_id not in self._projects:
            raise KeyError(f"Project not found: {project_id}")
        return self._projects[project_id]

    def toggle_event(self, project_id: str, event_key: EventKey, mode: MaskMode):
        """Toggle a single event."""
        project = self.get_project(project_id)
        command = ToggleEventCommand(project, event_key, mode)

        stack = self._get_command_stack(project_id)
        stack.push(command)

    def toggle_events(self, project_id: str, event_keys: List[EventKey], mode: MaskMode):
        """Toggle multiple events as one operation."""
        project = self.get_project(project_id)
        commands = [
            ToggleEventCommand(project, key, mode) 
            for key in event_keys
        ]
        macro = MacroCommand(commands, f"Toggle {len(event_keys)} events")

        stack = self._get_command_stack(project_id)
        stack.push(macro)

    def select_all_events(self, project_id: str, mode: MaskMode, subtab_name: str):
        """Select all events in a subtab."""
        project = self.get_project(project_id)
        command = SelectAllCommand(project, mode, subtab_name)

        stack = self._get_command_stack(project_id)
        stack.push(command)

    def clear_all_events(self, project_id: str, mode: MaskMode, subtab_name: str):
        """Clear all events in a subtab."""
        project = self.get_project(project_id)
        command = ClearAllCommand(project, mode, subtab_name)

        stack = self._get_command_stack(project_id)
        stack.push(command)

    def undo(self, project_id: str) -> Optional[str]:
        """Undo last operation."""
        stack = self._get_command_stack(project_id)
        command = stack.undo()
        return command.get_description() if command else None

    def redo(self, project_id: str) -> Optional[str]:
        """Redo last undone operation."""
        stack = self._get_command_stack(project_id)
        command = stack.redo()
        return command.get_description() if command else None

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

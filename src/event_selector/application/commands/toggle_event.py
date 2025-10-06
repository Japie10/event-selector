from event_selector.application.base import Command
from event_selector.domain.models.base import Project
from event_selector.shared.types import EventKey, MaskMode

class ToggleEventCommand(Command):
    """Command to toggle a single event."""

    def __init__(self, project: Project, event_key: EventKey, mode: MaskMode):
        super().__init__(f"Toggle {event_key}")
        logger.trace(f"Starting {__name__}...")
        self.project = project
        self.event_key = event_key
        self.mode = mode

    def execute(self):
        """Toggle the event."""
        logger.trace(f"Starting {__name__}...")
        self.project.toggle_event(self.event_key, self.mode)

    def undo(self):
        """Toggle back (toggle is its own inverse)."""
        logger.trace(f"Starting {__name__}...")
        self.project.toggle_event(self.event_key, self.mode)

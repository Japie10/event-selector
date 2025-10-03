class SelectAllCommand(Command):
    """Command to select all events in a subtab."""

    def __init__(self, project: Project, mode: MaskMode, subtab_name: str):
        super().__init__(f"Select all in {subtab_name}")
        self.project = project
        self.mode = mode
        self.subtab_name = subtab_name
        self._previous_state = None

    def execute(self):
        """Select all events."""
        mask = self.project.get_active_mask(self.mode)
        self._previous_state = mask.data.copy()

        # Get events for subtab and set all bits
        events = self._get_subtab_events()
        for event in events:
            coord = event.get_coordinate()
            mask.set_bit(coord.id, coord.bit, True)

    def undo(self):
        """Restore previous state."""
        if self._previous_state is not None:
            mask = self.project.get_active_mask(self.mode)
            mask.data[:] = self._previous_state

    def _get_subtab_events(self):
        """Get events for the subtab."""
        format_obj = self.project.format

        if isinstance(format_obj, Mk1Format):
            return format_obj.get_events_by_subtab(self.subtab_name).values()
        elif isinstance(format_obj, Mk2Format):
            # Extract ID from subtab name
            # Implementation depends on naming convention
            pass


class ClearAllCommand(Command):
    """Command to clear all events in a subtab."""

    def __init__(self, project: Project, mode: MaskMode, subtab_name: str):
        super().__init__(f"Clear all in {subtab_name}")
        self.project = project
        self.mode = mode
        self.subtab_name = subtab_name
        self._previous_state = None

    def execute(self):
        """Clear all events."""
        mask = self.project.get_active_mask(self.mode)
        self._previous_state = mask.data.copy()

        # Get events for subtab and clear all bits
        events = self._get_subtab_events()
        for event in events:
            coord = event.get_coordinate()
            mask.set_bit(coord.id, coord.bit, False)

    def undo(self):
        """Restore previous state."""
        if self._previous_state is not None:
            mask = self.project.get_active_mask(self.mode)
            mask.data[:] = self._previous_state

    def _get_subtab_events(self):
        """Get events for the subtab."""
        # Same as SelectAllCommand
        pass

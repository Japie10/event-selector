"""Bulk operations commands"""

import re
from typing import List

from event_selector.application.base import Command
from event_selector.domain.models.base import Project, Event
from event_selector.domain.models.mk1 import Mk1Format
from event_selector.domain.models.mk2 import Mk2Format
from event_selector.shared.types import MaskMode
from event_selector.infrastructure.logging import get_logger

logger = get_logger(__name__)


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

        logger.debug(f"Selected {len(events)} events in {self.subtab_name}")

    def undo(self):
        """Restore previous state."""
        if self._previous_state is not None:
            mask = self.project.get_active_mask(self.mode)
            mask.data[:] = self._previous_state
            logger.debug(f"Undone select all in {self.subtab_name}")

    def _get_subtab_events(self) -> List[Event]:
        """Get events for the subtab.

        Returns:
            List of Event objects for this subtab
        """
        format_obj = self.project.format

        if isinstance(format_obj, Mk1Format):
            # MK1: get by subtab name directly
            events_dict = format_obj.get_events_by_subtab(self.subtab_name)
            return list(events_dict.values())

        elif isinstance(format_obj, Mk2Format):
            # MK2: extract ID from subtab name
            # Expected formats: "Data (0x00)", "Network (0x01)", or just "ID 0x00"
            id_num = self._extract_id_from_name(self.subtab_name)

            if id_num is not None:
                events_dict = format_obj.get_events_by_id(id_num)
                return list(events_dict.values())
            else:
                logger.warning(f"Could not extract ID from subtab name: {self.subtab_name}")
                return []

        return []

    def _extract_id_from_name(self, name: str) -> int:
        """Extract ID number from subtab name.

        Args:
            name: Subtab name (e.g., "Data (0x00)" or "ID 0x0F")

        Returns:
            ID number (0-15) or None if not found
        """
        # Try pattern: "Name (0xNN)"
        match = re.search(r'\(0x([0-9A-Fa-f]{1,2})\)', name)
        if match:
            return int(match.group(1), 16)

        # Try pattern: "ID 0xNN" or "ID NN"
        match = re.search(r'ID\s+(?:0x)?([0-9A-Fa-f]{1,2})', name, re.IGNORECASE)
        if match:
            return int(match.group(1), 16)

        # If no match found, return None
        return None


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

        logger.debug(f"Cleared {len(events)} events in {self.subtab_name}")

    def undo(self):
        """Restore previous state."""
        if self._previous_state is not None:
            mask = self.project.get_active_mask(self.mode)
            mask.data[:] = self._previous_state
            logger.debug(f"Undone clear all in {self.subtab_name}")

    def _get_subtab_events(self) -> List[Event]:
        """Get events for the subtab.

        Returns:
            List of Event objects for this subtab
        """
        format_obj = self.project.format

        if isinstance(format_obj, Mk1Format):
            events_dict = format_obj.get_events_by_subtab(self.subtab_name)
            return list(events_dict.values())

        elif isinstance(format_obj, Mk2Format):
            id_num = self._extract_id_from_name(self.subtab_name)

            if id_num is not None:
                events_dict = format_obj.get_events_by_id(id_num)
                return list(events_dict.values())
            else:
                logger.warning(f"Could not extract ID from subtab name: {self.subtab_name}")
                return []

        return []

    def _extract_id_from_name(self, name: str) -> int:
        """Extract ID number from subtab name.

        Args:
            name: Subtab name

        Returns:
            ID number (0-15) or None if not found
        """
        # Try pattern: "Name (0xNN)"
        match = re.search(r'\(0x([0-9A-Fa-f]{1,2})\)', name)
        if match:
            return int(match.group(1), 16)

        # Try pattern: "ID 0xNN" or "ID NN"
        match = re.search(r'ID\s+(?:0x)?([0-9A-Fa-f]{1,2})', name, re.IGNORECASE)
        if match:
            return int(match.group(1), 16)

        return None

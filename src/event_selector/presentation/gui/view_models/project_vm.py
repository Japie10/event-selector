"""View models for presentation layer."""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from event_selector.shared.types import EventKey, FormatType, MaskMode


@dataclass
class EventRowViewModel:
    """View model for a single event row in the table."""

    key: EventKey
    is_checked: bool
    id_or_addr: str  # Display value (address for MK1, ID for MK2)
    bit: int
    source: str
    description: str
    info: str

    # Computed properties for filtering
    is_error: bool = False
    is_sync: bool = False

    def __post_init__(self):
        """Compute derived properties."""
        info_lower = self.info.lower()
        self.is_error = 'error' in info_lower
        self.is_sync = any(
            term in info_lower 
            for term in ['sync', 'sbs', 'sws', 'ebs']
        )


@dataclass
class SubtabViewModel:
    """View model for a subtab."""

    name: str
    subtab_id: int  # ID number or range identifier
    events: List[EventRowViewModel] = field(default_factory=list)

    # UI state
    scroll_position: int = 0
    selected_rows: List[int] = field(default_factory=list)

    def get_error_events(self) -> List[EventRowViewModel]:
        """Get all events marked as errors."""
        return [e for e in self.events if e.is_error]

    def get_sync_events(self) -> List[EventRowViewModel]:
        """Get all events marked as sync."""
        return [e for e in self.events if e.is_sync]

    def get_checked_events(self) -> List[EventRowViewModel]:
        """Get all checked events."""
        return [e for e in self.events if e.is_checked]

    def count_checked(self) -> int:
        """Count checked events."""
        return sum(1 for e in self.events if e.is_checked)


@dataclass
class ProjectViewModel:
    """View model for an entire project."""

    project_id: str
    format_type: FormatType
    sources: List[str] = field(default_factory=list)  # Source names
    subtabs: List[SubtabViewModel] = field(default_factory=list)

    # UI state
    active_subtab: int = 0
    current_mode: MaskMode = MaskMode.MASK

    @classmethod
    def from_project(cls, project, project_id: str) -> 'ProjectViewModel':
        """Create view model from domain project.

        Args:
            project: Domain project object
            project_id: Project identifier

        Returns:
            ProjectViewModel instance
        """
        vm = cls(
            project_id=project_id,
            format_type=project.format.format_type,
            sources=[s.name for s in project.format.sources]
        )

        # Build subtabs based on format
        subtab_config = project.format.get_subtab_config()

        if project.format.format_type == FormatType.MK1:
            vm.subtabs = cls._build_mk1_subtabs(project, subtab_config)
        elif project.format.format_type == FormatType.MK2:
            vm.subtabs = cls._build_mk2_subtabs(project, subtab_config)

        return vm

    @staticmethod
    def _build_mk1_subtabs(project, config) -> List[SubtabViewModel]:
        """Build subtabs for MK1 format."""
        from event_selector.domain.models.mk1 import Mk1Format

        subtabs = []
        mk1_format = project.format

        for subtab_info in config['subtabs']:
            name = subtab_info['name']
            events = mk1_format.get_events_by_subtab(name)

            # Convert to view models
            event_rows = []
            for key, event in events.items():
                coord = event.get_coordinate()

                # Check if bit is set in current mask
                is_checked = project.event_mask.get_bit(coord.id, coord.bit)

                row = EventRowViewModel(
                    key=key,
                    is_checked=is_checked,
                    id_or_addr=event.address.hex,
                    bit=coord.bit,
                    source=event.info.source,
                    description=event.info.description,
                    info=event.info.info
                )
                event_rows.append(row)

            # Sort by address
            event_rows.sort(key=lambda r: r.id_or_addr)

            subtab = SubtabViewModel(
                name=name,
                subtab_id=subtab_info['ids'][0],
                events=event_rows
            )
            subtabs.append(subtab)

        return subtabs

    @staticmethod
    def _build_mk2_subtabs(project, config) -> List[SubtabViewModel]:
        """Build subtabs for MK2 format."""
        from event_selector.domain.models.mk2 import Mk2Format

        subtabs = []
        mk2_format = project.format

        for subtab_info in config['subtabs']:
            name = subtab_info['name']
            id_num = subtab_info['id']

            events = mk2_format.get_events_by_id(id_num)

            # Convert to view models
            event_rows = []
            for key, event in events.items():
                coord = event.get_coordinate()

                # Check if bit is set in current mask
                is_checked = project.event_mask.get_bit(coord.id, coord.bit)

                row = EventRowViewModel(
                    key=key,
                    is_checked=is_checked,
                    id_or_addr=f"{coord.id:02X}",
                    bit=coord.bit,
                    source=event.info.source,
                    description=event.info.description,
                    info=event.info.info
                )
                event_rows.append(row)

            # Sort by bit
            event_rows.sort(key=lambda r: r.bit)

            subtab = SubtabViewModel(
                name=name,
                subtab_id=id_num,
                events=event_rows
            )
            subtabs.append(subtab)

        return subtabs

    def get_subtab(self, index: int) -> Optional[SubtabViewModel]:
        """Get subtab by index.

        Args:
            index: Subtab index

        Returns:
            SubtabViewModel or None
        """
        if 0 <= index < len(self.subtabs):
            return self.subtabs[index]
        return None

    def get_active_subtab(self) -> Optional[SubtabViewModel]:
        """Get the currently active subtab.

        Returns:
            Active SubtabViewModel or None
        """
        return self.get_subtab(self.active_subtab)

    def update_event_state(self, key: EventKey, is_checked: bool):
        """Update the checked state of an event.

        Args:
            key: Event key
            is_checked: New checked state
        """
        for subtab in self.subtabs:
            for event in subtab.events:
                if event.key == key:
                    event.is_checked = is_checked
                    return

    def refresh_from_project(self, project):
        """Refresh view model from updated project.

        Args:
            project: Updated domain project
        """
        for subtab in self.subtabs:
            for event in subtab.events:
                # Find corresponding domain event
                domain_event = project.format.get_event(event.key)
                if domain_event:
                    coord = domain_event.get_coordinate()

                    # Update checked state from mask
                    if self.current_mode == MaskMode.MASK:
                        event.is_checked = project.event_mask.get_bit(
                            coord.id, coord.bit
                        )
                    else:
                        event.is_checked = project.capture_mask.get_bit(
                            coord.id, coord.bit
                        )

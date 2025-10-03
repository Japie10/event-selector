"""MK2 format domain models."""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List

from event_selector.shared.types import (
    EventKey, EventID, BitPosition, FormatType,
    EventCoordinate, MK2_MAX_ID, MK2_MAX_BIT
)
from event_selector.domain.models.base import Event, EventFormat
from event_selector.domain.models.value_objects import EventInfo, EventSource
from event_selector.domain.interfaces.format_strategy import (
    ValidationResult, ValidationCode, ValidationLevel
)


@dataclass
class Mk2Event(Event):
    """MK2 format event."""

    key: EventKey  # e.g., "0x01C" means ID 1, bit 28
    info: EventInfo
    _id: Optional[int] = None
    _bit: Optional[int] = None

    def __post_init__(self):
        """Parse key into ID and bit."""
        if self._id is None or self._bit is None:
            # Parse key: 0xABC where A = ID high nibble, B = ID low nibble, C = bit
            key_int = int(self.key, 16) if isinstance(self.key, str) else self.key
            self._id = (key_int >> 8) & 0xFF  # Upper 8 bits
            self._bit = key_int & 0xFF  # Lower 8 bits

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "event_source": self.info.source,
            "description": self.info.description,
            "info": self.info.info,
        }

    def get_coordinate(self) -> EventCoordinate:
        """Get the coordinate (ID, bit) for this event."""
        return EventCoordinate(id=self._id, bit=self._bit)

    @property
    def id(self) -> int:
        """Get the ID."""
        return self._id

    @property
    def bit(self) -> int:
        """Get the bit position."""
        return self._bit


@dataclass
class Mk2Format(EventFormat):
    """MK2 format - 16 IDs with 28 bits each."""

    format_type: FormatType = FormatType.MK2
    events: Dict[EventKey, Mk2Event] = field(default_factory=dict)
    sources: List[EventSource] = field(default_factory=list)
    id_names: Dict[int, str] = field(default_factory=dict)  # Optional ID names
    base_address: Optional[int] = None  # Optional base address

    def add_event(self, key: EventKey, info: EventInfo) -> None:
        """Add an event to the format."""
        event = Mk2Event(key=key, info=info)

        # Validate ID and bit ranges
        if event.id > MK2_MAX_ID:
            raise ValueError(f"ID {event.id} exceeds maximum {MK2_MAX_ID}")
        if event.bit > MK2_MAX_BIT:
            raise ValueError(f"Bit {event.bit} exceeds maximum {MK2_MAX_BIT}")

        self.events[key] = event

    def remove_event(self, key: EventKey) -> None:
        """Remove an event from the format."""
        if key in self.events:
            del self.events[key]

    def get_event(self, key: EventKey) -> Optional[Mk2Event]:
        """Get an event by key."""
        return self.events.get(key)

    def get_events_by_id(self, id_num: int) -> Dict[EventKey, Mk2Event]:
        """Get all events for a specific ID.

        Args:
            id_num: ID number (0-15)

        Returns:
            Dictionary of events for that ID
        """
        return {
            key: event 
            for key, event in self.events.items() 
            if event.id == id_num
        }

    def validate(self) -> ValidationResult:
        """Validate the format structure."""
        result = ValidationResult()

        # Check for duplicate keys
        seen_coords = set()
        for key, event in self.events.items():
            coord = (event.id, event.bit)
            if coord in seen_coords:
                result.add_error(
                    ValidationCode.KEY_FORMAT,
                    f"Duplicate coordinate: ID {event.id}, bit {event.bit}",
                    location=key
                )
            seen_coords.add(coord)

        # Validate ID range
        for key, event in self.events.items():
            if event.id > MK2_MAX_ID:
                result.add_error(
                    ValidationCode.KEY_FORMAT,
                    f"ID {event.id} exceeds maximum {MK2_MAX_ID}",
                    location=key
                )

            # Validate bit range (bits 28-31 are invalid)
            if event.bit > MK2_MAX_BIT:
                result.add_error(
                    ValidationCode.KEY_FORMAT,
                    f"Bit {event.bit} in invalid range 28-31",
                    location=key,
                    suggestion="Only bits 0-27 are valid for MK2 format"
                )

        # Validate id_names
        for id_num, name in self.id_names.items():
            if not isinstance(id_num, int):
                result.add_error(
                    ValidationCode.KEY_FORMAT,
                    f"Invalid ID key type: {type(id_num).__name__}",
                    location=f"id_names[{id_num}]"
                )
            elif id_num > MK2_MAX_ID:
                result.add_error(
                    ValidationCode.KEY_FORMAT,
                    f"Invalid ID {id_num} in id_names (max: {MK2_MAX_ID})"
                )
            elif not name or not name.strip():
                result.add_warning(
                    ValidationCode.KEY_FORMAT,
                    f"Empty name for ID {id_num}"
                )

        # Validate base_address
        if self.base_address is not None:
            if self.base_address < 0 or self.base_address > 0xFFFFFFFF:
                result.add_error(
                    ValidationCode.KEY_FORMAT,
                    f"Base address 0x{self.base_address:X} exceeds 32-bit range"
                )
            elif self.base_address % 4 != 0:
                result.add_warning(
                    ValidationCode.KEY_FORMAT,
                    f"Base address 0x{self.base_address:X} is not 4-byte aligned"
                )

        # Check for missing id_names
        used_ids = set(event.id for event in self.events.values())
        named_ids = set(self.id_names.keys())
        missing_names = used_ids - named_ids

        if missing_names:
            result.add_info(
                ValidationCode.KEY_FORMAT,
                f"IDs without names: {sorted(missing_names)}"
            )

        # Validate sources
        defined_sources = {source.name for source in self.sources}
        for key, event in self.events.items():
            if event.info.source and event.info.source not in defined_sources:
                result.add_warning(
                    ValidationCode.KEY_FORMAT,
                    f"Event uses undefined source '{event.info.source}'",
                    location=key
                )

        return result

    def get_subtab_config(self) -> dict[str, Any]:
        """Get GUI subtab configuration.

        Returns:
            Dictionary with subtab configuration
        """
        # Determine which IDs have events
        used_ids = sorted(set(event.id for event in self.events.values()))

        subtabs = []
        for id_num in used_ids:
            name = self.id_names.get(id_num, f"ID {id_num:02X}")
            subtabs.append({
                "name": name,
                "id": id_num,
            })

        return {
            "format": "mk2",
            "subtabs": subtabs,
            "base_address": self.base_address,
        }

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


    @classmethod
    def normalize_key(cls, key: str | int) -> EventKey:
        """Normalize MK2 key to standard "0xibb" format.

        Args:
            key: Raw key (string or integer)

        Returns:
            Normalized EventKey in format "0xibb"

        Raises:
            ValueError: If key is invalid or out of range
        """
        if isinstance(key, int):
            value = key
        elif isinstance(key, str):
            key = key.strip()
            value = int(key, 16) if 'x' in key.lower() else int(key, 16)
        else:
            raise ValueError(f"Invalid key type: {type(key)}")

        # Extract ID and bit from value (format: 0xibb)
        id_num = (value >> 8) & 0xF
        bit_num = value & 0xFF

        # Validate ranges
        if id_num > 15:
            raise ValueError(f"ID {id_num} out of range (0-15)")
        if bit_num > 27:
            raise ValueError(f"Bit {bit_num} out of range (0-27)")

        return EventKey(f"0x{id_num:01X}{bit_num:02X}")

    @classmethod
    def _parse_events(cls, data: Dict[str, Any], source: str, validation: ValidationResult) -> Tuple[Dict[EventKey, Event], Dict[str, Any]]:
        """Parse MK2 events and format-specific data.

        Args:
            data: YAML data dictionary
            source: Source identifier
            validation: ValidationResult for collecting errors

        Returns:
            Tuple of (events dict, extra_data dict with id_names and base_address)
        """
        from event_selector.domain.interfaces.format_strategy import ValidationCode

        events = {}
        seen_keys = set()

        # Parse id_names (MK2-specific)
        id_names = {}
        if 'id_names' in data and isinstance(data['id_names'], dict):
            for id_key, name in data['id_names'].items():
                try:
                    id_num = int(id_key)
                    if 0 <= id_num <= 15:
                        id_names[id_num] = str(name)
                    else:
                        validation.add_warning(
                            ValidationCode.MK2_ADDR_RANGE,
                            f"ID {id_num} out of range (0-15), skipping"
                        )
                except (ValueError, TypeError):
                    validation.add_warning(
                        ValidationCode.KEY_FORMAT,
                        f"Invalid ID in id_names: {id_key}"
                    )

        # Parse base_address (MK2-specific)
        base_address = None
        if 'base_address' in data:
            try:
                ba = data['base_address']
                base_address = int(ba, 16) if isinstance(ba, str) else int(ba)
            except (ValueError, TypeError):
                validation.add_warning(
                    ValidationCode.INVALID_BASE_ADDRESS,
                    f"Invalid base_address: {data['base_address']}"
                )

        # Parse events
        for key, value in data.items():
            # Skip metadata keys
            if key in ['sources', 'id_names', 'base_address']:
                continue

            # Validate event data structure
            if not isinstance(value, dict):
                validation.add_error(
                    ValidationCode.KEY_FORMAT,
                    f"Event '{key}' must be a dictionary",
                    location=source
                )
                continue

            try:
                # Normalize the key
                normalized_key = cls.normalize_key(key)

                # Check for duplicates
                if normalized_key in seen_keys:
                    validation.add_error(
                        ValidationCode.DUPLICATE_KEY,
                        f"Duplicate key: {normalized_key} (original: {key})",
                        location=source
                    )
                    continue

                seen_keys.add(normalized_key)

                # Create event info
                event_info = EventInfo(
                    source=value.get('event_source', 'unknown'),
                    description=value.get('description', ''),
                    info=value.get('info', '')
                )

                # Create MK2 event
                event = Mk2Event(key=normalized_key, info=event_info)
                events[normalized_key] = event

            except ValueError as e:
                validation.add_error(
                    ValidationCode.MK2_ADDR_RANGE,
                    f"Invalid MK2 key '{key}': {e}",
                    location=source
                )

        # Return events and MK2-specific extra data
        extra_data = {
            'id_names': id_names,
            'base_address': base_address
        }

        return events, extra_data

    @classmethod
    def _create_instance(cls, sources: list[EventSource], events: Dict[EventKey, Event], extra_data: Dict[str, Any]) -> 'Mk2Format':
        """Create Mk2Format instance.

        Args:
            sources: Parsed sources
            events: Parsed events
            extra_data: MK2-specific data (id_names, base_address)

        Returns:
            Mk2Format instance
        """
        return cls(
            sources=sources,
            events=events,
            id_names=extra_data.get('id_names', {}),
            base_address=extra_data.get('base_address')
        )
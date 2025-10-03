from event_selector.domain.models.base import Event, EventFormat

@dataclass
class Mk2Event(Event):
    """MK2 event implementation."""

    @property
    def id(self) -> int:
        """Extract ID from key (0xibb format)."""
        key_value = int(str(self.key), 16)
        return (key_value >> 8) & 0xF

    @property
    def bit(self) -> int:
        """Extract bit from key."""
        key_value = int(str(self.key), 16)
        return key_value & 0xFF

    def get_coordinate(self) -> EventCoordinate:
        """Get coordinate for this event."""
        return EventCoordinate(
            id=EventID(self.id),
            bit=BitPosition(self.bit)
        )

class Mk2Format(EventFormat):
    """MK2 format with 16 IDs."""

    def __init__(self, 
                 id_names: Optional[Dict[int, str]] = None,
                 base_address: Optional[int] = None):
        super().__init__(format_type=FormatType.MK2)
        self.id_names = id_names or {}
        self.base_address = base_address

    def get_events_by_id(self, id_num: int) -> Dict[EventKey, Mk2Event]:
        """Get all events for a specific ID."""
        result = {}
        for key, event in self.events.items():
            if isinstance(event, Mk2Event) and event.id == id_num:
                result[key] = event
        return result

    def get_id_name(self, id_num: int) -> str:
        """Get display name for ID."""
        if id_num in self.id_names:
            return f"{self.id_names[id_num]} (ID {id_num:X})"
        return f"ID {id_num:X}"

    def get_subtab_config(self) -> Dict[str, Any]:
        """Get GUI subtab configuration."""
        subtabs = []
        for id_num in range(16):
            subtabs.append({
                'name': self.get_id_name(id_num),
                'id': id_num,
                'bits': 28  # Only 0-27 valid
            })
        return {'type': 'dynamic', 'subtabs': subtabs}
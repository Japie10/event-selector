"""MK1 format domain model implementation."""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from pathlib import Path

from event_selector.shared.types import (
    EventKey, EventID, BitPosition, FormatType,
    EventCoordinate, MK1_RANGES, ValidationCode
)
from event_selector.shared.exceptions import AddressError, ValidationError
from event_selector.domain.models.base import Event, EventFormat
from event_selector.domain.models.value_objects import EventAddress, EventInfo
from event_selector.domain.interfaces.format_strategy import ValidationResult


@dataclass
class Mk1Event(Event):
    """MK1 event implementation."""
    address: EventAddress
    
    def __post_init__(self):
        """Validate MK1 event."""
        # Validate address is in valid ranges
        addr_value = self.address.value
        valid = False
        
        for range_name, addr_range in MK1_RANGES.items():
            if addr_range.contains(addr_value):
                valid = True
                break
        
        if not valid:
            raise AddressError(
                self.address.hex,
                f"Address {self.address.hex} not in valid MK1 ranges"
            )
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'address': self.address.hex,
            'event_source': self.info.source,
            'description': self.info.description,
            'info': self.info.info
        }
    
    def get_coordinate(self) -> EventCoordinate:
        """Get the coordinate (ID, bit) for this event."""
        addr_value = self.address.value
        
        # Find which range this address belongs to
        for range_name, addr_range in MK1_RANGES.items():
            if addr_range.contains(addr_value):
                # Calculate base ID for this range
                base_id = {
                    "Data": 0,      # IDs 0-3
                    "Network": 4,   # IDs 4-7
                    "Application": 8  # IDs 8-11
                }[range_name]
                
                # Calculate offset within range
                offset = addr_value - addr_range.start
                id_num = base_id + (offset // 32)
                bit = offset % 32
                
                return EventCoordinate(
                    id=EventID(id_num),
                    bit=BitPosition(bit)
                )
        
        # Should never reach here due to validation in __post_init__
        raise AddressError(self.address.hex, "Invalid MK1 address")
    
    @classmethod
    def from_dict(cls, data: dict[str, Any], key: EventKey) -> 'Mk1Event':
        """Create from dictionary representation."""
        # Parse address from key
        address = EventAddress.from_hex(key)
        
        # Create event info
        info = EventInfo(
            source=data.get('event_source', ''),
            description=data.get('description', ''),
            info=data.get('info', '')
        )
        
        return cls(key=key, info=info, address=address)


class Mk1Format(EventFormat):
    """MK1 format implementation."""
    
    def __init__(self):
        """Initialize MK1 format."""
        super().__init__(format_type=FormatType.MK1)
        self._subtab_names = ["Data", "Network", "Application"]
    
    def add_event(self, key: EventKey, info: EventInfo) -> None:
        """Add an MK1 event."""
        # Normalize the key
        try:
            if isinstance(key, str):
                address = EventAddress.from_hex(key)
            else:
                address = EventAddress.from_int(int(key))
            
            normalized_key = EventKey(address.hex.lower())
            
            # Create and add the event
            event = Mk1Event(
                key=normalized_key,
                info=info,
                address=address
            )
            
            self.events[normalized_key] = event
            
        except (AddressError, ValidationError) as e:
            raise ValidationError(f"Cannot add event: {e}")
    
    def remove_event(self, key: EventKey) -> None:
        """Remove an event."""
        normalized_key = self._normalize_key(key)
        if normalized_key not in self.events:
            raise KeyError(f"Event {key} not found")
        del self.events[normalized_key]
    
    def get_event(self, key: EventKey) -> Optional[Mk1Event]:
        """Get an event by key."""
        normalized_key = self._normalize_key(key)
        return self.events.get(normalized_key)
    
    def validate(self) -> ValidationResult:
        """Validate the MK1 format structure."""
        result = ValidationResult()
        
        # Check for duplicate keys (already handled by dict)
        # but validate each event's address
        for key, event in self.events.items():
            try:
                coord = event.get_coordinate()
                
                # Validate ID is in valid range (0-11)
                if coord.id > 11:
                    result.add_error(
                        ValidationCode.MK1_ADDR_RANGE,
                        f"Event {key} maps to invalid ID {coord.id}",
                        location=key
                    )
                
                # All 32 bits are valid in MK1
                if coord.bit > 31:
                    result.add_error(
                        ValidationCode.MK1_ADDR_RANGE,
                        f"Event {key} maps to invalid bit {coord.bit}",
                        location=key
                    )
                    
            except AddressError as e:
                result.add_error(
                    ValidationCode.MK1_ADDR_RANGE,
                    str(e),
                    location=key
                )
        
        return result
    
    def get_subtab_config(self) -> dict[str, Any]:
        """Get GUI subtab configuration for MK1."""
        return {
            'type': 'fixed',
            'subtabs': [
                {
                    'name': 'Data',
                    'ids': [0, 1, 2, 3],
                    'bits': 32,
                    'address_range': (0x000, 0x07F)
                },
                {
                    'name': 'Network',
                    'ids': [4, 5, 6, 7],
                    'bits': 32,
                    'address_range': (0x200, 0x27F)
                },
                {
                    'name': 'Application',
                    'ids': [8, 9, 10, 11],
                    'bits': 32,
                    'address_range': (0x400, 0x47F)
                }
            ]
        }
    
    def _normalize_key(self, key: str | int) -> EventKey:
        """Normalize a key to standard MK1 format (0xNNN)."""
        try:
            if isinstance(key, str):
                address = EventAddress.from_hex(key)
            else:
                address = EventAddress.from_int(int(key))
            return EventKey(address.hex.lower())
        except Exception as e:
            raise ValidationError(f"Invalid key format: {key}") from e
    
    def get_events_by_subtab(self, subtab_name: str) -> dict[EventKey, Mk1Event]:
        """Get all events for a specific subtab."""
        if subtab_name not in self._subtab_names:
            raise ValueError(f"Invalid subtab: {subtab_name}")
        
        # Get ID range for this subtab
        id_ranges = {
            "Data": range(0, 4),
            "Network": range(4, 8),
            "Application": range(8, 12)
        }
        
        valid_ids = id_ranges[subtab_name]
        result = {}
        
        for key, event in self.events.items():
            coord = event.get_coordinate()
            if coord.id in valid_ids:
                result[key] = event
        
        return result

"""Base domain models for event formats."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import numpy as np

from event_selector.shared.types import (
    EventKey, EventID, BitPosition, FormatType, 
    EventCoordinate, MaskMode
)
from event_selector.domain.models.value_objects import (
    EventAddress, EventInfo, EventSource, BitMask
)
from event_selector.domain.interfaces.format_strategy import ValidationResult


@dataclass
class Event(ABC):
    """Abstract base class for events."""
    key: EventKey
    info: EventInfo
    
    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary representation."""
        pass
    
    @abstractmethod
    def get_coordinate(self) -> EventCoordinate:
        """Get the coordinate (ID, bit) for this event."""
        pass


@dataclass
class EventFormat(ABC):
    """Abstract base class for event formats."""
    format_type: FormatType
    events: Dict[EventKey, Event] = field(default_factory=dict)
    sources: list[EventSource] = field(default_factory=list)
    
    @abstractmethod
    def add_event(self, key: EventKey, info: EventInfo) -> None:
        """Add an event to the format."""
        pass
    
    @abstractmethod
    def remove_event(self, key: EventKey) -> None:
        """Remove an event from the format."""
        pass
    
    @abstractmethod
    def get_event(self, key: EventKey) -> Optional[Event]:
        """Get an event by key."""
        pass
    
    @abstractmethod
    def validate(self) -> ValidationResult:
        """Validate the format structure."""
        pass
    
    @abstractmethod
    def get_subtab_config(self) -> dict[str, Any]:
        """Get GUI subtab configuration."""
        pass
    
    def get_all_events(self) -> dict[EventKey, Event]:
        """Get all events."""
        return self.events.copy()
    
    def has_event(self, key: EventKey) -> bool:
        """Check if an event exists."""
        return key in self.events
    
    def count_events(self) -> int:
        """Count total events."""
        return len(self.events)


@dataclass
class MaskData:
    """Container for mask/trigger data."""
    format_type: FormatType
    mode: MaskMode
    data: np.ndarray  # Array of 32-bit values
    metadata: Optional[dict[str, Any]] = None
    
    def __post_init__(self):
        """Validate mask data."""
        if self.data.dtype != np.uint32:
            self.data = self.data.astype(np.uint32)
        
        # Validate size based on format
        expected_size = {
            FormatType.MK1: 12,
            FormatType.MK2: 16,
            FormatType.MK3: 32,  # Future
        }.get(self.format_type)
        
        if expected_size and len(self.data) != expected_size:
            raise ValueError(
                f"Invalid mask size for {self.format_type.value}: "
                f"expected {expected_size}, got {len(self.data)}"
            )
    
    def get_bit(self, id: int, bit: int) -> bool:
        """Get a specific bit value."""
        if not 0 <= id < len(self.data):
            raise IndexError(f"Invalid ID: {id}")
        if not 0 <= bit <= 31:
            raise ValueError(f"Invalid bit: {bit}")
        return bool(self.data[id] & (1 << bit))
    
    def set_bit(self, id: int, bit: int, value: bool) -> None:
        """Set a specific bit value."""
        if not 0 <= id < len(self.data):
            raise IndexError(f"Invalid ID: {id}")
        if not 0 <= bit <= 31:
            raise ValueError(f"Invalid bit: {bit}")
        
        if value:
            self.data[id] |= (1 << bit)
        else:
            self.data[id] &= ~(1 << bit)
    
    def toggle_bit(self, id: int, bit: int) -> None:
        """Toggle a specific bit."""
        if not 0 <= id < len(self.data):
            raise IndexError(f"Invalid ID: {id}")
        if not 0 <= bit <= 31:
            raise ValueError(f"Invalid bit: {bit}")
        
        self.data[id] ^= (1 << bit)
    
    def apply_mask(self, mask: int) -> None:
        """Apply a mask to all registers."""
        self.data &= mask
    
    def clear_all(self) -> None:
        """Clear all bits."""
        self.data.fill(0)
    
    def set_all(self) -> None:
        """Set all bits to 1."""
        self.data.fill(0xFFFFFFFF)
    
    def copy(self) -> 'MaskData':
        """Create a deep copy."""
        return MaskData(
            format_type=self.format_type,
            mode=self.mode,
            data=self.data.copy(),
            metadata=self.metadata.copy() if self.metadata else None
        )


@dataclass
class Project:
    """Represents a complete project with format and masks."""
    format: EventFormat
    event_mask: MaskData
    capture_mask: MaskData
    yaml_path: Optional[Path] = None
    validation_result: Optional[ValidationResult] = None
    
    def __post_init__(self):
        """Validate project consistency."""
        # Ensure masks match format type
        if self.event_mask.format_type != self.format.format_type:
            raise ValueError("Event mask format doesn't match project format")
        if self.capture_mask.format_type != self.format.format_type:
            raise ValueError("Capture mask format doesn't match project format")
        
        # Ensure mask modes are correct
        if self.event_mask.mode != MaskMode.MASK:
            raise ValueError("Event mask must be in MASK mode")
        if self.capture_mask.mode != MaskMode.TRIGGER:
            raise ValueError("Capture mask must be in TRIGGER mode")
    
    def get_active_mask(self, mode: MaskMode) -> MaskData:
        """Get the mask for the specified mode."""
        return self.event_mask if mode == MaskMode.MASK else self.capture_mask
    
    def toggle_event(self, key: EventKey, mode: MaskMode) -> None:
        """Toggle an event in the specified mask."""
        event = self.format.get_event(key)
        if not event:
            raise KeyError(f"Event {key} not found")
        
        coord = event.get_coordinate()
        mask = self.get_active_mask(mode)
        mask.toggle_bit(coord.id, coord.bit)

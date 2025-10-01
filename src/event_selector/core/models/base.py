"""Abstract base classes for Event Selector models.

This module defines the abstract interfaces that all format-specific
implementations must follow, using the Template Method pattern.
"""

from typing import Any, Optional, Dict, List, Tuple
from abc import ABC, abstractmethod

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    ConfigDict,
)
import numpy as np

from .constants import FormatType, MaskMode


# =====================
# Base Pydantic Model
# =====================

class StrictModel(BaseModel):
    """Base model with strict validation."""
    model_config = ConfigDict(
        validate_assignment=True,
        extra="forbid",
        str_strip_whitespace=True,
        use_enum_values=False,
    )


# =====================
# Event Source Model
# =====================

class EventSource(StrictModel):
    """Event source definition.
    
    Represents a source of events (e.g., hardware module, firmware component).
    """
    source_id: str = Field(..., min_length=1, max_length=2)
    name: str = Field(..., min_length=1, max_length=500)
    
    @field_validator('source_id')
    @classmethod
    def validate_source_id(cls, v: str) -> str:
        """Validate source ID is hexadecimal."""
        try:
            int(v, 16)
        except ValueError:
            raise ValueError(f"Source ID must be a hexadecimal string: {v}")
        return v

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate source name contains only allowed characters."""
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError(f"Source name must be alphanumeric (with _ or -): {v}")
        return v


# =====================
# Abstract Event Base Class
# =====================

class BaseFormatEvent(StrictModel, ABC):
    """Abstract base class for all event types.
    
    This class uses the Template Method pattern to define the structure
    of event validation and normalization, while allowing subclasses
    to provide format-specific implementations.
    
    The validation flow is:
    1. Field validator calls normalize_key() (format-specific)
    2. Model validator calls parse_key_components() (format-specific)
    3. Model validator calls validate_key_range() (format-specific)
    4. Model validator stores computed _id, _bit, _normalized_key
    """
    
    # Common fields for all events
    event_source: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1, max_length=500)
    info: str = Field("", max_length=500)

    # Internal state (computed during validation)
    _normalized_key: Optional[str] = None
    _id: Optional[int] = None
    _bit: Optional[int] = None

    @field_validator('event_source')
    @classmethod
    def validate_event_source(cls, v: str) -> str:
        """Validate event source reference."""
        if not v.strip():
            raise ValueError("Event source cannot be empty")
        return v.strip()

    # ========================================
    # ABSTRACT METHODS - Must be implemented by subclasses
    # ========================================
    
    @classmethod
    @abstractmethod
    def normalize_key(cls, raw_key: str | int) -> str:
        """Normalize the raw key/address to canonical format.
        
        Args:
            raw_key: Raw key/address (string or integer)
            
        Returns:
            Normalized key string
            
        Raises:
            ValueError: If key format is invalid
            
        Examples:
            MK1: "0x0" -> "0x000"
            MK2: "0x1b" -> "0x01B"
        """
        ...
    
    @abstractmethod
    def parse_key_components(self) -> Tuple[int, int]:
        """Parse the normalized key into ID and bit components.
        
        Returns:
            Tuple of (id, bit)
            
        Raises:
            ValueError: If key cannot be parsed
            
        Examples:
            MK1: "0x000" -> (0, 0)
            MK1: "0x020" -> (1, 0)
            MK2: "0x115" -> (1, 21)
        """
        ...
    
    @abstractmethod
    def validate_key_range(self, id_val: int, bit_val: int) -> None:
        """Validate that the parsed ID and bit are within valid ranges.
        
        Args:
            id_val: Parsed ID value
            bit_val: Parsed bit value
            
        Raises:
            ValueError: If ID or bit is out of range
        """
        ...
    
    @abstractmethod
    def get_raw_key_field(self) -> str:
        """Get the raw key value from the appropriate field.
        
        Returns:
            Raw key string (self.address for MK1, self.key for MK2)
        """
        ...

    # ========================================
    # CONCRETE PROPERTIES - Implemented in base class
    # ========================================
    
    @property
    def id(self) -> int:
        """Get register ID.
        
        Returns:
            Register ID (0-11 for MK1, 0-15 for MK2)
            
        Raises:
            ValueError: If event not properly initialized
        """
        if self._id is None:
            raise ValueError("Event not properly initialized (missing ID)")
        return self._id

    @property
    def bit(self) -> int:
        """Get bit position.
        
        Returns:
            Bit position (0-31 for MK1, 0-27 for MK2)
            
        Raises:
            ValueError: If event not properly initialized
        """
        if self._bit is None:
            raise ValueError("Event not properly initialized (missing bit)")
        return self._bit
    
    @property
    def normalized_key(self) -> str:
        """Get normalized key.
        
        Returns:
            Normalized key string
            
        Raises:
            ValueError: If event not properly initialized
        """
        if self._normalized_key is None:
            raise ValueError("Event not properly initialized (missing normalized key)")
        return self._normalized_key
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation.
        
        This base implementation provides common fields.
        Subclasses can override to add format-specific fields.
        
        Returns:
            Dictionary with event data
        """
        return {
            "event_source": self.event_source,
            "description": self.description,
            "info": self.info,
            "id": self.id,
            "bit": self.bit,
            "normalized_key": self.normalized_key
        }


# =====================
# Abstract Format Base Class
# =====================

class BaseFormat(StrictModel, ABC):
    """Abstract base class for all format types.
    
    All format implementations (MK1, MK2, future MK3) must provide
    these methods to ensure a consistent interface for operations
    like validation, export, and GUI rendering.
    """
    
    # Common fields for all formats
    sources: List[EventSource] = Field(default_factory=list)
    # Note: events is defined in subclasses with proper typing
    
    # ========================================
    # ABSTRACT PROPERTIES
    # ========================================
    
    @property
    @abstractmethod
    def format_type(self) -> FormatType:
        """Get format type (MK1 or MK2).
        
        Returns:
            FormatType enum value
        """
        ...
    
    @property
    @abstractmethod
    def num_registers(self) -> int:
        """Get number of registers.
        
        Returns:
            Number of registers (12 for MK1, 16 for MK2)
        """
        ...
    
    @property
    @abstractmethod
    def max_bit(self) -> int:
        """Get maximum valid bit.
        
        Returns:
            Maximum bit position (31 for MK1, 27 for MK2)
        """
        ...
    
    @property
    @abstractmethod
    def events(self) -> Dict[str, BaseFormatEvent]:
        """Get events dictionary.
        
        Returns:
            Dictionary mapping keys to events
        """
        ...
    
    # ========================================
    # ABSTRACT METHODS
    # ========================================
    
    @abstractmethod
    def get_events_for_register(self, register_id: int) -> Dict[str, BaseFormatEvent]:
        """Get all events for a specific register ID.
        
        Args:
            register_id: Register ID to query
            
        Returns:
            Dictionary of key -> event for that register
            
        Raises:
            ValueError: If register_id is out of range
        """
        ...
    
    @abstractmethod
    def to_mask_array(self, mode: MaskMode = MaskMode.EVENT) -> np.ndarray:
        """Convert events to mask array.
        
        Args:
            mode: Mask or trigger mode
            
        Returns:
            NumPy array of uint32 values with appropriate length
        """
        ...
    
    @abstractmethod
    def validate_event_key(self, key: str) -> bool:
        """Validate if a key is valid for this format.
        
        Args:
            key: Event key/address to validate
            
        Returns:
            True if valid, False otherwise
        """
        ...
    
    # ========================================
    # CONCRETE METHODS - Common implementations
    # ========================================
    
    def get_source_by_name(self, name: str) -> Optional[EventSource]:
        """Get event source by name.
        
        Args:
            name: Source name to find
            
        Returns:
            EventSource if found, None otherwise
        """
        for source in self.sources:
            if source.name == name:
                return source
        return None
    
    def get_all_register_ids(self) -> List[int]:
        """Get list of all register IDs for this format.
        
        Returns:
            List of valid register IDs (0..num_registers-1)
        """
        return list(range(self.num_registers))
    
    def get_event_count(self) -> int:
        """Get total number of events.
        
        Returns:
            Total event count
        """
        return len(self.events)
    
    def get_source_names(self) -> List[str]:
        """Get list of all source names.
        
        Returns:
            List of source names
        """
        return [source.name for source in self.sources]
    
    def has_events(self) -> bool:
        """Check if format has any events defined.
        
        Returns:
            True if at least one event exists
        """
        return len(self.events) > 0
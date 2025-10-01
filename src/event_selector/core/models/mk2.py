"""MK2 format implementation.

This module implements the MK2 event format with key-based
event identification and configurable ID names.
"""

from typing import Dict, Optional, Tuple
from pydantic import Field, field_validator, model_validator
import numpy as np

from .base import BaseFormatEvent, BaseFormat
from .constants import (
    FormatType,
    MaskMode,
    MK2_MAX_ID,
    MK2_MAX_BIT,
    MK2_BIT_MASK,
    MK2_NUM_REGISTERS,
)


# =====================
# MK2 Event Model
# =====================

class EventMk2(BaseFormatEvent):
    """MK2 event with key-based identification.
    
    MK2 events use a key format 0xibb where:
    - i: ID (0-15, one hex digit)
    - bb: Bit (0-27, two hex digits)
    
    Note: Bits 28-31 are invalid in MK2.
    """
    
    key: str = Field(..., description="Event key in 0xibb format")

    @field_validator('key')
    @classmethod
    def validate_and_normalize_key(cls, v: str | int) -> str:
        """Validate and normalize key using template method."""
        return cls.normalize_key(v)

    @model_validator(mode='after')
    def compute_id_and_bit(self) -> 'EventMk2':
        """Compute ID and bit from key using template method."""
        # Parse components
        id_val, bit_val = self.parse_key_components()
        
        # Validate range
        self.validate_key_range(id_val, bit_val)
        
        # Store computed values
        self._id = id_val
        self._bit = bit_val
        self._normalized_key = self.key
        
        return self

    # ========================================
    # Implement abstract methods from BaseFormatEvent
    # ========================================
    
    @classmethod
    def normalize_key(cls, raw_key: str | int) -> str:
        """Normalize MK2 key to 0xibb format.
        
        Args:
            raw_key: Key as string or integer
            
        Returns:
            Normalized key in format 0xibb
            
        Raises:
            ValueError: If key format invalid or out of range
            
        Examples:
            >>> EventMk2.normalize_key("0x1b")
            "0x01B"
            >>> EventMk2.normalize_key(0x115)
            "0x115"
        """
        try:
            if isinstance(raw_key, str):
                key_str = raw_key.lower().strip()
                if key_str.startswith('0x'):
                    key_value = int(key_str, 16)
                else:
                    key_value = int(key_str, 16)
            else:
                key_value = int(raw_key)

            # Extract ID and bit
            id_part = (key_value >> 8) & 0xF
            bit_part = key_value & 0xFF

            # Validate before normalizing
            if id_part > MK2_MAX_ID:
                raise ValueError(f"ID {id_part} exceeds maximum {MK2_MAX_ID}")
            if bit_part > MK2_MAX_BIT:
                raise ValueError(f"Bit {bit_part} exceeds maximum {MK2_MAX_BIT}")

            return f"0x{id_part:01X}{bit_part:02X}"

        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid MK2 key format: {raw_key}") from e
    
    def parse_key_components(self) -> Tuple[int, int]:
        """Parse MK2 key into ID and bit.
        
        Returns:
            Tuple of (id, bit)
        """
        key_value = int(self.key, 16)
        id_val = (key_value >> 8) & 0xF
        bit_val = key_value & 0xFF
        return id_val, bit_val
    
    def validate_key_range(self, id_val: int, bit_val: int) -> None:
        """Validate MK2 ID and bit ranges.
        
        Args:
            id_val: ID value to validate
            bit_val: Bit value to validate
            
        Raises:
            ValueError: If ID or bit out of range
        """
        if not 0 <= id_val <= MK2_MAX_ID:
            raise ValueError(f"MK2 ID {id_val} out of range (must be 0-{MK2_MAX_ID})")
        if not 0 <= bit_val <= MK2_MAX_BIT:
            raise ValueError(f"MK2 bit {bit_val} out of range (must be 0-{MK2_MAX_BIT})")
    
    def get_raw_key_field(self) -> str:
        """Get raw key field.
        
        Returns:
            The key field value
        """
        return self.key
    
    def to_dict(self) -> Dict[str, str | int]:
        """Convert to dictionary with MK2-specific fields.
        
        Returns:
            Dictionary with all event data
        """
        base_dict = super().to_dict()
        base_dict["key"] = self.key
        return base_dict


# =====================
# MK2 Format Model
# =====================

class Mk2Format(BaseFormat):
    """MK2 format with 16 registers and optional ID names.
    
    MK2 format features:
    - 16 registers (IDs 0-15)
    - Only bits 0-27 are valid (bits 28-31 forced to zero)
    - Optional base address for memory mapping
    - Optional ID names for better organization
    """
    
    id_names: Dict[int, str] = Field(default_factory=dict)
    base_address: Optional[int] = Field(None, ge=0, le=0xFFFFFFFF)
    events: Dict[str, EventMk2] = Field(default_factory=dict)

    @field_validator('id_names')
    @classmethod
    def validate_id_names(cls, v: Dict[int, str]) -> Dict[int, str]:
        """Validate ID names have valid IDs and non-empty names.
        
        Args:
            v: Dictionary of ID -> name
            
        Returns:
            Validated dictionary
            
        Raises:
            ValueError: If invalid ID or empty name
        """
        for id_num, name in v.items():
            if not 0 <= id_num <= MK2_MAX_ID:
                raise ValueError(f"Invalid ID {id_num}, must be 0-{MK2_MAX_ID}")
            if not name or not name.strip():
                raise ValueError(f"Empty name for ID {id_num}")
        return v

    @field_validator('base_address')
    @classmethod
    def validate_base_address(cls, v: Optional[int]) -> Optional[int]:
        """Validate base address is 32-bit.
        
        Args:
            v: Base address value
            
        Returns:
            Validated base address
            
        Raises:
            ValueError: If address exceeds 32-bit range
        """
        if v is not None and v > 0xFFFFFFFF:
            raise ValueError(f"Base address {v:#x} exceeds 32-bit range")
        return v

    @model_validator(mode='after')
    def validate_no_duplicate_keys(self) -> 'Mk2Format':
        """Check for duplicate normalized keys.
        
        Returns:
            Self for method chaining
            
        Raises:
            ValueError: If duplicate keys found
        """
        normalized = {}
        for key, event in self.events.items():
            norm_key = event.normalized_key
            if norm_key in normalized:
                raise ValueError(
                    f"Duplicate key: {key} and {normalized[norm_key]} "
                    f"both normalize to {norm_key}"
                )
            normalized[norm_key] = key
        return self

    # ========================================
    # Implement abstract properties from BaseFormat
    # ========================================
    
    @property
    def format_type(self) -> FormatType:
        """Get format type.
        
        Returns:
            FormatType.MK2
        """
        return FormatType.MK2
    
    @property
    def num_registers(self) -> int:
        """Get number of registers.
        
        Returns:
            16 (MK2 has 16 registers)
        """
        return MK2_NUM_REGISTERS
    
    @property
    def max_bit(self) -> int:
        """Get maximum valid bit.
        
        Returns:
            27 (MK2 only uses bits 0-27, bits 28-31 are invalid)
        """
        return MK2_MAX_BIT

    # ========================================
    # Implement abstract methods from BaseFormat
    # ========================================
    
    def get_events_for_register(self, register_id: int) -> Dict[str, EventMk2]:
        """Get events for specific register.
        
        Args:
            register_id: Register ID (0-15)
            
        Returns:
            Dictionary of key -> event for that register
            
        Raises:
            ValueError: If register_id out of range
        """
        if not 0 <= register_id <= 15:
            raise ValueError(f"Invalid MK2 register ID {register_id} (must be 0-15)")
        
        return {
            key: event
            for key, event in self.events.items()
            if event.id == register_id
        }
    
    def to_mask_array(self, mode: MaskMode = MaskMode.EVENT) -> np.ndarray:
        """Convert to mask array.
        
        Args:
            mode: Mask or trigger mode
            
        Returns:
            NumPy array of shape (16,) with uint32 values
            
        Note:
            This returns an array of zeros with bits 28-31 masked.
            Actual mask values come from GUI selections.
        """
        mask = np.zeros(16, dtype=np.uint32)
        mask &= MK2_BIT_MASK  # Ensure bits 28-31 are zero
        return mask
    
    def validate_event_key(self, key: str) -> bool:
        """Validate if key is valid MK2 key.
        
        Args:
            key: Key to validate
            
        Returns:
            True if valid MK2 key, False otherwise
        """
        try:
            EventMk2.normalize_key(key)
            return True
        except ValueError:
            return False

    # ========================================
    # MK2-specific methods
    # ========================================
    
    def get_id_name(self, id_num: int) -> str:
        """Get name for an ID with fallback.
        
        Args:
            id_num: ID number (0-15)
            
        Returns:
            Formatted ID name (with ID number) or default format
        """
        if id_num in self.id_names:
            return f"{self.id_names[id_num]} (ID {id_num:X})"
        return f"ID {id_num:X}"
    
    def get_used_ids(self) -> list[int]:
        """Get list of IDs that have events defined.
        
        Returns:
            Sorted list of IDs with at least one event
        """
        if not self.events:
            return []
        ids = set(event.id for event in self.events.values())
        return sorted(ids)
    
    def get_events_by_id(self) -> Dict[int, Dict[str, EventMk2]]:
        """Get events organized by ID.
        
        Returns:
            Dictionary mapping ID numbers to event dictionaries
        """
        result: Dict[int, Dict[str, EventMk2]] = {}
        for key, event in self.events.items():
            if event.id not in result:
                result[event.id] = {}
            result[event.id][key] = event
        return result
    
    def has_base_address(self) -> bool:
        """Check if base address is defined.
        
        Returns:
            True if base_address is set
        """
        return self.base_address is not None
    
    def get_physical_address(self, register_id: int) -> Optional[int]:
        """Calculate physical address for a register.
        
        Args:
            register_id: Register ID (0-15)
            
        Returns:
            Physical address if base_address is set, None otherwise
            
        Raises:
            ValueError: If register_id out of range
        """
        if not 0 <= register_id <= 15:
            raise ValueError(f"Invalid register ID {register_id}")
        
        if self.base_address is None:
            return None
        
        return self.base_address + (register_id * 4)  # 4 bytes per register
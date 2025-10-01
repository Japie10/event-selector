"""MK1 format implementation.

This module implements the MK1 event format with address-based
event identification and three subtabs (Data, Network, Application).
"""

from typing import Dict, Literal, Tuple
from pydantic import Field, field_validator, model_validator
import numpy as np

from .base import BaseFormatEvent, BaseFormat, StrictModel
from .constants import (
    FormatType,
    MaskMode,
    MK1_RANGES,
    MK1_NUM_REGISTERS,
    MK1_MAX_BIT,
)


# =====================
# MK1 Event Model
# =====================

class EventMk1(BaseFormatEvent):
    """MK1 event with address-based identification.
    
    MK1 events use hexadecimal addresses within three ranges:
    - Data:        0x000-0x07F (IDs 0-3)
    - Network:     0x200-0x27F (IDs 4-7)
    - Application: 0x400-0x47F (IDs 8-11)
    """
    
    address: str = Field(..., description="Event address in hex format (0xNNN)")
    _range: str = None  # MK1-specific: Data/Network/Application

    @field_validator('address')
    @classmethod
    def validate_and_normalize_address(cls, v: str | int) -> str:
        """Validate and normalize address using template method."""
        return cls.normalize_key(v)

    @model_validator(mode='after')
    def compute_id_and_bit(self) -> 'EventMk1':
        """Compute ID and bit from address using template method."""
        # Parse components
        id_val, bit_val = self.parse_key_components()
        
        # Validate range
        self.validate_key_range(id_val, bit_val)
        
        # Store computed values
        self._id = id_val
        self._bit = bit_val
        self._normalized_key = self.address
        
        return self

    # ========================================
    # Implement abstract methods from BaseFormatEvent
    # ========================================
    
    @classmethod
    def normalize_key(cls, raw_key: str | int) -> str:
        """Normalize MK1 address to 0xNNN format.
        
        Args:
            raw_key: Address as string or integer
            
        Returns:
            Normalized address in format 0xNNN
            
        Raises:
            ValueError: If address format is invalid
            
        Examples:
            >>> EventMk1.normalize_key("0x0")
            "0x000"
            >>> EventMk1.normalize_key(512)
            "0x200"
        """
        try:
            if isinstance(raw_key, str):
                addr_str = raw_key.lower().strip()
                if addr_str.startswith('0x'):
                    addr_value = int(addr_str, 16)
                else:
                    addr_value = int(addr_str, 16)
            else:
                addr_value = int(raw_key)

            return f"0x{addr_value:03X}"

        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid MK1 address format: {raw_key}") from e
    
    def parse_key_components(self) -> Tuple[int, int]:
        """Parse MK1 address into ID and bit.
        
        Returns:
            Tuple of (id, bit)
            
        Raises:
            ValueError: If address not in valid MK1 ranges
        """
        addr_value = int(self.address, 16)

        # Determine range and compute ID/bit
        for range_name, (start, end) in MK1_RANGES.items():
            if start <= addr_value <= end:
                base_id = {
                    "Data": 0,
                    "Network": 4,
                    "Application": 8
                }[range_name]

                offset = addr_value - start
                id_num = base_id + (offset // 32)
                bit = offset % 32
                
                # Store range name (MK1-specific)
                self._range = range_name
                
                return id_num, bit

        # If we get here, address is invalid
        raise ValueError(
            f"Address {self.address} not in valid MK1 ranges. "
            f"Valid: Data(0x000-0x07F), Network(0x200-0x27F), Application(0x400-0x47F)"
        )
    
    def validate_key_range(self, id_val: int, bit_val: int) -> None:
        """Validate MK1 ID and bit ranges.
        
        Args:
            id_val: ID value to validate
            bit_val: Bit value to validate
            
        Raises:
            ValueError: If ID or bit out of range
        """
        if not 0 <= id_val <= 11:
            raise ValueError(f"MK1 ID {id_val} out of range (must be 0-11)")
        if not 0 <= bit_val <= 31:
            raise ValueError(f"MK1 bit {bit_val} out of range (must be 0-31)")
    
    def get_raw_key_field(self) -> str:
        """Get raw address field.
        
        Returns:
            The address field value
        """
        return self.address

    # ========================================
    # MK1-specific properties and methods
    # ========================================
    
    @property
    def range_name(self) -> str:
        """Get range name (Data/Network/Application).
        
        Returns:
            Range name string
            
        Raises:
            ValueError: If event not properly initialized
        """
        if self._range is None:
            raise ValueError("Event not properly initialized (missing range)")
        return self._range
    
    def to_dict(self) -> Dict[str, str | int]:
        """Convert to dictionary with MK1-specific fields.
        
        Returns:
            Dictionary with all event data including MK1-specific fields
        """
        base_dict = super().to_dict()
        base_dict["address"] = self.address
        base_dict["range"] = self.range_name
        return base_dict


# =====================
# MK1 Format Model
# =====================

class Mk1Format(BaseFormat):
    """MK1 format with 12 registers organized into 3 subtabs.
    
    The MK1 format organizes events into three address ranges (subtabs):
    - Data (IDs 0-3): General data events
    - Network (IDs 4-7): Network-related events
    - Application (IDs 8-11): Application-specific events
    """
    
    events: Dict[str, EventMk1] = Field(default_factory=dict)

    @model_validator(mode='after')
    def validate_no_duplicate_addresses(self) -> 'Mk1Format':
        """Check for duplicate normalized addresses.
        
        Returns:
            Self for method chaining
            
        Raises:
            ValueError: If duplicate addresses found
        """
        normalized = {}
        for addr, event in self.events.items():
            norm_addr = event.normalized_key
            if norm_addr in normalized:
                raise ValueError(
                    f"Duplicate address: {addr} and {normalized[norm_addr]} "
                    f"both normalize to {norm_addr}"
                )
            normalized[norm_addr] = addr
        return self

    # ========================================
    # Implement abstract properties from BaseFormat
    # ========================================
    
    @property
    def format_type(self) -> FormatType:
        """Get format type.
        
        Returns:
            FormatType.MK1
        """
        return FormatType.MK1
    
    @property
    def num_registers(self) -> int:
        """Get number of registers.
        
        Returns:
            12 (MK1 has 12 registers)
        """
        return MK1_NUM_REGISTERS
    
    @property
    def max_bit(self) -> int:
        """Get maximum valid bit.
        
        Returns:
            31 (MK1 uses all 32 bits, 0-31)
        """
        return MK1_MAX_BIT

    # ========================================
    # Implement abstract methods from BaseFormat
    # ========================================
    
    def get_events_for_register(self, register_id: int) -> Dict[str, EventMk1]:
        """Get events for specific register.
        
        Args:
            register_id: Register ID (0-11)
            
        Returns:
            Dictionary of address -> event for that register
            
        Raises:
            ValueError: If register_id out of range
        """
        if not 0 <= register_id <= 11:
            raise ValueError(f"Invalid MK1 register ID {register_id} (must be 0-11)")
        
        return {
            addr: event 
            for addr, event in self.events.items()
            if event.id == register_id
        }
    
    def to_mask_array(self, mode: MaskMode = MaskMode.EVENT) -> np.ndarray:
        """Convert to mask array.
        
        Args:
            mode: Mask or trigger mode
            
        Returns:
            NumPy array of shape (12,) with uint32 values
            
        Note:
            This returns an array of zeros. Actual mask values
            come from GUI selections and are managed separately.
        """
        return np.zeros(12, dtype=np.uint32)
    
    def validate_event_key(self, key: str) -> bool:
        """Validate if key is valid MK1 address.
        
        Args:
            key: Address to validate
            
        Returns:
            True if valid MK1 address, False otherwise
        """
        try:
            normalized = EventMk1.normalize_key(key)
            # Try to create event to fully validate
            EventMk1(
                address=normalized,
                event_source="test",
                description="test"
            )
            return True
        except ValueError:
            return False

    # ========================================
    # MK1-specific methods
    # ========================================
    
    def get_subtab_events(
        self, 
        subtab: Literal["Data", "Network", "Application"]
    ) -> Dict[str, EventMk1]:
        """Get events for specific subtab.
        
        Args:
            subtab: Subtab name (Data, Network, or Application)
            
        Returns:
            Dictionary of address -> event for that subtab
        """
        return {
            addr: event 
            for addr, event in self.events.items()
            if event.range_name == subtab
        }
    
    def get_range_names(self) -> list[str]:
        """Get list of range names used in events.
        
        Returns:
            List of unique range names present in events
        """
        if not self.events:
            return []
        return list(set(event.range_name for event in self.events.values()))
    
    def get_events_by_range(self) -> Dict[str, Dict[str, EventMk1]]:
        """Get events organized by range.
        
        Returns:
            Dictionary mapping range names to event dictionaries
        """
        result = {"Data": {}, "Network": {}, "Application": {}}
        for addr, event in self.events.items():
            result[event.range_name][addr] = event
        return result
"""Export and import data models.

This module contains models for mask data export/import and metadata.
"""

from typing import Optional, List
from pydantic import Field, field_validator
import numpy as np

from .base import StrictModel
from .constants import FormatType, MaskMode, MK2_BIT_MASK


# =====================
# Export Metadata Model
# =====================

class ExportMetadata(StrictModel):
    """Metadata for exported mask/trigger files.
    
    Contains information about the source format, mode, and related files
    to enable proper round-trip import.
    """
    format: FormatType = Field(..., description="Source format (MK1 or MK2)")
    mode: MaskMode = Field(..., description="Mask or trigger mode")
    yaml: Optional[str] = Field(None, description="Source YAML filename")
    base_address: Optional[int] = Field(None, description="MK2 base address")
    id_names_hash: Optional[str] = Field(None, description="Hash of ID names")
    version: str = Field(..., description="Event Selector version")
    timestamp: str = Field(..., description="Export timestamp (ISO 8601)")


# =====================
# Mask Data Model
# =====================

class MaskData(StrictModel):
    """Mask data model for import/export.
    
    Represents mask or trigger data as a list of 32-bit values,
    one per register.
    """
    format_type: FormatType = Field(..., description="Format type")
    mode: MaskMode = Field(..., description="Mask or trigger mode")
    data: List[int] = Field(..., description="Mask values as integers")
    metadata: Optional[ExportMetadata] = Field(None, description="Optional metadata")

    @field_validator('data')
    @classmethod
    def validate_data_length(cls, v: List[int], info) -> List[int]:
        """Validate data array length based on format.
        
        Args:
            v: Data array
            info: Validation info with format_type
            
        Returns:
            Validated data array
            
        Raises:
            ValueError: If array length incorrect or values out of range
        """
        format_type = info.data.get('format_type')
        
        # Check length
        if format_type == FormatType.MK1:
            if len(v) != 12:
                raise ValueError(f"MK1 requires 12 values, got {len(v)}")
        elif format_type == FormatType.MK2:
            if len(v) != 16:
                raise ValueError(f"MK2 requires 16 values, got {len(v)}")

        # Validate each value is 32-bit
        for i, val in enumerate(v):
            if not 0 <= val <= 0xFFFFFFFF:
                raise ValueError(f"Value at index {i} out of 32-bit range: {val}")

        return v

    def to_numpy(self) -> np.ndarray:
        """Convert to NumPy array.
        
        Returns:
            NumPy array with uint32 dtype
        """
        arr = np.array(self.data, dtype=np.uint32)

        # For MK2, ensure bits 28-31 are zero
        if self.format_type == FormatType.MK2:
            arr &= MK2_BIT_MASK

        return arr

    @classmethod
    def from_numpy(
        cls, 
        arr: np.ndarray,
        format_type: FormatType,
        mode: MaskMode,
        metadata: Optional[ExportMetadata] = None
    ) -> 'MaskData':
        """Create from NumPy array.
        
        Args:
            arr: NumPy array with mask data
            format_type: Format type
            mode: Mask mode
            metadata: Optional metadata
            
        Returns:
            MaskData instance
        """
        # Ensure proper type
        arr = arr.astype(np.uint32)
        
        # For MK2, ensure bits 28-31 are zero
        if format_type == FormatType.MK2:
            arr = arr & MK2_BIT_MASK

        return cls(
            format_type=format_type,
            mode=mode,
            data=arr.tolist(),
            metadata=metadata
        )
    
    def get_register_value(self, register_id: int) -> int:
        """Get value for a specific register.
        
        Args:
            register_id: Register ID
            
        Returns:
            32-bit register value
            
        Raises:
            IndexError: If register_id out of range
        """
        return self.data[register_id]
    
    def set_register_value(self, register_id: int, value: int) -> None:
        """Set value for a specific register.
        
        Args:
            register_id: Register ID
            value: 32-bit value to set
            
        Raises:
            IndexError: If register_id out of range
            ValueError: If value out of 32-bit range
        """
        if not 0 <= value <= 0xFFFFFFFF:
            raise ValueError(f"Value {value} out of 32-bit range")
        
        # For MK2, enforce bit mask
        if self.format_type == FormatType.MK2:
            value &= MK2_BIT_MASK
        
        self.data[register_id] = value
    
    def is_bit_set(self, register_id: int, bit: int) -> bool:
        """Check if a specific bit is set.
        
        Args:
            register_id: Register ID
            bit: Bit position (0-31)
            
        Returns:
            True if bit is set
        """
        value = self.get_register_value(register_id)
        return bool(value & (1 << bit))
    
    def set_bit(self, register_id: int, bit: int, enabled: bool = True) -> None:
        """Set or clear a specific bit.
        
        Args:
            register_id: Register ID
            bit: Bit position (0-31)
            enabled: True to set, False to clear
        """
        value = self.get_register_value(register_id)
        
        if enabled:
            value |= (1 << bit)
        else:
            value &= ~(1 << bit)
        
        self.set_register_value(register_id, value)
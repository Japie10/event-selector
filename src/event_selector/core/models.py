"""Core Pydantic models for Event Selector.

This module defines the data models for mk1 and mk2 event formats,
including validation rules and normalization logic.
"""

from typing import Any, Optional, Dict, List, Literal
from enum import Enum
import re
from pathlib import Path

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
    ConfigDict,
    ValidationError,
)
import numpy as np
from event_selector.utils.logging import get_logger


# =====================
# Enums and Constants
# =====================

class FormatType(str, Enum):
    """Event format type enumeration."""
    MK1 = "mk1"
    MK2 = "mk2"


class MaskMode(str, Enum):
    """Mask mode enumeration."""
    MASK = "mask"
    TRIGGER = "trigger"


class ValidationLevel(str, Enum):
    """Validation error severity levels."""
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class ValidationCode(str, Enum):
    """Validation error codes."""
    MK1_ADDR_RANGE = "MK1_ADDR_RANGE"
    MK2_ADDR_RANGE = "MK2_ADDR_RANGE"
    KEY_FORMAT = "KEY_FORMAT"
    DUPLICATE_KEY = "DUPLICATE_KEY"
    BITS_28_31_FORCED_ZERO = "BITS_28_31_FORCED_ZERO"
    INVALID_COLOR_FALLBACK = "INVALID_COLOR_FALLBACK"
    MISSING_FILE_RESTORED = "MISSING_FILE_RESTORED"


# MK1 valid address ranges
MK1_RANGES = {
    "Data": (0x000, 0x07F),      # IDs 0-3
    "Network": (0x200, 0x27F),   # IDs 4-7
    "Application": (0x400, 0x47F) # IDs 8-11
}

# MK2 constants
MK2_MAX_ID = 15  # 0-15
MK2_MAX_BIT = 27  # 0-27 valid, 28-31 invalid
MK2_BIT_MASK = 0x0FFFFFFF  # Mask for valid bits


# =====================
# Base Models
# =====================

class StrictModel(BaseModel):
    """Base model with strict validation."""
    model_config = ConfigDict(
        validate_assignment=True,
        extra="forbid",
        str_strip_whitespace=True,
        use_enum_values=False,
    )


class EventSource(StrictModel):
    """Event source definition."""
    source_id: str = Field(..., min_length=1, max_length=2)
    name: str = Field(..., min_length=1, max_length=500)
    @field_validator('source_id')
    @classmethod
    def validate_source_id(cls, v: str) -> str:
        """Validate source name."""
        try:
            int(v, 16)
        except ValueError:
            raise ValueError(f"Source ID must be a hexadecimal string: {v}")
        return v

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate source name."""
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError(f"Source name must be alphanumeric (with _ or -): {v}")
        return v


class BaseEvent(StrictModel):
    """Base event model."""
    event_source: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1, max_length=500)
    info: str = Field("", max_length=500)

    @field_validator('event_source')
    @classmethod
    def validate_event_source(cls, v: str) -> str:
        """Validate event source reference."""
        if not v.strip():
            raise ValueError("Event source cannot be empty")
        return v.strip()


# =====================
# MK1 Models
# =====================

def normalize_mk1_address(address: str | int) -> str:
    """Normalize MK1 address to 0xNNN format.

    Args:
        address: Address as string (hex) or integer

    Returns:
        Normalized address string in format 0xNNN

    Raises:
        ValueError: If address format is invalid
    """
    try:
        if isinstance(address, str):
            # Remove 0x prefix if present
            addr_str = address.lower().strip()
            if addr_str.startswith('0x'):
                addr_value = int(addr_str, 16)
            else:
                # Try as hex without prefix
                addr_value = int(addr_str, 16)
        else:
            addr_value = int(address)

        # Format as 0xNNN (3 hex digits)
        return f"0x{addr_value:03X}"

    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid address format: {address}") from e


def validate_mk1_address_range(address: str) -> tuple[str, int, int]:
    """Validate MK1 address is in valid range.

    Args:
        address: Normalized address string

    Returns:
        Tuple of (range_name, id, bit)

    Raises:
        ValueError: If address is out of valid ranges
    """
    addr_value = int(address, 16)

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

            return range_name, id_num, bit

    raise ValueError(
        f"Address {address} not in valid MK1 ranges. "
        f"Valid ranges: Data(0x000-0x07F), Network(0x200-0x27F), Application(0x400-0x47F)"
    )


class EventMk1(BaseEvent):
    """MK1 event model."""
    address: str = Field(..., description="Event address in hex format")
    _normalized_address: str = None
    _id: int = None
    _bit: int = None
    _range: str = None

    @field_validator('address')
    @classmethod
    def validate_and_normalize_address(cls, v: str | int) -> str:
        """Validate and normalize address."""
        return normalize_mk1_address(v)

    @model_validator(mode='after')
    def validate_address_range(self) -> 'EventMk1':
        """Validate address is in valid range and compute ID/bit."""
        range_name, id_num, bit = validate_mk1_address_range(self.address)
        self._range = range_name
        self._id = id_num
        self._bit = bit
        self._normalized_address = self.address
        return self

    @property
    def id(self) -> int:
        """Get computed ID (0-11)."""
        return self._id

    @property
    def bit(self) -> int:
        """Get computed bit position (0-31)."""
        return self._bit

    @property
    def range_name(self) -> str:
        """Get range name (Data/Network/Application)."""
        return self._range


class Mk1Format(StrictModel):
    """Complete MK1 format model."""
    sources: List[EventSource] = Field(default_factory=list)
    events: Dict[str, EventMk1] = Field(default_factory=dict)

    @model_validator(mode='after')
    def validate_no_duplicate_addresses(self) -> 'Mk1Format':
        """Check for duplicate normalized addresses."""
        normalized = {}
        for addr, event in self.events.items():
            norm_addr = event._normalized_address
            if norm_addr in normalized:
                raise ValueError(
                    f"Duplicate address after normalization: "
                    f"{addr} and {normalized[norm_addr]} both normalize to {norm_addr}"
                )
            normalized[norm_addr] = addr
        return self

    @model_validator(mode='after')
    def validate_event_sources(self) -> 'Mk1Format':
        """Validate that all event sources are defined."""
        if not self.sources:
            return self  # Sources are optional

        source_names = {s.name for s in self.sources}
        for event in self.events.values():
            if event.event_source not in source_names:
                # Just a warning, not an error
                pass  # Could log warning here
        return self

    @property
    def format_type(self) -> FormatType:
        return FormatType.MK1

    def get_subtab_events(self, subtab: Literal["Data", "Network", "Application"]) -> Dict[str, EventMk1]:
        """Get events for a specific subtab."""
        return {
            addr: event 
            for addr, event in self.events.items()
            if event.range_name == subtab
        }

    def to_mask_array(self, mode: MaskMode = MaskMode.MASK) -> np.ndarray:
        """Convert events to mask array.

        Args:
            mode: Mask or trigger mode

        Returns:
            NumPy array of shape (12,) with uint32 values
        """
        mask = np.zeros(12, dtype=np.uint32)
        # This would be populated based on GUI selections
        return mask


# =====================
# MK2 Models
# =====================

def normalize_mk2_key(key: str | int) -> str:
    """Normalize MK2 key to 0xibb format.

    Args:
        key: Key as string (hex) or integer

    Returns:
        Normalized key string in format 0xibb

    Raises:
        ValueError: If key format is invalid
    """
    try:
        if isinstance(key, str):
            key_str = key.lower().strip()
            if key_str.startswith('0x'):
                key_value = int(key_str, 16)
            else:
                key_value = int(key_str, 16)
        else:
            key_value = int(key)

        # Extract ID and bit
        id_part = (key_value >> 8) & 0xF
        bit_part = key_value & 0xFF

        # Validate ranges
        if id_part > MK2_MAX_ID:
            raise ValueError(f"ID {id_part} exceeds maximum {MK2_MAX_ID}")
        if bit_part > MK2_MAX_BIT:
            raise ValueError(f"Bit {bit_part} exceeds maximum {MK2_MAX_BIT}")

        # Format as 0xibb
        return f"0x{id_part:01X}{bit_part:02X}"

    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid MK2 key format: {key}") from e


class EventMk2(BaseEvent):
    """MK2 event model."""
    key: str = Field(..., description="Event key in 0xibb format")
    _normalized_key: str = None
    _id: int = None
    _bit: int = None

    @field_validator('key')
    @classmethod
    def validate_and_normalize_key(cls, v: str | int) -> str:
        """Validate and normalize key."""
        return normalize_mk2_key(v)

    @model_validator(mode='after')
    def extract_id_and_bit(self) -> 'EventMk2':
        """Extract ID and bit from normalized key."""
        key_value = int(self.key, 16)
        self._id = (key_value >> 8) & 0xF
        self._bit = key_value & 0xFF
        self._normalized_key = self.key
        return self

    @property
    def id(self) -> int:
        """Get ID (0-15)."""
        return self._id

    @property
    def bit(self) -> int:
        """Get bit position (0-27)."""
        return self._bit


class Mk2Format(StrictModel):
    """Complete MK2 format model."""
    sources: List[EventSource] = Field(default_factory=list)
    id_names: Dict[int, str] = Field(default_factory=dict)
    base_address: Optional[int] = Field(None, ge=0, le=0xFFFFFFFF)
    events: Dict[str, EventMk2] = Field(default_factory=dict)

    @field_validator('id_names')
    @classmethod
    def validate_id_names(cls, v: Dict[int, str]) -> Dict[int, str]:
        """Validate ID names."""
        for id_num, name in v.items():
            if not 0 <= id_num <= MK2_MAX_ID:
                raise ValueError(f"Invalid ID {id_num}, must be 0-{MK2_MAX_ID}")
            if not name or not name.strip():
                raise ValueError(f"Empty name for ID {id_num}")
        return v

    @field_validator('base_address')
    @classmethod
    def validate_base_address(cls, v: Optional[int]) -> Optional[int]:
        """Validate base address is 32-bit."""
        if v is not None and v > 0xFFFFFFFF:
            raise ValueError(f"Base address {v:#x} exceeds 32-bit range")
        return v

    @model_validator(mode='after')
    def validate_no_duplicate_keys(self) -> 'Mk2Format':
        """Check for duplicate normalized keys."""
        normalized = {}
        for key, event in self.events.items():
            norm_key = event._normalized_key
            if norm_key in normalized:
                raise ValueError(
                    f"Duplicate key after normalization: "
                    f"{key} and {normalized[norm_key]} both normalize to {norm_key}"
                )
            normalized[norm_key] = key
        return self

    @property
    def format_type(self) -> FormatType:
        return FormatType.MK2

    def get_id_events(self, id_num: int) -> Dict[str, EventMk2]:
        """Get events for a specific ID."""
        return {
            key: event
            for key, event in self.events.items()
            if event.id == id_num
        }

    def get_id_name(self, id_num: int) -> str:
        """Get name for an ID, with fallback."""
        if id_num in self.id_names:
            return f"{self.id_names[id_num]} (ID {id_num:X})"
        return f"ID {id_num:X}"

    def to_mask_array(self, mode: MaskMode = MaskMode.MASK) -> np.ndarray:
        """Convert events to mask array.

        Args:
            mode: Mask or trigger mode

        Returns:
            NumPy array of shape (16,) with uint32 values
        """
        mask = np.zeros(16, dtype=np.uint32)
        # Ensure bits 28-31 are always zero
        for i in range(16):
            mask[i] &= MK2_BIT_MASK
        return mask


# =====================
# Validation Models
# =====================

class ValidationIssue(StrictModel):
    """Validation issue model."""
    code: ValidationCode
    level: ValidationLevel
    message: str
    location: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class ValidationResult(StrictModel):
    """Validation result containing all issues."""
    issues: List[ValidationIssue] = Field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return any(issue.level == ValidationLevel.ERROR for issue in self.issues)

    @property
    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return any(issue.level == ValidationLevel.WARNING for issue in self.issues)

    def get_errors(self) -> List[ValidationIssue]:
        """Get only error-level issues."""
        return [i for i in self.issues if i.level == ValidationLevel.ERROR]

    def get_warnings(self) -> List[ValidationIssue]:
        """Get only warning-level issues."""
        return [i for i in self.issues if i.level == ValidationLevel.WARNING]

    def add_issue(self, 
                  code: ValidationCode,
                  level: ValidationLevel,
                  message: str,
                  location: Optional[str] = None,
                  details: Optional[Dict[str, Any]] = None) -> None:
        """Add a validation issue."""
        issue = ValidationIssue(
            code=code,
            level=level,
            message=message,
            location=location,
            details=details
        )

        self.issues.append(issue)


# =====================
# Export/Import Models
# =====================

class ExportMetadata(StrictModel):
    """Metadata for exported files."""
    format: FormatType
    mode: MaskMode
    yaml: Optional[str] = None
    base_address: Optional[int] = None
    id_names_hash: Optional[str] = None
    version: str
    timestamp: str


class MaskData(StrictModel):
    """Mask data model for import/export."""
    format_type: FormatType
    mode: MaskMode
    data: List[int] = Field(..., description="Mask values as integers")
    metadata: Optional[ExportMetadata] = None

    @field_validator('data')
    @classmethod
    def validate_data_length(cls, v: List[int], info) -> List[int]:
        """Validate data array length based on format."""
        format_type = info.data.get('format_type')
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
        """Convert to NumPy array."""
        arr = np.array(self.data, dtype=np.uint32)

        # For MK2, ensure bits 28-31 are zero
        if self.format_type == FormatType.MK2:
            arr &= MK2_BIT_MASK

        return arr

    @classmethod
    def from_numpy(cls, 
                   arr: np.ndarray,
                   format_type: FormatType,
                   mode: MaskMode,
                   metadata: Optional[ExportMetadata] = None) -> 'MaskData':
        """Create from NumPy array."""
        if format_type == FormatType.MK2:
            # Ensure bits 28-31 are zero
            arr = arr & MK2_BIT_MASK

        return cls(
            format_type=format_type,
            mode=mode,
            data=arr.tolist(),
            metadata=metadata
        )


# =====================
# Session Models
# =====================

class SessionState(StrictModel):
    """Session state for autosave/restore."""
    open_files: List[str] = Field(default_factory=list)
    active_tab: Optional[int] = None
    active_subtab: Optional[int] = None
    scroll_positions: Dict[str, int] = Field(default_factory=dict)
    window_geometry: Optional[Dict[str, int]] = None
    dock_states: Dict[str, bool] = Field(default_factory=dict)
    mask_states: Dict[str, List[int]] = Field(default_factory=dict)
    trigger_states: Dict[str, List[int]] = Field(default_factory=dict)
    current_mode: MaskMode = MaskMode.MASK

    def add_file(self, filepath: str) -> None:
        """Add a file to the session."""
        if filepath not in self.open_files:
            self.open_files.append(filepath)

    def remove_file(self, filepath: str) -> None:
        """Remove a file from the session."""
        if filepath in self.open_files:
            self.open_files.remove(filepath)
            # Also remove associated states
            self.mask_states.pop(filepath, None)
            self.trigger_states.pop(filepath, None)

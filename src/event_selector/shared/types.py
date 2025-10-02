"""Core type definitions used throughout the application."""

from enum import Enum, auto
from typing import NewType, TypeAlias, Literal, TypedDict, NotRequired
from dataclasses import dataclass

# Basic type aliases
EventKey = NewType('EventKey', str)       # Normalized event key (0xNNN for mk1, 0xibb for mk2)
EventID = NewType('EventID', int)         # Register ID (0-11 for mk1, 0-15 for mk2)
BitPosition = NewType('BitPosition', int) # Bit position (0-31)
Address = NewType('Address', int)         # 32-bit address value

# Type aliases for clarity
MaskArray: TypeAlias = list[int]  # Array of 32-bit mask values
HexString: TypeAlias = str        # Hex string like "0xNNN" or "0xibb"


class FormatType(str, Enum):
    """Event format type enumeration."""
    MK1 = "mk1"
    MK2 = "mk2"
    # Reserved for future
    MK3 = "mk3"


class MaskMode(str, Enum):
    """Mask mode enumeration."""
    EVENT = "event"      # Event mask mode
    CAPTURE = "capture"  # Capture mask mode


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
    INVALID_BASE_ADDRESS = "INVALID_BASE_ADDRESS"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"


@dataclass(frozen=True)
class EventCoordinate:
    """Immutable coordinate for an event in the register space."""
    id: EventID
    bit: BitPosition

    def __post_init__(self):
        if not 0 <= self.id <= 255:  # Support up to 256 IDs
            raise ValueError(f"Invalid ID: {self.id}")
        if not 0 <= self.bit <= 31:
            raise ValueError(f"Invalid bit position: {self.bit}")


@dataclass(frozen=True)
class AddressRange:
    """Immutable address range."""
    start: Address
    end: Address
    name: str

    def __post_init__(self):
        if self.start > self.end:
            raise ValueError(f"Invalid range: {self.start:#x} > {self.end:#x}")
        if self.start > 0xFFFFFFFF or self.end > 0xFFFFFFFF:
            raise ValueError("Address exceeds 32-bit range")

    def contains(self, address: int) -> bool:
        """Check if address is within range."""
        return self.start <= address <= self.end


# MK1 specific ranges
MK1_RANGES = {
    "Data": AddressRange(Address(0x000), Address(0x07F), "Data"),
    "Network": AddressRange(Address(0x200), Address(0x27F), "Network"),
    "Application": AddressRange(Address(0x400), Address(0x47F), "Application"),
}

# MK2 constants
MK2_MAX_ID = 15
MK2_MAX_BIT = 27
MK2_BIT_MASK = 0x0FFFFFFF  # Mask for valid bits (28-31 invalid)


class ExportFormat(str, Enum):
    """Export format types."""
    FORMAT_A = "format_a"  # <ID2> <VALUE8>
    FORMAT_B = "format_b"  # <ADDR8> <VALUE8>


class MetadataDict(TypedDict):
    """Type definition for metadata."""
    format: str
    mode: NotRequired[str]
    yaml: NotRequired[str]
    base_address: NotRequired[str]
    version: NotRequired[str]
    timestamp: NotRequired[str]
    id_names_hash: NotRequired[str]

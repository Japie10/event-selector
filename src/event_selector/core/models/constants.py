"""Constants and enumerations for Event Selector.

This module contains all constants, enums, and magic numbers used
throughout the application.
"""

from enum import Enum


# =====================
# Enums
# =====================

class FormatType(str, Enum):
    """Event format type enumeration."""
    MK1 = "mk1"
    MK2 = "mk2"


class MaskMode(str, Enum):
    """Mask mode enumeration."""
    EVENT = "event_mask"
    CAPTURE = "capture_mask"


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


# =====================
# MK1 Constants
# =====================

MK1_RANGES = {
    "Data": (0x000, 0x07F),       # IDs 0-3
    "Network": (0x200, 0x27F),    # IDs 4-7
    "Application": (0x400, 0x47F) # IDs 8-11
}

MK1_NUM_REGISTERS = 12
MK1_MAX_BIT = 31


# =====================
# MK2 Constants
# =====================

MK2_MAX_ID = 15           # 0-15
MK2_MAX_BIT = 27          # 0-27 valid, 28-31 invalid
MK2_BIT_MASK = 0x0FFFFFFF # Mask for valid bits (bits 0-27)
MK2_NUM_REGISTERS = 16


# =====================
# Common Constants
# =====================

BITS_PER_REGISTER = 32
MAX_UINT32 = 0xFFFFFFFF
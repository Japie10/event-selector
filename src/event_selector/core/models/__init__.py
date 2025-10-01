"""Event Selector core models package.

This package contains all data models for the Event Selector application,
organized into logical modules:

- constants: Enums and constants
- base: Abstract base classes and common models
- mk1: MK1 format implementation
- mk2: MK2 format implementation
- validation: Validation models
- export: Export/import models
- session: Session state models
"""

# Re-export everything for backward compatibility
from .constants import (
    # Enums
    FormatType,
    MaskMode,
    ValidationLevel,
    ValidationCode,
    # MK1 Constants
    MK1_RANGES,
    MK1_NUM_REGISTERS,
    MK1_MAX_BIT,
    # MK2 Constants
    MK2_MAX_ID,
    MK2_MAX_BIT,
    MK2_BIT_MASK,
    MK2_NUM_REGISTERS,
    # Common Constants
    BITS_PER_REGISTER,
    MAX_UINT32,
)

from .base import (
    # Base classes
    StrictModel,
    EventSource,
    BaseFormatEvent,
    BaseFormat,
)

from .mk1 import (
    EventMk1,
    Mk1Format,
)

from .mk2 import (
    EventMk2,
    Mk2Format,
)

from .validation import (
    ValidationIssue,
    ValidationResult,
)

from .export import (
    ExportMetadata,
    MaskData,
)

from .session import (
    SessionState,
)


__all__ = [
    # Enums
    "FormatType",
    "MaskMode",
    "ValidationLevel",
    "ValidationCode",
    
    # Constants
    "MK1_RANGES",
    "MK1_NUM_REGISTERS",
    "MK1_MAX_BIT",
    "MK2_MAX_ID",
    "MK2_MAX_BIT",
    "MK2_BIT_MASK",
    "MK2_NUM_REGISTERS",
    "BITS_PER_REGISTER",
    "MAX_UINT32",
    
    # Base classes
    "StrictModel",
    "EventSource",
    "BaseFormatEvent",
    "BaseFormat",
    
    # MK1
    "EventMk1",
    "Mk1Format",
    
    # MK2
    "EventMk2",
    "Mk2Format",
    
    # Validation
    "ValidationIssue",
    "ValidationResult",
    
    # Export/Import
    "ExportMetadata",
    "MaskData",
    
    # Session
    "SessionState",
]
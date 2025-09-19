"""Core package for Event Selector."""

from event_selector.core.models import (
    FormatType,
    MaskMode,
    ValidationLevel,
    ValidationCode,
    EventSource,
    EventMk1,
    EventMk2,
    Mk1Format,
    Mk2Format,
    ValidationIssue,
    ValidationResult,
    ExportMetadata,
    MaskData,
    SessionState
)
from event_selector.core.parser import (
    EventParser,
    parse_yaml_file,
    parse_yaml_data,
    detect_format
)
from event_selector.core.validator import (
    Validator,
    validate_format,
    validate_mask,
    aggregate_errors
)
from event_selector.core.exporter import (
    Exporter,
    export_mask,
    export_from_format,
    parse_metadata_header
)
from event_selector.core.importer import (
    Importer,
    import_mask_file,
    detect_mask_format,
    find_associated_yaml
)

__all__ = [
    # Models
    "FormatType",
    "MaskMode",
    "ValidationLevel",
    "ValidationCode",
    "EventSource",
    "EventMk1",
    "EventMk2",
    "Mk1Format",
    "Mk2Format",
    "ValidationIssue",
    "ValidationResult",
    "ExportMetadata",
    "MaskData",
    "SessionState",
    # Parser
    "EventParser",
    "parse_yaml_file",
    "parse_yaml_data",
    "detect_format",
    # Validator
    "Validator",
    "validate_format",
    "validate_mask",
    "aggregate_errors",
    # Exporter
    "Exporter",
    "export_mask",
    "export_from_format",
    "parse_metadata_header",
    # Importer
    "Importer",
    "import_mask_file",
    "detect_mask_format",
    "find_associated_yaml"
]

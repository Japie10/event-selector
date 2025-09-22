"""Validation logic for events and masks.

This module provides comprehensive validation for mk1 and mk2 formats,
including cross-validation, mask validation, and error aggregation.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, TypeAlias
from collections import defaultdict

import numpy as np

from event_selector.core.models import (
    FormatType,
    MaskMode,
    ValidationResult,
    ValidationCode,
    ValidationLevel,
    ValidationIssue,
    EventMk1,
    EventMk2,
    Mk1Format,
    Mk2Format,
    MaskData,
    MK1_RANGES,
    MK2_MAX_ID,
    MK2_MAX_BIT,
    MK2_BIT_MASK,
)

FormatObject: TypeAlias = Mk1Format | Mk2Format

class Validator:
    """Comprehensive validator for event formats and masks."""

    def __init__(self):
        """Initialize validator."""
        self.result = ValidationResult()
        self._reset_state()

    def _reset_state(self) -> None:
        """Reset validator state."""
        self.result = ValidationResult()
        self._seen_addresses: Set[str] = set()
        self._seen_keys: Set[str] = set()
        self._source_names: Set[str] = set()
        self._undefined_sources: Set[str] = set()

    def validate_mk1_format(self, format_obj: Mk1Format) -> ValidationResult:
        """Validate complete MK1 format.

        Args:
            format_obj: MK1 format object to validate

        Returns:
            ValidationResult with all issues found
        """
        self._reset_state()

        # Validate sources
        self._validate_sources(format_obj.sources)

        # Validate events
        for addr, event in format_obj.events.items():
            self._validate_mk1_event(addr, event)

        # Cross-validation
        self._validate_mk1_cross_references(format_obj)

        # Check for required elements
        if not format_obj.events:
            self.result.add_issue(
                code=ValidationCode.KEY_FORMAT,
                level=ValidationLevel.WARNING,
                message="No events defined in MK1 format"
            )

        return self.result

    def validate_mk2_format(self, format_obj: Mk2Format) -> ValidationResult:
        """Validate complete MK2 format.

        Args:
            format_obj: MK2 format object to validate

        Returns:
            ValidationResult with all issues found
        """
        self._reset_state()

        # Validate sources
        self._validate_sources(format_obj.sources)

        # Validate id_names
        self._validate_id_names(format_obj.id_names)

        # Validate base_address
        if format_obj.base_address is not None:
            self._validate_base_address(format_obj.base_address)

        # Validate events
        for key, event in format_obj.events.items():
            self._validate_mk2_event(key, event)

        # Cross-validation
        self._validate_mk2_cross_references(format_obj)

        # Check for required elements
        if not format_obj.events:
            self.result.add_issue(
                code=ValidationCode.KEY_FORMAT,
                level=ValidationLevel.WARNING,
                message="No events defined in MK2 format"
            )

        return self.result

    def validate_mask_data(self, mask_data: MaskData) -> ValidationResult:
        """Validate mask data.

        Args:
            mask_data: Mask data to validate

        Returns:
            ValidationResult with all issues found
        """
        self._reset_state()

        # Validate data length
        expected_length = 12 if mask_data.format_type == FormatType.MK1 else 16
        if len(mask_data.data) != expected_length:
            self.result.add_issue(
                code=ValidationCode.KEY_FORMAT,
                level=ValidationLevel.ERROR,
                message=f"{mask_data.format_type.value} requires {expected_length} values, got {len(mask_data.data)}"
            )

        # Validate value ranges
        for i, value in enumerate(mask_data.data):
            if not 0 <= value <= 0xFFFFFFFF:
                self.result.add_issue(
                    code=ValidationCode.KEY_FORMAT,
                    level=ValidationLevel.ERROR,
                    message=f"Mask value at index {i} out of 32-bit range: {value}",
                    location=f"data[{i}]"
                )

            # For MK2, check bits 28-31
            if mask_data.format_type == FormatType.MK2 and (value & ~MK2_BIT_MASK):
                self.result.add_issue(
                    code=ValidationCode.BITS_28_31_FORCED_ZERO,
                    level=ValidationLevel.WARNING,
                    message=f"MK2 mask at ID {i} has bits 28-31 set, will be forced to zero",
                    location=f"data[{i}]",
                    details={"value": value, "masked": value & MK2_BIT_MASK}
                )

        return self.result

    def validate_mask_compatibility(self,
                                   mask_data: MaskData,
                                   format_obj: FormatObject) -> ValidationResult:
        """Validate that mask is compatible with format definition.

        Args:
            mask_data: Mask data to validate
            format_obj: Format definition to check against

        Returns:
            ValidationResult with compatibility issues
        """
        self._reset_state()

        # Check format type match
        if isinstance(format_obj, Mk1Format) and mask_data.format_type != FormatType.MK1:
            self.result.add_issue(
                code=ValidationCode.KEY_FORMAT,
                level=ValidationLevel.ERROR,
                message="Mask format MK2 does not match definition format MK1"
            )
            return self.result

        if isinstance(format_obj, Mk2Format) and mask_data.format_type != FormatType.MK2:
            self.result.add_issue(
                code=ValidationCode.KEY_FORMAT,
                level=ValidationLevel.ERROR,
                message="Mask format MK1 does not match definition format MK2"
            )
            return self.result

        # Check which bits are set in mask vs defined events
        mask_array = np.array(mask_data.data, dtype=np.uint32)

        if isinstance(format_obj, Mk1Format):
            self._validate_mk1_mask_compatibility(mask_array, format_obj)
        else:
            self._validate_mk2_mask_compatibility(mask_array, format_obj)

        return self.result

    def _validate_sources(self, sources: List) -> None:
        """Validate event sources."""
        seen_names = set()

        for i, source in enumerate(sources):
            # Check for duplicate names
            if source.name in seen_names:
                self.result.add_issue(
                    code=ValidationCode.DUPLICATE_KEY,
                    level=ValidationLevel.WARNING,
                    message=f"Duplicate source name: {source.name}",
                    location=f"sources[{i}]"
                )
            seen_names.add(source.name)
            self._source_names.add(source.name)

            # Validate name format
            if not re.match(r'^[a-zA-Z0-9_-]+$', source.name):
                self.result.add_issue(
                    code=ValidationCode.KEY_FORMAT,
                    level=ValidationLevel.WARNING,
                    message=f"Source name contains invalid characters: {source.name}",
                    location=f"sources[{i}].name"
                )

    def _validate_mk1_event(self, addr: str, event: EventMk1) -> None:
        """Validate individual MK1 event."""
        # Check for duplicate normalized address
        norm_addr = event._normalized_address
        if norm_addr in self._seen_addresses:
            self.result.add_issue(
                code=ValidationCode.DUPLICATE_KEY,
                level=ValidationLevel.ERROR,
                message=f"Duplicate normalized address: {norm_addr}",
                location=addr
            )
        self._seen_addresses.add(norm_addr)

        # Validate address is in valid range
        addr_val = int(norm_addr, 16)
        valid = False
        for range_name, (start, end) in MK1_RANGES.items():
            if start <= addr_val <= end:
                valid = True
                break

        if not valid:
            self.result.add_issue(
                code=ValidationCode.MK1_ADDR_RANGE,
                level=ValidationLevel.ERROR,
                message=f"Address {norm_addr} not in valid MK1 ranges",
                location=addr,
                details={"address": norm_addr, "value": addr_val}
            )

        # Check event source reference
        if event.event_source not in self._source_names:
            self._undefined_sources.add(event.event_source)

        # Validate ID and bit are within expected ranges
        if hasattr(event, '_id') and event._id is not None:
            if not 0 <= event._id <= 11:
                self.result.add_issue(
                    code=ValidationCode.MK1_ADDR_RANGE,
                    level=ValidationLevel.ERROR,
                    message=f"Computed ID {event._id} out of range (0-11)",
                    location=addr
                )

        if hasattr(event, '_bit') and event._bit is not None:
            if not 0 <= event._bit <= 31:
                self.result.add_issue(
                    code=ValidationCode.MK1_ADDR_RANGE,
                    level=ValidationLevel.ERROR,
                    message=f"Computed bit {event._bit} out of range (0-31)",
                    location=addr
                )

    def _validate_mk2_event(self, key: str, event: EventMk2) -> None:
        """Validate individual MK2 event."""
        # Check for duplicate normalized key
        norm_key = event._normalized_key
        if norm_key in self._seen_keys:
            self.result.add_issue(
                code=ValidationCode.DUPLICATE_KEY,
                level=ValidationLevel.ERROR,
                message=f"Duplicate normalized key: {norm_key}",
                location=key
            )
        self._seen_keys.add(norm_key)

        # Validate ID is in valid range
        if hasattr(event, '_id') and event._id is not None:
            if not 0 <= event._id <= MK2_MAX_ID:
                self.result.add_issue(
                    code=ValidationCode.MK2_ADDR_RANGE,
                    level=ValidationLevel.ERROR,
                    message=f"ID {event._id} exceeds maximum {MK2_MAX_ID}",
                    location=key
                )

        # Validate bit is in valid range
        if hasattr(event, '_bit') and event._bit is not None:
            if event._bit > MK2_MAX_BIT:
                self.result.add_issue(
                    code=ValidationCode.MK2_ADDR_RANGE,
                    level=ValidationLevel.ERROR,
                    message=f"Bit {event._bit} exceeds maximum {MK2_MAX_BIT}",
                    location=key
                )
            elif event._bit >= 28:
                # This shouldn't happen if model validation works
                self.result.add_issue(
                    code=ValidationCode.BITS_28_31_FORCED_ZERO,
                    level=ValidationLevel.ERROR,
                    message=f"Bit {event._bit} is in invalid range 28-31",
                    location=key
                )

        # Check event source reference
        if event.event_source not in self._source_names:
            self._undefined_sources.add(event.event_source)

    def _validate_id_names(self, id_names: Dict[int, str]) -> None:
        """Validate ID names."""
        for id_num, name in id_names.items():
            if not 0 <= id_num <= MK2_MAX_ID:
                self.result.add_issue(
                    code=ValidationCode.MK2_ADDR_RANGE,
                    level=ValidationLevel.ERROR,
                    message=f"Invalid ID {id_num} in id_names (must be 0-{MK2_MAX_ID})",
                    location=f"id_names[{id_num}]"
                )

            if not name or not name.strip():
                self.result.add_issue(
                    code=ValidationCode.KEY_FORMAT,
                    level=ValidationLevel.WARNING,
                    message=f"Empty name for ID {id_num}",
                    location=f"id_names[{id_num}]"
                )

    def _validate_base_address(self, base_address: int) -> None:
        """Validate base address."""
        if base_address > 0xFFFFFFFF:
            self.result.add_issue(
                code=ValidationCode.MK2_ADDR_RANGE,
                level=ValidationLevel.ERROR,
                message=f"Base address {base_address:#x} exceeds 32-bit range",
                location="base_address"
            )

        # Check alignment (typically should be 4-byte aligned)
        if base_address % 4 != 0:
            self.result.add_issue(
                code=ValidationCode.KEY_FORMAT,
                level=ValidationLevel.WARNING,
                message=f"Base address {base_address:#x} is not 4-byte aligned",
                location="base_address"
            )

    def _validate_mk1_cross_references(self, format_obj: Mk1Format) -> None:
        """Cross-validate MK1 format references."""
        # Report undefined event sources
        if self._undefined_sources and self._source_names:
            for source in self._undefined_sources:
                self.result.add_issue(
                    code=ValidationCode.KEY_FORMAT,
                    level=ValidationLevel.WARNING,
                    message=f"Event source '{source}' is not defined in sources list",
                    details={"undefined": source, "defined": list(self._source_names)}
                )

        # Check for gaps in event definitions
        self._check_mk1_coverage(format_obj)

    def _validate_mk2_cross_references(self, format_obj: Mk2Format) -> None:
        """Cross-validate MK2 format references."""
        # Report undefined event sources
        if self._undefined_sources and self._source_names:
            for source in self._undefined_sources:
                self.result.add_issue(
                    code=ValidationCode.KEY_FORMAT,
                    level=ValidationLevel.WARNING,
                    message=f"Event source '{source}' is not defined in sources list",
                    details={"undefined": source, "defined": list(self._source_names)}
                )

        # Check for missing ID names
        used_ids = set()
        for event in format_obj.events.values():
            if hasattr(event, '_id'):
                used_ids.add(event._id)

        for id_num in used_ids:
            if id_num not in format_obj.id_names:
                self.result.add_issue(
                    code=ValidationCode.KEY_FORMAT,
                    level=ValidationLevel.INFO,
                    message=f"ID {id_num} has events but no name defined",
                    location=f"id_names"
                )

    def _check_mk1_coverage(self, format_obj: Mk1Format) -> None:
        """Check coverage of MK1 address space."""
        # Group events by subtab
        subtab_coverage = defaultdict(set)

        for event in format_obj.events.values():
            if hasattr(event, 'range_name') and hasattr(event, '_id'):
                subtab_coverage[event.range_name].add(event._id)

        # Report empty subtabs
        for subtab in ["Data", "Network", "Application"]:
            if subtab not in subtab_coverage:
                self.result.add_issue(
                    code=ValidationCode.KEY_FORMAT,
                    level=ValidationLevel.INFO,
                    message=f"No events defined for {subtab} subtab"
                )
            else:
                # Check for missing IDs in subtab
                expected_ids = {
                    "Data": {0, 1, 2, 3},
                    "Network": {4, 5, 6, 7},
                    "Application": {8, 9, 10, 11}
                }[subtab]

                missing_ids = expected_ids - subtab_coverage[subtab]
                if missing_ids:
                    self.result.add_issue(
                        code=ValidationCode.KEY_FORMAT,
                        level=ValidationLevel.INFO,
                        message=f"{subtab} subtab missing events for IDs: {sorted(missing_ids)}"
                    )

    def _validate_mk1_mask_compatibility(self, mask: np.ndarray, format_obj: Mk1Format) -> None:
        """Validate MK1 mask compatibility with format definition."""
        # Create a map of defined events
        defined_events = set()
        for event in format_obj.events.values():
            if hasattr(event, '_id') and hasattr(event, '_bit'):
                defined_events.add((event._id, event._bit))

        # Check each bit in mask
        for id_idx in range(12):
            mask_value = mask[id_idx]
            for bit in range(32):
                if mask_value & (1 << bit):
                    if (id_idx, bit) not in defined_events:
                        self.result.add_issue(
                            code=ValidationCode.KEY_FORMAT,
                            level=ValidationLevel.WARNING,
                            message=f"Mask has bit set for undefined event at ID {id_idx}, bit {bit}",
                            location=f"mask[{id_idx}]",
                            details={"id": id_idx, "bit": bit}
                        )

    def _validate_mk2_mask_compatibility(self, mask: np.ndarray, format_obj: Mk2Format) -> None:
        """Validate MK2 mask compatibility with format definition."""
        # Create a map of defined events
        defined_events = set()
        for event in format_obj.events.values():
            if hasattr(event, '_id') and hasattr(event, '_bit'):
                defined_events.add((event._id, event._bit))

        # Check each bit in mask
        for id_idx in range(16):
            mask_value = mask[id_idx]

            # Check bits 28-31 are not set
            if mask_value & ~MK2_BIT_MASK:
                self.result.add_issue(
                    code=ValidationCode.BITS_28_31_FORCED_ZERO,
                    level=ValidationLevel.ERROR,
                    message=f"MK2 mask at ID {id_idx} has invalid bits 28-31 set",
                    location=f"mask[{id_idx}]"
                )

            # Check each valid bit
            for bit in range(28):
                if mask_value & (1 << bit):
                    if (id_idx, bit) not in defined_events:
                        self.result.add_issue(
                            code=ValidationCode.KEY_FORMAT,
                            level=ValidationLevel.WARNING,
                            message=f"Mask has bit set for undefined event at ID {id_idx}, bit {bit}",
                            location=f"mask[{id_idx}]",
                            details={"id": id_idx, "bit": bit}
                        )


def validate_format(format_obj: FormatObject) -> ValidationResult:
    """Convenience function to validate a format object.

    Args:
        format_obj: Format object to validate

    Returns:
        ValidationResult with all issues found
    """
    validator = Validator()

    if isinstance(format_obj, Mk1Format):
        return validator.validate_mk1_format(format_obj)
    elif isinstance(format_obj, Mk2Format):
        return validator.validate_mk2_format(format_obj)
    else:
        result = ValidationResult()
        result.add_issue(
            code=ValidationCode.KEY_FORMAT,
            level=ValidationLevel.ERROR,
            message=f"Unknown format type: {type(format_obj).__name__}"
        )
        return result


def validate_mask(mask_data: MaskData,
                  format_obj: Optional[FormatObject] = None) -> ValidationResult:
    """Convenience function to validate mask data.

    Args:
        mask_data: Mask data to validate
        format_obj: Optional format to check compatibility against

    Returns:
        ValidationResult with all issues found
    """
    validator = Validator()

    # Validate mask data itself
    result = validator.validate_mask_data(mask_data)

    # If format provided, check compatibility
    if format_obj is not None:
        validator_compat = Validator()
        compat_result = validator_compat.validate_mask_compatibility(mask_data, format_obj)

        # Merge results
        for issue in compat_result.issues:
            result.issues.append(issue)

    return result


def aggregate_errors(*results: ValidationResult) -> ValidationResult:
    """Aggregate multiple validation results.

    Args:
        *results: Variable number of ValidationResult objects

    Returns:
        Single ValidationResult with all issues aggregated
    """
    aggregated = ValidationResult()

    for result in results:
        for issue in result.issues:
            aggregated.issues.append(issue)

    return aggregated
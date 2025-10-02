"""Domain validation service for event formats and masks."""

from typing import Optional, Set, Dict, Any

from event_selector.shared.types import (
    FormatType, ValidationCode, ValidationLevel,
    MK1_RANGES, MK2_MAX_ID, MK2_MAX_BIT
)
from event_selector.domain.models.base import EventFormat, MaskData
from event_selector.domain.models.mk1 import Mk1Format
from event_selector.domain.models.mk2 import Mk2Format
from event_selector.domain.interfaces.format_strategy import ValidationResult


class ValidationService:
    """Service for validating event formats and mask data."""
    
    def validate_format(self, format_obj: EventFormat) -> ValidationResult:
        """Validate an event format.
        
        Args:
            format_obj: Format to validate
            
        Returns:
            ValidationResult with any issues found
        """
        result = ValidationResult()
        
        # Dispatch to appropriate validator
        if isinstance(format_obj, Mk1Format):
            self._validate_mk1_format(format_obj, result)
        elif isinstance(format_obj, Mk2Format):
            self._validate_mk2_format(format_obj, result)
        else:
            result.add_error(
                ValidationCode.KEY_FORMAT,
                f"Unknown format type: {type(format_obj).__name__}"
            )
        
        return result
    
    def validate_mask_data(self, mask_data: MaskData) -> ValidationResult:
        """Validate mask data.
        
        Args:
            mask_data: Mask data to validate
            
        Returns:
            ValidationResult with any issues found
        """
        result = ValidationResult()
        
        # Check data size
        expected_sizes = {
            FormatType.MK1: 12,
            FormatType.MK2: 16,
        }
        
        expected_size = expected_sizes.get(mask_data.format_type)
        if expected_size and len(mask_data.data) != expected_size:
            result.add_error(
                ValidationCode.KEY_FORMAT,
                f"Invalid mask size for {mask_data.format_type.value}: "
                f"expected {expected_size}, got {len(mask_data.data)}"
            )
        
        # Check value ranges
        for i, value in enumerate(mask_data.data):
            if not isinstance(value, (int, np.integer)):
                result.add_error(
                    ValidationCode.KEY_FORMAT,
                    f"Mask value at index {i} is not an integer"
                )
            elif value < 0:
                result.add_error(
                    ValidationCode.KEY_FORMAT,
                    f"Mask value at index {i} is negative: {value}"
                )
            elif value > 0xFFFFFFFF:
                result.add_error(
                    ValidationCode.KEY_FORMAT,
                    f"Mask value at index {i} exceeds 32-bit range: {value:#x}"
                )
        
        # Check MK2 bit restrictions
        if mask_data.format_type == FormatType.MK2:
            for i, value in enumerate(mask_data.data):
                if value & 0xF0000000:  # Bits 28-31 set
                    result.add_warning(
                        ValidationCode.BITS_28_31_FORCED_ZERO,
                        f"Register {i:02X} has bits 28-31 set, these will be forced to zero",
                        location=f"ID_{i:02X}"
                    )
        
        return result
    
    def validate_consistency(self, 
                           format_obj: EventFormat,
                           mask_data: MaskData) -> ValidationResult:
        """Validate consistency between format and mask.
        
        Args:
            format_obj: Event format
            mask_data: Mask data
            
        Returns:
            ValidationResult with any issues found
        """
        result = ValidationResult()
        
        # Check format type matches
        if format_obj.format_type != mask_data.format_type:
            result.add_error(
                ValidationCode.KEY_FORMAT,
                f"Format type mismatch: format is {format_obj.format_type.value}, "
                f"mask is {mask_data.format_type.value}"
            )
            return result  # Can't do further validation if types don't match
        
        # Check for bits set without corresponding events
        for id_num in range(len(mask_data.data)):
            mask_value = mask_data.data[id_num]
            if mask_value == 0:
                continue
            
            for bit_pos in range(32):
                if mask_value & (1 << bit_pos):
                    # Check if event exists for this bit
                    if not self._has_event_at_position(format_obj, id_num, bit_pos):
                        result.add_warning(
                            ValidationCode.KEY_FORMAT,
                            f"Bit set at ID {id_num:02X} bit {bit_pos} but no event defined",
                            location=f"ID_{id_num:02X}_bit_{bit_pos}"
                        )
        
        return result
    
    def _validate_mk1_format(self, format_obj: Mk1Format, result: ValidationResult):
        """Validate MK1 format specifics."""
        # Check for events in valid ranges
        for key, event in format_obj.events.items():
            addr_value = event.address.value
            
            # Check if in any valid range
            valid = False
            for range_name, addr_range in MK1_RANGES.items():
                if addr_range.contains(addr_value):
                    valid = True
                    break
            
            if not valid:
                result.add_error(
                    ValidationCode.MK1_ADDR_RANGE,
                    f"Address {event.address.hex} not in valid MK1 ranges",
                    location=key
                )
        
        # Check for source references
        defined_sources = {s.name for s in format_obj.sources}
        for key, event in format_obj.events.items():
            if event.info.source and event.info.source not in defined_sources:
                result.add_warning(
                    ValidationCode.KEY_FORMAT,
                    f"Event {key} references undefined source: {event.info.source}",
                    location=key
                )
        
        # Check coverage
        self._check_mk1_coverage(format_obj, result)
    
    def _validate_mk2_format(self, format_obj: Mk2Format, result: ValidationResult):
        """Validate MK2 format specifics."""
        # Check events are in valid range
        for key, event in format_obj.events.items():
            if event.id > MK2_MAX_ID:
                result.add_error(
                    ValidationCode.MK2_ADDR_RANGE,
                    f"Event {key} has invalid ID {event.id} (max: {MK2_MAX_ID})",
                    location=key
                )
            
            if event.bit > MK2_MAX_BIT:
                result.add_error(
                    ValidationCode.MK2_ADDR_RANGE,
                    f"Event {key} has invalid bit {event.bit} (max: {MK2_MAX_BIT})",
                    location=key
                )
        
        # Validate ID names
        for id_num, name in format_obj.id_names.items():
            if not 0 <= id_num <= MK2_MAX_ID:
                result.add_error(
                    ValidationCode.MK2_ADDR_RANGE,
                    f"Invalid ID {id_num} in id_names (must be 0-{MK2_MAX_ID})",
                    location='id_names'
                )
            
            if not name or not name.strip():
                result.add_warning(
                    ValidationCode.KEY_FORMAT,
                    f"Empty name for ID {id_num}",
                    location=f"id_names[{id_num}]"
                )
        
        # Check base address if present
        if format_obj.base_address is not None:
            if format_obj.base_address > 0xFFFFFFFF:
                result.add_error(
                    ValidationCode.INVALID_BASE_ADDRESS,
                    f"Base address {format_obj.base_address:#x} exceeds 32-bit range"
                )
            elif format_obj.base_address & 0x3:  # Not 4-byte aligned
                result.add_warning(
                    ValidationCode.INVALID_BASE_ADDRESS,
                    f"Base address {format_obj.base_address:#x} is not 4-byte aligned"
                )
    
    def _check_mk1_coverage(self, format_obj: Mk1Format, result: ValidationResult):
        """Check MK1 subtab coverage."""
        # Count events per subtab
        subtab_events = {
            "Data": 0,
            "Network": 0,
            "Application": 0
        }
        
        for event in format_obj.events.values():
            coord = event.get_coordinate()
            if 0 <= coord.id <= 3:
                subtab_events["Data"] += 1
            elif 4 <= coord.id <= 7:
                subtab_events["Network"] += 1
            elif 8 <= coord.id <= 11:
                subtab_events["Application"] += 1
        
        # Report missing coverage
        for subtab, count in subtab_events.items():
            if count == 0:
                result.add_info(
                    ValidationCode.KEY_FORMAT,
                    f"No events defined for {subtab} subtab"
                )
    
    def _has_event_at_position(self, 
                              format_obj: EventFormat,
                              id_num: int,
                              bit_pos: int) -> bool:
        """Check if an event exists at the given ID and bit position."""
        for event in format_obj.events.values():
            coord = event.get_coordinate()
            if coord.id == id_num and coord.bit == bit_pos:
                return True
        return False


import numpy as np  # Import at the end to avoid circular dependency issues
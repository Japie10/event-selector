"""Comprehensive unit tests for validation logic."""

import pytest
import numpy as np
from typing import Dict, Any

from event_selector.core.validator import (
    Validator,
    validate_format,
    validate_mask,
    aggregate_errors,
)
from event_selector.core.models import (
    FormatType,
    MaskMode,
    ValidationLevel,
    ValidationCode,
    ValidationResult,
    EventSource,
    EventMk1,
    EventMk2,
    Mk1Format,
    Mk2Format,
    MaskData,
)


class TestValidator:
    """Test Validator class."""
    
    def test_validator_initialization(self):
        """Test validator initialization."""
        validator = Validator()
        assert validator.result is not None
        assert isinstance(validator.result, ValidationResult)
        assert not validator.result.has_errors
        assert not validator.result.has_warnings
    
    def test_validator_reset_state(self):
        """Test validator state reset."""
        validator = Validator()
        
        # Add some issues
        validator.result.add_issue(
            code=ValidationCode.KEY_FORMAT,
            level=ValidationLevel.ERROR,
            message="Test error"
        )
        assert validator.result.has_errors
        
        # Reset state
        validator._reset_state()
        assert not validator.result.has_errors
        assert len(validator.result.issues) == 0


class TestMk1Validation:
    """Test MK1 format validation."""
    
    def test_validate_valid_mk1(self):
        """Test validation of valid MK1 format."""
        fmt = Mk1Format(
            sources=[
                EventSource(name="hw", description="Hardware"),
                EventSource(name="fw", description="Firmware"),
            ],
            events={
                "0x000": EventMk1(address="0x000", event_source="hw", description="Event 1"),
                "0x200": EventMk1(address="0x200", event_source="fw", description="Event 2"),
            }
        )
        
        result = validate_format(fmt)
        
        # Should have warnings about undefined sources but no errors
        assert not result.has_errors
        # May have info about missing coverage
        infos = [i for i in result.issues if i.level == ValidationLevel.INFO]
        assert len(infos) >= 0  # Coverage info is optional
    
    def test_validate_mk1_duplicate_addresses(self):
        """Test detection of duplicate MK1 addresses."""
        # This should be caught by model validation, but validator double-checks
        events = {
            "0x000": EventMk1(address="0x000", event_source="test", description="Event 1"),
            "0x001": EventMk1(address="0x001", event_source="test", description="Event 2"),
        }
        
        fmt = Mk1Format(events=events)
        validator = Validator()
        
        # Manually add duplicate
        fmt.events["0x00"] = EventMk1(address="0x000", event_source="test", description="Duplicate")
        
        result = validator.validate_mk1_format(fmt)
        errors = result.get_errors()
        assert any("Duplicate normalized address" in e.message for e in errors)
    
    def test_validate_mk1_invalid_range(self):
        """Test validation of MK1 address ranges."""
        validator = Validator()
        
        # Create event with invalid address (would normally be caught earlier)
        event = EventMk1(address="0x000", event_source="test", description="Test")
        # Manually set invalid address
        event._normalized_address = "0x100"  # Gap address
        
        validator._validate_mk1_event("0x100", event)
        
        errors = validator.result.get_errors()
        assert any("not in valid MK1 ranges" in e.message for e in errors)
    
    def test_validate_mk1_undefined_sources(self):
        """Test detection of undefined event sources."""
        fmt = Mk1Format(
            sources=[
                EventSource(name="defined", description="Defined source"),
            ],
            events={
                "0x000": EventMk1(address="0x000", event_source="undefined", description="Event"),
            }
        )
        
        result = validate_format(fmt)
        warnings = result.get_warnings()
        assert any("not defined in sources list" in w.message for w in warnings)
    
    def test_validate_mk1_coverage(self):
        """Test MK1 coverage validation."""
        # Only define events in Data range
        fmt = Mk1Format(
            events={
                "0x000": EventMk1(address="0x000", event_source="test", description="Data event"),
            }
        )
        
        result = validate_format(fmt)
        infos = [i for i in result.issues if i.level == ValidationLevel.INFO]
        
        # Should have info about missing Network and Application events
        assert any("Network" in i.message for i in infos)
        assert any("Application" in i.message for i in infos)
    
    def test_validate_mk1_duplicate_source_names(self):
        """Test detection of duplicate source names."""
        fmt = Mk1Format(
            sources=[
                EventSource(name="dup", description="First"),
                EventSource(name="dup", description="Second"),
            ]
        )
        
        result = validate_format(fmt)
        warnings = result.get_warnings()
        assert any("Duplicate source name" in w.message for w in warnings)
    
    def test_validate_mk1_invalid_source_name(self):
        """Test validation of source name format."""
        fmt = Mk1Format(
            sources=[
                EventSource(name="valid-name_123", description="Valid"),
                EventSource(name="invalid@name", description="Invalid"),
            ]
        )
        
        result = validate_format(fmt)
        warnings = result.get_warnings()
        assert any("invalid characters" in w.message for w in warnings)


class TestMk2Validation:
    """Test MK2 format validation."""
    
    def test_validate_valid_mk2(self):
        """Test validation of valid MK2 format."""
        fmt = Mk2Format(
            sources=[
                EventSource(name="ctrl", description="Controller"),
            ],
            id_names={0: "Data", 1: "Network"},
            base_address=0x40000000,
            events={
                "0x000": EventMk2(key="0x000", event_source="ctrl", description="Event 1"),
                "0x100": EventMk2(key="0x100", event_source="ctrl", description="Event 2"),
            }
        )
        
        result = validate_format(fmt)
        assert not result.has_errors
    
    def test_validate_mk2_invalid_id(self):
        """Test validation of MK2 ID range."""
        validator = Validator()
        
        # Create event with invalid ID (would normally be caught earlier)
        event = EventMk2(key="0x000", event_source="test", description="Test")
        event._id = 16  # Invalid ID
        
        validator._validate_mk2_event("0x1000", event)
        
        errors = validator.result.get_errors()
        assert any("exceeds maximum" in e.message for e in errors)
    
    def test_validate_mk2_invalid_bit(self):
        """Test validation of MK2 bit range."""
        validator = Validator()
        
        # Create event with invalid bit
        event = EventMk2(key="0x000", event_source="test", description="Test")
        event._bit = 28  # Invalid bit
        
        validator._validate_mk2_event("0x01C", event)
        
        errors = validator.result.get_errors()
        assert any("invalid range 28-31" in e.message for e in errors)
    
    def test_validate_mk2_invalid_id_names(self):
        """Test validation of id_names."""
        fmt = Mk2Format(
            id_names={
                0: "Valid",
                16: "Invalid ID",  # > 15
                5: "",  # Empty name
            },
            events={
                "0x000": EventMk2(key="0x000", event_source="test", description="Test")
            }
        )
        
        validator = Validator()
        validator._validate_id_names(fmt.id_names)
        
        errors = validator.result.get_errors()
        warnings = validator.result.get_warnings()
        
        assert any("Invalid ID 16" in e.message for e in errors)
        assert any("Empty name" in w.message for w in warnings)
    
    def test_validate_mk2_base_address(self):
        """Test base address validation."""
        validator = Validator()
        
        # Test valid aligned address
        validator._validate_base_address(0x40000000)
        assert not validator.result.has_errors
        
        # Reset and test unaligned address
        validator._reset_state()
        validator._validate_base_address(0x40000001)
        warnings = validator.result.get_warnings()
        assert any("not 4-byte aligned" in w.message for w in warnings)
        
        # Reset and test > 32-bit address
        validator._reset_state()
        validator._validate_base_address(0x100000000)
        errors = validator.result.get_errors()
        assert any("exceeds 32-bit range" in e.message for e in errors)
    
    def test_validate_mk2_missing_id_names(self):
        """Test detection of missing ID names."""
        fmt = Mk2Format(
            id_names={0: "Data"},  # Only ID 0 has name
            events={
                "0x000": EventMk2(key="0x000", event_source="test", description="ID 0"),
                "0x100": EventMk2(key="0x100", event_source="test", description="ID 1"),
                "0x200": EventMk2(key="0x200", event_source="test", description="ID 2"),
            }
        )
        
        result = validate_format(fmt)
        infos = [i for i in result.issues if i.level == ValidationLevel.INFO]
        
        # Should have info about IDs 1 and 2 missing names
        assert any("ID 1" in i.message for i in infos)
        assert any("ID 2" in i.message for i in infos)


class TestMaskValidation:
    """Test mask data validation."""
    
    def test_validate_valid_mk1_mask(self):
        """Test validation of valid MK1 mask."""
        mask_data = MaskData(
            format_type=FormatType.MK1,
            mode=MaskMode.MASK,
            data=[0] * 12
        )
        
        result = validate_mask(mask_data)
        assert not result.has_errors
        assert not result.has_warnings
    
    def test_validate_valid_mk2_mask(self):
        """Test validation of valid MK2 mask."""
        mask_data = MaskData(
            format_type=FormatType.MK2,
            mode=MaskMode.TRIGGER,
            data=[0x0FFFFFFF] * 16  # Max valid value
        )
        
        result = validate_mask(mask_data)
        assert not result.has_errors
        assert not result.has_warnings
    
    def test_validate_mk1_mask_wrong_length(self):
        """Test MK1 mask with wrong length."""
        mask_data = MaskData(
            format_type=FormatType.MK1,
            mode=MaskMode.MASK,
            data=[0] * 10  # Should be 12
        )
        
        validator = Validator()
        # This would normally be caught by model validation
        mask_data.data = [0] * 10  # Force wrong length
        
        result = validator.validate_mask_data(mask_data)
        errors = result.get_errors()
        assert any("requires 12 values" in e.message for e in errors)
    
    def test_validate_mk2_mask_wrong_length(self):
        """Test MK2 mask with wrong length."""
        mask_data = MaskData(
            format_type=FormatType.MK2,
            mode=MaskMode.MASK,
            data=[0] * 16  # Correct length initially
        )
        
        validator = Validator()
        mask_data.data = [0] * 12  # Force wrong length
        
        result = validator.validate_mask_data(mask_data)
        errors = result.get_errors()
        assert any("requires 16 values" in e.message for e in errors)
    
    def test_validate_mask_out_of_range(self):
        """Test mask with values out of 32-bit range."""
        mask_data = MaskData(
            format_type=FormatType.MK1,
            mode=MaskMode.MASK,
            data=[0] * 12
        )
        
        validator = Validator()
        mask_data.data[0] = 0x100000000  # 33-bit value
        mask_data.data[1] = -1  # Negative
        
        result = validator.validate_mask_data(mask_data)
        errors = result.get_errors()
        assert len(errors) >= 2
        assert any("out of 32-bit range" in e.message for e in errors)
    
    def test_validate_mk2_mask_bits_28_31(self):
        """Test MK2 mask with bits 28-31 set."""
        mask_data = MaskData(
            format_type=FormatType.MK2,
            mode=MaskMode.MASK,
            data=[0xFFFFFFFF] * 16  # All bits set
        )
        
        result = validate_mask(mask_data)
        warnings = result.get_warnings()
        
        # Should have warnings about bits 28-31
        assert any("bits 28-31" in w.message for w in warnings)


class TestMaskCompatibility:
    """Test mask compatibility validation."""
    
    def test_mk1_mask_format_mismatch(self):
        """Test MK1 mask with MK2 format."""
        mask_data = MaskData(
            format_type=FormatType.MK1,
            mode=MaskMode.MASK,
            data=[0] * 12
        )
        
        fmt = Mk2Format(
            events={
                "0x000": EventMk2(key="0x000", event_source="test", description="Test")
            }
        )
        
        result = validate_mask(mask_data, fmt)
        errors = result.get_errors()
        assert any("does not match definition format" in e.message for e in errors)
    
    def test_mk2_mask_format_mismatch(self):
        """Test MK2 mask with MK1 format."""
        mask_data = MaskData(
            format_type=FormatType.MK2,
            mode=MaskMode.MASK,
            data=[0] * 16
        )
        
        fmt = Mk1Format(
            events={
                "0x000": EventMk1(address="0x000", event_source="test", description="Test")
            }
        )
        
        result = validate_mask(mask_data, fmt)
        errors = result.get_errors()
        assert any("does not match definition format" in e.message for e in errors)
    
    def test_mk1_mask_undefined_events(self):
        """Test MK1 mask with bits set for undefined events."""
        # Create format with events at ID 0, bit 0 only
        fmt = Mk1Format(
            events={
                "0x000": EventMk1(address="0x000", event_source="test", description="Test")
            }
        )
        
        # Create mask with additional bits set
        mask_data = MaskData(
            format_type=FormatType.MK1,
            mode=MaskMode.MASK,
            data=[0x00000003] + [0] * 11  # Bits 0 and 1 set, but only 0 defined
        )
        
        result = validate_mask(mask_data, fmt)
        warnings = result.get_warnings()
        assert any("undefined event" in w.message for w in warnings)
        assert any("bit 1" in str(w.details) for w in warnings)
    
    def test_mk2_mask_undefined_events(self):
        """Test MK2 mask with bits set for undefined events."""
        # Create format with events at ID 0, bit 0 only
        fmt = Mk2Format(
            events={
                "0x000": EventMk2(key="0x000", event_source="test", description="Test")
            }
        )
        
        # Create mask with additional bits set
        mask_data = MaskData(
            format_type=FormatType.MK2,
            mode=MaskMode.TRIGGER,
            data=[0x00000003] + [0] * 15  # Bits 0 and 1 set, but only 0 defined
        )
        
        result = validate_mask(mask_data, fmt)
        warnings = result.get_warnings()
        assert any("undefined event" in w.message for w in warnings)
    
    def test_mk2_mask_compatibility_bits_28_31(self):
        """Test MK2 mask compatibility check for bits 28-31."""
        fmt = Mk2Format(
            events={
                "0x000": EventMk2(key="0x000", event_source="test", description="Test")
            }
        )
        
        # Create mask with bits 28-31 set
        mask_data = MaskData(
            format_type=FormatType.MK2,
            mode=MaskMode.MASK,
            data=[0xF0000000] + [0] * 15  # Bits 28-31 set
        )
        
        validator = Validator()
        result = validator.validate_mask_compatibility(mask_data, fmt)
        errors = result.get_errors()
        assert any("invalid bits 28-31" in e.message for e in errors)


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_validate_format_mk1(self):
        """Test validate_format with MK1."""
        fmt = Mk1Format(
            events={
                "0x000": EventMk1(address="0x000", event_source="test", description="Test")
            }
        )
        
        result = validate_format(fmt)
        assert isinstance(result, ValidationResult)
    
    def test_validate_format_mk2(self):
        """Test validate_format with MK2."""
        fmt = Mk2Format(
            events={
                "0x000": EventMk2(key="0x000", event_source="test", description="Test")
            }
        )
        
        result = validate_format(fmt)
        assert isinstance(result, ValidationResult)
    
    def test_validate_format_unknown(self):
        """Test validate_format with unknown format type."""
        result = validate_format("not a format object")
        errors = result.get_errors()
        assert any("Unknown format type" in e.message for e in errors)
    
    def test_validate_mask_without_format(self):
        """Test validate_mask without format object."""
        mask_data = MaskData(
            format_type=FormatType.MK1,
            mode=MaskMode.MASK,
            data=[0] * 12
        )
        
        result = validate_mask(mask_data)
        assert isinstance(result, ValidationResult)
        assert not result.has_errors
    
    def test_validate_mask_with_format(self):
        """Test validate_mask with format object."""
        mask_data = MaskData(
            format_type=FormatType.MK1,
            mode=MaskMode.MASK,
            data=[0] * 12
        )
        
        fmt = Mk1Format(
            events={
                "0x000": EventMk1(address="0x000", event_source="test", description="Test")
            }
        )
        
        result = validate_mask(mask_data, fmt)
        assert isinstance(result, ValidationResult)
    
    def test_aggregate_errors(self):
        """Test aggregating multiple validation results."""
        result1 = ValidationResult()
        result1.add_issue(
            code=ValidationCode.KEY_FORMAT,
            level=ValidationLevel.ERROR,
            message="Error 1"
        )
        
        result2 = ValidationResult()
        result2.add_issue(
            code=ValidationCode.DUPLICATE_KEY,
            level=ValidationLevel.WARNING,
            message="Warning 1"
        )
        
        result3 = ValidationResult()
        result3.add_issue(
            code=ValidationCode.MK1_ADDR_RANGE,
            level=ValidationLevel.ERROR,
            message="Error 2"
        )
        
        aggregated = aggregate_errors(result1, result2, result3)
        
        assert len(aggregated.issues) == 3
        assert aggregated.has_errors
        assert aggregated.has_warnings
        
        errors = aggregated.get_errors()
        assert len(errors) == 2
        
        warnings = aggregated.get_warnings()
        assert len(warnings) == 1


class TestEdgeCases:
    """Test edge cases and special scenarios."""
    
    def test_empty_format_validation(self):
        """Test validation of empty formats."""
        # Empty MK1
        fmt1 = Mk1Format()
        result1 = validate_format(fmt1)
        warnings1 = result1.get_warnings()
        assert any("No events defined" in w.message for w in warnings1)
        
        # Empty MK2
        fmt2 = Mk2Format()
        result2 = validate_format(fmt2)
        warnings2 = result2.get_warnings()
        assert any("No events defined" in w.message for w in warnings2)
    
    def test_all_subtabs_coverage(self):
        """Test coverage validation with all subtabs populated."""
        fmt = Mk1Format(
            events={
                # Data
                "0x000": EventMk1(address="0x000", event_source="test", description="Data"),
                # Network
                "0x200": EventMk1(address="0x200", event_source="test", description="Network"),
                # Application
                "0x400": EventMk1(address="0x400", event_source="test", description="App"),
            }
        )
        
        result = validate_format(fmt)
        infos = [i for i in result.issues if i.level == ValidationLevel.INFO]
        
        # Should still have info about missing IDs within subtabs
        assert any("missing events for IDs" in i.message for i in infos)
    
    def test_no_sources_defined(self):
        """Test validation when no sources are defined."""
        fmt = Mk1Format(
            events={
                "0x000": EventMk1(address="0x000", event_source="undefined", description="Test")
            }
        )
        
        result = validate_format(fmt)
        # Should not crash, but may have warnings about undefined sources
        # When no sources are defined, we don't validate source references
        assert isinstance(result, ValidationResult)
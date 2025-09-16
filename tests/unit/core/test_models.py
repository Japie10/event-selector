"""Comprehensive unit tests for Pydantic models."""

import pytest
from pydantic import ValidationError
import numpy as np
from typing import Dict, Any

from event_selector.core.models import (
    # Enums
    FormatType,
    MaskMode,
    ValidationLevel,
    ValidationCode,
    
    # Constants
    MK1_RANGES,
    MK2_MAX_ID,
    MK2_MAX_BIT,
    MK2_BIT_MASK,
    
    # Models
    EventSource,
    EventMk1,
    EventMk2,
    Mk1Format,
    Mk2Format,
    ValidationIssue,
    ValidationResult,
    ExportMetadata,
    MaskData,
    SessionState,
    
    # Functions
    normalize_mk1_address,
    validate_mk1_address_range,
    normalize_mk2_key,
)


class TestEventSource:
    """Test EventSource model."""
    
    def test_valid_source(self):
        """Test creating valid event source."""
        source = EventSource(name="hardware", description="Hardware events")
        assert source.name == "hardware"
        assert source.description == "Hardware events"
    
    def test_source_with_underscores(self):
        """Test source name with underscores."""
        source = EventSource(name="test_source", description="Test")
        assert source.name == "test_source"
    
    def test_source_with_hyphens(self):
        """Test source name with hyphens."""
        source = EventSource(name="test-source", description="Test")
        assert source.name == "test-source"
    
    def test_invalid_source_name(self):
        """Test invalid source name with special characters."""
        with pytest.raises(ValidationError) as exc:
            EventSource(name="test@source", description="Test")
        assert "alphanumeric" in str(exc.value)
    
    def test_empty_name(self):
        """Test empty source name."""
        with pytest.raises(ValidationError):
            EventSource(name="", description="Test")
    
    def test_empty_description(self):
        """Test empty description."""
        with pytest.raises(ValidationError):
            EventSource(name="test", description="")
    
    def test_whitespace_stripping(self):
        """Test that whitespace is stripped."""
        source = EventSource(name="  test  ", description="  Test  ")
        assert source.name == "test"
        assert source.description == "Test"
    
    def test_missing_field(self):
        """Test validation with missing field."""
        with pytest.raises(ValidationError) as exc:
            EventSource(name="hardware")
        assert "description" in str(exc.value)


class TestMk1Address:
    """Test MK1 address normalization and validation."""
    
    def test_normalize_hex_string(self):
        """Test normalizing hex string addresses."""
        assert normalize_mk1_address("0x000") == "0x000"
        assert normalize_mk1_address("0x00") == "0x000"
        assert normalize_mk1_address("0x0") == "0x000"
        assert normalize_mk1_address("0x200") == "0x200"
        assert normalize_mk1_address("0x47F") == "0x47F"
    
    def test_normalize_hex_without_prefix(self):
        """Test normalizing hex without 0x prefix."""
        assert normalize_mk1_address("000") == "0x000"
        assert normalize_mk1_address("200") == "0x200"
        assert normalize_mk1_address("47f") == "0x47F"
    
    def test_normalize_integer(self):
        """Test normalizing integer addresses."""
        assert normalize_mk1_address(0) == "0x000"
        assert normalize_mk1_address(512) == "0x200"  # 0x200
        assert normalize_mk1_address(1151) == "0x47F"  # 0x47F
    
    def test_normalize_with_leading_zeros(self):
        """Test normalization preserves correct format."""
        assert normalize_mk1_address("0x001") == "0x001"
        assert normalize_mk1_address("0x010") == "0x010"
        assert normalize_mk1_address("0x100") == "0x100"
    
    def test_validate_mk1_ranges(self):
        """Test MK1 address range validation."""
        # Data range
        range_name, id_num, bit = validate_mk1_address_range("0x000")
        assert range_name == "Data"
        assert id_num == 0
        assert bit == 0
        
        range_name, id_num, bit = validate_mk1_address_range("0x020")
        assert range_name == "Data"
        assert id_num == 1
        assert bit == 0
        
        # Network range
        range_name, id_num, bit = validate_mk1_address_range("0x200")
        assert range_name == "Network"
        assert id_num == 4
        assert bit == 0
        
        # Application range
        range_name, id_num, bit = validate_mk1_address_range("0x400")
        assert range_name == "Application"
        assert id_num == 8
        assert bit == 0
    
    def test_invalid_mk1_range(self):
        """Test invalid MK1 address ranges."""
        with pytest.raises(ValueError) as exc:
            validate_mk1_address_range("0x080")  # Gap between Data and Network
        assert "not in valid MK1 ranges" in str(exc.value)
        
        with pytest.raises(ValueError):
            validate_mk1_address_range("0x500")  # Beyond Application range


class TestEventMk1:
    """Test EventMk1 model."""
    
    def test_valid_event(self):
        """Test creating valid mk1 event."""
        event = EventMk1(
            address="0x000",
            event_source="hardware",
            description="Test event",
            info="Normal"
        )
        assert event.address == "0x000"
        assert event.id == 0
        assert event.bit == 0
        assert event.range_name == "Data"
    
    def test_address_normalization_in_model(self):
        """Test address normalization within model."""
        event = EventMk1(
            address="0x00",  # Will be normalized
            event_source="test",
            description="Test"
        )
        assert event.address == "0x000"
    
    def test_integer_address(self):
        """Test using integer address."""
        event = EventMk1(
            address=512,  # 0x200
            event_source="test",
            description="Test"
        )
        assert event.address == "0x200"
        assert event.range_name == "Network"
        assert event.id == 4
    
    def test_computed_properties(self):
        """Test computed ID and bit properties."""
        # Test various addresses
        test_cases = [
            ("0x000", 0, 0),    # First Data
            ("0x01F", 0, 31),   # Last bit of ID 0
            ("0x020", 1, 0),    # First bit of ID 1
            ("0x200", 4, 0),    # First Network
            ("0x27F", 7, 31),   # Last Network
            ("0x400", 8, 0),    # First Application
            ("0x47F", 11, 31),  # Last Application
        ]
        
        for addr, expected_id, expected_bit in test_cases:
            event = EventMk1(
                address=addr,
                event_source="test",
                description=f"Test at {addr}"
            )
            assert event.id == expected_id, f"Failed for {addr}"
            assert event.bit == expected_bit, f"Failed for {addr}"
    
    def test_invalid_address_range(self):
        """Test creating event with invalid address."""
        with pytest.raises(ValidationError) as exc:
            EventMk1(
                address="0x100",  # Invalid range
                event_source="test",
                description="Test"
            )
        assert "not in valid MK1 ranges" in str(exc.value)
    
    def test_empty_info_field(self):
        """Test that info field is optional."""
        event = EventMk1(
            address="0x000",
            event_source="test",
            description="Test"
            # info not provided
        )
        assert event.info == ""  # Default empty string


class TestMk2Key:
    """Test MK2 key normalization and validation."""
    
    def test_normalize_mk2_key(self):
        """Test normalizing MK2 keys."""
        assert normalize_mk2_key("0x000") == "0x000"
        assert normalize_mk2_key("0x100") == "0x100"
        assert normalize_mk2_key("0xF1B") == "0xF1B"
    
    def test_normalize_integer_key(self):
        """Test normalizing integer keys."""
        assert normalize_mk2_key(0) == "0x000"
        assert normalize_mk2_key(0x100) == "0x100"
        assert normalize_mk2_key(0xF1B) == "0xF1B"
    
    def test_invalid_id_range(self):
        """Test key with invalid ID (>15)."""
        with pytest.raises(ValueError) as exc:
            normalize_mk2_key("0x1000")  # ID = 16
        assert "ID 16 exceeds maximum 15" in str(exc.value)
    
    def test_invalid_bit_range(self):
        """Test key with invalid bit (>27)."""
        with pytest.raises(ValueError) as exc:
            normalize_mk2_key("0x01C")  # bit = 28
        assert "Bit 28 exceeds maximum 27" in str(exc.value)
        
        with pytest.raises(ValueError):
            normalize_mk2_key("0x01F")  # bit = 31


class TestEventMk2:
    """Test EventMk2 model."""
    
    def test_valid_event(self):
        """Test creating valid mk2 event."""
        event = EventMk2(
            key="0x000",
            event_source="controller",
            description="Test event",
            info="Normal"
        )
        assert event.key == "0x000"
        assert event.id == 0
        assert event.bit == 0
    
    def test_key_normalization_in_model(self):
        """Test key normalization within model."""
        event = EventMk2(
            key="0x0",  # Will be normalized
            event_source="test",
            description="Test"
        )
        assert event.key == "0x000"
    
    def test_integer_key(self):
        """Test using integer key."""
        event = EventMk2(
            key=0x115,  # ID=1, bit=21
            event_source="test",
            description="Test"
        )
        assert event.key == "0x115"
        assert event.id == 1
        assert event.bit == 0x15  # 21
    
    def test_computed_properties(self):
        """Test computed ID and bit properties."""
        test_cases = [
            ("0x000", 0, 0),
            ("0x001", 0, 1),
            ("0x01B", 0, 27),  # Max valid bit
            ("0x100", 1, 0),
            ("0xF00", 15, 0),  # Max ID
            ("0xF1B", 15, 27), # Max ID and bit
        ]
        
        for key, expected_id, expected_bit in test_cases:
            event = EventMk2(
                key=key,
                event_source="test",
                description=f"Test at {key}"
            )
            assert event.id == expected_id, f"Failed for {key}"
            assert event.bit == expected_bit, f"Failed for {key}"
    
    def test_invalid_bit_28_31(self):
        """Test that bits 28-31 are invalid."""
        with pytest.raises(ValidationError):
            EventMk2(
                key="0x01C",  # bit 28
                event_source="test",
                description="Test"
            )
        
        with pytest.raises(ValidationError):
            EventMk2(
                key="0x01F",  # bit 31
                event_source="test",
                description="Test"
            )


class TestMk1Format:
    """Test Mk1Format model."""
    
    def test_empty_format(self):
        """Test creating empty MK1 format."""
        fmt = Mk1Format()
        assert fmt.sources == []
        assert fmt.events == {}
    
    def test_format_with_sources(self):
        """Test MK1 format with sources."""
        fmt = Mk1Format(
            sources=[
                EventSource(name="hw", description="Hardware"),
                EventSource(name="fw", description="Firmware"),
            ]
        )
        assert len(fmt.sources) == 2
        assert fmt.sources[0].name == "hw"
    
    def test_format_with_events(self):
        """Test MK1 format with events."""
        fmt = Mk1Format(
            events={
                "0x000": EventMk1(
                    address="0x000",
                    event_source="test",
                    description="Event 1"
                ),
                "0x200": EventMk1(
                    address="0x200",
                    event_source="test",
                    description="Event 2"
                ),
            }
        )
        assert len(fmt.events) == 2
        assert "0x000" in fmt.events
    
    def test_duplicate_normalized_addresses(self):
        """Test detection of duplicate addresses after normalization."""
        with pytest.raises(ValidationError) as exc:
            Mk1Format(
                events={
                    "0x00": EventMk1(
                        address="0x00",  # Normalizes to 0x000
                        event_source="test",
                        description="Event 1"
                    ),
                    "0x000": EventMk1(
                        address="0x000",  # Also 0x000
                        event_source="test",
                        description="Event 2"
                    ),
                }
            )
        assert "Duplicate address after normalization" in str(exc.value)
    
    def test_get_subtab_events(self):
        """Test getting events by subtab."""
        fmt = Mk1Format(
            events={
                "0x000": EventMk1(address="0x000", event_source="test", description="Data event"),
                "0x200": EventMk1(address="0x200", event_source="test", description="Network event"),
                "0x400": EventMk1(address="0x400", event_source="test", description="App event"),
            }
        )
        
        data_events = fmt.get_subtab_events("Data")
        assert len(data_events) == 1
        assert "0x000" in data_events
        
        network_events = fmt.get_subtab_events("Network")
        assert len(network_events) == 1
        assert "0x200" in network_events
        
        app_events = fmt.get_subtab_events("Application")
        assert len(app_events) == 1
        assert "0x400" in app_events
    
    def test_to_mask_array(self):
        """Test conversion to mask array."""
        fmt = Mk1Format()
        mask = fmt.to_mask_array()
        
        assert isinstance(mask, np.ndarray)
        assert mask.shape == (12,)
        assert mask.dtype == np.uint32
        assert np.all(mask == 0)  # Should be all zeros initially


class TestMk2Format:
    """Test Mk2Format model."""
    
    def test_empty_format(self):
        """Test creating empty MK2 format."""
        fmt = Mk2Format()
        assert fmt.sources == []
        assert fmt.id_names == {}
        assert fmt.base_address is None
        assert fmt.events == {}
    
    def test_format_with_id_names(self):
        """Test MK2 format with ID names."""
        fmt = Mk2Format(
            id_names={
                0: "Data",
                1: "Network",
                15: "Debug"
            }
        )
        assert len(fmt.id_names) == 3
        assert fmt.id_names[0] == "Data"
    
    def test_invalid_id_in_names(self):
        """Test invalid ID in id_names."""
        with pytest.raises(ValidationError) as exc:
            Mk2Format(
                id_names={
                    16: "Invalid"  # ID > 15
                }
            )
        assert "Invalid ID 16" in str(exc.value)
    
    def test_base_address_validation(self):
        """Test base address validation."""
        fmt = Mk2Format(base_address=0x40000000)
        assert fmt.base_address == 0x40000000
        
        # Test 32-bit limit
        with pytest.raises(ValidationError) as exc:
            Mk2Format(base_address=0x100000000)  # 33-bit
        assert "exceeds 32-bit range" in str(exc.value)
    
    def test_duplicate_normalized_keys(self):
        """Test detection of duplicate keys after normalization."""
        with pytest.raises(ValidationError) as exc:
            Mk2Format(
                events={
                    "0x0": EventMk2(
                        key="0x0",  # Normalizes to 0x000
                        event_source="test",
                        description="Event 1"
                    ),
                    "0x000": EventMk2(
                        key="0x000",  # Also 0x000
                        event_source="test",
                        description="Event 2"
                    ),
                }
            )
        assert "Duplicate key after normalization" in str(exc.value)
    
    def test_get_id_events(self):
        """Test getting events by ID."""
        fmt = Mk2Format(
            events={
                "0x000": EventMk2(key="0x000", event_source="test", description="ID 0 bit 0"),
                "0x001": EventMk2(key="0x001", event_source="test", description="ID 0 bit 1"),
                "0x100": EventMk2(key="0x100", event_source="test", description="ID 1 bit 0"),
            }
        )
        
        id0_events = fmt.get_id_events(0)
        assert len(id0_events) == 2
        assert "0x000" in id0_events
        assert "0x001" in id0_events
        
        id1_events = fmt.get_id_events(1)
        assert len(id1_events) == 1
        assert "0x100" in id1_events
    
    def test_get_id_name(self):
        """Test getting ID name with fallback."""
        fmt = Mk2Format(
            id_names={
                0: "Data Processing",
                1: "Network Stack"
            }
        )
        
        assert fmt.get_id_name(0) == "Data Processing (ID 0)"
        assert fmt.get_id_name(1) == "Network Stack (ID 1)"
        assert fmt.get_id_name(2) == "ID 2"  # Fallback
    
    def test_to_mask_array(self):
        """Test conversion to mask array."""
        fmt = Mk2Format()
        mask = fmt.to_mask_array()
        
        assert isinstance(mask, np.ndarray)
        assert mask.shape == (16,)
        assert mask.dtype == np.uint32
        assert np.all(mask == 0)  # Should be all zeros initially


class TestValidationModels:
    """Test validation issue and result models."""
    
    def test_validation_issue(self):
        """Test creating validation issue."""
        issue = ValidationIssue(
            code=ValidationCode.MK1_ADDR_RANGE,
            level=ValidationLevel.ERROR,
            message="Address out of range"
        )
        assert issue.code == ValidationCode.MK1_ADDR_RANGE
        assert issue.level == ValidationLevel.ERROR
        assert issue.message == "Address out of range"
        assert issue.location is None
        assert issue.details is None
    
    def test_validation_issue_with_details(self):
        """Test validation issue with location and details."""
        issue = ValidationIssue(
            code=ValidationCode.DUPLICATE_KEY,
            level=ValidationLevel.ERROR,
            message="Duplicate key",
            location="line 10",
            details={"key": "0x000", "previous": "line 5"}
        )
        assert issue.location == "line 10"
        assert issue.details["key"] == "0x000"
    
    def test_validation_result_empty(self):
        """Test empty validation result."""
        result = ValidationResult()
        assert not result.has_errors
        assert not result.has_warnings
        assert len(result.issues) == 0
    
    def test_validation_result_operations(self):
        """Test validation result operations."""
        result = ValidationResult()
        
        # Add errors
        result.add_issue(
            code=ValidationCode.DUPLICATE_KEY,
            level=ValidationLevel.ERROR,
            message="Duplicate key found",
            location="key: 0x000"
        )
        
        # Add warnings
        result.add_issue(
            code=ValidationCode.BITS_28_31_FORCED_ZERO,
            level=ValidationLevel.WARNING,
            message="Bits forced to zero"
        )
        
        # Add info
        result.add_issue(
            code=ValidationCode.BITS_28_31_FORCED_ZERO,
            level=ValidationLevel.INFO,
            message="Information message"
        )
        
        assert result.has_errors
        assert result.has_warnings
        assert len(result.issues) == 3
        assert len(result.get_errors()) == 1
        assert len(result.get_warnings()) == 1
    
    def test_validation_codes(self):
        """Test all validation codes are defined."""
        codes = [
            ValidationCode.MK1_ADDR_RANGE,
            ValidationCode.MK2_ADDR_RANGE,
            ValidationCode.KEY_FORMAT,
            ValidationCode.DUPLICATE_KEY,
            ValidationCode.BITS_28_31_FORCED_ZERO,
            ValidationCode.INVALID_COLOR_FALLBACK,
            ValidationCode.MISSING_FILE_RESTORED,
        ]
        # Just verify they exist
        assert len(codes) == 7


class TestExportMetadata:
    """Test ExportMetadata model."""
    
    def test_minimal_metadata(self):
        """Test minimal export metadata."""
        meta = ExportMetadata(
            format=FormatType.MK1,
            mode=MaskMode.MASK,
            version="1.0.0",
            timestamp="2025-01-01T00:00:00+00:00"
        )
        assert meta.format == FormatType.MK1
        assert meta.mode == MaskMode.MASK
        assert meta.yaml is None
        assert meta.base_address is None
    
    def test_full_metadata(self):
        """Test full export metadata."""
        meta = ExportMetadata(
            format=FormatType.MK2,
            mode=MaskMode.TRIGGER,
            yaml="events.yaml",
            base_address=0x40000000,
            id_names_hash="abc123",
            version="1.2.3",
            timestamp=datetime.now().isoformat()
        )
        assert meta.format == FormatType.MK2
        assert meta.yaml == "events.yaml"
        assert meta.base_address == 0x40000000
        assert meta.id_names_hash == "abc123"


class TestMaskData:
    """Test MaskData model."""
    
    def test_mk1_mask_data(self):
        """Test MK1 mask data."""
        data = MaskData(
            format_type=FormatType.MK1,
            mode=MaskMode.MASK,
            data=[0] * 12,
            metadata=meta
        )
        
        assert data.metadata is not None
        assert data.metadata.version == "1.0.0"


class TestSessionState:
    """Test SessionState model."""
    
    def test_empty_session(self):
        """Test creating empty session."""
        session = SessionState()
        assert session.open_files == []
        assert session.active_tab is None
        assert session.active_subtab is None
        assert session.scroll_positions == {}
        assert session.window_geometry is None
        assert session.dock_states == {}
        assert session.mask_states == {}
        assert session.trigger_states == {}
        assert session.current_mode == MaskMode.MASK
    
    def test_session_with_files(self):
        """Test session with open files."""
        session = SessionState(
            open_files=["file1.yaml", "file2.yaml"],
            active_tab=0,
            active_subtab=1
        )
        assert len(session.open_files) == 2
        assert session.active_tab == 0
        assert session.active_subtab == 1
    
    def test_add_file(self):
        """Test adding files to session."""
        session = SessionState()
        session.add_file("file1.yaml")
        session.add_file("file2.yaml")
        
        assert len(session.open_files) == 2
        assert "file1.yaml" in session.open_files
        assert "file2.yaml" in session.open_files
    
    def test_add_duplicate_file(self):
        """Test that duplicate files are not added."""
        session = SessionState()
        session.add_file("file1.yaml")
        session.add_file("file1.yaml")  # Duplicate
        
        assert len(session.open_files) == 1
    
    def test_remove_file(self):
        """Test removing files from session."""
        session = SessionState()
        session.add_file("file1.yaml")
        session.add_file("file2.yaml")
        session.mask_states["file1.yaml"] = [0] * 12
        session.trigger_states["file1.yaml"] = [0] * 12
        
        session.remove_file("file1.yaml")
        
        assert "file1.yaml" not in session.open_files
        assert "file1.yaml" not in session.mask_states
        assert "file1.yaml" not in session.trigger_states
        assert "file2.yaml" in session.open_files
    
    def test_remove_nonexistent_file(self):
        """Test removing file that doesn't exist."""
        session = SessionState()
        session.remove_file("nonexistent.yaml")  # Should not raise
        assert len(session.open_files) == 0
    
    def test_window_geometry(self):
        """Test window geometry storage."""
        session = SessionState(
            window_geometry={
                "x": 100,
                "y": 200,
                "width": 800,
                "height": 600
            }
        )
        assert session.window_geometry["x"] == 100
        assert session.window_geometry["y"] == 200
        assert session.window_geometry["width"] == 800
        assert session.window_geometry["height"] == 600
    
    def test_dock_states(self):
        """Test dock states storage."""
        session = SessionState(
            dock_states={
                "problems_dock": True,
                "toolbar": False
            }
        )
        assert session.dock_states["problems_dock"] is True
        assert session.dock_states["toolbar"] is False
    
    def test_mask_and_trigger_states(self):
        """Test mask and trigger states storage."""
        session = SessionState()
        session.mask_states["file1.yaml"] = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
        session.trigger_states["file1.yaml"] = [0] * 12
        
        assert len(session.mask_states["file1.yaml"]) == 12
        assert session.mask_states["file1.yaml"][0] == 1
        assert session.trigger_states["file1.yaml"][0] == 0
    
    def test_scroll_positions(self):
        """Test scroll positions storage."""
        session = SessionState(
            scroll_positions={
                "tab1": 100,
                "tab2": 250
            }
        )
        assert session.scroll_positions["tab1"] == 100
        assert session.scroll_positions["tab2"] == 250
    
    def test_mode_switching(self):
        """Test mode switching."""
        session = SessionState()
        assert session.current_mode == MaskMode.MASK
        
        session.current_mode = MaskMode.TRIGGER
        assert session.current_mode == MaskMode.TRIGGER


class TestEnumValues:
    """Test enum values are as expected."""
    
    def test_format_type_values(self):
        """Test FormatType enum values."""
        assert FormatType.MK1.value == "mk1"
        assert FormatType.MK2.value == "mk2"
    
    def test_mask_mode_values(self):
        """Test MaskMode enum values."""
        assert MaskMode.MASK.value == "mask"
        assert MaskMode.TRIGGER.value == "trigger"
    
    def test_validation_level_values(self):
        """Test ValidationLevel enum values."""
        assert ValidationLevel.ERROR.value == "ERROR"
        assert ValidationLevel.WARNING.value == "WARNING"
        assert ValidationLevel.INFO.value == "INFO"


class TestConstants:
    """Test module constants."""
    
    def test_mk1_ranges(self):
        """Test MK1 range constants."""
        assert MK1_RANGES["Data"] == (0x000, 0x07F)
        assert MK1_RANGES["Network"] == (0x200, 0x27F)
        assert MK1_RANGES["Application"] == (0x400, 0x47F)
    
    def test_mk2_constants(self):
        """Test MK2 constants."""
        assert MK2_MAX_ID == 15
        assert MK2_MAX_BIT == 27
        assert MK2_BIT_MASK == 0x0FFFFFFF


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_mk1_boundary_addresses(self):
        """Test MK1 boundary addresses."""
        # Test first and last valid addresses in each range
        test_cases = [
            ("0x000", "Data", 0, 0),      # First Data
            ("0x07F", "Data", 3, 31),     # Last Data
            ("0x200", "Network", 4, 0),   # First Network
            ("0x27F", "Network", 7, 31),  # Last Network
            ("0x400", "Application", 8, 0),  # First Application
            ("0x47F", "Application", 11, 31), # Last Application
        ]
        
        for addr, expected_range, expected_id, expected_bit in test_cases:
            event = EventMk1(
                address=addr,
                event_source="test",
                description=f"Boundary test at {addr}"
            )
            assert event.range_name == expected_range
            assert event.id == expected_id
            assert event.bit == expected_bit
    
    def test_mk2_boundary_keys(self):
        """Test MK2 boundary keys."""
        # Test boundary values
        test_cases = [
            ("0x000", 0, 0),    # Minimum
            ("0x01B", 0, 27),   # Max bit for ID 0
            ("0xF00", 15, 0),   # Max ID
            ("0xF1B", 15, 27),  # Maximum valid key
        ]
        
        for key, expected_id, expected_bit in test_cases:
            event = EventMk2(
                key=key,
                event_source="test",
                description=f"Boundary test at {key}"
            )
            assert event.id == expected_id
            assert event.bit == expected_bit
    
    def test_very_long_strings(self):
        """Test handling of very long strings."""
        # Test max length validation
        long_string = "a" * 500  # Max length
        source = EventSource(
            name="test",
            description=long_string
        )
        assert len(source.description) == 500
        
        # Test too long string
        with pytest.raises(ValidationError):
            EventSource(
                name="test",
                description="a" * 501  # Over max length
            )
    
    def test_unicode_in_strings(self):
        """Test Unicode characters in strings."""
        source = EventSource(
            name="test",
            description="Unicode test: 你好 🚀 Ω"
        )
        assert "你好" in source.description
        assert "🚀" in source.description
        assert "Ω" in source.description
    
    def test_empty_mk1_format_operations(self):
        """Test operations on empty MK1 format."""
        fmt = Mk1Format()
        
        # Should return empty dict for any subtab
        assert fmt.get_subtab_events("Data") == {}
        assert fmt.get_subtab_events("Network") == {}
        assert fmt.get_subtab_events("Application") == {}
        
        # Should create zero mask
        mask = fmt.to_mask_array()
        assert np.all(mask == 0)
    
    def test_empty_mk2_format_operations(self):
        """Test operations on empty MK2 format."""
        fmt = Mk2Format()
        
        # Should return empty dict for any ID
        assert fmt.get_id_events(0) == {}
        assert fmt.get_id_events(15) == {}
        
        # Should use fallback for all IDs
        assert fmt.get_id_name(0) == "ID 0"
        assert fmt.get_id_name(15) == "ID F"
        
        # Should create zero mask
        mask = fmt.to_mask_array()
        assert np.all(mask == 0)


class TestIntegration:
    """Integration tests for models working together."""
    
    def test_complete_mk1_workflow(self):
        """Test complete MK1 workflow from YAML to export."""
        # Step 1: Create sources
        sources = [
            EventSource(name="hardware", description="Hardware events"),
            EventSource(name="firmware", description="Firmware events"),
            EventSource(name="software", description="Software events"),
        ]
        
        # Step 2: Create events across all ranges
        events = {
            "0x000": EventMk1(
                address="0x000",
                event_source="hardware",
                description="Data start",
                info="Normal operation"
            ),
            "0x01F": EventMk1(
                address="0x01F",
                event_source="hardware",
                description="Data end of first ID",
                info="Status flag"
            ),
            "0x020": EventMk1(
                address="0x020",
                event_source="firmware",
                description="Data second ID",
                info="Error condition"
            ),
            "0x200": EventMk1(
                address="0x200",
                event_source="firmware",
                description="Network start",
                info="Sync event sbs"
            ),
            "0x400": EventMk1(
                address="0x400",
                event_source="software",
                description="Application start",
                info="Application layer"
            ),
            "0x47F": EventMk1(
                address="0x47F",
                event_source="software",
                description="Application end",
                info="Last valid address"
            ),
        }
        
        # Step 3: Create format
        fmt = Mk1Format(sources=sources, events=events)
        
        # Step 4: Verify subtab organization
        data_events = fmt.get_subtab_events("Data")
        assert len(data_events) == 3  # 0x000, 0x01F, 0x020
        
        network_events = fmt.get_subtab_events("Network")
        assert len(network_events) == 1  # 0x200
        
        app_events = fmt.get_subtab_events("Application")
        assert len(app_events) == 2  # 0x400, 0x47F
        
        # Step 5: Create mask array
        mask = fmt.to_mask_array()
        assert mask.shape == (12,)
        assert mask.dtype == np.uint32
        
        # Step 6: Simulate some mask values
        mask[0] = 0x80000001  # ID 0: bits 0 and 31
        mask[4] = 0x00000001  # ID 4: bit 0
        mask[11] = 0x80000000 # ID 11: bit 31
        
        # Step 7: Export to MaskData
        mask_data = MaskData.from_numpy(mask, FormatType.MK1, MaskMode.MASK)
        assert len(mask_data.data) == 12
        assert mask_data.data[0] == 0x80000001
        assert mask_data.data[4] == 0x00000001
        assert mask_data.data[11] == 0x80000000
        
        # Step 8: Add metadata
        meta = ExportMetadata(
            format=FormatType.MK1,
            mode=MaskMode.MASK,
            yaml="test_events.yaml",
            version="1.0.0",
            timestamp=datetime.now().isoformat()
        )
        mask_data.metadata = meta
        
        # Step 9: Round-trip test
        recovered = mask_data.to_numpy()
        assert np.array_equal(recovered, mask)
    
    def test_complete_mk2_workflow(self):
        """Test complete MK2 workflow with all features."""
        # Step 1: Create comprehensive MK2 format
        fmt = Mk2Format(
            sources=[
                EventSource(name="controller", description="Main controller"),
                EventSource(name="peripheral", description="Peripheral devices"),
            ],
            id_names={
                i: f"Module_{i}" for i in range(16)
            },
            base_address=0x40000000,
            events={}
        )
        
        # Step 2: Add events for multiple IDs
        for id_num in [0, 1, 15]:  # Test first, second, and last ID
            for bit in [0, 1, 26, 27]:  # Test various valid bits
                key = f"0x{id_num:01X}{bit:02X}"
                fmt.events[key] = EventMk2(
                    key=key,
                    event_source="controller",
                    description=f"Event ID{id_num} Bit{bit}",
                    info="Test event"
                )
        
        # Step 3: Verify ID names
        assert fmt.get_id_name(0) == "Module_0 (ID 0)"
        assert fmt.get_id_name(15) == "Module_15 (ID F)"
        
        # Step 4: Verify event organization
        id0_events = fmt.get_id_events(0)
        assert len(id0_events) == 4  # 4 bits for ID 0
        
        id15_events = fmt.get_id_events(15)
        assert len(id15_events) == 4  # 4 bits for ID 15
        
        # Step 5: Create mask with potential issues
        mask = np.ones(16, dtype=np.uint32) * 0xFFFFFFFF
        
        # Step 6: Convert to MaskData (should auto-mask bits 28-31)
        mask_data = MaskData.from_numpy(mask, FormatType.MK2, MaskMode.TRIGGER)
        
        # Step 7: Verify bit masking
        for val in mask_data.data:
            assert val == 0x0FFFFFFF  # Bits 28-31 should be masked
        
        # Step 8: Add metadata with base address
        meta = ExportMetadata(
            format=FormatType.MK2,
            mode=MaskMode.TRIGGER,
            yaml="test_mk2.yaml",
            base_address=0x40000000,
            version="2.0.0",
            timestamp=datetime.now().isoformat()
        )
        mask_data.metadata = meta
        
        # Step 9: Verify metadata
        assert mask_data.metadata.base_address == 0x40000000
    
    def test_validation_workflow(self):
        """Test complete validation workflow with aggregation."""
        # Step 1: Create validation result
        result = ValidationResult()
        
        # Step 2: Simulate validation of MK1 file
        # Check addresses
        test_addresses = ["0x000", "0x100", "0x200", "0x300", "0x400", "0x500"]
        
        for addr in test_addresses:
            try:
                validate_mk1_address_range(addr)
            except ValueError as e:
                result.add_issue(
                    code=ValidationCode.MK1_ADDR_RANGE,
                    level=ValidationLevel.ERROR,
                    message=str(e),
                    location=f"address: {addr}",
                    details={"address": addr}
                )
        
        # Step 3: Add some warnings
        result.add_issue(
            code=ValidationCode.INVALID_COLOR_FALLBACK,
            level=ValidationLevel.WARNING,
            message="Invalid color '#GGGGGG', using default",
            location="config.accent_color"
        )
        
        # Step 4: Check results
        assert result.has_errors
        assert result.has_warnings
        
        errors = result.get_errors()
        assert len(errors) == 3  # 0x100, 0x300, 0x500 are invalid
        
        warnings = result.get_warnings()
        assert len(warnings) == 1
        
        # Step 5: Check specific error details
        error_addresses = [e.details["address"] for e in errors if e.details]
        assert "0x100" in error_addresses
        assert "0x300" in error_addresses
        assert "0x500" in error_addresses
    
    def test_session_management_workflow(self):
        """Test complete session management workflow."""
        # Step 1: Create new session
        session = SessionState()
        
        # Step 2: Open files
        files = ["events_mk1.yaml", "events_mk2.yaml", "test.yaml"]
        for f in files:
            session.add_file(f)
        
        # Step 3: Set UI state
        session.active_tab = 0
        session.active_subtab = 2
        session.window_geometry = {
            "x": 100, "y": 100,
            "width": 1024, "height": 768
        }
        session.dock_states = {
            "problems_dock": True,
            "toolbar": True
        }
        
        # Step 4: Set mask states
        session.mask_states["events_mk1.yaml"] = [0x00000001] * 12
        session.mask_states["events_mk2.yaml"] = [0x00000002] * 16
        
        # Step 5: Set trigger states
        session.trigger_states["events_mk1.yaml"] = [0x00000004] * 12
        session.trigger_states["events_mk2.yaml"] = [0x00000008] * 16
        
        # Step 6: Switch mode
        session.current_mode = MaskMode.TRIGGER
        
        # Step 7: Remove a file
        session.remove_file("test.yaml")
        
        # Step 8: Verify final state
        assert len(session.open_files) == 2
        assert "test.yaml" not in session.open_files
        assert session.current_mode == MaskMode.TRIGGER
        assert session.window_geometry["width"] == 1024
        assert len(session.mask_states) == 2
        assert len(session.trigger_states) == 2
    
    def test_mixed_format_validation(self):
        """Test validation when mixing MK1 and MK2 concepts."""
        # This should fail - can't use MK2 base_address with MK1
        mask_data = MaskData(
            format_type=FormatType.MK1,
            mode=MaskMode.MASK,
            data=[0] * 12
        )
        
        # MK1 doesn't use base_address in metadata
        meta = ExportMetadata(
            format=FormatType.MK1,
            mode=MaskMode.MASK,
            base_address=0x40000000,  # This is allowed but ignored for MK1
            version="1.0.0",
            timestamp="2025-01-01T00:00:00"
        )
        
        mask_data.metadata = meta
        
        # Should not raise - base_address is simply ignored for MK1
        assert mask_data.metadata.base_address == 0x40000000
        
        # But the mask should still be 12 elements for MK1
        assert len(mask_data.data) == 12
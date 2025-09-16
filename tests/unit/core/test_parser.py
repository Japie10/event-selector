"""Comprehensive unit tests for YAML parser."""

import pytest
from pathlib import Path
import tempfile
import yaml
from typing import Dict, Any

from event_selector.core.parser import (
    EventParser,
    ParseError,
    FormatDetectionError,
    YAMLLoadError,
    parse_yaml_file,
    parse_yaml_data,
    detect_format,
)
from event_selector.core.models import (
    FormatType,
    EventMk1,
    EventMk2,
    Mk1Format,
    Mk2Format,
    ValidationResult,
    ValidationLevel,
)


class TestFormatDetection:
    """Test format detection logic."""
    
    def test_detect_mk1_by_addresses(self):
        """Test detecting mk1 format by address ranges."""
        data = {
            "0x000": {"event_source": "test", "description": "Test"},
            "0x200": {"event_source": "test", "description": "Test"},
            "0x400": {"event_source": "test", "description": "Test"},
        }
        assert detect_format(data) == FormatType.MK1
    
    def test_detect_mk2_by_id_names(self):
        """Test detecting mk2 format by id_names key."""
        data = {
            "id_names": {0: "Test"},
            "0x000": {"event_source": "test", "description": "Test"},
        }
        assert detect_format(data) == FormatType.MK2
    
    def test_detect_mk2_by_base_address(self):
        """Test detecting mk2 format by base_address key."""
        data = {
            "base_address": 0x40000000,
            "0x000": {"event_source": "test", "description": "Test"},
        }
        assert detect_format(data) == FormatType.MK2
    
    def test_detect_mk2_by_keys(self):
        """Test detecting mk2 format by key patterns."""
        data = {
            "0x000": {"event_source": "test", "description": "Test"},
            "0x100": {"event_source": "test", "description": "Test"},  # ID 1, bit 0
            "0xF00": {"event_source": "test", "description": "Test"},  # ID 15, bit 0
        }
        assert detect_format(data) == FormatType.MK2
    
    def test_detect_ambiguous_format(self):
        """Test ambiguous format detection defaults to mk1."""
        parser = EventParser()
        data = {
            "0x000": {"event_source": "test", "description": "Test"},
            # 0x000 is valid for both mk1 and mk2
        }
        format_type = parser.detect_format(data)
        assert format_type == FormatType.MK1
        # Should have warning about ambiguity
        warnings = parser.validation_result.get_warnings()
        assert any("Ambiguous format" in w.message for w in warnings)
    
    def test_detect_empty_events(self):
        """Test format detection with only sources."""
        data = {
            "sources": [{"name": "test", "description": "Test"}]
        }
        assert detect_format(data) == FormatType.MK1  # Default
    
    def test_detect_invalid_format(self):
        """Test format detection failure."""
        data = {
            "invalid_key": {"some": "data"}
        }
        with pytest.raises(FormatDetectionError):
            detect_format(data)


class TestMk1Parser:
    """Test mk1 format parser."""
    
    def test_parse_simple_mk1(self):
        """Test parsing simple mk1 YAML."""
        data = {
            "0x000": {
                "event_source": "hardware",
                "description": "Test event",
                "info": "Normal"
            }
        }
        
        result, validation = parse_yaml_data(data)
        
        assert isinstance(result, Mk1Format)
        assert len(result.events) == 1
        assert "0x000" in result.events
        assert not validation.has_errors
    
    def test_parse_mk1_with_sources(self):
        """Test parsing mk1 with sources."""
        data = {
            "sources": [
                {"name": "hw", "description": "Hardware"},
                {"name": "fw", "description": "Firmware"}
            ],
            "0x000": {"event_source": "hw", "description": "Test"},
            "0x200": {"event_source": "fw", "description": "Test"}
        }
        
        result, validation = parse_yaml_data(data)
        
        assert isinstance(result, Mk1Format)
        assert len(result.sources) == 2
        assert result.sources[0].name == "hw"
        assert len(result.events) == 2
    
    def test_parse_mk1_address_normalization(self):
        """Test mk1 address normalization during parsing."""
        data = {
            "0x00": {"event_source": "test", "description": "Test 1"},
            "00": {"event_source": "test", "description": "Test 2"},
            0: {"event_source": "test", "description": "Test 3"},
        }
        
        parser = EventParser()
        
        # These should be detected as duplicates
        with pytest.raises(ParseError):
            parser.parse_data(data)
        
        # Check that duplicates were detected
        errors = parser.validation_result.get_errors()
        assert any("Duplicate address" in e.message for e in errors)
    
    def test_parse_mk1_invalid_range(self):
        """Test parsing mk1 with invalid address ranges."""
        data = {
            "0x000": {"event_source": "test", "description": "Valid"},
            "0x100": {"event_source": "test", "description": "Invalid"},  # Gap
            "0x200": {"event_source": "test", "description": "Valid"},
        }
        
        parser = EventParser()
        result = parser.parse_data(data)
        
        # Should parse valid events and report errors for invalid
        assert isinstance(result, Mk1Format)
        assert len(result.events) == 2  # Only valid events
        assert "0x000" in result.events
        assert "0x200" in result.events
        assert "0x100" not in result.events
        
        # Check validation errors
        errors = parser.validation_result.get_errors()
        assert any("0x100" in e.message or "0x100" in str(e.details) for e in errors)
    
    def test_parse_mk1_all_ranges(self):
        """Test parsing mk1 with events in all ranges."""
        data = {
            # Data range
            "0x000": {"event_source": "test", "description": "Data start"},
            "0x07F": {"event_source": "test", "description": "Data end"},
            # Network range
            "0x200": {"event_source": "test", "description": "Network start"},
            "0x27F": {"event_source": "test", "description": "Network end"},
            # Application range  
            "0x400": {"event_source": "test", "description": "App start"},
            "0x47F": {"event_source": "test", "description": "App end"},
        }
        
        result, validation = parse_yaml_data(data)
        
        assert isinstance(result, Mk1Format)
        assert len(result.events) == 6
        assert not validation.has_errors
        
        # Check subtab organization
        assert len(result.get_subtab_events("Data")) == 2
        assert len(result.get_subtab_events("Network")) == 2
        assert len(result.get_subtab_events("Application")) == 2
    
    def test_parse_mk1_missing_fields(self):
        """Test parsing mk1 with missing required fields."""
        data = {
            "0x000": {
                # Missing event_source and description
                "info": "Test"
            }
        }
        
        result, validation = parse_yaml_data(data)
        
        # Should use defaults
        assert isinstance(result, Mk1Format)
        event = result.events["0x000"]
        assert event.event_source == "unknown"  # Default
        assert event.description == ""  # Default
        assert event.info == "Test"
    
    def test_parse_mk1_invalid_event_value(self):
        """Test parsing mk1 with invalid event values."""
        data = {
            "0x000": "Not a dictionary",  # Invalid
            "0x001": {"event_source": "test", "description": "Valid"},
        }
        
        parser = EventParser()
        result = parser.parse_data(data)
        
        # Should parse valid event and report error for invalid
        assert isinstance(result, Mk1Format)
        assert len(result.events) == 1
        assert "0x001" in result.events
        
        errors = parser.validation_result.get_errors()
        assert any("must be a dictionary" in e.message for e in errors)


class TestMk2Parser:
    """Test mk2 format parser."""
    
    def test_parse_simple_mk2(self):
        """Test parsing simple mk2 YAML."""
        data = {
            "0x000": {
                "event_source": "controller",
                "description": "Test event",
                "info": "Normal"
            },
            "0x100": {
                "event_source": "controller",
                "description": "ID 1 event",
                "info": "Normal"
            }
        }
        
        result, validation = parse_yaml_data(data)
        
        assert isinstance(result, Mk2Format)
        assert len(result.events) == 2
        assert "0x000" in result.events
        assert "0x100" in result.events
        assert not validation.has_errors
    
    def test_parse_mk2_with_id_names(self):
        """Test parsing mk2 with id_names."""
        data = {
            "id_names": {
                0: "Data",
                1: "Network",
                15: "Debug"
            },
            "0x000": {"event_source": "test", "description": "Test"}
        }
        
        result, validation = parse_yaml_data(data)
        
        assert isinstance(result, Mk2Format)
        assert len(result.id_names) == 3
        assert result.id_names[0] == "Data"
        assert result.id_names[15] == "Debug"
        assert result.get_id_name(0) == "Data (ID 0)"
        assert result.get_id_name(2) == "ID 2"  # Fallback
    
    def test_parse_mk2_with_base_address(self):
        """Test parsing mk2 with base_address."""
        data = {
            "base_address": "0x40000000",  # Hex string
            "0x000": {"event_source": "test", "description": "Test"}
        }
        
        result, validation = parse_yaml_data(data)
        
        assert isinstance(result, Mk2Format)
        assert result.base_address == 0x40000000
        
        # Test with integer
        data["base_address"] = 0x40000000
        result, validation = parse_yaml_data(data)
        assert result.base_address == 0x40000000
        
        # Test with decimal
        data["base_address"] = 1073741824  # Same as 0x40000000
        result, validation = parse_yaml_data(data)
        assert result.base_address == 0x40000000
    
    def test_parse_mk2_invalid_base_address(self):
        """Test parsing mk2 with invalid base_address."""
        data = {
            "base_address": 0x100000000,  # 33-bit
            "0x000": {"event_source": "test", "description": "Test"}
        }
        
        parser = EventParser()
        result = parser.parse_data(data)
        
        assert isinstance(result, Mk2Format)
        assert result.base_address is None  # Should be rejected
        
        errors = parser.validation_result.get_errors()
        assert any("exceeds 32-bit range" in e.message for e in errors)
    
    def test_parse_mk2_key_normalization(self):
        """Test mk2 key normalization during parsing."""
        data = {
            "0x0": {"event_source": "test", "description": "Test 1"},
            "00": {"event_source": "test", "description": "Test 2"},
            0: {"event_source": "test", "description": "Test 3"},
        }
        
        parser = EventParser()
        
        # These should be detected as duplicates
        with pytest.raises(ParseError):
            parser.parse_data(data)
        
        # Check that duplicates were detected
        errors = parser.validation_result.get_errors()
        assert any("Duplicate key" in e.message for e in errors)
    
    def test_parse_mk2_invalid_bits(self):
        """Test parsing mk2 with invalid bit indices."""
        data = {
            "0x000": {"event_source": "test", "description": "Valid bit 0"},
            "0x01B": {"event_source": "test", "description": "Valid bit 27"},
            "0x01C": {"event_source": "test", "description": "Invalid bit 28"},
            "0x01F": {"event_source": "test", "description": "Invalid bit 31"},
        }
        
        parser = EventParser()
        result = parser.parse_data(data)
        
        # Should parse valid events only
        assert isinstance(result, Mk2Format)
        assert len(result.events) == 2
        assert "0x000" in result.events
        assert "0x01B" in result.events
        
        # Check for bit warnings/errors
        warnings = parser.validation_result.get_warnings()
        assert any("bits 28-31" in w.message for w in warnings)
        
        errors = parser.validation_result.get_errors()
        assert any("0x01C" in str(e.details) for e in errors)
        assert any("0x01F" in str(e.details) for e in errors)
    
    def test_parse_mk2_invalid_id(self):
        """Test parsing mk2 with invalid ID."""
        data = {
            "0xF00": {"event_source": "test", "description": "Valid ID 15"},
            "0x1000": {"event_source": "test", "description": "Invalid ID 16"},
        }
        
        parser = EventParser()
        result = parser.parse_data(data)
        
        assert isinstance(result, Mk2Format)
        assert len(result.events) == 1
        assert "0xF00" in result.events
        
        errors = parser.validation_result.get_errors()
        assert any("0x1000" in str(e.details) for e in errors)
    
    def test_parse_mk2_invalid_id_names(self):
        """Test parsing mk2 with invalid id_names."""
        data = {
            "id_names": {
                0: "Valid",
                16: "Invalid ID",  # > 15
                "not_a_number": "Invalid key",
            },
            "0x000": {"event_source": "test", "description": "Test"}
        }
        
        parser = EventParser()
        result = parser.parse_data(data)
        
        assert isinstance(result, Mk2Format)
        assert len(result.id_names) == 1  # Only valid one
        assert result.id_names[0] == "Valid"
        
        errors = parser.validation_result.get_errors()
        assert any("Invalid ID 16" in e.message for e in errors)
        assert any("Invalid ID key" in e.message for e in errors)
    
    def test_parse_mk2_comprehensive(self):
        """Test comprehensive mk2 parsing."""
        data = {
            "sources": [
                {"name": "ctrl", "description": "Controller"}
            ],
            "id_names": {i: f"Module_{i}" for i in range(16)},
            "base_address": 0x40000000,
        }
        
        # Add events for all IDs
        for i in range(16):
            for bit in [0, 27]:  # First and last valid bit
                key = f"0x{i:01X}{bit:02X}"
                data[key] = {
                    "event_source": "ctrl",
                    "description": f"Event ID{i} Bit{bit}",
                    "info": "Test"
                }
        
        result, validation = parse_yaml_data(data)
        
        assert isinstance(result, Mk2Format)
        assert len(result.sources) == 1
        assert len(result.id_names) == 16
        assert result.base_address == 0x40000000
        assert len(result.events) == 32  # 16 IDs × 2 bits
        assert not validation.has_errors


class TestFileOperations:
    """Test file-based parsing operations."""
    
    def test_parse_file_not_found(self):
        """Test parsing non-existent file."""
        with pytest.raises(FileNotFoundError):
            parse_yaml_file("non_existent_file.yaml")
    
    def test_parse_file_invalid_yaml(self, tmp_path):
        """Test parsing invalid YAML file."""
        # Create invalid YAML file
        yaml_file = tmp_path / "invalid.yaml"
        yaml_file.write_text("{ invalid yaml content :")
        
        with pytest.raises(YAMLLoadError):
            parse_yaml_file(yaml_file)
    
    def test_parse_file_mk1(self, tmp_path):
        """Test parsing mk1 file."""
        # Create mk1 YAML file
        yaml_file = tmp_path / "mk1.yaml"
        data = {
            "sources": [{"name": "test", "description": "Test"}],
            "0x000": {"event_source": "test", "description": "Event 1"},
            "0x200": {"event_source": "test", "description": "Event 2"},
        }
        yaml_file.write_text(yaml.dump(data))
        
        result, validation = parse_yaml_file(yaml_file)
        
        assert isinstance(result, Mk1Format)
        assert len(result.events) == 2
        assert not validation.has_errors
    
    def test_parse_file_mk2(self, tmp_path):
        """Test parsing mk2 file."""
        # Create mk2 YAML file
        yaml_file = tmp_path / "mk2.yaml"
        data = {
            "id_names": {0: "Test"},
            "base_address": 0x40000000,
            "0x000": {"event_source": "test", "description": "Event 1"},
        }
        yaml_file.write_text(yaml.dump(data))
        
        result, validation = parse_yaml_file(yaml_file)
        
        assert isinstance(result, Mk2Format)
        assert len(result.events) == 1
        assert result.base_address == 0x40000000
        assert not validation.has_errors
    
    def test_parse_file_with_unicode(self, tmp_path):
        """Test parsing file with Unicode content."""
        yaml_file = tmp_path / "unicode.yaml"
        data = {
            "sources": [{"name": "测试", "description": "Unicode test 你好 🚀"}],
            "0x000": {"event_source": "test", "description": "Event with Ω"},
        }
        yaml_file.write_text(yaml.dump(data, allow_unicode=True), encoding='utf-8')
        
        result, validation = parse_yaml_file(yaml_file)
        
        assert isinstance(result, Mk1Format)
        assert result.sources[0].description == "Unicode test 你好 🚀"
        assert "Ω" in result.events["0x000"].description


class TestErrorHandling:
    """Test error handling and validation."""
    
    def test_parse_non_dict_root(self):
        """Test parsing non-dictionary at root."""
        parser = EventParser()
        
        with pytest.raises(ParseError) as exc:
            parser.parse_data([], "test")
        assert "Expected dictionary at root" in str(exc.value)
    
    def test_parse_invalid_sources(self):
        """Test parsing invalid sources."""
        data = {
            "sources": "Not a list",  # Should be list
            "0x000": {"event_source": "test", "description": "Test"}
        }
        
        parser = EventParser()
        result = parser.parse_data(data)
        
        # Should continue with empty sources
        assert isinstance(result, Mk1Format)
        assert len(result.sources) == 0
        assert len(result.events) == 1
        
        warnings = parser.validation_result.get_warnings()
        assert any("Sources should be a list" in w.message for w in warnings)
    
    def test_parse_invalid_source_entry(self):
        """Test parsing invalid source entry."""
        data = {
            "sources": [
                {"name": "valid", "description": "Valid source"},
                "Invalid source",  # Not a dict
                {"name": "", "description": "Empty name"},  # Invalid name
            ],
            "0x000": {"event_source": "test", "description": "Test"}
        }
        
        parser = EventParser()
        result = parser.parse_data(data)
        
        # Should only have valid source
        assert isinstance(result, Mk1Format)
        assert len(result.sources) == 1
        assert result.sources[0].name == "valid"
        
        warnings = parser.validation_result.get_warnings()
        assert any("should be a dictionary" in w.message for w in warnings)
        assert any("Invalid source" in w.message for w in warnings)
    
    def test_parse_all_invalid_events(self):
        """Test parsing when all events are invalid."""
        data = {
            "0x100": {"event_source": "test", "description": "Invalid 1"},
            "0x300": {"event_source": "test", "description": "Invalid 2"},
            "0x500": {"event_source": "test", "description": "Invalid 3"},
        }
        
        parser = EventParser()
        
        with pytest.raises(ParseError) as exc:
            parser.parse_data(data)
        assert "No valid events could be parsed" in str(exc.value)
        
        # Should have errors for all invalid addresses
        errors = parser.validation_result.get_errors()
        assert len(errors) >= 3
    
    def test_validation_result_aggregation(self):
        """Test that validation results are properly aggregated."""
        data = {
            # Mix of valid and invalid
            "0x000": {"event_source": "test", "description": "Valid"},
            "0x100": {"event_source": "test", "description": "Invalid range"},
            "0x00": {"event_source": "test", "description": "Duplicate of 0x000"},
            "sources": "Invalid sources",
        }
        
        parser = EventParser()
        
        with pytest.raises(ParseError):  # Due to duplicate
            parser.parse_data(data)
        
        # Check all issues were collected
        assert parser.validation_result.has_errors
        assert parser.validation_result.has_warnings
        
        errors = parser.validation_result.get_errors()
        warnings = parser.validation_result.get_warnings()
        
        # Should have error for invalid range and duplicate
        assert any("0x100" in str(e.details) for e in errors)
        assert any("Duplicate" in e.message for e in errors)
        
        # Should have warning for invalid sources
        assert any("Sources should be a list" in w.message for w in warnings)


class TestEdgeCases:
    """Test edge cases and special scenarios."""
    
    def test_empty_yaml(self):
        """Test parsing empty YAML."""
        data = {}
        
        # Should default to mk1 with no events
        result, validation = parse_yaml_data(data)
        assert isinstance(result, Mk1Format)
        assert len(result.events) == 0
        assert len(result.sources) == 0
    
    def test_only_sources(self):
        """Test YAML with only sources."""
        data = {
            "sources": [{"name": "test", "description": "Test"}]
        }
        
        result, validation = parse_yaml_data(data)
        assert isinstance(result, Mk1Format)
        assert len(result.sources) == 1
        assert len(result.events) == 0
    
    def test_mixed_format_keys(self):
        """Test YAML with mixed mk1/mk2 characteristics."""
        data = {
            # mk1 addresses
            "0x000": {"event_source": "test", "description": "MK1 Data"},
            "0x200": {"event_source": "test", "description": "MK1 Network"},
            # mk2-like but actually valid mk1
            "0x001": {"event_source": "test", "description": "Valid for both"},
        }
        
        # Should detect as mk1
        result, validation = parse_yaml_data(data)
        assert isinstance(result, Mk1Format)
        assert len(result.events) == 3
    
    def test_case_sensitivity(self):
        """Test case sensitivity in keys."""
        data = {
            "0x000": {"event_source": "test", "description": "Lower"},
            "0X000": {"event_source": "test", "description": "Upper X"},
            "0x0": {"event_source": "test", "description": "Short"},
        }
        
        parser = EventParser()
        
        # All normalize to same address - duplicates
        with pytest.raises(ParseError):
            parser.parse_data(data)
        
        errors = parser.validation_result.get_errors()
        duplicate_errors = [e for e in errors if "Duplicate" in e.message]
        assert len(duplicate_errors) >= 1

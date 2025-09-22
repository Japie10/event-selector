"""Comprehensive unit tests for import functionality."""

import pytest
import numpy as np
from pathlib import Path
import tempfile

from event_selector.core.importer import (
    Importer,
    ImportError,
    FileFormat,
    import_mask_file,
    detect_mask_format,
    find_associated_yaml,
)
from event_selector.core.models import (
    FormatType,
    MaskMode,
    MaskData,
    ValidationLevel,
    MK2_BIT_MASK,
)


class TestImporter:
    """Test Importer class."""
    
    def test_importer_initialization(self):
        """Test importer initialization."""
        importer = Importer()
        assert importer.validation_result is not None
        assert not importer.validation_result.has_errors
    
    def test_detect_format_a(self):
        """Test Format A detection."""
        importer = Importer()
        data_lines = [
            "00 12345678",
            "01 9ABCDEF0",
        ]
        assert importer._detect_file_format(data_lines) == FileFormat.FORMAT_A
    
    def test_detect_format_b(self):
        """Test Format B detection."""
        importer = Importer()
        data_lines = [
            "40000040 12345678",
            "40000044 9ABCDEF0",
        ]
        assert importer._detect_file_format(data_lines) == FileFormat.FORMAT_B


class TestFormatAImport:
    """Test Format A import."""
    
    def test_import_mk1_format_a(self):
        """Test importing MK1 Format A file."""
        text = """# event-selector: format=mk1, mode=mask, yaml=test.yaml
# version=1.0.0, timestamp=2025-01-01T00:00:00Z
00 00000001
01 00000002
02 00000004
03 00000008
04 00000010
05 00000020
06 00000040
07 00000080
08 00000100
09 00000200
0A 00000400
0B 00000800"""
        
        importer = Importer()
        mask_data = importer.import_text(text, "test")
        
        assert mask_data.format_type == FormatType.MK1
        assert mask_data.mode == MaskMode.MASK
        assert len(mask_data.data) == 12
        assert mask_data.data[0] == 0x00000001
        assert mask_data.data[11] == 0x00000800
    
    def test_import_mk2_format_a(self):
        """Test importing MK2 Format A file."""
        text = """00 00000001
01 00000002
02 00000004
03 00000008
04 00000010
05 00000020
06 00000040
07 00000080
08 00000100
09 00000200
0A 00000400
0B 00000800
0C 00001000
0D 00002000
0E 00004000
0F 00008000"""
        
        importer = Importer()
        mask_data = importer.import_text(text, "test")
        
        assert mask_data.format_type == FormatType.MK2
        assert len(mask_data.data) == 16
    
    def test_import_mk2_bits_28_31_warning(self):
        """Test MK2 import warns about bits 28-31."""
        text = """00 FFFFFFFF
01 F0000000
02 0FFFFFFF
03 00000000"""
        
        # Pad to 16 lines
        for i in range(4, 16):
            text += f"\n{i:02X} 00000000"
        
        importer = Importer()
        mask_data = importer.import_text(text, "test")
        
        # Check bits were masked
        assert mask_data.data[0] == 0x0FFFFFFF
        assert mask_data.data[1] == 0x00000000  # All invalid bits
        assert mask_data.data[2] == 0x0FFFFFFF
        
        # Check for warnings
        warnings = importer.validation_result.get_warnings()
        assert any("bits 28-31" in w.message for w in warnings)


class TestFormatBImport:
    """Test Format B import."""
    
    def test_import_mk2_format_b(self):
        """Test importing MK2 Format B file."""
        text = """# event-selector: format=mk2, mode=mask, base_address=0x40000000
# version=1.0.0, timestamp=2025-01-01T00:00:00Z
40000040 00000001
40000044 00000002
40000048 00000004
4000004C 00000008
40000050 00000010
40000054 00000020
40000058 00000040
4000005C 00000080
40000060 00000100
40000064 00000200
40000068 00000400
4000006C 00000800
40000070 00001000
40000074 00002000
40000078 00004000
4000007C 00008000"""
        
        importer = Importer()
        mask_data = importer.import_text(text, "test")
        
        assert mask_data.format_type == FormatType.MK2
        assert mask_data.mode == MaskMode.MASK
        assert len(mask_data.data) == 16
        
        # Check values were correctly mapped
        for i in range(16):
            expected = 1 << i
            assert mask_data.data[i] == expected
    
    def test_import_format_b_trigger_mode(self):
        """Test Format B import with trigger mode offset."""
        text = """40000100 FFFFFFFF
40000104 00000000
40000108 AAAAAAAA
4000010C 55555555"""
        
        # Pad to 16 lines
        base = 0x40000100
        for i in range(4, 16):
            text += f"\n{base + i*4:08X} 00000000"
        
        importer = Importer()
        mask_data = importer.import_text(text, "test")
        
        # Should detect trigger mode from offset
        assert importer.mode == MaskMode.TRIGGER
        assert importer.base_address == 0x40000000


class TestMetadataParsing:
    """Test metadata parsing from import files."""
    
    def test_parse_metadata_header(self):
        """Test parsing metadata from header."""
        from event_selector.core.exporter import parse_metadata_header
        
        text = """# event-selector: format=mk1, mode=mask, yaml=events.yaml
# version=1.2.3, timestamp=2025-01-01T12:00:00Z
00 00000000"""
        
        metadata = parse_metadata_header(text)
        
        assert metadata is not None
        assert metadata["format"] == "mk1"
        assert metadata["mode"] == "mask"
        assert metadata["yaml"] == "events.yaml"
        assert metadata["version"] == "1.2.3"
        assert metadata["timestamp"] == "2025-01-01T12:00:00Z"


class TestFileOperations:
    """Test file-based import operations."""
    
    def test_import_from_file(self, tmp_path):
        """Test importing from file."""
        # Create test file
        mask_file = tmp_path / "mask.txt"
        mask_file.write_text("""00 12345678
01 9ABCDEF0
02 00000000
03 00000000
04 00000000
05 00000000
06 00000000
07 00000000
08 00000000
09 00000000
0A 00000000
0B 00000000""")
        
        mask_data, validation = import_mask_file(mask_file)
        
        assert mask_data.format_type == FormatType.MK1
        assert mask_data.data[0] == 0x12345678
        assert mask_data.data[1] == 0x9ABCDEF0
    
    def test_find_associated_yaml(self, tmp_path):
        """Test finding associated YAML file."""
        # Create mask file with metadata
        mask_file = tmp_path / "test_mask.txt"
        mask_file.write_text("""# event-selector: format=mk1, mode=mask, yaml=events.yaml
00 00000000""")
        
        # Create YAML file
        yaml_file = tmp_path / "events.yaml"
        yaml_file.write_text("sources: []")
        
        found_yaml = find_associated_yaml(mask_file)
        assert found_yaml == yaml_file
    
    def test_find_yaml_by_basename(self, tmp_path):
        """Test finding YAML by matching basename."""
        mask_file = tmp_path / "test.txt"
        mask_file.write_text("00 00000000")
        
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text("sources: []")
        
        found_yaml = find_associated_yaml(mask_file)
        assert found_yaml == yaml_file


class TestErrorHandling:
    """Test error handling in import."""
    
    def test_import_empty_file(self):
        """Test importing empty file."""
        importer = Importer()
        
        with pytest.raises(ImportError) as exc:
            importer.import_text("", "empty")
        assert "No data lines" in str(exc.value)
    
    def test_import_invalid_format(self):
        """Test importing file with invalid format."""
        text = """INVALID DATA
NOT HEX VALUES
RANDOM TEXT"""
        
        importer = Importer()
        
        with pytest.raises(ImportError) as exc:
            importer.import_text(text, "invalid")
        assert "Unable to determine file format" in str(exc.value)
    
    def test_import_wrong_line_count(self):
        """Test importing with wrong number of lines."""
        text = """00 12345678
01 9ABCDEF0
02 FFFFFFFF"""  # Only 3 lines
        
        importer = Importer()
        mask_data = importer.import_text(text, "test")
        
        # Should pad with zeros
        assert len(mask_data.data) == 12  # Padded to MK1 size
        assert mask_data.data[3] == 0
        
        # Should have warning
        warnings = importer.validation_result.get_warnings()
        assert len(warnings) > 0
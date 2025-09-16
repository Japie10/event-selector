"""Comprehensive unit tests for export functionality."""

import pytest
import numpy as np
from pathlib import Path
from datetime import datetime
import tempfile

from event_selector.core.exporter import (
    Exporter,
    ExportError,
    export_mask,
    export_from_format,
    parse_metadata_header,
)
from event_selector.core.models import (
    FormatType,
    MaskMode,
    MaskData,
    ExportMetadata,
    EventMk1,
    EventMk2,
    Mk1Format,
    Mk2Format,
    MK2_BIT_MASK,
)


class TestExporter:
    """Test Exporter class."""
    
    def test_exporter_initialization(self):
        """Test exporter initialization."""
        # With mask data
        mask_data = MaskData(
            format_type=FormatType.MK1,
            mode=MaskMode.MASK,
            data=[0] * 12
        )
        exporter = Exporter(mask_data=mask_data)
        assert exporter.format_type == FormatType.MK1
        
        # With MK1 format
        mk1_format = Mk1Format()
        exporter = Exporter(format_obj=mk1_format)
        assert exporter.format_type == FormatType.MK1
        
        # With MK2 format
        mk2_format = Mk2Format()
        exporter = Exporter(format_obj=mk2_format)
        assert exporter.format_type == FormatType.MK2
    
    def test_exporter_no_format(self):
        """Test exporter with no format information."""
        exporter = Exporter()
        assert exporter.format_type is None
        
        mask = np.zeros(12, dtype=np.uint32)
        with pytest.raises(ExportError) as exc:
            exporter.export_format_a(mask)
        assert "Format type not determined" in str(exc.value)


class TestFormatAExport:
    """Test Format A export (<ID2> <VALUE8>)."""
    
    def test_export_mk1_format_a(self):
        """Test exporting MK1 mask in Format A."""
        mask = np.array([
            0x00000001,  # ID 00
            0x00000002,  # ID 01
            0x00000004,  # ID 02
            0x00000008,  # ID 03
            0x00000010,  # ID 04
            0x00000020,  # ID 05
            0x00000040,  # ID 06
            0x00000080,  # ID 07
            0x00000100,  # ID 08
            0x00000200,  # ID 09
            0x00000400,  # ID 0A
            0x00000800,  # ID 0B
        ], dtype=np.uint32)
        
        result = export_mask(
            mask,
            FormatType.MK1,
            MaskMode.MASK,
            include_metadata=False
        )
        
        lines = result.strip().split('\n')
        assert len(lines) == 12
        
        # Check format
        assert lines[0] == "00 00000001"
        assert lines[1] == "01 00000002"
        assert lines[10] == "0A 00000400"
        assert lines[11] == "0B 00000800"
    
    def test_export_mk2_format_a(self):
        """Test exporting MK2 mask in Format A."""
        mask = np.ones(16, dtype=np.uint32) * 0x0FFFFFFF  # Max valid value
        
        result = export_mask(
            mask,
            FormatType.MK2,
            MaskMode.TRIGGER,
            include_metadata=False
        )
        
        lines = result.strip().split('\n')
        assert len(lines) == 16
        
        # Check all lines
        for i, line in enumerate(lines):
            assert line == f"{i:02X} 0FFFFFFF"
    
    def test_export_mk2_bits_28_31_masking(self):
        """Test that MK2 masks bits 28-31 in Format A."""
        mask = np.ones(16, dtype=np.uint32) * 0xFFFFFFFF  # All bits set
        
        result = export_mask(
            mask,
            FormatType.MK2,
            MaskMode.MASK,
            include_metadata=False
        )
        
        lines = result.strip().split('\n')
        
        # All values should be masked to 0x0FFFFFFF
        for line in lines:
            parts = line.split()
            assert parts[1] == "0FFFFFFF"
    
    def test_export_format_a_with_metadata(self):
        """Test Format A export with metadata header."""
        mask = np.zeros(12, dtype=np.uint32)
        
        result = export_mask(
            mask,
            FormatType.MK1,
            MaskMode.MASK,
            yaml_file="test.yaml",
            include_metadata=True
        )
        
        lines = result.split('\n')
        
        # Check metadata header
        assert lines[0].startswith("# event-selector:")
        assert "format=mk1" in lines[0]
        assert "mode=mask" in lines[0]
        assert "yaml=test.yaml" in lines[0]
        
        assert lines[1].startswith("# version=")
        assert "timestamp=" in lines[1]
        
        # Check data starts after header
        assert lines[2] == "00 00000000"
    
    def test_export_format_a_wrong_array_size(self):
        """Test Format A export with wrong array size."""
        mask = np.zeros(10, dtype=np.uint32)  # Wrong size
        
        with pytest.raises(ExportError) as exc:
            export_mask(mask, FormatType.MK1, MaskMode.MASK)
        assert "requires 12 values" in str(exc.value)
        
        mask = np.zeros(12, dtype=np.uint32)  # Wrong size for MK2
        
        with pytest.raises(ExportError) as exc:
            export_mask(mask, FormatType.MK2, MaskMode.MASK)
        assert "requires 16 values" in str(exc.value)


class TestFormatBExport:
    """Test Format B export (<ADDR8> <VALUE8>)."""
    
    def test_export_mk2_format_b(self):
        """Test exporting MK2 mask in Format B."""
        mask = np.array([0x00000001] * 16, dtype=np.uint32)
        base_address = 0x40000000
        
        result = export_mask(
            mask,
            FormatType.MK2,
            MaskMode.MASK,
            format_b=True,
            base_address=base_address,
            include_metadata=False
        )
        
        lines = result.strip().split('\n')
        assert len(lines) == 16
        
        # Check addresses (base + 0x40 for mask + 4*id)
        expected_addresses = [
            0x40000040 + (4 * i) for i in range(16)
        ]
        
        for i, line in enumerate(lines):
            parts = line.split()
            assert parts[0] == f"{expected_addresses[i]:08X}"
            assert parts[1] == "00000001"
    
    def test_export_mk2_format_b_trigger_mode(self):
        """Test Format B with trigger mode (different offset)."""
        mask = np.zeros(16, dtype=np.uint32)
        base_address = 0x40000000
        
        result = export_mask(
            mask,
            FormatType.MK2,
            MaskMode.TRIGGER,
            format_b=True,
            base_address=base_address,
            include_metadata=False
        )
        
        lines = result.strip().split('\n')
        
        # Check addresses (base + 0x100 for trigger + 4*id)
        expected_addresses = [
            0x40000100 + (4 * i) for i in range(16)
        ]
        
        for i, line in enumerate(lines):
            parts = line.split()
            assert parts[0] == f"{expected_addresses[i]:08X}"
    
    def test_export_format_b_mk1_not_supported(self):
        """Test that Format B is not supported for MK1."""
        mask = np.zeros(12, dtype=np.uint32)
        
        with pytest.raises(ExportError) as exc:
            export_mask(
                mask,
                FormatType.MK1,
                MaskMode.MASK,
                format_b=True,
                base_address=0x40000000
            )
        assert "only supported for MK2" in str(exc.value)
    
    def test_export_format_b_no_base_address(self):
        """Test Format B without base address."""
        mask = np.zeros(16, dtype=np.uint32)
        
        with pytest.raises(ExportError) as exc:
            export_mask(
                mask,
                FormatType.MK2,
                MaskMode.MASK,
                format_b=True,
                base_address=None
            )
        assert "Base address required" in str(exc.value)
    
    def test_export_format_b_invalid_base_address(self):
        """Test Format B with invalid base address."""
        mask = np.zeros(16, dtype=np.uint32)
        
        with pytest.raises(ExportError) as exc:
            export_mask(
                mask,
                FormatType.MK2,
                MaskMode.MASK,
                format_b=True,
                base_address=0x100000000  # 33-bit
            )
        assert "exceeds 32-bit range" in str(exc.value)
    
    def test_export_format_b_with_metadata(self):
        """Test Format B export with metadata."""
        mask = np.zeros(16, dtype=np.uint32)
        base_address = 0x40000000
        
        result = export_mask(
            mask,
            FormatType.MK2,
            MaskMode.TRIGGER,
            format_b=True,
            base_address=base_address,
            yaml_file="test_mk2.yaml",
            include_metadata=True
        )
        
        lines = result.split('\n')
        
        # Check metadata
        assert "format=mk2" in lines[0]
        assert "mode=trigger" in lines[0]
        assert "base_address=0x40000000" in lines[0]
        assert "yaml=test_mk2.yaml" in lines[0]


class TestExportFromFormat:
    """Test exporting using format objects."""
    
    def test_export_from_mk1_format(self):
        """Test export using MK1 format object."""
        fmt = Mk1Format(
            events={
                "0x000": EventMk1(address="0x000", event_source="test", description="Test")
            }
        )
        
        mask = np.zeros(12, dtype=np.uint32)
        result = export_from_format(fmt, mask, include_metadata=False)
        
        lines = result.strip().split('\n')
        assert len(lines) == 12
        assert lines[0] == "00 00000000"
    
    def test_export_from_mk2_format_with_base(self):
        """Test export using MK2 format with base address."""
        fmt = Mk2Format(
            base_address=0x80000000,
            id_names={0: "Test"},
            events={
                "0x000": EventMk2(key="0x000", event_source="test", description="Test")
            }
        )
        
        mask = np.ones(16, dtype=np.uint32)
        
        # Format B should use base address from format
        result = export_from_format(
            fmt,
            mask,
            format_b=True,
            include_metadata=False
        )
        
        lines = result.strip().split('\n')
        # First address should be base + 0x40 (mask mode)
        assert lines[0].startswith("80000040")
    
    def test_export_from_format_with_id_names_hash(self):
        """Test that id_names are hashed in metadata."""
        fmt = Mk2Format(
            id_names={
                0: "Data",
                1: "Network",
                2: "Application"
            },
            events={
                "0x000": EventMk2(key="0x000", event_source="test", description="Test")
            }
        )
        
        mask = np.zeros(16, dtype=np.uint32)
        result = export_from_format(fmt, mask, include_metadata=True)
        
        # Check for id_names_hash in metadata
        assert "id_names_hash=" in result


class TestFileExport:
    """Test file export operations."""
    
    def test_export_to_file(self, tmp_path):
        """Test exporting to file."""
        mask = np.zeros(12, dtype=np.uint32)
        output_file = tmp_path / "export.txt"
        
        exporter = Exporter()
        exporter.format_type = FormatType.MK1
        
        exporter.export_to_file(
            output_file,
            mask,
            MaskMode.MASK,
            include_metadata=False
        )
        
        assert output_file.exists()
        content = output_file.read_text()
        lines = content.strip().split('\n')
        assert len(lines) == 12
    
    def test_export_to_file_creates_directory(self, tmp_path):
        """Test that export creates parent directory if needed."""
        mask = np.zeros(12, dtype=np.uint32)
        output_file = tmp_path / "subdir" / "nested" / "export.txt"
        
        exporter = Exporter()
        exporter.format_type = FormatType.MK1
        
        exporter.export_to_file(
            output_file,
            mask,
            MaskMode.MASK,
            include_metadata=False
        )
        
        assert output_file.exists()
        assert output_file.parent.exists()
    
    def test_export_atomic_write(self, tmp_path):
        """Test atomic file writing."""
        mask = np.zeros(12, dtype=np.uint32)
        output_file = tmp_path / "export.txt"
        
        # Write initial content
        output_file.write_text("Initial content")
        
        exporter = Exporter()
        exporter.format_type = FormatType.MK1
        
        # Export should replace atomically
        exporter.export_to_file(
            output_file,
            mask,
            MaskMode.MASK,
            include_metadata=False
        )
        
        # Check temp file doesn't exist
        temp_file = output_file.with_suffix('.tmp')
        assert not temp_file.exists()
        
        # Check content was replaced
        content = output_file.read_text()
        assert "Initial content" not in content
        assert "00 00000000" in content


class TestMetadata:
    """Test metadata handling."""
    
    def test_create_metadata(self):
        """Test metadata creation."""
        exporter = Exporter()
        exporter.format_type = FormatType.MK1
        
        metadata = exporter._create_metadata(
            MaskMode.MASK,
            yaml_file="test.yaml"
        )
        
        assert metadata.format == FormatType.MK1
        assert metadata.mode == MaskMode.MASK
        assert metadata.yaml == "test.yaml"
        assert metadata.base_address is None
        assert metadata.version is not None
        assert metadata.timestamp is not None
    
    def test_metadata_with_mk2_format(self):
        """Test metadata with MK2 format object."""
        fmt = Mk2Format(
            base_address=0x40000000,
            id_names={0: "Test", 1: "Test2"}
        )
        
        exporter = Exporter(format_obj=fmt)
        metadata = exporter._create_metadata(
            MaskMode.TRIGGER,
            base_address=0x40000000
        )
        
        assert metadata.format == FormatType.MK2
        assert metadata.base_address == 0x40000000
        assert metadata.id_names_hash is not None  # Should be calculated
    
    def test_format_metadata_header(self):
        """Test metadata header formatting."""
        metadata = ExportMetadata(
            format=FormatType.MK1,
            mode=MaskMode.MASK,
            yaml="events.yaml",
            version="1.2.3",
            timestamp="2025-01-01T00:00:00+00:00"
        )
        
        exporter = Exporter()
        header = exporter._format_metadata_header(metadata)
        
        lines = header.split('\n')
        assert lines[0] == "# event-selector: format=mk1, mode=mask, yaml=events.yaml"
        assert lines[1] == "# version=1.2.3, timestamp=2025-01-01T00:00:00+00:00"
        assert lines[2] == ""  # Trailing newline
    
    def test_format_metadata_header_all_fields(self):
        """Test metadata header with all fields."""
        metadata = ExportMetadata(
            format=FormatType.MK2,
            mode=MaskMode.TRIGGER,
            yaml="test.yaml",
            base_address=0x40000000,
            id_names_hash="12345678",
            version="2.0.0",
            timestamp="2025-01-01T12:00:00+00:00"
        )
        
        exporter = Exporter()
        header = exporter._format_metadata_header(metadata)
        
        assert "format=mk2" in header
        assert "mode=trigger" in header
        assert "yaml=test.yaml" in header
        assert "base_address=0x40000000" in header
        assert "id_names_hash=12345678" in header
        assert "version=2.0.0" in header


class TestParseMetadata:
    """Test metadata parsing."""
    
    def test_parse_metadata_basic(self):
        """Test parsing basic metadata."""
        text = """# event-selector: format=mk1, mode=mask, yaml=test.yaml
# version=1.0.0, timestamp=2025-01-01T00:00:00+00:00
00 00000000
01 00000000"""
        
        metadata = parse_metadata_header(text)
        
        assert metadata is not None
        assert metadata["format"] == "mk1"
        assert metadata["mode"] == "mask"
        assert metadata["yaml"] == "test.yaml"
        assert metadata["version"] == "1.0.0"
        assert metadata["timestamp"] == "2025-01-01T00:00:00+00:00"
    
    def test_parse_metadata_mk2(self):
        """Test parsing MK2 metadata with all fields."""
        text = """# event-selector: format=mk2, mode=trigger, yaml=events.yaml, base_address=0x40000000, id_names_hash=abc123
# version=2.1.0, timestamp=2025-01-15T10:30:00+00:00
40000100 00000001"""
        
        metadata = parse_metadata_header(text)
        
        assert metadata["format"] == "mk2"
        assert metadata["mode"] == "trigger"
        assert metadata["yaml"] == "events.yaml"
        assert metadata["base_address"] == "0x40000000"
        assert metadata["id_names_hash"] == "abc123"
        assert metadata["version"] == "2.1.0"
    
    def test_parse_metadata_no_header(self):
        """Test parsing file with no metadata header."""
        text = """00 00000000
01 00000001
02 00000002"""
        
        metadata = parse_metadata_header(text)
        assert metadata is None
    
    def test_parse_metadata_partial(self):
        """Test parsing partial metadata."""
        text = """# event-selector: format=mk1
00 00000000"""
        
        metadata = parse_metadata_header(text)
        assert metadata is not None
        assert metadata["format"] == "mk1"
        assert "mode" not in metadata


class TestRoundTrip:
    """Test round-trip export/import scenarios."""
    
    def test_mk1_round_trip(self):
        """Test MK1 export and metadata parsing round trip."""
        # Create original mask
        original_mask = np.array([
            0x12345678, 0x9ABCDEF0, 0x11111111, 0x22222222,
            0x33333333, 0x44444444, 0x55555555, 0x66666666,
            0x77777777, 0x88888888, 0x99999999, 0xAAAAAAAA
        ], dtype=np.uint32)
        
        # Export
        export_text = export_mask(
            original_mask,
            FormatType.MK1,
            MaskMode.MASK,
            yaml_file="test.yaml",
            include_metadata=True
        )
        
        # Parse metadata
        metadata = parse_metadata_header(export_text)
        assert metadata["format"] == "mk1"
        assert metadata["mode"] == "mask"
        assert metadata["yaml"] == "test.yaml"
        
        # Parse data lines
        lines = export_text.strip().split('\n')
        data_lines = [l for l in lines if not l.startswith('#')]
        
        # Reconstruct mask
        reconstructed_mask = np.zeros(12, dtype=np.uint32)
        for line in data_lines:
            parts = line.split()
            idx = int(parts[0], 16)
            value = int(parts[1], 16)
            reconstructed_mask[idx] = value
        
        # Verify
        np.testing.assert_array_equal(original_mask, reconstructed_mask)
    
    def test_mk2_format_b_round_trip(self):
        """Test MK2 Format B export and parsing round trip."""
        # Create original mask with bits 28-31 set (should be masked)
        original_mask = np.array([0xFFFFFFFF] * 16, dtype=np.uint32)
        expected_mask = np.array([0x0FFFFFFF] * 16, dtype=np.uint32)
        
        base_address = 0x80000000
        
        # Export
        export_text = export_mask(
            original_mask,
            FormatType.MK2,
            MaskMode.TRIGGER,
            format_b=True,
            base_address=base_address,
            yaml_file="mk2.yaml",
            include_metadata=True
        )
        
        # Parse metadata
        metadata = parse_metadata_header(export_text)
        assert metadata["format"] == "mk2"
        assert metadata["mode"] == "trigger"
        assert metadata["base_address"] == "0x80000000"
        
        # Parse data lines
        lines = export_text.strip().split('\n')
        data_lines = [l for l in lines if not l.startswith('#')]
        
        # Reconstruct mask
        reconstructed_mask = np.zeros(16, dtype=np.uint32)
        mode_offset = 0x100  # trigger mode
        
        for line in data_lines:
            parts = line.split()
            addr = int(parts[0], 16)
            value = int(parts[1], 16)
            
            # Calculate ID from address
            offset = addr - base_address - mode_offset
            idx = offset // 4
            
            reconstructed_mask[idx] = value
        
        # Verify (should be masked)
        np.testing.assert_array_equal(expected_mask, reconstructed_mask)


class TestEdgeCases:
    """Test edge cases and special scenarios."""
    
    def test_export_all_zeros(self):
        """Test exporting mask with all zeros."""
        mask = np.zeros(12, dtype=np.uint32)
        
        result = export_mask(
            mask,
            FormatType.MK1,
            MaskMode.MASK,
            include_metadata=False
        )
        
        lines = result.strip().split('\n')
        for line in lines:
            assert line.endswith(" 00000000")
    
    def test_export_all_ones_mk1(self):
        """Test exporting MK1 mask with all ones."""
        mask = np.ones(12, dtype=np.uint32) * 0xFFFFFFFF
        
        result = export_mask(
            mask,
            FormatType.MK1,
            MaskMode.MASK,
            include_metadata=False
        )
        
        lines = result.strip().split('\n')
        for line in lines:
            assert line.endswith(" FFFFFFFF")
    
    def test_export_all_ones_mk2(self):
        """Test exporting MK2 mask with all ones (should mask)."""
        mask = np.ones(16, dtype=np.uint32) * 0xFFFFFFFF
        
        result = export_mask(
            mask,
            FormatType.MK2,
            MaskMode.TRIGGER,
            include_metadata=False
        )
        
        lines = result.strip().split('\n')
        for line in lines:
            assert line.endswith(" 0FFFFFFF")  # Masked
    
    def test_export_single_bit_per_register(self):
        """Test exporting with single bit set per register."""
        mask = np.array([1 << i for i in range(12)], dtype=np.uint32)
        
        result = export_mask(
            mask,
            FormatType.MK1,
            MaskMode.MASK,
            include_metadata=False
        )
        
        lines = result.strip().split('\n')
        
        expected = [
            "00 00000001", "01 00000002", "02 00000004", "03 00000008",
            "04 00000010", "05 00000020", "06 00000040", "07 00000080",
            "08 00000100", "09 00000200", "0A 00000400", "0B 00000800"
        ]
        
        for i, line in enumerate(lines):
            assert line == expected[i]
    
    def test_export_alternating_pattern(self):
        """Test exporting alternating bit pattern."""
        mask = np.array(
            [0xAAAAAAAA if i % 2 == 0 else 0x55555555 for i in range(12)],
            dtype=np.uint32
        )
        
        result = export_mask(
            mask,
            FormatType.MK1,
            MaskMode.MASK,
            include_metadata=False
        )
        
        lines = result.strip().split('\n')
        
        for i, line in enumerate(lines):
            if i % 2 == 0:
                assert line.endswith(" AAAAAAAA")
            else:
                assert line.endswith(" 55555555")
    
    def test_export_trailing_newline(self):
        """Test that export always ends with newline."""
        mask = np.zeros(12, dtype=np.uint32)
        
        result = export_mask(
            mask,
            FormatType.MK1,
            MaskMode.MASK,
            include_metadata=False
        )
        
        assert result.endswith('\n')
        assert not result.endswith('\n\n')  # Only one newline
    
    def test_export_case_consistency(self):
        """Test that hex output is consistently uppercase."""
        mask = np.array([0xabcdef12] * 12, dtype=np.uint32)
        
        result = export_mask(
            mask,
            FormatType.MK1,
            MaskMode.MASK,
            include_metadata=False
        )
        
        # Should be uppercase
        assert "ABCDEF12" in result
        assert "abcdef12" not in result
        
        # ID should also be uppercase
        assert "0A " in result  # ID 10
        assert "0B " in result  # ID 11
        assert "0a " not in result
        assert "0b " not in result

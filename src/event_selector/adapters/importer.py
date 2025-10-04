"""Importer for mask/trigger files."""

import re
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import numpy as np

from event_selector.shared.types import (
    FormatType, MaskMode, ValidationCode, ExportFormat, MetadataDict
)
from event_selector.shared.exceptions import ImportError, ValidationError
from event_selector.domain.models.base import MaskData
from event_selector.domain.interfaces.format_strategy import ValidationResult
from event_selector.adapters.registry import get_format_strategy


class MaskImporter:
    """Importer for mask and trigger files."""

    # Regex patterns for parsing
    METADATA_PATTERN = re.compile(r'#\s*event-selector:\s*(.+)')
    METADATA_FIELD_PATTERN = re.compile(r'(\w+)=([^,]+)')
    FORMAT_A_PATTERN = re.compile(r'^([0-9A-Fa-f]{2})\s+([0-9A-Fa-f]{8})$')
    FORMAT_B_PATTERN = re.compile(r'^([0-9A-Fa-f]{8})\s+([0-9A-Fa-f]{8})$')

    def __init__(self):
        """Initialize importer."""
        self.validation_result = ValidationResult()
        self.metadata: Optional[MetadataDict] = None
        self.detected_format: Optional[FormatType] = None
        self.detected_export_format: Optional[ExportFormat] = None
        self.detected_mode: Optional[MaskMode] = None

    def import_file(self, filepath: Path) -> MaskData:
        """Import a mask/trigger file.

        Args:
            filepath: Path to mask file

        Returns:
            MaskData with imported values

        Raises:
            ImportError: If import fails
            FileNotFoundError: If file doesn't exist
        """
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        try:
            content = filepath.read_text(encoding='utf-8')
        except Exception as e:
            raise ImportError(f"Failed to read file: {e}") from e

        return self.import_text(content, source=str(filepath))

    def import_text(self, text: str, source: str = "unknown") -> MaskData:
        """Import mask/trigger from text content.

        Args:
            text: File content as string
            source: Source identifier for error messages

        Returns:
            MaskData with imported values

        Raises:
            ImportError: If import fails
        """
        self.validation_result = ValidationResult()
        lines = text.strip().split('\n')

        # Parse metadata if present
        self.metadata = self._parse_metadata(lines)

        # Parse data lines
        data_lines = [line for line in lines 
                      if line.strip() and not line.strip().startswith('#')]

        if not data_lines:
            raise ImportError("No data lines found in file")

        # Detect format from metadata or content
        self._detect_format(data_lines)

        # Parse based on detected format
        if self.detected_export_format == ExportFormat.FORMAT_B:
            mask_data = self._parse_format_b(data_lines, source)
        else:
            mask_data = self._parse_format_a(data_lines, source)

        # Apply any necessary masks
        if self.detected_format == FormatType.MK2:
            # Apply MK2 bit mask to ensure bits 28-31 are zero
            strategy = get_format_strategy(FormatType.MK2)
            bit_mask = strategy.get_bit_mask()

            for i in range(len(mask_data.data)):
                original = mask_data.data[i]
                mask_data.data[i] &= bit_mask
                if original != mask_data.data[i]:
                    self.validation_result.add_warning(
                        ValidationCode.BITS_28_31_FORCED_ZERO,
                        f"ID {i:02X}: Bits 28-31 forced to zero",
                        location=f"{source}:ID_{i:02X}"
                    )

        # Add metadata to mask data
        mask_data.metadata = self.metadata

        if self.validation_result.has_errors:
            errors = "\n".join(str(e) for e in self.validation_result.get_errors())
            raise ImportError(f"Import failed:\n{errors}")

        return mask_data

    def _parse_metadata(self, lines: list[str]) -> Optional[MetadataDict]:
        """Parse metadata from comment lines."""
        metadata: MetadataDict = {'format': 'unknown'}

        for line in lines:
            if not line.strip().startswith('#'):
                continue

            match = self.METADATA_PATTERN.search(line)
            if match:
                fields_str = match.group(1)

                # Parse individual fields
                for field_match in self.METADATA_FIELD_PATTERN.finditer(fields_str):
                    key = field_match.group(1)
                    value = field_match.group(2).strip()

                    if key == 'format':
                        metadata['format'] = value
                        try:
                            self.detected_format = FormatType(value)
                        except ValueError:
                            self.validation_result.add_warning(
                                ValidationCode.KEY_FORMAT,
                                f"Unknown format in metadata: {value}"
                            )
                    elif key == 'mode':
                        metadata['mode'] = value
                        try:
                            self.detected_mode = MaskMode(value)
                        except ValueError:
                            self.validation_result.add_warning(
                                ValidationCode.KEY_FORMAT,
                                f"Unknown mode in metadata: {value}"
                            )
                    elif key in ['yaml', 'base_address', 'version', 'timestamp', 'id_names_hash']:
                        metadata[key] = value  # type: ignore

        return metadata if len(metadata) > 1 else None

    def _detect_format(self, data_lines: list[str]) -> None:
        """Detect format type and export format from data lines."""
        if not data_lines:
            return

        # Check first line format
        first_line = data_lines[0].strip()

        if self.FORMAT_B_PATTERN.match(first_line):
            self.detected_export_format = ExportFormat.FORMAT_B
            # Format B is MK2 only
            self.detected_format = FormatType.MK2

            # Try to detect mode from addresses
            if self._detect_mode_from_format_b(data_lines):
                pass  # Mode detected in helper method

        elif self.FORMAT_A_PATTERN.match(first_line):
            self.detected_export_format = ExportFormat.FORMAT_A

            # Count lines to determine format
            if len(data_lines) == 12:
                self.detected_format = FormatType.MK1
            elif len(data_lines) == 16:
                self.detected_format = FormatType.MK2
            else:
                self.validation_result.add_warning(
                    ValidationCode.KEY_FORMAT,
                    f"Unusual number of data lines: {len(data_lines)}"
                )

        # Use metadata format if not detected from content
        if not self.detected_format and self.metadata and 'format' in self.metadata:
            try:
                self.detected_format = FormatType(self.metadata['format'])
            except ValueError:
                pass

        # Default to MK1 if still not detected
        if not self.detected_format:
            self.detected_format = FormatType.MK1
            self.validation_result.add_info(
                ValidationCode.KEY_FORMAT,
                "Format not detected, defaulting to MK1"
            )

    def _detect_mode_from_format_b(self, data_lines: list[str]) -> bool:
        """Detect mode from Format B addresses."""
        if not data_lines:
            return False

        # Parse first address
        match = self.FORMAT_B_PATTERN.match(data_lines[0].strip())
        if not match:
            return False

        first_addr = int(match.group(1), 16)

        # Check offset from base to determine mode
        # Assuming base is aligned, offset 0x40 = mask, 0x100 = trigger
        offset = first_addr & 0xFFF

        if offset == 0x40:
            self.detected_mode = MaskMode.EVENT
            return True
        elif offset == 0x100:
            self.detected_mode = MaskMode.CAPTURE
            return True

        return False

    def _parse_format_a(self, data_lines: list[str], source: str) -> MaskData:
        """Parse Format A data (<ID2> <VALUE8>)."""
        # Determine expected size
        if self.detected_format == FormatType.MK1:
            expected_size = 12
        elif self.detected_format == FormatType.MK2:
            expected_size = 16
        else:
            expected_size = 16  # Default

        # Initialize data array
        data = np.zeros(expected_size, dtype=np.uint32)
        seen_ids = set()

        for line_num, line in enumerate(data_lines, 1):
            line = line.strip()
            if not line:
                continue

            match = self.FORMAT_A_PATTERN.match(line)
            if not match:
                self.validation_result.add_error(
                    ValidationCode.KEY_FORMAT,
                    f"Invalid Format A line: {line}",
                    location=f"{source}:line_{line_num}"
                )
                continue

            id_str = match.group(1)
            value_str = match.group(2)

            try:
                id_val = int(id_str, 16)
                value = int(value_str, 16)
            except ValueError as e:
                self.validation_result.add_error(
                    ValidationCode.KEY_FORMAT,
                    f"Invalid hex values: {e}",
                    location=f"{source}:line_{line_num}"
                )
                continue

            # Validate ID
            if id_val in seen_ids:
                self.validation_result.add_error(
                    ValidationCode.DUPLICATE_KEY,
                    f"Duplicate ID: {id_val:02X}",
                    location=f"{source}:line_{line_num}"
                )
                continue

            seen_ids.add(id_val)

            if id_val >= expected_size:
                self.validation_result.add_error(
                    ValidationCode.KEY_FORMAT,
                    f"ID {id_val:02X} out of range (max: {expected_size-1:02X})",
                    location=f"{source}:line_{line_num}"
                )
                continue

            # Store value
            data[id_val] = value

        # Create MaskData
        mode = self.detected_mode or MaskMode.EVENT
        return MaskData(
            format_type=self.detected_format,
            mode=mode,
            data=data
        )

    def _parse_format_b(self, data_lines: list[str], source: str) -> MaskData:
        """Parse Format B data (<ADDR8> <VALUE8>)."""
        # Format B is MK2 only
        data = np.zeros(16, dtype=np.uint32)
        seen_addrs = set()
        base_address = None
        mode_offset = None

        for line_num, line in enumerate(data_lines, 1):
            line = line.strip()
            if not line:
                continue

            match = self.FORMAT_B_PATTERN.match(line)
            if not match:
                self.validation_result.add_error(
                    ValidationCode.KEY_FORMAT,
                    f"Invalid Format B line: {line}",
                    location=f"{source}:line_{line_num}"
                )
                continue

            addr_str = match.group(1)
            value_str = match.group(2)

            try:
                addr = int(addr_str, 16)
                value = int(value_str, 16)
            except ValueError as e:
                self.validation_result.add_error(
                    ValidationCode.KEY_FORMAT,
                    f"Invalid hex values: {e}",
                    location=f"{source}:line_{line_num}"
                )
                continue

            # Detect base address and mode from first address
            if base_address is None:
                # Extract base (upper bits) and offset
                base_address = addr & 0xFFFFF000
                offset = addr & 0xFFF

                # Determine mode from offset
                if 0x40 <= offset < 0x80:
                    mode_offset = 0x40
                    self.detected_mode = MaskMode.EVENT
                elif 0x100 <= offset < 0x140:
                    mode_offset = 0x100
                    self.detected_mode = MaskMode.CAPTURE
                else:
                    self.validation_result.add_warning(
                        ValidationCode.KEY_FORMAT,
                        f"Unusual address offset: {offset:#x}",
                        location=f"{source}:line_{line_num}"
                    )
                    mode_offset = offset & 0xFFFFFFC0  # Align to 64-byte

            # Calculate ID from address
            expected_addr_base = base_address + mode_offset
            if addr < expected_addr_base:
                self.validation_result.add_error(
                    ValidationCode.KEY_FORMAT,
                    f"Address {addr:#08x} below expected base {expected_addr_base:#08x}",
                    location=f"{source}:line_{line_num}"
                )
                continue

            id_val = (addr - expected_addr_base) // 4

            if id_val >= 16:
                self.validation_result.add_error(
                    ValidationCode.MK2_ADDR_RANGE,
                    f"Address {addr:#08x} maps to invalid ID {id_val}",
                    location=f"{source}:line_{line_num}"
                )
                continue

            if addr in seen_addrs:
                self.validation_result.add_error(
                    ValidationCode.DUPLICATE_KEY,
                    f"Duplicate address: {addr:#08x}",
                    location=f"{source}:line_{line_num}"
                )
                continue

            seen_addrs.add(addr)
            data[id_val] = value

        # Store detected base address in metadata
        if not self.metadata:
            self.metadata = {'format': 'mk2'}
        self.metadata['base_address'] = f"0x{base_address:08x}"

        mode = self.detected_mode or MaskMode.EVENT
        return MaskData(
            format_type=FormatType.MK2,
            mode=mode,
            data=data
        )

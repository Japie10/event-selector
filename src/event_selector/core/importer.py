"""Import functionality for existing mask/trigger files.

This module provides functionality to import mask and trigger files,
detect their format, and associate them with YAML definitions.
"""

import re
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from enum import Enum

import numpy as np

from event_selector.core.models import (
    FormatType,
    MaskMode,
    MaskData,
    ValidationResult,
    ValidationCode,
    ValidationLevel,
    MK2_BIT_MASK,
)
from event_selector.core.exporter import parse_metadata_header


class ImportError(Exception):
    """Base exception for import errors."""
    pass


class FileFormat(Enum):
    """Detected file format."""
    FORMAT_A = "format_a"  # <ID2> <VALUE8>
    FORMAT_B = "format_b"  # <ADDR8> <VALUE8>
    UNKNOWN = "unknown"


class Importer:
    """Importer for mask and trigger files."""

    def __init__(self):
        """Initialize importer."""
        self.validation_result = ValidationResult()
        self._reset_state()

    def _reset_state(self) -> None:
        """Reset importer state."""
        self.validation_result = ValidationResult()
        self.metadata: Optional[Dict[str, Any]] = None
        self.format_type: Optional[FormatType] = None
        self.file_format: Optional[FileFormat] = None
        self.mode: Optional[MaskMode] = None
        self.base_address: Optional[int] = None
        self.yaml_file: Optional[str] = None

    def import_file(self, filepath: str | Path) -> MaskData:
        """Import mask/trigger file.

        Args:
            filepath: Path to mask file

        Returns:
            MaskData object with imported data

        Raises:
            ImportError: If import fails
        """
        filepath = Path(filepath)

        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        try:
            content = filepath.read_text(encoding='utf-8')
        except Exception as e:
            raise ImportError(f"Failed to read file: {e}") from e

        return self.import_text(content, str(filepath))

    def import_text(self, text: str, source: str = "unknown") -> MaskData:
        """Import mask/trigger from text.

        Args:
            text: Text content to import
            source: Source identifier for error messages

        Returns:
            MaskData object with imported data

        Raises:
            ImportError: If import fails
        """
        self._reset_state()

        # Parse metadata header if present
        self.metadata = parse_metadata_header(text)

        # Extract format information from metadata
        if self.metadata:
            self._extract_metadata_info()

        # Parse data lines
        lines = text.strip().split('\n')
        data_lines = [l.strip() for l in lines if l.strip() and not l.startswith('#')]

        if not data_lines:
            raise ImportError("No data lines found in file")

        # Detect file format if not determined from metadata
        if self.file_format is None:
            self.file_format = self._detect_file_format(data_lines)

        # Parse based on format
        if self.file_format == FileFormat.FORMAT_A:
            mask_data = self._parse_format_a(data_lines, source)
        elif self.file_format == FileFormat.FORMAT_B:
            mask_data = self._parse_format_b(data_lines, source)
        else:
            raise ImportError("Unable to determine file format")

        # Add metadata to mask data
        if self.metadata:
            mask_data.metadata = self._create_export_metadata()

        return mask_data

    def detect_format(self, filepath: str | Path) -> Tuple[FormatType, FileFormat, MaskMode]:
        """Detect format of mask file without full import.

        Args:
            filepath: Path to mask file

        Returns:
            Tuple of (format_type, file_format, mode)

        Raises:
            ImportError: If format cannot be detected
        """
        filepath = Path(filepath)

        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        try:
            content = filepath.read_text(encoding='utf-8')
        except Exception as e:
            raise ImportError(f"Failed to read file: {e}") from e

        # Try to get info from metadata
        metadata = parse_metadata_header(content)
        if metadata:
            format_type = FormatType(metadata.get('format', 'mk1'))
            mode = MaskMode(metadata.get('mode', 'mask'))

            # Determine file format
            if 'base_address' in metadata:
                file_format = FileFormat.FORMAT_B
            else:
                file_format = FileFormat.FORMAT_A

            return format_type, file_format, mode

        # Fall back to content analysis
        lines = content.strip().split('\n')
        data_lines = [l.strip() for l in lines if l.strip() and not l.startswith('#')]

        if not data_lines:
            raise ImportError("No data lines found")

        file_format = self._detect_file_format(data_lines)

        # Guess format type based on number of lines
        if file_format == FileFormat.FORMAT_A:
            if len(data_lines) == 12:
                format_type = FormatType.MK1
            elif len(data_lines) == 16:
                format_type = FormatType.MK2
            else:
                raise ImportError(f"Invalid number of data lines: {len(data_lines)}")
        else:
            # FORMAT_B is always MK2
            format_type = FormatType.MK2

        # Default mode
        mode = MaskMode.MASK

        return format_type, file_format, mode

    def _extract_metadata_info(self) -> None:
        """Extract format information from metadata."""
        if not self.metadata:
            return

        # Extract format type
        if 'format' in self.metadata:
            try:
                self.format_type = FormatType(self.metadata['format'])
            except ValueError:
                self.validation_result.add_issue(
                    code=ValidationCode.KEY_FORMAT,
                    level=ValidationLevel.WARNING,
                    message=f"Unknown format in metadata: {self.metadata['format']}"
                )

        # Extract mode
        if 'mode' in self.metadata:
            try:
                self.mode = MaskMode(self.metadata['mode'])
            except ValueError:
                self.validation_result.add_issue(
                    code=ValidationCode.KEY_FORMAT,
                    level=ValidationLevel.WARNING,
                    message=f"Unknown mode in metadata: {self.metadata['mode']}"
                )

        # Extract base address
        if 'base_address' in self.metadata:
            try:
                addr_str = self.metadata['base_address']
                if addr_str.startswith('0x') or addr_str.startswith('0X'):
                    self.base_address = int(addr_str, 16)
                else:
                    self.base_address = int(addr_str)

                # This indicates Format B
                self.file_format = FileFormat.FORMAT_B
            except ValueError as e:
                self.validation_result.add_issue(
                    code=ValidationCode.KEY_FORMAT,
                    level=ValidationLevel.WARNING,
                    message=f"Invalid base_address in metadata: {e}"
                )
        else:
            # No base address suggests Format A
            self.file_format = FileFormat.FORMAT_A

        # Extract YAML file
        if 'yaml' in self.metadata:
            self.yaml_file = self.metadata['yaml']

    def _detect_file_format(self, data_lines: list[str]) -> FileFormat:
        """Detect file format from data lines.

        Args:
            data_lines: List of data lines (no comments)

        Returns:
            Detected file format
        """
        if not data_lines:
            return FileFormat.UNKNOWN

        # Check first line format
        first_line = data_lines[0].strip()
        parts = first_line.split()

        if len(parts) != 2:
            return FileFormat.UNKNOWN

        # Check if first part is 2 or 8 hex digits
        if re.match(r'^[0-9A-Fa-f]{2}$', parts[0]):
            # 2 hex digits - Format A
            return FileFormat.FORMAT_A
        elif re.match(r'^[0-9A-Fa-f]{8}$', parts[0]):
            # 8 hex digits - Format B
            return FileFormat.FORMAT_B
        else:
            return FileFormat.UNKNOWN

    def _parse_format_a(self, data_lines: list[str], source: str) -> MaskData:
        """Parse Format A data lines.

        Args:
            data_lines: List of data lines
            source: Source identifier

        Returns:
            MaskData object

        Raises:
            ImportError: If parsing fails
        """
        # Determine format type from line count if not already known
        if self.format_type is None:
            if len(data_lines) == 12:
                self.format_type = FormatType.MK1
            elif len(data_lines) == 16:
                self.format_type = FormatType.MK2
            else:
                raise ImportError(
                    f"Invalid number of lines for Format A: {len(data_lines)} "
                    f"(expected 12 for MK1 or 16 for MK2)"
                )

        # Validate line count matches format
        expected_lines = 12 if self.format_type == FormatType.MK1 else 16
        if len(data_lines) != expected_lines:
            self.validation_result.add_issue(
                code=ValidationCode.KEY_FORMAT,
                level=ValidationLevel.ERROR,
                message=f"{self.format_type.value} requires {expected_lines} lines, got {len(data_lines)}",
                location=source
            )
            # Try to continue with available lines
            if len(data_lines) < expected_lines:
                # Pad with zeros
                data_lines.extend(['FF 00000000'] * (expected_lines - len(data_lines)))
            else:
                # Truncate
                data_lines = data_lines[:expected_lines]

        # Parse data
        mask_values = []
        seen_ids = set()

        for i, line in enumerate(data_lines):
            parts = line.strip().split()

            if len(parts) != 2:
                self.validation_result.add_issue(
                    code=ValidationCode.KEY_FORMAT,
                    level=ValidationLevel.ERROR,
                    message=f"Invalid line format at line {i+1}: '{line}'",
                    location=f"{source}:{i+1}"
                )
                mask_values.append(0)
                continue

            try:
                id_val = int(parts[0], 16)
                value = int(parts[1], 16)

                # Validate ID
                if id_val in seen_ids:
                    self.validation_result.add_issue(
                        code=ValidationCode.DUPLICATE_KEY,
                        level=ValidationLevel.ERROR,
                        message=f"Duplicate ID {id_val:02X}",
                        location=f"{source}:{i+1}"
                    )
                seen_ids.add(id_val)

                if self.format_type == FormatType.MK1:
                    if id_val > 0x0B:
                        self.validation_result.add_issue(
                            code=ValidationCode.MK1_ADDR_RANGE,
                            level=ValidationLevel.ERROR,
                            message=f"Invalid MK1 ID {id_val:02X} (must be 00-0B)",
                            location=f"{source}:{i+1}"
                        )
                else:  # MK2
                    if id_val > 0x0F:
                        self.validation_result.add_issue(
                            code=ValidationCode.MK2_ADDR_RANGE,
                            level=ValidationLevel.ERROR,
                            message=f"Invalid MK2 ID {id_val:02X} (must be 00-0F)",
                            location=f"{source}:{i+1}"
                        )

                    # Check and warn about bits 28-31
                    if value & ~MK2_BIT_MASK:
                        self.validation_result.add_issue(
                            code=ValidationCode.BITS_28_31_FORCED_ZERO,
                            level=ValidationLevel.WARNING,
                            message=f"MK2 ID {id_val:02X} has bits 28-31 set, clearing",
                            location=f"{source}:{i+1}",
                            details={"original": value, "cleared": value & MK2_BIT_MASK}
                        )
                        value = value & MK2_BIT_MASK

                # Store value at correct index
                while len(mask_values) <= id_val:
                    mask_values.append(0)
                mask_values[id_val] = value

            except ValueError as e:
                self.validation_result.add_issue(
                    code=ValidationCode.KEY_FORMAT,
                    level=ValidationLevel.ERROR,
                    message=f"Invalid hex values at line {i+1}: {e}",
                    location=f"{source}:{i+1}"
                )
                mask_values.append(0)

        # Ensure correct length
        expected_length = 12 if self.format_type == FormatType.MK1 else 16
        while len(mask_values) < expected_length:
            mask_values.append(0)
        mask_values = mask_values[:expected_length]

        # Create MaskData
        return MaskData(
            format_type=self.format_type,
            mode=self.mode or MaskMode.MASK,
            data=mask_values
        )

    def _parse_format_b(self, data_lines: list[str], source: str) -> MaskData:
        """Parse Format B data lines.

        Args:
            data_lines: List of data lines
            source: Source identifier

        Returns:
            MaskData object

        Raises:
            ImportError: If parsing fails
        """
        # Format B is always MK2
        self.format_type = FormatType.MK2

        if len(data_lines) != 16:
            self.validation_result.add_issue(
                code=ValidationCode.KEY_FORMAT,
                level=ValidationLevel.WARNING,
                message=f"Format B expects 16 lines, got {len(data_lines)}",
                location=source
            )

        # Parse data
        mask_values = [0] * 16
        addresses_seen = set()

        # Try to determine base address and mode from addresses
        if self.base_address is None and data_lines:
            # Parse first address to estimate base and mode
            try:
                first_addr = int(data_lines[0].split()[0], 16)
                # Assume first address is for ID 0
                # Address = base + mode_offset + 4*0
                # Try to guess mode from offset
                if (first_addr & 0xFF) == 0x40:
                    self.mode = MaskMode.MASK
                    self.base_address = first_addr - 0x40
                elif (first_addr & 0xFF) == 0x100:
                    self.mode = MaskMode.TRIGGER
                    self.base_address = first_addr - 0x100
                else:
                    # Can't determine, assume mask mode
                    self.mode = MaskMode.MASK
                    self.base_address = first_addr - 0x40

                self.validation_result.add_issue(
                    code=ValidationCode.KEY_FORMAT,
                    level=ValidationLevel.INFO,
                    message=f"Guessed base_address={self.base_address:#x}, mode={self.mode.value}",
                    location=source
                )
            except (ValueError, IndexError):
                pass

        mode_offset = 0x40 if self.mode == MaskMode.MASK else 0x100

        for i, line in enumerate(data_lines):
            parts = line.strip().split()

            if len(parts) != 2:
                self.validation_result.add_issue(
                    code=ValidationCode.KEY_FORMAT,
                    level=ValidationLevel.ERROR,
                    message=f"Invalid line format at line {i+1}: '{line}'",
                    location=f"{source}:{i+1}"
                )
                continue

            try:
                addr = int(parts[0], 16)
                value = int(parts[1], 16)

                # Check for duplicate addresses
                if addr in addresses_seen:
                    self.validation_result.add_issue(
                        code=ValidationCode.DUPLICATE_KEY,
                        level=ValidationLevel.ERROR,
                        message=f"Duplicate address {addr:08X}",
                        location=f"{source}:{i+1}"
                    )
                addresses_seen.add(addr)

                # Calculate ID from address if base is known
                if self.base_address is not None:
                    offset = addr - self.base_address - mode_offset
                    if offset % 4 != 0:
                        self.validation_result.add_issue(
                            code=ValidationCode.KEY_FORMAT,
                            level=ValidationLevel.WARNING,
                            message=f"Address {addr:08X} not 4-byte aligned",
                            location=f"{source}:{i+1}"
                        )

                    id_val = offset // 4

                    if 0 <= id_val <= 15:
                        # Check and clear bits 28-31
                        if value & ~MK2_BIT_MASK:
                            self.validation_result.add_issue(
                                code=ValidationCode.BITS_28_31_FORCED_ZERO,
                                level=ValidationLevel.WARNING,
                                message=f"Address {addr:08X} has bits 28-31 set, clearing",
                                location=f"{source}:{i+1}"
                            )
                            value = value & MK2_BIT_MASK

                        mask_values[id_val] = value
                    else:
                        self.validation_result.add_issue(
                            code=ValidationCode.MK2_ADDR_RANGE,
                            level=ValidationLevel.ERROR,
                            message=f"Address {addr:08X} maps to invalid ID {id_val}",
                            location=f"{source}:{i+1}"
                        )
                else:
                    # Without base address, use line order
                    if i < 16:
                        if value & ~MK2_BIT_MASK:
                            value = value & MK2_BIT_MASK
                        mask_values[i] = value

            except ValueError as e:
                self.validation_result.add_issue(
                    code=ValidationCode.KEY_FORMAT,
                    level=ValidationLevel.ERROR,
                    message=f"Invalid hex values at line {i+1}: {e}",
                    location=f"{source}:{i+1}"
                )

        # Create MaskData
        return MaskData(
            format_type=FormatType.MK2,
            mode=self.mode or MaskMode.MASK,
            data=mask_values
        )

    def _create_export_metadata(self) -> Any:
        """Create ExportMetadata from parsed metadata."""
        from event_selector.core.models import ExportMetadata

        return ExportMetadata(
            format=self.format_type or FormatType.MK1,
            mode=self.mode or MaskMode.MASK,
            yaml=self.yaml_file,
            base_address=self.base_address,
            id_names_hash=self.metadata.get('id_names_hash') if self.metadata else None,
            version=self.metadata.get('version', 'unknown') if self.metadata else 'unknown',
            timestamp=self.metadata.get('timestamp', '') if self.metadata else ''
        )


def import_mask_file(filepath: str | Path) -> Tuple[MaskData, ValidationResult]:
    """Convenience function to import a mask file.

    Args:
        filepath: Path to mask file

    Returns:
        Tuple of (MaskData, ValidationResult)

    Raises:
        ImportError: If import fails
    """
    importer = Importer()
    mask_data = importer.import_file(filepath)
    return mask_data, importer.validation_result


def detect_mask_format(filepath: str | Path) -> Tuple[FormatType, FileFormat, MaskMode]:
    """Convenience function to detect mask file format.

    Args:
        filepath: Path to mask file

    Returns:
        Tuple of (format_type, file_format, mode)

    Raises:
        ImportError: If format cannot be detected
    """
    importer = Importer()
    return importer.detect_format(filepath)


def find_associated_yaml(mask_filepath: str | Path) -> Optional[Path]:
    """Find YAML file associated with mask file.

    Looks for:
    1. YAML file specified in metadata
    2. File with same base name but .yaml extension
    3. Any .yaml file in same directory

    Args:
        mask_filepath: Path to mask file

    Returns:
        Path to associated YAML or None if not found
    """
    mask_path = Path(mask_filepath)

    # Try to get from metadata
    try:
        importer = Importer()
        with open(mask_path, 'r') as f:
            content = f.read()
        metadata = parse_metadata_header(content)

        if metadata and 'yaml' in metadata:
            yaml_name = metadata['yaml']
            # Try relative to mask file directory
            yaml_path = mask_path.parent / yaml_name
            if yaml_path.exists():
                return yaml_path
            # Try just the name in same directory
            yaml_path = mask_path.parent / Path(yaml_name).name
            if yaml_path.exists():
                return yaml_path
    except Exception:
        pass

    # Try same base name
    yaml_path = mask_path.with_suffix('.yaml')
    if yaml_path.exists():
        return yaml_path

    # Try any YAML in directory
    yaml_files = list(mask_path.parent.glob('*.yaml'))
    if len(yaml_files) == 1:
        return yaml_files[0]

    return None
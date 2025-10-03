"""Mask importer for reading mask data from files."""

from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import re
import numpy as np

from event_selector.domain.models.base import MaskData
from event_selector.shared.types import FormatType, MaskMode
from event_selector.domain.interfaces.format_strategy import (
    ValidationResult, ValidationCode, ValidationLevel
)
from event_selector.infrastructure.logging import get_logger

logger = get_logger(__name__)


class MaskImporter:
    """Imports mask data from text files."""

    def __init__(self):
        """Initialize importer."""
        self.validation_result = ValidationResult()

    def import_file(self, file_path: Path) -> MaskData:
        """Import mask data from file.

        Args:
            file_path: Path to mask file

        Returns:
            MaskData instance

        Raises:
            IOError: If file cannot be read
            ValueError: If file format is invalid
        """
        self.validation_result = ValidationResult()

        logger.info(f"Importing mask from {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Parse metadata and values
            metadata = self._parse_metadata(lines)
            values = self._parse_values(lines, metadata)

            # Create MaskData
            mask_data = MaskData(
                format_type=metadata.get('format', FormatType.MK1),
                mode=metadata.get('mode', MaskMode.MASK),
                data=values,
                metadata=metadata
            )

            # Validate
            self._validate_mask_data(mask_data)

            logger.info(f"Successfully imported {mask_data.mode.value}")
            return mask_data

        except Exception as e:
            logger.error(f"Failed to import: {e}")
            raise

    def _parse_metadata(self, lines: list[str]) -> Dict[str, Any]:
        """Parse metadata from header comments.

        Args:
            lines: File lines

        Returns:
            Dictionary of metadata
        """
        metadata = {}

        for line in lines:
            line = line.strip()

            # Look for event-selector header
            if line.startswith('# event-selector:'):
                # Extract metadata from header
                header_content = line.replace('# event-selector:', '').strip()

                # Parse key=value pairs
                for pair in header_content.split(','):
                    pair = pair.strip()
                    if '=' in pair:
                        key, value = pair.split('=', 1)
                        key = key.strip()
                        value = value.strip()

                        # Convert known types
                        if key == 'format':
                            metadata['format'] = FormatType(value)
                        elif key == 'mode':
                            metadata['mode'] = MaskMode(value)
                        else:
                            metadata[key] = value

            # Stop at first non-comment line
            elif not line.startswith('#') and line:
                break

        # Set defaults if not found
        if 'format' not in metadata:
            self.validation_result.add_warning(
                ValidationCode.KEY_FORMAT,
                "No format specified in metadata, defaulting to MK1"
            )
            metadata['format'] = FormatType.MK1

        if 'mode' not in metadata:
            self.validation_result.add_warning(
                ValidationCode.KEY_FORMAT,
                "No mode specified in metadata, defaulting to MASK"
            )
            metadata['mode'] = MaskMode.MASK

        return metadata

    def _parse_values(self, lines: list[str], metadata: Dict[str, Any]) -> np.ndarray:
        """Parse mask values from file lines.

        Args:
            lines: File lines
            metadata: Parsed metadata

        Returns:
            NumPy array of mask values
        """
        format_type = metadata.get('format', FormatType.MK1)

        # Determine expected size
        expected_size = 12 if format_type == FormatType.MK1 else 16

        values_dict = {}

        # Parse value lines
        for line in lines:
            line = line.strip()

            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue

            # Parse "ID: VALUE" format
            match = re.match(r'(0x[0-9A-Fa-f]+)\s*:\s*(0x[0-9A-Fa-f]+)', line)
            if match:
                id_str = match.group(1)
                value_str = match.group(2)

                try:
                    id_num = int(id_str, 16)
                    value = int(value_str, 16)

                    # Validate ID range
                    if id_num >= expected_size:
                        self.validation_result.add_error(
                            ValidationCode.KEY_FORMAT,
                            f"ID {id_str} exceeds maximum for {format_type.value}",
                            location=f"line: {line}"
                        )
                        continue

                    # Validate value range
                    if value > 0xFFFFFFFF:
                        self.validation_result.add_error(
                            ValidationCode.KEY_FORMAT,
                            f"Value {value_str} exceeds 32-bit range",
                            location=f"line: {line}"
                        )
                        continue

                    # For MK2, check bits 28-31
                    if format_type == FormatType.MK2 and (value & 0xF0000000):
                        self.validation_result.add_warning(
                            ValidationCode.KEY_FORMAT,
                            f"ID {id_str}: bits 28-31 are set, will be cleared",
                            location=f"line: {line}"
                        )
                        value &= 0x0FFFFFFF  # Clear bits 28-31

                    values_dict[id_num] = value

                except ValueError as e:
                    self.validation_result.add_error(
                        ValidationCode.KEY_FORMAT,
                        f"Invalid number format: {e}",
                        location=f"line: {line}"
                    )

        # Create array with all values
        values = np.zeros(expected_size, dtype=np.uint32)
        for id_num, value in values_dict.items():
            values[id_num] = value

        # Check if all IDs were provided
        if len(values_dict) < expected_size:
            missing = set(range(expected_size)) - set(values_dict.keys())
            self.validation_result.add_info(
                ValidationCode.KEY_FORMAT,
                f"Missing IDs (defaulted to 0): {sorted(missing)}"
            )

        return values

    def _validate_mask_data(self, mask_data: MaskData) -> None:
        """Validate imported mask data.

        Args:
            mask_data: Mask data to validate
        """
        # Check array size
        expected_size = 12 if mask_data.format_type == FormatType.MK1 else 16

        if len(mask_data.data) != expected_size:
            self.validation_result.add_error(
                ValidationCode.KEY_FORMAT,
                f"Incorrect array size: expected {expected_size}, got {len(mask_data.data)}"
            )

        # Check for undefined bits set (if we have format definition)
        # This would require access to the format object, which we don't have here
        # So we just log a warning
        set_bits_count = np.count_nonzero(mask_data.data)
        if set_bits_count == 0:
            self.validation_result.add_info(
                ValidationCode.KEY_FORMAT,
                "All bits are cleared (mask is empty)"
            )

        logger.debug(f"Validated mask: {set_bits_count} non-zero values")

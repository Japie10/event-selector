"""Export functionality for masks and triggers.

This module provides functionality to export mask and trigger data
in Format A and Format B, with comprehensive metadata headers.
"""

import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, TypeAlias
from io import StringIO

import numpy as np

from event_selector.core.models import (
    FormatType,
    MaskMode,
    MaskData,
    ExportMetadata,
    Mk1Format,
    Mk2Format,
    MK2_BIT_MASK,
)
from event_selector.utils.logging import get_logger

logger = get_logger(__name__)

FormatObject: TypeAlias = Mk1Format | Mk2Format

# Try to import version, fallback if not available
try:
    from event_selector import __version__
except ImportError:
    __version__ = "0.0.0+unknown"


class ExportError(Exception):
    """Base exception for export errors."""
    pass


class Exporter:
    """Exporter for mask and trigger data."""
    
    def __init__(self, 
                 format_obj: Optional[FormatObject] = None,
                 mask_data: Optional[MaskData] = None):
        """Initialize exporter.

        Args:
            format_obj: Optional format definition for metadata
            mask_data: Optional mask data to export
        """
        logger.trace("Entering {function_name}", function_name=__name__)
        self.format_obj = format_obj
        self.mask_data = mask_data
        self._determine_format_type()

    def _determine_format_type(self) -> None:
        """Determine format type from available data."""
        logger.trace("Entering {function_name}", function_name=__name__)
        if self.mask_data:
            self.format_type = self.mask_data.format_type
        elif self.format_obj:
            if isinstance(self.format_obj, Mk1Format):
                self.format_type = FormatType.MK1
            elif isinstance(self.format_obj, Mk2Format):
                self.format_type = FormatType.MK2
            else:
                raise ExportError(f"Unknown format object type: {type(self.format_obj)}")
        else:
            self.format_type = None

    def export_format_a(self,
                       mask_array: np.ndarray,
                       mode: MaskMode = MaskMode.MASK,
                       yaml_file: Optional[str] = None,
                       include_metadata: bool = True) -> str:
        """Export mask/trigger in Format A (<ID2> <VALUE8>).

        Args:
            mask_array: NumPy array of mask values
            mode: Mask or trigger mode
            yaml_file: Optional YAML filename for metadata
            include_metadata: Whether to include metadata header

        Returns:
            Exported text in Format A

        Raises:
            ExportError: If export fails
        """
        logger.trace("Entering {function_name}", function_name=__name__)
        if self.format_type is None:
            raise ExportError("Format type not determined")

        # Validate array size
        expected_size = 12 if self.format_type == FormatType.MK1 else 16
        if len(mask_array) != expected_size:
            raise ExportError(
                f"{self.format_type.value} requires {expected_size} values, got {len(mask_array)}"
            )

        output = StringIO()

        # Add metadata header if requested
        if include_metadata:
            metadata = self._create_metadata(mode, yaml_file)
            header = self._format_metadata_header(metadata)
            output.write(header)

        # Export data lines
        for i in range(expected_size):
            value = int(mask_array[i])

            # For MK2, ensure bits 28-31 are zero
            if self.format_type == FormatType.MK2:
                if value & ~MK2_BIT_MASK:
                    # Log warning but continue with masked value
                    value = value & MK2_BIT_MASK

            # Format: <ID2> <VALUE8>
            output.write(f"{i:02X} {value:08X}\n")

        return output.getvalue()

    def export_format_b(self,
                       mask_array: np.ndarray,
                       mode: MaskMode = MaskMode.MASK,
                       base_address: Optional[int] = None,
                       yaml_file: Optional[str] = None,
                       include_metadata: bool = True) -> str:
        """Export mask/trigger in Format B (<ADDR8> <VALUE8>).

        Format B is only supported for MK2.

        Args:
            mask_array: NumPy array of mask values
            mode: Mask or trigger mode
            base_address: Base address for address calculation
            yaml_file: Optional YAML filename for metadata
            include_metadata: Whether to include metadata header

        Returns:
            Exported text in Format B

        Raises:
            ExportError: If export fails or format not supported
        """
        logger.trace("Entering {function_name}", function_name=__name__)
        if self.format_type != FormatType.MK2:
            raise ExportError("Format B is only supported for MK2")

        if len(mask_array) != 16:
            raise ExportError(f"MK2 requires 16 values, got {len(mask_array)}")

        # Get base address
        if base_address is None:
            if isinstance(self.format_obj, Mk2Format) and self.format_obj.base_address:
                base_address = self.format_obj.base_address
            else:
                raise ExportError("Base address required for Format B export")

        # Validate base address
        if base_address > 0xFFFFFFFF:
            raise ExportError(f"Base address {base_address:#x} exceeds 32-bit range")

        # Calculate mode offset
        mode_offset = 0x40 if mode == MaskMode.MASK else 0x100

        output = StringIO()

        # Add metadata header if requested
        if include_metadata:
            metadata = self._create_metadata(mode, yaml_file, base_address)
            header = self._format_metadata_header(metadata)
            output.write(header)

        # Export data lines
        for i in range(16):
            value = int(mask_array[i])

            # Ensure bits 28-31 are zero
            if value & ~MK2_BIT_MASK:
                value = value & MK2_BIT_MASK

            # Calculate address: base_address + mode_offset + 4*id
            address = base_address + mode_offset + (4 * i)

            # Format: <ADDR8> <VALUE8>
            output.write(f"{address:08X} {value:08X}\n")

        return output.getvalue()

    def export_to_file(self,
                      filepath: str | Path,
                      mask_array: np.ndarray,
                      mode: MaskMode = MaskMode.MASK,
                      format_b: bool = False,
                      base_address: Optional[int] = None,
                      yaml_file: Optional[str] = None,
                      include_metadata: bool = True) -> None:
        """Export mask/trigger to file.

        Args:
            filepath: Output file path
            mask_array: NumPy array of mask values
            mode: Mask or trigger mode
            format_b: Use Format B (MK2 only)
            base_address: Base address for Format B
            yaml_file: Optional YAML filename for metadata
            include_metadata: Whether to include metadata header

        Raises:
            ExportError: If export fails
        """
        logger.trace("Entering {function_name}", function_name=__name__)
        filepath = Path(filepath)

        # Generate export text
        if format_b:
            export_text = self.export_format_b(
                mask_array, mode, base_address, yaml_file, include_metadata
            )
        else:
            export_text = self.export_format_a(
                mask_array, mode, yaml_file, include_metadata
            )

        # Write to file
        try:
            # Create parent directory if needed
            filepath.parent.mkdir(parents=True, exist_ok=True)

            # Write atomically using temporary file
            temp_file = filepath.with_suffix('.tmp')
            temp_file.write_text(export_text, encoding='utf-8')
            temp_file.replace(filepath)

        except Exception as e:
            raise ExportError(f"Failed to write file {filepath}: {e}") from e

    def _create_metadata(self,
                        mode: MaskMode,
                        yaml_file: Optional[str] = None,
                        base_address: Optional[int] = None) -> ExportMetadata:
        """Create metadata for export.

        Args:
            mode: Mask or trigger mode
            yaml_file: Optional YAML filename
            base_address: Optional base address for MK2

        Returns:
            ExportMetadata object
        """
        logger.trace("Entering {function_name}", function_name=__name__)
        # Get current timestamp
        timestamp = datetime.now(timezone.utc).isoformat()

        # Calculate id_names hash if available
        id_names_hash = None
        if isinstance(self.format_obj, Mk2Format) and self.format_obj.id_names:
            # Create deterministic hash of id_names
            names_str = ";".join(
                f"{k}:{v}" for k, v in sorted(self.format_obj.id_names.items())
            )
            id_names_hash = hashlib.md5(names_str.encode()).hexdigest()[:8]

        return ExportMetadata(
            format=self.format_type,
            mode=mode,
            yaml=yaml_file,
            base_address=base_address,
            id_names_hash=id_names_hash,
            version=__version__,
            timestamp=timestamp
        )

    def _format_metadata_header(self, metadata: ExportMetadata) -> str:
        """Format metadata as comment header.

        Args:
            metadata: ExportMetadata object

        Returns:
            Formatted header string
        """
        logger.trace("Entering {function_name}", function_name=__name__)
        lines = []

        # Main metadata line
        parts = [
            f"format={metadata.format.value}",
            f"mode={metadata.mode.value}",
        ]

        if metadata.yaml:
            parts.append(f"yaml={metadata.yaml}")

        if metadata.base_address is not None:
            parts.append(f"base_address={metadata.base_address:#x}")

        if metadata.id_names_hash:
            parts.append(f"id_names_hash={metadata.id_names_hash}")

        lines.append(f"# event-selector: {', '.join(parts)}")

        # Version and timestamp line
        lines.append(f"# version={metadata.version}, timestamp={metadata.timestamp}")

        return "\n".join(lines) + "\n"


def export_mask(mask_array: np.ndarray,
               format_type: FormatType,
               mode: MaskMode = MaskMode.MASK,
               format_b: bool = False,
               base_address: Optional[int] = None,
               yaml_file: Optional[str] = None,
               include_metadata: bool = True) -> str:
    """Convenience function to export mask data.

    Args:
        mask_array: NumPy array of mask values
        format_type: MK1 or MK2 format
        mode: Mask or trigger mode
        format_b: Use Format B (MK2 only)
        base_address: Base address for Format B
        yaml_file: Optional YAML filename for metadata
        include_metadata: Whether to include metadata header

    Returns:
        Exported text

    Raises:
        ExportError: If export fails
    """
    logger.trace("Entering {function_name}", function_name=__name__)
    # Create mask data
    mask_data = MaskData.from_numpy(mask_array, format_type, mode)

    # Create exporter
    exporter = Exporter(mask_data=mask_data)

    # Export
    if format_b:
        return exporter.export_format_b(
            mask_array, mode, base_address, yaml_file, include_metadata
        )
    else:
        return exporter.export_format_a(
            mask_array, mode, yaml_file, include_metadata
        )


def export_from_format(format_obj: FormatObject,
                       mask_array: np.ndarray,
                       mode: MaskMode = MaskMode.MASK,
                       format_b: bool = False,
                       yaml_file: Optional[str] = None,
                       include_metadata: bool = True) -> str:
    """Export mask using format definition for metadata.

    Args:
        format_obj: Format definition object
        mask_array: NumPy array of mask values
        mode: Mask or trigger mode
        format_b: Use Format B (MK2 only)
        yaml_file: Optional YAML filename for metadata
        include_metadata: Whether to include metadata header

    Returns:
        Exported text

    Raises:
        ExportError: If export fails
    """
    logger.trace("Entering {function_name}", function_name=__name__)
    exporter = Exporter(format_obj=format_obj)

    if format_b:
        base_address = None
        if isinstance(format_obj, Mk2Format):
            base_address = format_obj.base_address
        return exporter.export_format_b(
            mask_array, mode, base_address, yaml_file, include_metadata
        )
    else:
        return exporter.export_format_a(
            mask_array, mode, yaml_file, include_metadata
        )


def parse_metadata_header(text: str) -> Optional[Dict[str, Any]]:
    """Parse metadata from export file header.

    Args:
        text: Export file text

    Returns:
        Dictionary of metadata fields or None if no header found
    """
    logger.trace("Entering {function_name}", function_name=__name__)
    lines = text.strip().split('\n')
    metadata = {}

    for line in lines:
        if not line.startswith('#'):
            break  # End of header

        if 'event-selector:' in line:
            # Parse main metadata line
            parts = line.split(':', 1)[1].strip()
            for part in parts.split(','):
                part = part.strip()
                if '=' in part:
                    key, value = part.split('=', 1)
                    metadata[key.strip()] = value.strip()

        elif 'version=' in line and 'timestamp=' in line:
            # Parse version/timestamp line
            parts = line[1:].strip()  # Remove #
            for part in parts.split(','):
                part = part.strip()
                if '=' in part:
                    key, value = part.split('=', 1)
                    metadata[key.strip()] = value.strip()

    return metadata if metadata else None
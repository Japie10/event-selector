"""Mask exporter for writing mask data to files."""

from pathlib import Path
from typing import Optional
from datetime import datetime, timezone
import numpy as np

from event_selector.domain.models.base import MaskData
from event_selector.shared.types import FormatType, MaskMode
from event_selector.infrastructure.logging import get_logger

logger = get_logger(__name__)


class MaskExporter:
    """Exports mask data to text files."""

    def __init__(self):
        """Initialize exporter."""
        self.version = "1.0.0"

    def export_file(
        self,
        mask_data: MaskData,
        output_path: Path,
        include_metadata: bool = True,
        yaml_file: Optional[Path] = None
    ) -> None:
        """Export mask data to file.

        Args:
            mask_data: Mask data to export
            output_path: Output file path
            include_metadata: Whether to include metadata header
            yaml_file: Optional YAML file path for metadata

        Raises:
            IOError: If file cannot be written
        """
        logger.info(f"Exporting {mask_data.mode.value} to {output_path}")

        lines = []

        # Add metadata header
        if include_metadata:
            lines.extend(self._generate_metadata_header(mask_data, yaml_file))

        # Add mask values
        lines.extend(self._generate_mask_values(mask_data))

        # Write to file
        try:
            # Write to temporary file first
            temp_path = output_path.with_suffix(output_path.suffix + '.tmp')

            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
                f.write('\n')  # Final newline

            # Atomic rename
            temp_path.replace(output_path)

            logger.info(f"Successfully exported to {output_path}")

        except Exception as e:
            logger.error(f"Failed to export: {e}")
            # Clean up temp file if it exists
            if temp_path.exists():
                temp_path.unlink()
            raise IOError(f"Failed to write file: {e}")

    def _generate_metadata_header(
        self,
        mask_data: MaskData,
        yaml_file: Optional[Path]
    ) -> list[str]:
        """Generate metadata header lines.

        Args:
            mask_data: Mask data
            yaml_file: Optional YAML file path

        Returns:
            List of header lines
        """
        lines = []

        # Format line
        format_str = mask_data.format_type.value
        mode_str = mask_data.mode.value

        metadata_parts = [
            f"format={format_str}",
            f"mode={mode_str}",
        ]

        # Add YAML file reference if provided
        if yaml_file:
            metadata_parts.append(f"yaml={yaml_file.name}")

        # Add version and timestamp
        metadata_parts.append(f"version={self.version}")
        timestamp = datetime.now(timezone.utc).isoformat()
        metadata_parts.append(f"timestamp={timestamp}")

        # Create header comment
        lines.append(f"# event-selector: {', '.join(metadata_parts)}")
        lines.append("#")

        # Add additional info
        if mask_data.metadata:
            for key, value in mask_data.metadata.items():
                lines.append(f"# {key}: {value}")

        lines.append("")  # Blank line after header

        return lines

    def _generate_mask_values(self, mask_data: MaskData) -> list[str]:
        """Generate mask value lines.

        Args:
            mask_data: Mask data

        Returns:
            List of value lines
        """
        lines = []

        # Format based on mask format type
        if mask_data.format_type == FormatType.MK1:
            lines.extend(self._format_mk1_values(mask_data))
        elif mask_data.format_type == FormatType.MK2:
            lines.extend(self._format_mk2_values(mask_data))
        else:
            raise ValueError(f"Unsupported format: {mask_data.format_type}")

        return lines

    def _format_mk1_values(self, mask_data: MaskData) -> list[str]:
        """Format MK1 mask values.

        Args:
            mask_data: Mask data (12 values)

        Returns:
            List of formatted lines
        """
        lines = []

        # MK1: 12 IDs (0x00-0x0B)
        for i in range(12):
            if i < len(mask_data.data):
                value = mask_data.data[i]
                lines.append(f"0x{i:02X}: 0x{value:08X}")
            else:
                lines.append(f"0x{i:02X}: 0x00000000")

        return lines

    def _format_mk2_values(self, mask_data: MaskData) -> list[str]:
        """Format MK2 mask values.

        Args:
            mask_data: Mask data (16 values)

        Returns:
            List of formatted lines
        """
        lines = []

        # MK2: 16 IDs (0x00-0x0F), mask bits 28-31
        for i in range(16):
            if i < len(mask_data.data):
                value = mask_data.data[i]
                # Clear bits 28-31 for MK2
                value &= 0x0FFFFFFF
                lines.append(f"0x{i:02X}: 0x{value:08X}")
            else:
                lines.append(f"0x{i:02X}: 0x00000000")

        return lines

    def export_both(
        self,
        mask_data: MaskData,
        trigger_data: MaskData,
        mask_path: Path,
        trigger_path: Path,
        yaml_file: Optional[Path] = None
    ) -> None:
        """Export both mask and trigger files.

        Args:
            mask_data: Event mask data
            trigger_data: Capture mask data
            mask_path: Output path for mask file
            trigger_path: Output path for trigger file
            yaml_file: Optional YAML file reference
        """
        self.export_file(mask_data, mask_path, include_metadata=True, yaml_file=yaml_file)
        self.export_file(trigger_data, trigger_path, include_metadata=True, yaml_file=yaml_file)

        logger.info(f"Exported both mask and trigger files")

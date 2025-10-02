"""Exporter for mask/trigger files."""

from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import hashlib

from event_selector.shared.types import (
    FormatType, MaskMode, ExportFormat, MetadataDict
)
from event_selector.shared.exceptions import ExportError
from event_selector.domain.models.base import MaskData, EventFormat
from event_selector.adapters.registry import get_format_strategy


class MaskExporter:
    """Exporter for mask and trigger files."""

    def __init__(self):
        """Initialize exporter."""
        pass

    def export_file(self,
                    mask_data: MaskData,
                    filepath: Path,
                    include_metadata: bool = True,
                    yaml_file: Optional[str] = None,
                    export_format: ExportFormat = ExportFormat.FORMAT_A,
                    base_address: Optional[int] = None) -> None:
        """Export mask data to file.

        Args:
            mask_data: Mask data to export
            filepath: Output file path
            include_metadata: Whether to include metadata header
            yaml_file: Associated YAML file for metadata
            export_format: Format A or B
            base_address: Base address for Format B

        Raises:
            ExportError: If export fails
        """
        content = self.export_text(
            mask_data,
            include_metadata=include_metadata,
            yaml_file=yaml_file,
            export_format=export_format,
            base_address=base_address
        )

        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(content, encoding='utf-8')
        except Exception as e:
            raise ExportError(f"Failed to write file: {e}") from e

    def export_text(self,
                    mask_data: MaskData,
                    include_metadata: bool = True,
                    yaml_file: Optional[str] = None,
                    export_format: ExportFormat = ExportFormat.FORMAT_A,
                    base_address: Optional[int] = None) -> str:
        """Export mask data to text.

        Args:
            mask_data: Mask data to export
            include_metadata: Whether to include metadata header
            yaml_file: Associated YAML file for metadata
            export_format: Format A or B
            base_address: Base address for Format B

        Returns:
            Exported text content

        Raises:
            ExportError: If export fails
        """
        # Validate parameters
        if export_format == ExportFormat.FORMAT_B:
            if mask_data.format_type != FormatType.MK2:
                raise ExportError("Format B is only supported for MK2")
            if base_address is None:
                raise ExportError("Base address required for Format B export")
            if base_address > 0xFFFFFFFF:
                raise ExportError(f"Base address {base_address:#x} exceeds 32-bit range")

        lines = []

        # Add metadata header if requested
        if include_metadata:
            metadata = self._build_metadata(
                mask_data,
                yaml_file=yaml_file,
                base_address=base_address
            )
            lines.extend(self._format_metadata(metadata))

        # Export data based on format
        if export_format == ExportFormat.FORMAT_B:
            lines.extend(self._export_format_b(mask_data, base_address))
        else:
            lines.extend(self._export_format_a(mask_data))

        # Ensure trailing newline
        return '\n'.join(lines) + '\n'

    def _build_metadata(self,
                        mask_data: MaskData,
                        yaml_file: Optional[str] = None,
                        base_address: Optional[int] = None) -> MetadataDict:
        """Build metadata dictionary."""
        metadata: MetadataDict = {
            'format': mask_data.format_type.value,
            'mode': mask_data.mode.value
        }

        if yaml_file:
            metadata['yaml'] = yaml_file

        if base_address is not None:
            metadata['base_address'] = f"0x{base_address:08x}"

        # Add version and timestamp
        try:
            from event_selector._version import __version__
            metadata['version'] = __version__
        except ImportError:
            metadata['version'] = "dev"

        metadata['timestamp'] = datetime.now().isoformat()

        # Add ID names hash if present in mask metadata
        if mask_data.metadata and 'id_names_hash' in mask_data.metadata:
            metadata['id_names_hash'] = mask_data.metadata['id_names_hash']

        return metadata

    def _format_metadata(self, metadata: MetadataDict) -> list[str]:
        """Format metadata as comment lines."""
        lines = []

        # First line: main metadata
        main_fields = []
        for key in ['format', 'mode', 'yaml', 'base_address']:
            if key in metadata:
                main_fields.append(f"{key}={metadata[key]}")

        if main_fields:
            lines.append(f"# event-selector: {', '.join(main_fields)}")

        # Second line: additional metadata
        extra_fields = []
        for key in ['version', 'timestamp', 'id_names_hash']:
            if key in metadata:
                extra_fields.append(f"{key}={metadata[key]}")

        if extra_fields:
            lines.append(f"# {', '.join(extra_fields)}")

        return lines

    def _export_format_a(self, mask_data: MaskData) -> list[str]:
        """Export as Format A (<ID2> <VALUE8>)."""
        lines = []
        strategy = get_format_strategy(mask_data.format_type)

        # Apply bit mask for format
        bit_mask = strategy.get_bit_mask()

        for i, value in enumerate(mask_data.data):
            # Apply mask to ensure only valid bits
            masked_value = int(value) & bit_mask
            lines.append(f"{i:02X} {masked_value:08X}")

        return lines

    def _export_format_b(self, 
                         mask_data: MaskData,
                         base_address: Optional[int]) -> list[str]:
        """Export as Format B (<ADDR8> <VALUE8>)."""
        if base_address is None:
            raise ExportError("Base address required for Format B")

        lines = []
        strategy = get_format_strategy(mask_data.format_type)

        # Apply bit mask for format
        bit_mask = strategy.get_bit_mask()

        # Calculate offset based on mode
        if mask_data.mode == MaskMode.MASK:
            mode_offset = 0x40
        else:  # TRIGGER
            mode_offset = 0x100

        for i, value in enumerate(mask_data.data):
            # Calculate address
            addr = base_address + mode_offset + (i * 4)

            # Apply mask to ensure only valid bits
            masked_value = int(value) & bit_mask

            lines.append(f"{addr:08X} {masked_value:08X}")

        return lines


class ExportBuilder:
    """Builder for creating export configurations."""

    def __init__(self):
        """Initialize builder."""
        self.reset()

    def reset(self) -> 'ExportBuilder':
        """Reset builder state."""
        self._mask_data: Optional[MaskData] = None
        self._filepath: Optional[Path] = None
        self._include_metadata = True
        self._yaml_file: Optional[str] = None
        self._export_format = ExportFormat.FORMAT_A
        self._base_address: Optional[int] = None
        return self

    def with_mask_data(self, mask_data: MaskData) -> 'ExportBuilder':
        """Set mask data."""
        self._mask_data = mask_data
        return self

    def with_filepath(self, filepath: Path) -> 'ExportBuilder':
        """Set output filepath."""
        self._filepath = filepath
        return self

    def with_metadata(self, include: bool = True) -> 'ExportBuilder':
        """Set whether to include metadata."""
        self._include_metadata = include
        return self

    def with_yaml_reference(self, yaml_file: str) -> 'ExportBuilder':
        """Set YAML file reference."""
        self._yaml_file = yaml_file
        return self

    def with_format_b(self, base_address: int) -> 'ExportBuilder':
        """Use Format B with base address."""
        self._export_format = ExportFormat.FORMAT_B
        self._base_address = base_address
        return self

    def build_and_export(self) -> None:
        """Build configuration and export."""
        if not self._mask_data:
            raise ExportError("Mask data not set")
        if not self._filepath:
            raise ExportError("Filepath not set")

        # Validate Format B requirements
        if self._export_format == ExportFormat.FORMAT_B:
            if self._mask_data.format_type != FormatType.MK2:
                raise ExportError("Format B only supported for MK2")
            if self._base_address is None:
                raise ExportError("Base address required for Format B")

        exporter = MaskExporter()
        exporter.export_file(
            self._mask_data,
            self._filepath,
            include_metadata=self._include_metadata,
            yaml_file=self._yaml_file,
            export_format=self._export_format,
            base_address=self._base_address
        )

    def build_text(self) -> str:
        """Build configuration and return as text."""
        if not self._mask_data:
            raise ExportError("Mask data not set")

        exporter = MaskExporter()
        return exporter.export_text(
            self._mask_data,
            include_metadata=self._include_metadata,
            yaml_file=self._yaml_file,
            export_format=self._export_format,
            base_address=self._base_address
        )

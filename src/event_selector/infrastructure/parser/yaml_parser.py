"""YAML parser for event definition files."""

from pathlib import Path
from typing import Dict, Any, Tuple
import yaml

from event_selector.domain.models.base import EventFormat
from event_selector.domain.models.mk1 import Mk1Format
from event_selector.domain.models.mk2 import Mk2Format
from event_selector.domain.interfaces.format_strategy import ValidationResult
from event_selector.shared.types import FormatType
from event_selector.shared.exceptions import ParseError
from event_selector.infrastructure.logging import get_logger

logger = get_logger(__name__)


class YamlParserError(ParseError):
    """YAML parsing error."""
    pass


class YamlParser:
    """Parser for YAML event definition files."""

    def __init__(self):
        """Initialize parser."""
        self.validation_result = ValidationResult()

    def parse_file(self, filepath: Path) -> Tuple[EventFormat, ValidationResult]:
        """Parse YAML file into EventFormat.

        Args:
            filepath: Path to YAML file

        Returns:
            Tuple of (EventFormat, ValidationResult)

        Raises:
            FileNotFoundError: If file doesn't exist
            YamlParserError: If parsing fails
        """
        if not filepath.exists():
            raise FileNotFoundError(f"YAML file not found: {filepath}")

        logger.info(f"Parsing YAML file: {filepath}")

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                # CRITICAL: Always use safe_load for security
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise YamlParserError(f"Invalid YAML: {e}", file=str(filepath)) from e
        except Exception as e:
            raise YamlParserError(f"Failed to read file: {e}", file=str(filepath)) from e

        if data is None:
            data = {}

        return self.parse_data(data, source=str(filepath))

    def parse_data(self, data: Dict[str, Any], source: str = "unknown") -> Tuple[EventFormat, ValidationResult]:
        """Parse dictionary into EventFormat.

        Args:
            data: Parsed YAML data
            source: Source identifier for errors

        Returns:
            Tuple of (EventFormat, ValidationResult)

        Raises:
            YamlParserError: If parsing fails
        """
        if not isinstance(data, dict):
            raise YamlParserError(f"Expected dict, got {type(data).__name__}", file=source)

        # Detect format
        format_type = self._detect_format(data)
        logger.debug(f"Detected format: {format_type.value}")

        # Delegate to appropriate format class
        if format_type == FormatType.MK1:
            return Mk1Format.from_yaml_data(data, source)
        else:  # MK2
            return Mk2Format.from_yaml_data(data, source)

    def _detect_format(self, data: Dict[str, Any]) -> FormatType:
        """Detect MK1 or MK2 format.

        Args:
            data: YAML data

        Returns:
            Detected FormatType
        """
        # MK2 indicators
        if 'id_names' in data or 'base_address' in data:
            return FormatType.MK2

        # Check event keys for MK1 address ranges
        for key in data.keys():
            if key in ['sources']:
                continue
            
            try:
                addr = self._parse_address(key)
                # MK1 ranges: 0x000-0x07F, 0x200-0x27F, 0x400-0x47F
                if (0x000 <= addr <= 0x07F or 
                    0x200 <= addr <= 0x27F or 
                    0x400 <= addr <= 0x47F):
                    return FormatType.MK1
            except (ValueError, TypeError):
                continue

        # Default to MK2
        return FormatType.MK2

    @staticmethod
    def _parse_address(key: Any) -> int:
        """Parse key to integer address."""
        if isinstance(key, int):
            return key
        if isinstance(key, str):
            key = key.strip()
            return int(key, 16) if 'x' in key.lower() else int(key, 16)
        raise ValueError(f"Invalid key type: {type(key)}")

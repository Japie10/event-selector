"""Parser for YAML event definition files."""

from pathlib import Path
from typing import Dict, Any, Optional, Union
import yaml

from event_selector.shared.types import (
    FormatType, EventKey, ValidationCode
)
from event_selector.shared.exceptions import ParseError, ValidationError
from event_selector.domain.models.base import EventFormat
from event_selector.domain.models.mk1 import Mk1Format
from event_selector.domain.models.mk2 import Mk2Format
from event_selector.domain.models.value_objects import EventInfo, EventSource
from event_selector.domain.interfaces.format_strategy import ValidationResult
from event_selector.adapters.registry import get_format_strategy


class YamlParser:
    """Parser for YAML event definition files."""

    def __init__(self):
        """Initialize parser."""
        self.validation_result = ValidationResult()

    def parse_file(self, filepath: Path) -> EventFormat:
        """Parse a YAML file into an EventFormat.

        Args:
            filepath: Path to YAML file

        Returns:
            Parsed EventFormat (Mk1Format or Mk2Format)

        Raises:
            ParseError: If parsing fails
            FileNotFoundError: If file doesn't exist
        """
        if not filepath.exists():
            raise FileNotFoundError(f"YAML file not found: {filepath}")

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ParseError(f"Invalid YAML: {e}", file=filepath) from e
        except Exception as e:
            raise ParseError(f"Failed to read file: {e}", file=filepath) from e

        if not isinstance(data, dict):
            raise ParseError("YAML must contain a dictionary at root", file=filepath)

        return self.parse_data(data, source=str(filepath))

    def parse_data(self, data: Dict[str, Any], source: str = "unknown") -> EventFormat:
        """Parse dictionary data into an EventFormat.

        Args:
            data: Dictionary containing event definitions
            source: Source identifier for error messages

        Returns:
            Parsed EventFormat

        Raises:
            ParseError: If parsing fails
        """
        self.validation_result = ValidationResult()

        # Detect format type
        format_type = self._detect_format(data)

        # Get strategy for validation
        strategy = get_format_strategy(format_type)

        # Create format instance
        if format_type == FormatType.MK1:
            format_obj = self._parse_mk1(data, source, strategy)
        elif format_type == FormatType.MK2:
            format_obj = self._parse_mk2(data, source, strategy)
        else:
            raise ParseError(f"Unsupported format: {format_type.value}")

        # Validate the format
        format_validation = format_obj.validate()
        self.validation_result.merge(format_validation)

        if self.validation_result.has_errors:
            errors = "\n".join(str(e) for e in self.validation_result.get_errors())
            raise ParseError(f"Validation failed:\n{errors}")

        return format_obj

    def _detect_format(self, data: Dict[str, Any]) -> FormatType:
        """Detect format type from data.

        MK1: Has keys matching 0xNNN pattern with N in ranges
        MK2: Has keys matching 0xibb pattern or has id_names/base_address
        """
        # Check for MK2-specific keys
        if 'id_names' in data or 'base_address' in data:
            return FormatType.MK2

        # Check event keys
        event_keys = [k for k in data.keys() 
                      if k not in ['sources', 'id_names', 'base_address']]

        if not event_keys:
            raise ParseError("No event definitions found")

        # Try to detect based on key patterns
        mk1_pattern_count = 0
        mk2_pattern_count = 0

        for key in event_keys[:10]:  # Sample first 10 keys
            # Try to normalize as each format
            try:
                # Try MK1 normalization
                normalized = self._normalize_key_for_detection(key)
                if self._looks_like_mk1(normalized):
                    mk1_pattern_count += 1
                if self._looks_like_mk2(normalized):
                    mk2_pattern_count += 1
            except:
                continue

        # Decide based on pattern matches
        if mk1_pattern_count > mk2_pattern_count:
            return FormatType.MK1
        elif mk2_pattern_count > 0:
            return FormatType.MK2
        else:
            # Default to MK1 for backward compatibility
            return FormatType.MK1

    def _normalize_key_for_detection(self, key: Union[str, int]) -> str:
        """Normalize key for format detection."""
        if isinstance(key, int):
            return f"0x{key:03x}"

        key_str = str(key).lower().strip()
        if not key_str.startswith('0x'):
            try:
                # Try to parse as hex
                value = int(key_str, 16)
                return f"0x{value:03x}"
            except ValueError:
                return key_str
        return key_str

    def _looks_like_mk1(self, key: str) -> bool:
        """Check if key looks like MK1 format."""
        try:
            if not key.startswith('0x'):
                return False
            value = int(key[2:], 16)
            # Check MK1 ranges
            return ((0x000 <= value <= 0x07F) or
                    (0x200 <= value <= 0x27F) or
                    (0x400 <= value <= 0x47F))
        except:
            return False

    def _looks_like_mk2(self, key: str) -> bool:
        """Check if key looks like MK2 format."""
        try:
            if not key.startswith('0x'):
                return False
            value = int(key[2:], 16)
            # MK2: 0xibb where i is 0-F and bb is 00-1B
            id_part = (value >> 8) & 0xF
            bit_part = value & 0xFF
            return id_part <= 0xF and bit_part <= 0x1B
        except:
            return False

    def _parse_mk1(self, data: Dict[str, Any], source: str,
                   strategy: 'EventFormatStrategy') -> Mk1Format:
        """Parse MK1 format data."""
        format_obj = Mk1Format()

        # Parse sources if present
        if 'sources' in data:
            format_obj.sources = self._parse_sources(data['sources'], source)

        # Parse events
        seen_keys = set()

        for key, value in data.items():
            if key in ['sources']:  # Skip non-event keys
                continue

            if not isinstance(value, dict):
                self.validation_result.add_error(
                    ValidationCode.KEY_FORMAT,
                    f"Event value must be a dictionary, got {type(value).__name__}",
                    location=f"{source}:{key}"
                )
                continue

            try:
                # Normalize key
                normalized_key = strategy.normalize_key(key)

                # Check for duplicates
                if normalized_key in seen_keys:
                    self.validation_result.add_error(
                        ValidationCode.DUPLICATE_KEY,
                        f"Duplicate key: {normalized_key} (from {key})",
                        location=f"{source}:{key}"
                    )
                    continue

                seen_keys.add(normalized_key)

                # Validate key
                is_valid, error_msg = strategy.validate_key(normalized_key)
                if not is_valid:
                    self.validation_result.add_error(
                        ValidationCode.MK1_ADDR_RANGE,
                        error_msg or f"Invalid key: {normalized_key}",
                        location=f"{source}:{key}"
                    )
                    continue

                # Create event info
                info = EventInfo(
                    source=value.get('event_source', ''),
                    description=value.get('description', ''),
                    info=value.get('info', '')
                )

                # Add event
                format_obj.add_event(normalized_key, info)

            except Exception as e:
                self.validation_result.add_error(
                    ValidationCode.KEY_FORMAT,
                    f"Failed to parse event: {e}",
                    location=f"{source}:{key}"
                )

        return format_obj

    def _parse_mk2(self, data: Dict[str, Any], source: str,
                   strategy: 'EventFormatStrategy') -> Mk2Format:
        """Parse MK2 format data."""
        # Parse optional fields
        id_names = None
        base_address = None

        if 'id_names' in data:
            id_names = self._parse_id_names(data['id_names'], source)

        if 'base_address' in data:
            base_address = self._parse_base_address(data['base_address'], source)

        format_obj = Mk2Format(id_names=id_names, base_address=base_address)

        # Parse sources if present
        if 'sources' in data:
            format_obj.sources = self._parse_sources(data['sources'], source)

        # Parse events (similar to MK1)
        seen_keys = set()

        for key, value in data.items():
            if key in ['sources', 'id_names', 'base_address']:
                continue

            if not isinstance(value, dict):
                self.validation_result.add_error(
                    ValidationCode.KEY_FORMAT,
                    f"Event value must be a dictionary, got {type(value).__name__}",
                    location=f"{source}:{key}"
                )
                continue

            try:
                # Normalize key
                normalized_key = strategy.normalize_key(key)

                # Check for duplicates
                if normalized_key in seen_keys:
                    self.validation_result.add_error(
                        ValidationCode.DUPLICATE_KEY,
                        f"Duplicate key: {normalized_key} (from {key})",
                        location=f"{source}:{key}"
                    )
                    continue

                seen_keys.add(normalized_key)

                # Validate key
                is_valid, error_msg = strategy.validate_key(normalized_key)
                if not is_valid:
                    self.validation_result.add_error(
                        ValidationCode.MK2_ADDR_RANGE,
                        error_msg or f"Invalid key: {normalized_key}",
                        location=f"{source}:{key}"
                    )
                    continue

                # Create event info
                info = EventInfo(
                    source=value.get('event_source', ''),
                    description=value.get('description', ''),
                    info=value.get('info', '')
                )

                # Add event
                format_obj.add_event(normalized_key, info)

            except Exception as e:
                self.validation_result.add_error(
                    ValidationCode.KEY_FORMAT,
                    f"Failed to parse event: {e}",
                    location=f"{source}:{key}"
                )

        return format_obj

    def _parse_sources(self, sources_data: Any, source: str) -> list[EventSource]:
        """Parse sources list."""
        if not isinstance(sources_data, list):
            self.validation_result.add_error(
                ValidationCode.KEY_FORMAT,
                "Sources must be a list",
                location=f"{source}:sources"
            )
            return []

        sources = []
        for i, item in enumerate(sources_data):
            if not isinstance(item, dict):
                self.validation_result.add_warning(
                    ValidationCode.KEY_FORMAT,
                    f"Source item {i} is not a dictionary",
                    location=f"{source}:sources[{i}]"
                )
                continue

            try:
                source_obj = EventSource(
                    source_id=item.get('source_id', ''),
                    name=item.get('name', '')
                )
                sources.append(source_obj)
            except ValidationError as e:
                self.validation_result.add_warning(
                    ValidationCode.KEY_FORMAT,
                    f"Invalid source: {e}",
                    location=f"{source}:sources[{i}]"
                )

        return sources

    def _parse_id_names(self, id_names_data: Any, source: str) -> Dict[int, str]:
        """Parse id_names dictionary."""
        if not isinstance(id_names_data, dict):
            self.validation_result.add_error(
                ValidationCode.KEY_FORMAT,
                "id_names must be a dictionary",
                location=f"{source}:id_names"
            )
            return {}

        id_names = {}
        for key, value in id_names_data.items():
            try:
                # Parse ID
                if isinstance(key, int):
                    id_num = key
                else:
                    id_num = int(str(key), 16) if str(key).startswith('0x') else int(key)

                # Validate ID
                if not 0 <= id_num <= 15:
                    self.validation_result.add_error(
                        ValidationCode.MK2_ADDR_RANGE,
                        f"Invalid ID {id_num} in id_names (must be 0-15)",
                        location=f"{source}:id_names:{key}"
                    )
                    continue

                id_names[id_num] = str(value)

            except (ValueError, TypeError) as e:
                self.validation_result.add_error(
                    ValidationCode.KEY_FORMAT,
                    f"Invalid id_names entry: {e}",
                    location=f"{source}:id_names:{key}"
                )

        return id_names

    def _parse_base_address(self, base_data: Any, source: str) -> Optional[int]:
        """Parse base address."""
        try:
            if isinstance(base_data, int):
                base_address = base_data
            else:
                base_str = str(base_data).strip()
                if base_str.startswith('0x'):
                    base_address = int(base_str, 16)
                else:
                    base_address = int(base_str)

            # Validate range
            if not 0 <= base_address <= 0xFFFFFFFF:
                self.validation_result.add_error(
                    ValidationCode.INVALID_BASE_ADDRESS,
                    f"Base address {base_address:#x} exceeds 32-bit range",
                    location=f"{source}:base_address"
                )
                return None

            return base_address

        except (ValueError, TypeError) as e:
            self.validation_result.add_error(
                ValidationCode.KEY_FORMAT,
                f"Invalid base_address: {e}",
                location=f"{source}:base_address"
            )
            return None

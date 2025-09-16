"""YAML parser for mk1 and mk2 event formats.

This module provides functionality to parse YAML files containing event
definitions in either mk1 or mk2 format, with automatic format detection
and comprehensive validation.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from enum import Enum

import yaml
from pydantic import ValidationError

from event_selector.core.models import (
    FormatType,
    EventSource,
    EventMk1,
    EventMk2,
    Mk1Format,
    Mk2Format,
    ValidationResult,
    ValidationCode,
    ValidationLevel,
    normalize_mk1_address,
    normalize_mk2_key,
)


class ParseError(Exception):
    """Base exception for parsing errors."""
    pass


class FormatDetectionError(ParseError):
    """Exception raised when format cannot be detected."""
    pass


class YAMLLoadError(ParseError):
    """Exception raised when YAML cannot be loaded."""
    pass


class EventParser:
    """Parser for event YAML files."""

    def __init__(self, validation_result: Optional[ValidationResult] = None):
        """Initialize parser.

        Args:
            validation_result: Optional ValidationResult to collect issues
        """
        self.validation_result = validation_result or ValidationResult()
        self._reset_state()

    def _reset_state(self) -> None:
        """Reset parser state."""
        self.format_type: Optional[FormatType] = None
        self.raw_data: Optional[Dict[str, Any]] = None
        self.sources: List[EventSource] = []
        self.events: Dict[str, Union[EventMk1, EventMk2]] = {}

    def parse_file(self, filepath: Union[str, Path]) -> Union[Mk1Format, Mk2Format]:
        """Parse YAML file and return appropriate format object.

        Args:
            filepath: Path to YAML file

        Returns:
            Mk1Format or Mk2Format object

        Raises:
            YAMLLoadError: If YAML cannot be loaded
            FormatDetectionError: If format cannot be detected
            ParseError: If parsing fails
        """
        filepath = Path(filepath)

        # Check file exists
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        # Load YAML
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                raw_data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise YAMLLoadError(f"Failed to load YAML: {e}") from e
        except Exception as e:
            raise YAMLLoadError(f"Failed to read file: {e}") from e

        return self.parse_data(raw_data, str(filepath))

    def parse_data(self, data: Dict[str, Any], source: str = "unknown") -> Union[Mk1Format, Mk2Format]:
        """Parse YAML data and return appropriate format object.

        Args:
            data: Parsed YAML data
            source: Source identifier for error messages

        Returns:
            Mk1Format or Mk2Format object

        Raises:
            FormatDetectionError: If format cannot be detected
            ParseError: If parsing fails
        """
        self._reset_state()
        self.raw_data = data

        if not isinstance(data, dict):
            raise ParseError(f"Expected dictionary at root, got {type(data).__name__}")

        # Detect format
        self.format_type = self.detect_format(data)

        # Parse based on format
        if self.format_type == FormatType.MK1:
            return self._parse_mk1(data, source)
        else:
            return self._parse_mk2(data, source)

    def detect_format(self, data: Dict[str, Any]) -> FormatType:
        """Detect whether data is mk1 or mk2 format.

        Detection rules:
        1. If 'id_names' or 'base_address' present -> mk2
        2. If any key matches mk2 pattern (0xibb) -> mk2
        3. If any key matches mk1 ranges -> mk1
        4. Default to mk1 if ambiguous

        Args:
            data: Parsed YAML data

        Returns:
            Detected format type

        Raises:
            FormatDetectionError: If format cannot be determined
        """
        # Check for mk2-specific keys
        if 'id_names' in data or 'base_address' in data:
            return FormatType.MK2

        # Check event keys
        mk1_pattern = re.compile(r'^(?:0x)?[0-9a-fA-F]{1,3}$')
        mk2_pattern = re.compile(r'^(?:0x)?[0-9a-fA-F]{3}$')

        has_mk1_keys = False
        has_mk2_keys = False

        for key in data.keys():
            if key in ['sources', 'id_names', 'base_address']:
                continue

            key_str = str(key)

            # Try to interpret as mk2 key
            if mk2_pattern.match(key_str):
                try:
                    normalized = normalize_mk2_key(key)
                    # If successful, it's a valid mk2 key
                    has_mk2_keys = True
                except (ValueError, ValidationError):
                    pass

            # Try to interpret as mk1 address
            if mk1_pattern.match(key_str) or isinstance(key, int):
                try:
                    normalized = normalize_mk1_address(key)
                    # Check if in valid mk1 range
                    addr_val = int(normalized, 16)
                    if (0x000 <= addr_val <= 0x07F or
                        0x200 <= addr_val <= 0x27F or
                        0x400 <= addr_val <= 0x47F):
                        has_mk1_keys = True
                except (ValueError, ValidationError):
                    pass

        # Determine format
        if has_mk2_keys and not has_mk1_keys:
            return FormatType.MK2
        elif has_mk1_keys and not has_mk2_keys:
            return FormatType.MK1
        elif has_mk1_keys and has_mk2_keys:
            # Ambiguous - check if mk2 keys are actually valid mk1 addresses
            # Default to mk1 if ambiguous
            self.validation_result.add_issue(
                code=ValidationCode.KEY_FORMAT,
                level=ValidationLevel.WARNING,
                message="Ambiguous format detected, defaulting to mk1",
                details={"has_mk1": has_mk1_keys, "has_mk2": has_mk2_keys}
            )
            return FormatType.MK1
        else:
            # No valid event keys found
            if not any(k not in ['sources'] for k in data.keys()):
                # Only sources, no events
                return FormatType.MK1  # Default
            raise FormatDetectionError(
                "Cannot detect format: no valid mk1 addresses or mk2 keys found"
            )

    def _parse_mk1(self, data: Dict[str, Any], source: str) -> Mk1Format:
        """Parse mk1 format data.

        Args:
            data: Parsed YAML data
            source: Source identifier

        Returns:
            Mk1Format object
        """
        # Parse sources
        sources = self._parse_sources(data.get('sources', []))

        # Parse events
        events = {}
        duplicates = {}

        for key, value in data.items():
            if key in ['sources']:
                continue

            if not isinstance(value, dict):
                self.validation_result.add_issue(
                    code=ValidationCode.KEY_FORMAT,
                    level=ValidationLevel.ERROR,
                    message=f"Event value must be a dictionary, got {type(value).__name__}",
                    location=f"{source}:{key}"
                )
                continue

            try:
                # Normalize address first
                normalized_addr = normalize_mk1_address(key)

                # Check for duplicates after normalization
                if normalized_addr in duplicates:
                    self.validation_result.add_issue(
                        code=ValidationCode.DUPLICATE_KEY,
                        level=ValidationLevel.ERROR,
                        message=f"Duplicate address after normalization: {key} and {duplicates[normalized_addr]} both normalize to {normalized_addr}",
                        location=f"{source}:{key}",
                        details={"original": key, "normalized": normalized_addr, "previous": duplicates[normalized_addr]}
                    )
                    continue

                # Create event
                event = EventMk1(
                    address=normalized_addr,
                    event_source=value.get('event_source', 'unknown'),
                    description=value.get('description', ''),
                    info=value.get('info', '')
                )

                events[key] = event  # Store with original key
                duplicates[normalized_addr] = key

            except ValidationError as e:
                self.validation_result.add_issue(
                    code=ValidationCode.MK1_ADDR_RANGE,
                    level=ValidationLevel.ERROR,
                    message=f"Invalid mk1 event at {key}: {e}",
                    location=f"{source}:{key}",
                    details={"key": key, "error": str(e)}
                )
            except ValueError as e:
                self.validation_result.add_issue(
                    code=ValidationCode.KEY_FORMAT,
                    level=ValidationLevel.ERROR,
                    message=f"Invalid address format at {key}: {e}",
                    location=f"{source}:{key}",
                    details={"key": key, "error": str(e)}
                )

        # Check if we have any valid events
        if not events and self.validation_result.has_errors:
            raise ParseError(f"No valid events could be parsed from {source}")

        # Create and return Mk1Format
        try:
            return Mk1Format(sources=sources, events=events)
        except ValidationError as e:
            raise ParseError(f"Failed to create Mk1Format: {e}") from e

    def _parse_mk2(self, data: Dict[str, Any], source: str) -> Mk2Format:
        """Parse mk2 format data.

        Args:
            data: Parsed YAML data
            source: Source identifier

        Returns:
            Mk2Format object
        """
        # Parse sources
        sources = self._parse_sources(data.get('sources', []))

        # Parse id_names
        id_names = {}
        if 'id_names' in data:
            raw_id_names = data['id_names']
            if isinstance(raw_id_names, dict):
                for id_key, name in raw_id_names.items():
                    try:
                        id_num = int(id_key)
                        if 0 <= id_num <= 15:
                            id_names[id_num] = str(name)
                        else:
                            self.validation_result.add_issue(
                                code=ValidationCode.MK2_ADDR_RANGE,
                                level=ValidationLevel.ERROR,
                                message=f"Invalid ID {id_num} in id_names (must be 0-15)",
                                location=f"{source}:id_names:{id_key}"
                            )
                    except (ValueError, TypeError) as e:
                        self.validation_result.add_issue(
                            code=ValidationCode.KEY_FORMAT,
                            level=ValidationLevel.ERROR,
                            message=f"Invalid ID key in id_names: {id_key}",
                            location=f"{source}:id_names:{id_key}"
                        )

        # Parse base_address
        base_address = None
        if 'base_address' in data:
            try:
                base_val = data['base_address']
                if isinstance(base_val, str):
                    # Handle hex string
                    if base_val.startswith('0x') or base_val.startswith('0X'):
                        base_address = int(base_val, 16)
                    else:
                        base_address = int(base_val)
                else:
                    base_address = int(base_val)

                if base_address > 0xFFFFFFFF:
                    self.validation_result.add_issue(
                        code=ValidationCode.MK2_ADDR_RANGE,
                        level=ValidationLevel.ERROR,
                        message=f"Base address {base_address:#x} exceeds 32-bit range",
                        location=f"{source}:base_address"
                    )
                    base_address = None

            except (ValueError, TypeError) as e:
                self.validation_result.add_issue(
                    code=ValidationCode.KEY_FORMAT,
                    level=ValidationLevel.ERROR,
                    message=f"Invalid base_address: {data['base_address']}",
                    location=f"{source}:base_address"
                )

        # Parse events
        events = {}
        duplicates = {}
        bits_28_31_warned = False

        for key, value in data.items():
            if key in ['sources', 'id_names', 'base_address']:
                continue

            if not isinstance(value, dict):
                self.validation_result.add_issue(
                    code=ValidationCode.KEY_FORMAT,
                    level=ValidationLevel.ERROR,
                    message=f"Event value must be a dictionary, got {type(value).__name__}",
                    location=f"{source}:{key}"
                )
                continue

            try:
                # Try to normalize key
                normalized_key = normalize_mk2_key(key)

                # Check for duplicates after normalization
                if normalized_key in duplicates:
                    self.validation_result.add_issue(
                        code=ValidationCode.DUPLICATE_KEY,
                        level=ValidationLevel.ERROR,
                        message=f"Duplicate key after normalization: {key} and {duplicates[normalized_key]} both normalize to {normalized_key}",
                        location=f"{source}:{key}",
                        details={"original": key, "normalized": normalized_key, "previous": duplicates[normalized_key]}
                    )
                    continue

                # Create event
                event = EventMk2(
                    key=normalized_key,
                    event_source=value.get('event_source', 'unknown'),
                    description=value.get('description', ''),
                    info=value.get('info', '')
                )

                events[key] = event  # Store with original key
                duplicates[normalized_key] = key

            except ValidationError as e:
                # Check if it's a bit 28-31 issue
                error_str = str(e)
                if "Bit" in error_str and "exceeds maximum" in error_str:
                    if not bits_28_31_warned:
                        self.validation_result.add_issue(
                            code=ValidationCode.BITS_28_31_FORCED_ZERO,
                            level=ValidationLevel.WARNING,
                            message="mk2 bits 28-31 are invalid and will be ignored",
                            location=f"{source}"
                        )
                        bits_28_31_warned = True

                    self.validation_result.add_issue(
                        code=ValidationCode.MK2_ADDR_RANGE,
                        level=ValidationLevel.ERROR,
                        message=f"Invalid bit index in key {key}: {e}",
                        location=f"{source}:{key}",
                        details={"key": key, "error": str(e)}
                    )
                else:
                    self.validation_result.add_issue(
                        code=ValidationCode.MK2_ADDR_RANGE,
                        level=ValidationLevel.ERROR,
                        message=f"Invalid mk2 event at {key}: {e}",
                        location=f"{source}:{key}",
                        details={"key": key, "error": str(e)}
                    )
            except ValueError as e:
                self.validation_result.add_issue(
                    code=ValidationCode.KEY_FORMAT,
                    level=ValidationLevel.ERROR,
                    message=f"Invalid key format at {key}: {e}",
                    location=f"{source}:{key}",
                    details={"key": key, "error": str(e)}
                )

        # Check if we have any valid events
        if not events and self.validation_result.has_errors:
            raise ParseError(f"No valid events could be parsed from {source}")

        # Create and return Mk2Format
        try:
            return Mk2Format(
                sources=sources,
                id_names=id_names,
                base_address=base_address,
                events=events
            )
        except ValidationError as e:
            raise ParseError(f"Failed to create Mk2Format: {e}") from e

    def _parse_sources(self, sources_data: Any) -> List[EventSource]:
        """Parse sources list.

        Args:
            sources_data: Raw sources data from YAML

        Returns:
            List of EventSource objects
        """
        sources = []

        if not sources_data:
            return sources

        if not isinstance(sources_data, list):
            self.validation_result.add_issue(
                code=ValidationCode.KEY_FORMAT,
                level=ValidationLevel.WARNING,
                message=f"Sources should be a list, got {type(sources_data).__name__}",
                location="sources"
            )
            return sources

        for i, source_data in enumerate(sources_data):
            if not isinstance(source_data, dict):
                self.validation_result.add_issue(
                    code=ValidationCode.KEY_FORMAT,
                    level=ValidationLevel.WARNING,
                    message=f"Source {i} should be a dictionary",
                    location=f"sources[{i}]"
                )
                continue

            try:
                source = EventSource(
                    name=source_data.get('name', f'source_{i}'),
                    description=source_data.get('description', '')
                )
                sources.append(source)
            except ValidationError as e:
                self.validation_result.add_issue(
                    code=ValidationCode.KEY_FORMAT,
                    level=ValidationLevel.WARNING,
                    message=f"Invalid source at index {i}: {e}",
                    location=f"sources[{i}]"
                )

        return sources


def parse_yaml_file(filepath: Union[str, Path]) -> Tuple[Union[Mk1Format, Mk2Format], ValidationResult]:
    """Convenience function to parse a YAML file.

    Args:
        filepath: Path to YAML file

    Returns:
        Tuple of (parsed format object, validation result)

    Raises:
        Various parsing exceptions
    """
    parser = EventParser()
    result = parser.parse_file(filepath)
    return result, parser.validation_result


def parse_yaml_data(data: Dict[str, Any], source: str = "unknown") -> Tuple[Union[Mk1Format, Mk2Format], ValidationResult]:
    """Convenience function to parse YAML data.

    Args:
        data: Parsed YAML data
        source: Source identifier

    Returns:
        Tuple of (parsed format object, validation result)

    Raises:
        Various parsing exceptions
    """
    parser = EventParser()
    result = parser.parse_data(data, source)
    return result, parser.validation_result


def detect_format(data: Dict[str, Any]) -> FormatType:
    """Convenience function to detect format type.

    Args:
        data: Parsed YAML data

    Returns:
        Detected format type

    Raises:
        FormatDetectionError: If format cannot be detected
    """
    parser = EventParser()
    return parser.detect_format(data)
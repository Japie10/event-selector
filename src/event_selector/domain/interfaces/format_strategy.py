"""Core interfaces for format strategies."""

from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable, Optional
from dataclasses import dataclass

from event_selector.shared.types import (
    EventKey, EventID, BitPosition, EventCoordinate,
    FormatType, ValidationLevel, ValidationCode, Address
)


@runtime_checkable
class EventFormatStrategy(Protocol):
    """Protocol for event format strategies."""
    
    def get_format_type(self) -> FormatType:
        """Get the format type this strategy handles."""
        ...
    
    def normalize_key(self, key: str | int) -> EventKey:
        """Normalize an event key to standard format.
        
        Args:
            key: Raw key (string or integer)
            
        Returns:
            Normalized EventKey
            
        Raises:
            ValidationError: If key format is invalid
        """
        ...
    
    def validate_key(self, key: EventKey) -> tuple[bool, Optional[str]]:
        """Validate if a key is in valid range.
        
        Args:
            key: Normalized event key
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        ...
    
    def key_to_coordinate(self, key: EventKey) -> EventCoordinate:
        """Convert normalized key to ID and bit position.
        
        Args:
            key: Normalized event key
            
        Returns:
            EventCoordinate with ID and bit position
            
        Raises:
            ValidationError: If key is invalid
        """
        ...
    
    def coordinate_to_key(self, coord: EventCoordinate) -> EventKey:
        """Convert ID and bit position to normalized key.
        
        Args:
            coord: Event coordinate
            
        Returns:
            Normalized EventKey
            
        Raises:
            ValidationError: If coordinate is invalid
        """
        ...
    
    def get_max_ids(self) -> int:
        """Get maximum number of IDs for this format."""
        ...
    
    def get_valid_bit_range(self) -> tuple[int, int]:
        """Get valid bit range (min, max) for this format."""
        ...
    
    def get_bit_mask(self) -> int:
        """Get mask for valid bits."""
        ...


@dataclass
class ValidationIssue:
    """Represents a validation issue."""
    code: ValidationCode
    level: ValidationLevel
    message: str
    location: Optional[str] = None
    suggestion: Optional[str] = None
    
    def __str__(self) -> str:
        parts = [f"[{self.level.value}] {self.message}"]
        if self.location:
            parts.append(f" at {self.location}")
        if self.suggestion:
            parts.append(f"\n  Suggestion: {self.suggestion}")
        return "".join(parts)


class ValidationResult:
    """Container for validation results."""
    
    def __init__(self):
        self._issues: list[ValidationIssue] = []
    
    def add_issue(self, 
                  code: ValidationCode,
                  level: ValidationLevel,
                  message: str,
                  location: Optional[str] = None,
                  suggestion: Optional[str] = None) -> None:
        """Add a validation issue."""
        self._issues.append(ValidationIssue(
            code=code,
            level=level,
            message=message,
            location=location,
            suggestion=suggestion
        ))
    
    def add_error(self, code: ValidationCode, message: str, **kwargs) -> None:
        """Add an error-level issue."""
        self.add_issue(code, ValidationLevel.ERROR, message, **kwargs)
    
    def add_warning(self, code: ValidationCode, message: str, **kwargs) -> None:
        """Add a warning-level issue."""
        self.add_issue(code, ValidationLevel.WARNING, message, **kwargs)
    
    def add_info(self, code: ValidationCode, message: str, **kwargs) -> None:
        """Add an info-level issue."""
        self.add_issue(code, ValidationLevel.INFO, message, **kwargs)
    
    @property
    def is_valid(self) -> bool:
        """Check if there are no errors."""
        return not self.has_errors
    
    @property
    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return any(issue.level == ValidationLevel.ERROR for issue in self._issues)
    
    @property
    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return any(issue.level == ValidationLevel.WARNING for issue in self._issues)
    
    def get_errors(self) -> list[ValidationIssue]:
        """Get all error-level issues."""
        return [i for i in self._issues if i.level == ValidationLevel.ERROR]
    
    def get_warnings(self) -> list[ValidationIssue]:
        """Get all warning-level issues."""
        return [i for i in self._issues if i.level == ValidationLevel.WARNING]
    
    def get_all_issues(self) -> list[ValidationIssue]:
        """Get all issues."""
        return self._issues.copy()
    
    def merge(self, other: 'ValidationResult') -> None:
        """Merge another validation result into this one."""
        self._issues.extend(other._issues)

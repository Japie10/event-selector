"""Validation models for Event Selector.

This module contains models for validation results and issues.
"""

from typing import Any, Optional, Dict, List
from pydantic import Field

from .base import StrictModel
from .constants import ValidationCode, ValidationLevel


# =====================
# Validation Models
# =====================

class ValidationIssue(StrictModel):
    """Validation issue model.
    
    Represents a single validation issue (error, warning, or info).
    """
    code: ValidationCode = Field(..., description="Validation error code")
    level: ValidationLevel = Field(..., description="Severity level")
    message: str = Field(..., description="Human-readable message")
    location: Optional[str] = Field(None, description="Location in file/structure")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional details")


class ValidationResult(StrictModel):
    """Validation result containing all issues.
    
    Aggregates all validation issues and provides convenience methods
    for querying errors, warnings, and info messages.
    """
    issues: List[ValidationIssue] = Field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        """Check if there are any errors.
        
        Returns:
            True if at least one error exists
        """
        return any(issue.level == ValidationLevel.ERROR for issue in self.issues)

    @property
    def has_warnings(self) -> bool:
        """Check if there are any warnings.
        
        Returns:
            True if at least one warning exists
        """
        return any(issue.level == ValidationLevel.WARNING for issue in self.issues)

    @property
    def has_info(self) -> bool:
        """Check if there are any info messages.
        
        Returns:
            True if at least one info message exists
        """
        return any(issue.level == ValidationLevel.INFO for issue in self.issues)

    def get_errors(self) -> List[ValidationIssue]:
        """Get only error-level issues.
        
        Returns:
            List of error issues
        """
        return [i for i in self.issues if i.level == ValidationLevel.ERROR]

    def get_warnings(self) -> List[ValidationIssue]:
        """Get only warning-level issues.
        
        Returns:
            List of warning issues
        """
        return [i for i in self.issues if i.level == ValidationLevel.WARNING]
    
    def get_info(self) -> List[ValidationIssue]:
        """Get only info-level issues.
        
        Returns:
            List of info messages
        """
        return [i for i in self.issues if i.level == ValidationLevel.INFO]

    def add_issue(
        self, 
        code: ValidationCode,
        level: ValidationLevel,
        message: str,
        location: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add a validation issue.
        
        Args:
            code: Validation code
            level: Issue severity level
            message: Human-readable message
            location: Optional location in file/structure
            details: Optional additional details
        """
        issue = ValidationIssue(
            code=code,
            level=level,
            message=message,
            location=location,
            details=details
        )
        self.issues.append(issue)
    
    def clear(self) -> None:
        """Clear all issues."""
        self.issues.clear()
    
    def merge(self, other: 'ValidationResult') -> None:
        """Merge another validation result into this one.
        
        Args:
            other: ValidationResult to merge
        """
        self.issues.extend(other.issues)
    
    def get_issue_count(self) -> Dict[ValidationLevel, int]:
        """Get count of issues by level.
        
        Returns:
            Dictionary mapping levels to counts
        """
        counts = {
            ValidationLevel.ERROR: 0,
            ValidationLevel.WARNING: 0,
            ValidationLevel.INFO: 0
        }
        for issue in self.issues:
            counts[issue.level] += 1
        return counts
    
    def __bool__(self) -> bool:
        """Check if validation passed (no errors).
        
        Returns:
            True if no errors (warnings and info are OK)
        """
        return not self.has_errors
    
    def __len__(self) -> int:
        """Get total number of issues.
        
        Returns:
            Total issue count
        """
        return len(self.issues)
"""Custom exceptions for Event Selector."""

from typing import Optional

class EventSelectorError(Exception):
    """Base exception for all Event Selector errors."""
    def __init__(self, message: str, **kwargs):
        super().__init__(message)
        for key, value in kwargs.items():
            setattr(self, key, value)

class ParseError(EventSelectorError):
    """Error parsing YAML or mask files."""
    pass

class ValidationError(EventSelectorError):
    """Validation error."""
    pass

class AddressError(ValidationError):
    """Invalid address error."""
    pass

class ExportError(EventSelectorError):
    """Error exporting masks."""
    pass

class ImportError(EventSelectorError):
    """Error importing masks."""
    pass

class SessionError(EventSelectorError):
    """Session management error."""
    pass

"""Structured logging setup for Event Selector."""

import sys
import json
from pathlib import Path
from typing import Optional, Any, Dict
from datetime import datetime
from contextvars import ContextVar
import structlog
from structlog.processors import CallsiteParameter, CallsiteParameterAdder


# Context variables for structured logging
trace_id_var: ContextVar[str] = ContextVar('trace_id', default='')
operation_var: ContextVar[str] = ContextVar('operation', default='')


class JSONLinesRenderer:
    """Custom renderer for JSONL format."""
    
    def __call__(self, _, __, event_dict: Dict[str, Any]) -> str:
        """Render event as JSON line."""
        # Ensure timestamp is ISO format string
        if 'timestamp' in event_dict and not isinstance(event_dict['timestamp'], str):
            event_dict['timestamp'] = event_dict['timestamp'].isoformat()
        
        return json.dumps(event_dict, ensure_ascii=False, default=str)


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[Path] = None,
    console_output: bool = True,
    json_output: bool = True
) -> structlog.BoundLogger:
    """Setup structured logging for the application.
    
    Args:
        log_level: Log level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional log file path
        console_output: Enable console output
        json_output: Use JSON format (vs human-readable)
        
    Returns:
        Configured logger instance
    """
    # Configure processors
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        CallsiteParameterAdder(
            parameters=[
                CallsiteParameter.FILENAME,
                CallsiteParameter.LINENO,
                CallsiteParameter.FUNC_NAME,
            ]
        ),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    
    # Add renderer based on output format
    if json_output:
        processors.append(JSONLinesRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        wrapper_class=structlog.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Get logger instance
    logger = structlog.get_logger()
    logger = logger.bind(component="event_selector")
    
    # Setup file logging if requested
    if log_file:
        setup_file_logging(log_file, log_level)
    
    return logger


def setup_file_logging(
    log_file: Path,
    log_level: str = "INFO",
    max_size: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5
) -> None:
    """Setup rotating file logging.
    
    Args:
        log_file: Log file path
        log_level: Log level
        max_size: Max file size before rotation
        backup_count: Number of backup files to keep
    """
    from logging.handlers import RotatingFileHandler
    import logging
    
    # Ensure log directory exists
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Create rotating file handler
    handler = RotatingFileHandler(
        str(log_file),
        maxBytes=max_size,
        backupCount=backup_count,
        encoding='utf-8'
    )
    
    # Set formatter for JSONL
    formatter = logging.Formatter('%(message)s')
    handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, log_level.upper()))


class LogContext:
    """Context manager for adding structured logging context."""
    
    def __init__(self, **kwargs):
        """Initialize with context variables.
        
        Args:
            **kwargs: Context variables to bind
        """
        self.context = kwargs
        self.tokens = []
    
    def __enter__(self):
        """Enter context and bind variables."""
        for key, value in self.context.items():
            if key == 'trace_id':
                token = trace_id_var.set(value)
            elif key == 'operation':
                token = operation_var.set(value)
            else:
                # For other variables, bind to logger directly
                structlog.contextvars.bind_contextvars(**{key: value})
            
            if 'token' in locals():
                self.tokens.append((key, token))
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context and unbind variables."""
        # Reset context vars
        for key, token in self.tokens:
            if key == 'trace_id':
                trace_id_var.reset(token)
            elif key == 'operation':
                operation_var.reset(token)
        
        # Unbind other variables
        other_keys = [k for k in self.context.keys() 
                      if k not in ['trace_id', 'operation']]
        if other_keys:
            structlog.contextvars.unbind_contextvars(*other_keys)


def get_logger(name: Optional[str] = None) -> structlog.BoundLogger:
    """Get a logger instance.
    
    Args:
        name: Optional logger name/component
        
    Returns:
        Logger instance
    """
    logger = structlog.get_logger()
    if name:
        logger = logger.bind(component=name)
    return logger


# Problem tracking for GUI
class ProblemTracker:
    """Track problems for display in GUI Problems Dock."""
    
    def __init__(self, max_entries: int = 200):
        """Initialize problem tracker.
        
        Args:
            max_entries: Maximum number of entries to keep
        """
        self.max_entries = max_entries
        self.problems = []
        self.listeners = []
    
    def add_problem(self,
                    level: str,
                    message: str,
                    location: Optional[str] = None,
                    suggestion: Optional[str] = None) -> None:
        """Add a problem entry.
        
        Args:
            level: Problem level (ERROR, WARNING, INFO)
            message: Problem message
            location: Optional location identifier
            suggestion: Optional suggestion for fixing
        """
        problem = {
            'timestamp': datetime.now().isoformat(),
            'level': level,
            'message': message,
            'location': location,
            'suggestion': suggestion
        }
        
        self.problems.append(problem)
        
        # Limit size
        if len(self.problems) > self.max_entries:
            self.problems.pop(0)
        
        # Notify listeners
        for listener in self.listeners:
            listener(problem)
    
    def get_problems(self, level: Optional[str] = None) -> list[Dict[str, Any]]:
        """Get problems, optionally filtered by level.
        
        Args:
            level: Optional level filter
            
        Returns:
            List of problem entries
        """
        if level:
            return [p for p in self.problems if p['level'] == level]
        return self.problems.copy()
    
    def clear(self) -> None:
        """Clear all problems."""
        self.problems.clear()
    
    def add_listener(self, callback) -> None:
        """Add a listener for new problems.
        
        Args:
            callback: Function to call with new problems
        """
        self.listeners.append(callback)
    
    def remove_listener(self, callback) -> None:
        """Remove a listener.
        
        Args:
            callback: Callback to remove
        """
        if callback in self.listeners:
            self.listeners.remove(callback)


# Global problem tracker instance
problem_tracker = ProblemTracker()

"""Logging setup - UPDATED to connect to problems dock."""

from pathlib import Path
from typing import Optional
import sys

from loguru import logger
from pythonjsonlogger import jsonlogger

from event_selector.presentation.gui.widgets.problems_dock import ProblemsLogHandler


# Add custom TRACE level (below DEBUG, which is 10)
logger.level("TRACE", no=5, color="<blue>", icon="🔍")


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[Path] = None,
    console_output: bool = True,
    json_output: bool = False,
    problems_dock: Optional['ProblemsDock'] = None  # ADD THIS
) -> logger:
    """Setup application logging.
    
    Args:
        log_level: Logging level
        log_file: Optional log file path
        console_output: Whether to log to console
        json_output: Whether to use JSON formatting
        problems_dock: Optional problems dock to send ERROR/WARN to
        
    Returns:
        Configured logger instance
    """
    # Remove default handler
    logger.remove()
    
    # Add console handler if requested
    if console_output:
        logger.add(
            sys.stderr,
            level=log_level,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
        )
    
    # Add file handler if requested
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        if json_output:
            logger.add(
                log_file,
                level=log_level,
                format="{message}",
                serialize=True
            )
        else:
            logger.add(
                log_file,
                level=log_level,
                rotation="10 MB",
                retention="7 days",
                compression="zip"
            )
    
    # Add problems dock handler if provided
    if problems_dock:
        handler = ProblemsLogHandler(problems_dock)
        logger.add(
            handler,
            level="WARNING",  # Only WARN and ERROR
            format="{message}"
        )
    
    return logger

def get_logger(name: str):
    """Get a logger instance with the given name.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Logger instance
    """
    return logger.bind(name=name)

"""Logging utilities for Event Selector.

This module provides logging configuration and utilities using loguru.
"""

import sys
import json
from pathlib import Path
from typing import Optional, Dict, Any

from loguru import logger
from event_selector.utils.paths import get_log_dir


def setup_logging(level: str = "INFO", 
                  log_file: Optional[Path] = None,
                  json_format: bool = True,
                  console_output: bool = False,
                  console_level: str = "WARNING") -> None:
    """Setup logging configuration.

    Args:
        level: Log level for file output
        log_file: Optional log file path
        json_format: Use JSON format for logs
        console_output: Enable console output (for debugging)
        console_level: Console output level
    """
    # Remove default handler
    logger.remove()

    # Map string level to loguru level
    level_map = {
        "TRACE": "TRACE",
        "DEBUG": "DEBUG",
        "INFO": "INFO",
        "WARNING": "WARNING",
        "ERROR": "ERROR",
        "CRITICAL": "CRITICAL"
    }
    log_level = level_map.get(level.upper(), "INFO")
    console_log_level = level_map.get(console_level.upper(), "WARNING")

    # Add console handler if requested (for debugging)
    if console_output:
        logger.add(
            sys.stdout,  # Use stdout for debug output
            level=console_log_level,
            format="<green>{time:HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            colorize=True
        )
    else:
        # In normal mode, only show errors/warnings to stderr
        logger.add(
            sys.stderr,
            level="WARNING",
            format="<yellow>{time:HH:mm:ss}</yellow> | <level>{level: <8}</level> | <level>{message}</level>",
            colorize=True
        )

    # Add file handler
    if log_file is None:
        log_dir = get_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "event-selector.jsonl"

    if json_format:
        # JSON Lines format
        # logger.add(
        #     log_file,
        #     level=log_level,
        #     format=json_formatter,
        #     rotation="10 MB",
        #     retention=5,
        #     compression="gz"
        # )
        pass
    else:
        # Plain text format
        logger.add(
            log_file,
            level=log_level,
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
            rotation="10 MB",
            retention=5
        )

    if console_output:
        logger.info(f"Logging initialized at level {log_level} with console output at {console_log_level}")
    else:
        logger.info(f"Logging initialized at level {log_level}")

def json_formatter(record: Dict[str, Any]) -> str:
    """Format log record as JSON.

    Args:
        record: Log record dictionary

    Returns:
        JSON formatted string
    """
    log_entry = {
        "ts": record["time"].isoformat(),
        "level": record["level"].name,
        "event": f"{record['name']}:{record['function']}",
        "msg": record["message"],
        "file": record["file"].path,
        "line": record["line"]
    }

    # Add extra fields
    if record["extra"]:
        log_entry.update(record["extra"])

    # Add exception info if present
    if record["exception"]:
        log_entry["exception"] = {
            "type": record["exception"].type.__name__,
            "value": str(record["exception"].value),
            "traceback": record["exception"].traceback
        }

    return json.dumps(log_entry, ensure_ascii=False) + "\n"


def get_logger(name: str):
    """Get logger instance with context.

    Args:
        name: Logger name/context

    Returns:
        Contextualized logger
    """
    return logger.bind(name=name)


# Convenience functions
def log_debug(message: str, **kwargs):
    """Log debug message."""
    logger.debug(message, **kwargs)


def log_info(message: str, **kwargs):
    """Log info message."""
    logger.info(message, **kwargs)


def log_warning(message: str, **kwargs):
    """Log warning message."""
    logger.warning(message, **kwargs)


def log_error(message: str, **kwargs):
    """Log error message."""
    logger.error(message, **kwargs)


def log_critical(message: str, **kwargs):
    """Log critical message."""
    logger.critical(message, **kwargs)
#!/usr/bin/env python3
"""Event Selector CLI - Minimal command-line interface."""

import sys
import argparse
import logging
from pathlib import Path
from typing import Optional, NoReturn

# Try to import version from package
try:
    from event_selector import __version__
except ImportError:
    __version__ = "0.0.0+unknown"

# Import logging setup
try:
    from event_selector.utils.logging import setup_logging, get_logger
except ImportError:
    # Fallback if logging module not yet implemented
    def setup_logging(level: str = "INFO") -> logging.Logger:
        """Fallback logging setup."""
        logging.basicConfig(
            level=getattr(logging, level.upper()),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        return logging.getLogger("event_selector")

    def get_logger(name: str) -> logging.Logger:
        """Get logger instance."""
        return logging.getLogger(name)


logger = get_logger(__name__)


class EventSelectorCLI:
    """Minimal CLI for Event Selector."""

    def __init__(self):
        """Initialize CLI."""
        self.parser = self._create_parser()
        self.args = None

    def _create_parser(self) -> argparse.ArgumentParser:
        """Create argument parser.

        Returns:
            Configured argument parser
        """
        parser = argparse.ArgumentParser(
            prog="event-selector",
            description="Event Selector - Hardware/Firmware Event Mask Management Tool",
            epilog="For GUI mode, use: event-selector-gui",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            add_help=True
        )

        # Version argument
        parser.add_argument(
            "--version",
            action="version",
            version=f"%(prog)s {__version__}",
            help="show program's version number and exit"
        )

        # Debug level argument
        parser.add_argument(
            "--debug",
            metavar="LEVEL",
            type=str,
            choices=["TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            default=None,
            help="set debug/logging level (TRACE, DEBUG, INFO, WARNING, ERROR, CRITICAL)"
        )

        # Hidden argument for future YAML file support (not in minimal spec but useful)
        parser.add_argument(
            "yaml_file",
            nargs="?",
            type=str,
            help=argparse.SUPPRESS  # Hidden for now as per minimal CLI spec
        )

        return parser

    def parse_args(self, args: Optional[list[str]] = None) -> argparse.Namespace:
        """Parse command-line arguments.

        Args:
            args: Optional list of arguments (for testing)

        Returns:
            Parsed arguments
        """
        self.args = self.parser.parse_args(args)
        return self.args

    def setup_logging(self) -> None:
        """Configure logging based on debug level."""
        if self.args and self.args.debug:
            level = self.args.debug
            logger.info(f"Setting logging level to: {level}")

            # Configure root logger
            root_logger = logging.getLogger()
            root_logger.setLevel(getattr(logging, level.upper()))

            # Configure console handler
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setLevel(getattr(logging, level.upper()))

            # Create formatter
            if level == "TRACE":
                # More detailed format for TRACE level
                formatter = logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - "
                    "[%(filename)s:%(lineno)d] - %(funcName)s() - %(message)s"
                )
            elif level == "DEBUG":
                # Detailed format for DEBUG
                formatter = logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - "
                    "[%(filename)s:%(lineno)d] - %(message)s"
                )
            else:
                # Standard format for INFO and above
                formatter = logging.Formatter(
                    "%(asctime)s - %(levelname)s - %(message)s"
                )

            console_handler.setFormatter(formatter)

            # Clear existing handlers and add new one
            root_logger.handlers.clear()
            root_logger.addHandler(console_handler)

            # Log initial debug message
            logger.debug(f"Logging configured with level: {level}")

    def run(self) -> int:
        """Run the CLI application.

        Returns:
            Exit code (0 for success, non-zero for error)
        """
        try:
            # Parse arguments
            self.parse_args()

            # Setup logging if debug flag provided
            self.setup_logging()

            # Log startup
            logger.debug(f"Event Selector CLI v{__version__} starting")
            logger.debug(f"Arguments: {self.args}")

            # Since this is minimal CLI, just check if we should launch GUI
            if self.args.yaml_file:
                logger.warning(
                    "Direct YAML file handling not supported in CLI mode. "
                    "Please use GUI mode: event-selector-gui"
                )
                print(
                    "Note: The CLI interface is minimal and intended for debugging only.\n"
                    "For full functionality, please use the GUI:\n"
                    "  event-selector-gui [yaml_file]\n",
                    file=sys.stderr
                )
                return 1

            # If we get here with just debug flag, show info message
            if self.args.debug:
                logger.info(f"Event Selector CLI v{__version__}")
                logger.info("Debug logging is now active")
                logger.debug("Use event-selector-gui for the graphical interface")
                print(
                    f"Event Selector v{__version__}\n"
                    f"Debug level: {self.args.debug}\n"
                    f"For GUI mode, use: event-selector-gui"
                )
            else:
                # No arguments provided, show help
                self.parser.print_help()
                print(
                    "\nNote: This is the minimal CLI interface.\n"
                    "For full functionality, use: event-selector-gui"
                )

            return 0

        except KeyboardInterrupt:
            logger.info("Interrupted by user")
            print("\nInterrupted by user", file=sys.stderr)
            return 130  # Standard exit code for SIGINT

        except Exception as e:
            logger.exception(f"Unexpected error: {e}")
            print(f"Error: {e}", file=sys.stderr)
            return 1


def main() -> NoReturn:
    """Main entry point for CLI.

    This function never returns normally; it always calls sys.exit().
    """
    cli = EventSelectorCLI()
    exit_code = cli.run()
    sys.exit(exit_code)


def parse_args(args: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse arguments (for testing).

    Args:
        args: Optional list of arguments

    Returns:
        Parsed arguments
    """
    cli = EventSelectorCLI()
    return cli.parse_args(args)


if __name__ == "__main__":
    main()

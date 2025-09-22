#!/usr/bin/env python3
"""Event Selector CLI - Single entry point with GUI and debug support."""

import sys
import argparse
import logging
from pathlib import Path
from typing import Optional, NoReturn, List

# Try to import version from package
try:
    from event_selector import __version__
except ImportError:
    __version__ = "0.0.0+unknown"

from event_selector.utils.logging import setup_logging, get_logger

logger = get_logger(__name__)


class EventSelectorCLI:
    """CLI entry point for Event Selector."""

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
            help="set debug/logging level and start GUI with debug output"
        )

        # YAML files to open on startup
        parser.add_argument(
            "yaml_files",
            nargs="*",
            type=str,
            help="YAML files to open on startup"
        )

        return parser

    def parse_args(self, args: Optional[List[str]] = None) -> argparse.Namespace:
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
            
            # Setup logging with console output for debugging
            setup_logging(
                level=level,
                console_output=True,  # Enable console output
                console_level=level   # Set console level to debug level
            )
            
            logger.info(f"Debug mode enabled: {level}")
            logger.debug(f"Command line arguments: {self.args}")
        else:
            # Normal mode - only file logging
            setup_logging(level="INFO", console_output=False)

    def run(self) -> int:
        """Run the application.

        Returns:
            Exit code (0 for success, non-zero for error)
        """
        try:
            # Parse arguments
            self.parse_args()

            # Setup logging
            self.setup_logging()

            # Log startup
            logger.info(f"Event Selector v{__version__} starting")

            # Launch GUI
            return self._launch_gui()

        except KeyboardInterrupt:
            logger.info("Interrupted by user")
            print("\nInterrupted by user", file=sys.stderr)
            return 130  # Standard exit code for SIGINT

        except Exception as e:
            logger.exception(f"Unexpected error: {e}")
            print(f"Error: {e}", file=sys.stderr)
            return 1

    def _launch_gui(self) -> int:
        """Launch the GUI application.

        Returns:
            Exit code from GUI application
        """
        try:
            from PyQt5.QtWidgets import QApplication
            from event_selector.gui.main_window import MainWindow

            logger.info("Launching GUI")

            # Create Qt application
            app = QApplication(sys.argv)
            app.setOrganizationName("EventSelector")
            app.setApplicationName("Event Selector")
            app.setStyle("Fusion")

            # Create main window
            window = MainWindow()

            # Load any YAML files specified on command line
            if self.args.yaml_files:
                for yaml_file in self.args.yaml_files:
                    filepath = Path(yaml_file)
                    if filepath.exists() and filepath.suffix in ['.yaml', '.yml']:
                        logger.info(f"Loading file from command line: {filepath}")
                        window.load_yaml_file(str(filepath))
                    else:
                        logger.warning(f"File not found or not a YAML file: {filepath}")

            # Show window
            window.show()

            # Run event loop
            logger.info("GUI started successfully")
            return app.exec_()

        except ImportError as e:
            logger.error(f"Failed to import GUI components: {e}")
            print(
                "Error: GUI components not available. "
                "Please install PyQt5: pip install PyQt5",
                file=sys.stderr
            )
            return 1


def main() -> NoReturn:
    """Main entry point for Event Selector.

    This function never returns normally; it always calls sys.exit().
    """
    cli = EventSelectorCLI()
    exit_code = cli.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

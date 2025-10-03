"""Command-line interface for Event Selector."""

import sys
import argparse
from pathlib import Path
from typing import Optional

from event_selector.infrastructure.logging import get_logger, setup_logging

# Version will be populated by setuptools_scm
try:
    from event_selector._version import version as __version__
except ImportError:
    __version__ = "0.0.0+unknown"


logger = get_logger(__name__)


class EventSelectorCLI:
    """Command-line interface for Event Selector."""

    def __init__(self):
        """Initialize CLI."""
        self.parser = self._create_parser()

    def _create_parser(self) -> argparse.ArgumentParser:
        """Create argument parser.

        Returns:
            ArgumentParser instance
        """
        parser = argparse.ArgumentParser(
            prog="event-selector",
            description="Hardware/Firmware Event Mask Management Tool",
            epilog="For GUI mode, use: event-selector-gui [yaml_file]"
        )

        parser.add_argument(
            "--version",
            action="version",
            version=f"event-selector {__version__}"
        )

        parser.add_argument(
            "--debug",
            type=str,
            choices=["DEBUG", "INFO", "WARNING", "ERROR"],
            help="Set debug logging level"
        )

        parser.add_argument(
            "yaml_file",
            nargs="?",
            type=Path,
            help="YAML event definition file (launches GUI)"
        )

        return parser

    def parse_args(self, args: Optional[list] = None) -> argparse.Namespace:
        """Parse command-line arguments.

        Args:
            args: Arguments to parse (default: sys.argv[1:])

        Returns:
            Parsed arguments
        """
        return self.parser.parse_args(args)

    def run(self, args: Optional[list] = None) -> int:
        """Run the CLI.

        Args:
            args: Arguments to parse

        Returns:
            Exit code (0 = success, non-zero = error)
        """
        try:
            parsed_args = self.parse_args(args)

            # Setup logging
            if parsed_args.debug:
                setup_logging(level=parsed_args.debug)

            # If YAML file provided, suggest GUI
            if parsed_args.yaml_file:
                print(f"Event Selector is primarily a GUI application.")
                print(f"To open '{parsed_args.yaml_file}', use:")
                print(f"  event-selector-gui {parsed_args.yaml_file}")
                print()
                print(f"The CLI is minimal and primarily for debugging.")
                return 1

            # If no arguments, show help
            self.parser.print_help()
            return 0

        except KeyboardInterrupt:
            print("\nInterrupted by user", file=sys.stderr)
            return 130  # Standard SIGINT exit code

        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            logger.exception("Unexpected error in CLI")
            return 1


def main() -> None:
    """Main entry point for CLI."""
    cli = EventSelectorCLI()
    exit_code = cli.run()
    sys.exit(exit_code)


def parse_args(args: Optional[list] = None) -> argparse.Namespace:
    """Parse command-line arguments (convenience function).

    Args:
        args: Arguments to parse

    Returns:
        Parsed arguments
    """
    cli = EventSelectorCLI()
    return cli.parse_args(args)


if __name__ == "__main__":
    main()

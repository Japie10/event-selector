"""Main application entry point for Event Selector."""

import sys
import argparse
from pathlib import Path
from typing import Optional

from event_selector.infrastructure.logging.setup import setup_logging, LogContext
from event_selector.application.facades.event_selector_facade import EventSelectorFacade
from event_selector.shared.exceptions import EventSelectorError


def setup_argument_parser() -> argparse.ArgumentParser:
    """Setup command line argument parser.
    
    Returns:
        Configured argument parser
    """
    parser = argparse.ArgumentParser(
        prog='event-selector',
        description='Hardware/Firmware Event Mask Management Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s dev'  # Will be replaced by setuptools_scm
    )
    
    parser.add_argument(
        '--debug',
        type=str,
        choices=['TRACE', 'DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Debug level (default: INFO)'
    )
    
    parser.add_argument(
        'yaml_files',
        nargs='*',
        type=Path,
        help='YAML event definition files to load'
    )
    
    parser.add_argument(
        '--import-mask',
        type=Path,
        dest='import_mask',
        help='Import mask file'
    )
    
    parser.add_argument(
        '--import-trigger',
        type=Path,
        dest='import_trigger',
        help='Import trigger file'
    )
    
    parser.add_argument(
        '--export-mask',
        type=Path,
        dest='export_mask',
        help='Export mask file'
    )
    
    parser.add_argument(
        '--export-trigger',
        type=Path,
        dest='export_trigger',
        help='Export trigger file'
    )
    
    parser.add_argument(
        '--no-gui',
        action='store_true',
        help='Run in CLI mode without GUI'
    )
    
    parser.add_argument(
        '--validate-only',
        action='store_true',
        help='Only validate files without loading GUI'
    )
    
    return parser


def run_cli_mode(args: argparse.Namespace, facade: EventSelectorFacade) -> int:
    """Run in CLI mode without GUI.
    
    Args:
        args: Parsed command line arguments
        facade: Application facade
        
    Returns:
        Exit code (0 for success)
    """
    logger = setup_logging(log_level=args.debug, console_output=True, json_output=False)
    
    try:
        # Load YAML files
        if not args.yaml_files:
            logger.error("No YAML files specified")
            return 1
        
        for yaml_file in args.yaml_files:
            with LogContext(operation="load_project", file=str(yaml_file)):
                logger.info(f"Loading project from {yaml_file}")
                
                project, validation_result = facade.load_project(yaml_file)
                
                # Report validation results
                if validation_result.has_errors:
                    logger.error("Validation errors found:")
                    for error in validation_result.get_errors():
                        logger.error(f"  {error}")
                    if args.validate_only:
                        return 1
                
                if validation_result.has_warnings:
                    logger.warning("Validation warnings:")
                    for warning in validation_result.get_warnings():
                        logger.warning(f"  {warning}")
                
                if args.validate_only:
                    logger.info(f"Validation successful: {yaml_file}")
                    continue
                
                # Import masks if specified
                if args.import_mask:
                    logger.info(f"Importing mask from {args.import_mask}")
                    import_result = facade.import_mask(project, args.import_mask)
                    if import_result.has_errors:
                        logger.error("Import failed")
                        return 1
                
                if args.import_trigger:
                    logger.info(f"Importing trigger from {args.import_trigger}")
                    import_result = facade.import_mask(
                        project, args.import_trigger, mode=MaskMode.TRIGGER
                    )
                    if import_result.has_errors:
                        logger.error("Import failed")
                        return 1
                
                # Export masks if specified
                if args.export_mask:
                    logger.info(f"Exporting mask to {args.export_mask}")
                    facade.export_mask(project, args.export_mask, MaskMode.MASK)
                
                if args.export_trigger:
                    logger.info(f"Exporting trigger to {args.export_trigger}")
                    facade.export_mask(project, args.export_trigger, MaskMode.TRIGGER)
        
        return 0
        
    except EventSelectorError as e:
        logger.error(f"Error: {e}", exc_info=True)
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 2


def run_gui_mode(args: argparse.Namespace, facade: EventSelectorFacade) -> int:
    """Run in GUI mode.
    
    Args:
        args: Parsed command line arguments
        facade: Application facade
        
    Returns:
        Exit code (0 for success)
    """
    from PyQt5.QtWidgets import QApplication
    from event_selector.presentation.gui.main_window import MainWindow
    
    app = QApplication(sys.argv)
    app.setApplicationName("Event Selector")
    app.setOrganizationName("EventSelector")
    
    # Setup logging
    log_file = Path.home() / ".local" / "state" / "event-selector" / "log.jsonl"
    logger = setup_logging(
        log_level=args.debug,
        log_file=log_file,
        console_output=False,
        json_output=True
    )
    
    with LogContext(operation="gui_startup"):
        logger.info("Starting GUI application")
        
        # Create main window
        window = MainWindow(facade)
        
        # Load initial files if specified
        for yaml_file in args.yaml_files:
            try:
                window.load_project(yaml_file)
            except Exception as e:
                logger.error(f"Failed to load {yaml_file}: {e}")
        
        # Show window
        window.show()
        
        # Run event loop
        return app.exec_()


def main() -> int:
    """Main entry point.
    
    Returns:
        Exit code
    """
    # Parse arguments
    parser = setup_argument_parser()
    args = parser.parse_args()
    
    # Create application facade
    facade = EventSelectorFacade()
    
    # Run in appropriate mode
    if args.no_gui or args.validate_only:
        return run_cli_mode(args, facade)
    else:
        return run_gui_mode(args, facade)


if __name__ == "__main__":
    sys.exit(main())

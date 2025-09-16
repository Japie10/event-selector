"""Comprehensive unit tests for CLI app."""

import sys
import pytest
import logging
from unittest.mock import patch, MagicMock, call
from io import StringIO
import argparse

from event_selector.cli.app import (
    EventSelectorCLI,
    main,
    parse_args,
)


class TestEventSelectorCLI:
    """Test EventSelectorCLI class."""
    
    def test_cli_initialization(self):
        """Test CLI initialization."""
        cli = EventSelectorCLI()
        assert cli.parser is not None
        assert cli.args is None
        
    def test_parser_creation(self):
        """Test argument parser creation."""
        cli = EventSelectorCLI()
        parser = cli._create_parser()
        
        assert isinstance(parser, argparse.ArgumentParser)
        assert parser.prog == "event-selector"
        assert "Event Selector" in parser.description
        
    def test_parse_args_no_arguments(self):
        """Test parsing with no arguments."""
        cli = EventSelectorCLI()
        args = cli.parse_args([])
        
        assert args.debug is None
        assert args.yaml_file is None
        
    def test_parse_args_debug_levels(self):
        """Test parsing debug level arguments."""
        cli = EventSelectorCLI()
        
        # Test each valid debug level
        for level in ["TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            args = cli.parse_args(["--debug", level])
            assert args.debug == level
            
    def test_parse_args_invalid_debug_level(self):
        """Test parsing invalid debug level."""
        cli = EventSelectorCLI()
        
        with pytest.raises(SystemExit):
            with patch('sys.stderr', new=StringIO()):
                cli.parse_args(["--debug", "INVALID"])
                
    def test_parse_args_version(self):
        """Test version flag."""
        cli = EventSelectorCLI()
        
        with pytest.raises(SystemExit) as exc:
            with patch('sys.stdout', new=StringIO()) as mock_stdout:
                cli.parse_args(["--version"])
                
        assert exc.value.code == 0
        
    def test_parse_args_help(self):
        """Test help flag."""
        cli = EventSelectorCLI()
        
        with pytest.raises(SystemExit) as exc:
            with patch('sys.stdout', new=StringIO()) as mock_stdout:
                cli.parse_args(["--help"])
                
        assert exc.value.code == 0
        
    def test_setup_logging_no_debug(self):
        """Test logging setup without debug flag."""
        cli = EventSelectorCLI()
        cli.args = argparse.Namespace(debug=None)
        
        # Should not raise any errors
        cli.setup_logging()
        
    def test_setup_logging_with_debug(self):
        """Test logging setup with debug flag."""
        cli = EventSelectorCLI()
        cli.args = argparse.Namespace(debug="DEBUG")
        
        with patch('logging.getLogger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            
            cli.setup_logging()
            
            # Verify logger was configured
            mock_logger.setLevel.assert_called()
            mock_logger.handlers.clear.assert_called()
            
    def test_setup_logging_trace_level(self):
        """Test logging setup with TRACE level (detailed format)."""
        cli = EventSelectorCLI()
        cli.args = argparse.Namespace(debug="TRACE")
        
        with patch('logging.getLogger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            
            cli.setup_logging()
            
            # Should use TRACE which maps to DEBUG in standard logging
            mock_logger.setLevel.assert_called_with(logging.DEBUG)
            
    def test_run_no_arguments(self):
        """Test run with no arguments (should show help)."""
        cli = EventSelectorCLI()
        
        with patch('sys.argv', ['event-selector']):
            with patch.object(cli.parser, 'print_help') as mock_help:
                exit_code = cli.run()
                
                assert exit_code == 0
                mock_help.assert_called_once()
                
    def test_run_with_debug(self):
        """Test run with debug flag."""
        cli = EventSelectorCLI()
        
        with patch('sys.argv', ['event-selector', '--debug', 'INFO']):
            with patch('builtins.print') as mock_print:
                exit_code = cli.run()
                
                assert exit_code == 0
                # Should print debug info
                assert any("Debug level: INFO" in str(call) for call in mock_print.call_args_list)
                
    def test_run_with_yaml_file(self):
        """Test run with YAML file (should warn about CLI limitations)."""
        cli = EventSelectorCLI()
        
        with patch('sys.argv', ['event-selector', 'test.yaml']):
            with patch('builtins.print') as mock_print:
                exit_code = cli.run()
                
                assert exit_code == 1
                # Should warn about using GUI
                assert any("GUI" in str(call) for call in mock_print.call_args_list)
                
    def test_run_keyboard_interrupt(self):
        """Test handling of keyboard interrupt."""
        cli = EventSelectorCLI()
        
        with patch.object(cli, 'parse_args', side_effect=KeyboardInterrupt):
            with patch('builtins.print') as mock_print:
                exit_code = cli.run()
                
                assert exit_code == 130  # Standard SIGINT exit code
                assert any("Interrupted" in str(call) for call in mock_print.call_args_list)
                
    def test_run_unexpected_exception(self):
        """Test handling of unexpected exception."""
        cli = EventSelectorCLI()
        
        with patch.object(cli, 'parse_args', side_effect=Exception("Test error")):
            with patch('builtins.print') as mock_print:
                exit_code = cli.run()
                
                assert exit_code == 1
                assert any("Error: Test error" in str(call) for call in mock_print.call_args_list)


class TestMainFunction:
    """Test main entry point function."""
    
    def test_main_normal_exit(self):
        """Test main function normal exit."""
        with patch.object(EventSelectorCLI, 'run', return_value=0):
            with pytest.raises(SystemExit) as exc:
                main()
                
            assert exc.value.code == 0
            
    def test_main_error_exit(self):
        """Test main function error exit."""
        with patch.object(EventSelectorCLI, 'run', return_value=1):
            with pytest.raises(SystemExit) as exc:
                main()
                
            assert exc.value.code == 1


class TestParseArgsFunction:
    """Test standalone parse_args function."""
    
    def test_parse_args_function(self):
        """Test parse_args standalone function."""
        args = parse_args(["--debug", "DEBUG"])
        assert args.debug == "DEBUG"
        
    def test_parse_args_function_no_args(self):
        """Test parse_args with no arguments."""
        args = parse_args([])
        assert args.debug is None


class TestCLIIntegration:
    """Integration tests for CLI."""
    
    def test_help_output_content(self):
        """Test that help output contains expected content."""
        cli = EventSelectorCLI()
        
        with patch('sys.stdout', new=StringIO()) as mock_stdout:
            with pytest.raises(SystemExit):
                cli.parse_args(["--help"])
                
            help_text = mock_stdout.getvalue()
            assert "Event Selector" in help_text
            assert "--debug" in help_text
            assert "--version" in help_text
            assert "--help" in help_text
            assert "GUI mode" in help_text
            
    def test_version_output_format(self):
        """Test version output format."""
        cli = EventSelectorCLI()
        
        with patch('sys.stdout', new=StringIO()) as mock_stdout:
            with pytest.raises(SystemExit):
                cli.parse_args(["--version"])
                
            version_text = mock_stdout.getvalue()
            assert "event-selector" in version_text
            # Should contain version number (even if unknown)
            assert any(c.isdigit() or c == '.' for c in version_text)
            
    def test_debug_levels_integration(self):
        """Test that all debug levels work end-to-end."""
        for level in ["TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            cli = EventSelectorCLI()
            
            with patch('sys.argv', ['event-selector', '--debug', level]):
                with patch('builtins.print'):
                    exit_code = cli.run()
                    assert exit_code == 0


class TestCLIEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_multiple_debug_flags(self):
        """Test behavior with multiple debug flags (last wins)."""
        cli = EventSelectorCLI()
        
        # argparse behavior: last value wins
        args = cli.parse_args(["--debug", "INFO", "--debug", "DEBUG"])
        assert args.debug == "DEBUG"
        
    def test_empty_debug_value(self):
        """Test debug flag without value."""
        cli = EventSelectorCLI()
        
        with pytest.raises(SystemExit):
            with patch('sys.stderr', new=StringIO()):
                cli.parse_args(["--debug"])
                
    def test_case_sensitive_debug_level(self):
        """Test that debug levels are case-sensitive."""
        cli = EventSelectorCLI()
        
        # Should work with uppercase
        args = cli.parse_args(["--debug", "DEBUG"])
        assert args.debug == "DEBUG"
        
        # Should fail with lowercase
        with pytest.raises(SystemExit):
            with patch('sys.stderr', new=StringIO()):
                cli.parse_args(["--debug", "debug"])
                
    @patch('event_selector.cli.app.__version__', "1.2.3")
    def test_version_number_display(self):
        """Test that actual version number is displayed."""
        cli = EventSelectorCLI()
        
        with patch('sys.stdout', new=StringIO()) as mock_stdout:
            with pytest.raises(SystemExit):
                cli.parse_args(["--version"])
                
            version_text = mock_stdout.getvalue()
            assert "1.2.3" in version_text

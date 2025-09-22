"""Property-based tests for parser using Hypothesis."""

import pytest
from hypothesis import given, strategies as st, assume
from hypothesis.strategies import composite

from event_selector.core.parser import EventParser, normalize_mk1_address, normalize_mk2_key
from event_selector.core.models import FormatType


@composite
def mk1_address(draw):
    """Generate valid MK1 addresses."""
    ranges = [
        (0x000, 0x07F),   # Data
        (0x200, 0x27F),   # Network
        (0x400, 0x47F),   # Application
    ]
    range_start, range_end = draw(st.sampled_from(ranges))
    return draw(st.integers(min_value=range_start, max_value=range_end))


@composite
def mk2_key(draw):
    """Generate valid MK2 keys."""
    id_part = draw(st.integers(min_value=0, max_value=15))
    bit_part = draw(st.integers(min_value=0, max_value=27))
    return (id_part << 8) | bit_part


class TestParserProperties:
    """Property-based tests for parser."""
    
    @given(mk1_address())
    def test_mk1_address_normalization_preserves_value(self, address):
        """Test that MK1 address normalization preserves the value."""
        # Test as integer
        normalized = normalize_mk1_address(address)
        recovered = int(normalized, 16)
        assert recovered == address
        
        # Test as hex string
        hex_str = f"0x{address:03X}"
        normalized = normalize_mk1_address(hex_str)
        recovered = int(normalized, 16)
        assert recovered == address
    
    @given(mk2_key())
    def test_mk2_key_normalization_preserves_value(self, key):
        """Test that MK2 key normalization preserves the value."""
        normalized = normalize_mk2_key(key)
        recovered = int(normalized, 16)
        assert recovered == key
    
    @given(st.dictionaries(
        st.text(min_size=1, max_size=10),
        st.dictionaries(
            st.sampled_from(["event_source", "description", "info"]),
            st.text(min_size=1, max_size=100)
        )
    ))
    def test_parser_doesnt_crash(self, data):
        """Test that parser handles arbitrary input without crashing."""
        parser = EventParser()
        try:
            result = parser.parse_data(data)
            # If it succeeds, check basic properties
            assert result is not None
            assert isinstance(result.events, dict)
        except Exception as e:
            # Should only raise our expected exceptions
            assert any(x in str(e) for x in ["ParseError", "FormatDetectionError", "ValidationError"])
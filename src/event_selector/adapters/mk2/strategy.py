"""MK2 format strategy implementation."""

from typing import Optional

from event_selector.shared.types import (
    EventKey, EventID, BitPosition, FormatType,
    EventCoordinate, MK2_MAX_ID, MK2_MAX_BIT, MK2_BIT_MASK
)
from event_selector.shared.exceptions import ValidationError
from event_selector.domain.interfaces.format_strategy import EventFormatStrategy


class Mk2Strategy(EventFormatStrategy):
    """Strategy for MK2 format operations."""

    def get_format_type(self) -> FormatType:
        """Get the format type this strategy handles."""
        return FormatType.MK2

    def normalize_key(self, key: str | int) -> EventKey:
        """Normalize an MK2 key to 0xibb format."""
        if isinstance(key, int):
            # Format as 0xibb
            return EventKey(f"0x{key:03x}")

        key_str = str(key).lower().strip()

        # Handle various input formats
        if key_str.startswith('0x'):
            hex_part = key_str[2:]
        else:
            # Treat as hex without prefix
            hex_part = key_str

        # Parse to validate
        try:
            value = int(hex_part, 16)
        except ValueError as e:
            raise ValidationError(f"Invalid MK2 key format: {key}") from e

        # Format consistently as 0xibb
        return EventKey(f"0x{value:03x}")

    def validate_key(self, key: EventKey) -> tuple[bool, Optional[str]]:
        """Validate if an MK2 key is in valid range."""
        try:
            # Parse the normalized key
            key_str = str(key).lower()
            if key_str.startswith('0x'):
                value = int(key_str[2:], 16)
            else:
                value = int(key_str, 16)

            # Extract ID and bit
            id_val = (value >> 8) & 0xF
            bit_val = value & 0xFF

            # Validate ID (0-15)
            if id_val > MK2_MAX_ID:
                return False, f"Invalid MK2 ID {id_val} (max: {MK2_MAX_ID})"

            # Validate bit (0-27)
            if bit_val > MK2_MAX_BIT:
                return False, f"Invalid MK2 bit {bit_val} (max: {MK2_MAX_BIT}). Bits 28-31 are not valid."

            return True, None

        except Exception as e:
            return False, f"Invalid key format: {e}"

    def key_to_coordinate(self, key: EventKey) -> EventCoordinate:
        """Convert MK2 key to ID and bit position."""
        # Validate key first
        is_valid, error_msg = self.validate_key(key)
        if not is_valid:
            raise ValidationError(error_msg or f"Invalid key: {key}")

        # Parse key
        key_str = str(key).lower()
        if key_str.startswith('0x'):
            value = int(key_str[2:], 16)
        else:
            value = int(key_str, 16)

        # Extract ID and bit
        id_val = (value >> 8) & 0xF
        bit_val = value & 0xFF

        return EventCoordinate(
            id=EventID(id_val),
            bit=BitPosition(bit_val)
        )

    def coordinate_to_key(self, coord: EventCoordinate) -> EventKey:
        """Convert ID and bit position to MK2 key."""
        # Validate coordinate
        if coord.id > MK2_MAX_ID:
            raise ValidationError(f"Invalid MK2 ID: {coord.id} (max: {MK2_MAX_ID})")
        if coord.bit > MK2_MAX_BIT:
            raise ValidationError(f"Invalid MK2 bit: {coord.bit} (max: {MK2_MAX_BIT})")

        # Combine ID and bit into key format
        value = (coord.id << 8) | coord.bit

        return EventKey(f"0x{value:03x}")

    def get_max_ids(self) -> int:
        """Get maximum number of IDs for MK2."""
        return 16

    def get_valid_bit_range(self) -> tuple[int, int]:
        """Get valid bit range for MK2."""
        return (0, 27)  # Bits 28-31 are invalid

    def get_bit_mask(self) -> int:
        """Get mask for valid bits in MK2."""
        return MK2_BIT_MASK  # 0x0FFFFFFF
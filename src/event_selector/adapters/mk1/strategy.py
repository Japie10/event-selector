"""MK1 format strategy implementation."""

from typing import Optional

from event_selector.shared.types import (
    EventKey, EventID, BitPosition, FormatType,
    EventCoordinate, MK1_RANGES, ValidationCode
)
from event_selector.shared.exceptions import ValidationError, AddressError
from event_selector.domain.interfaces.format_strategy import EventFormatStrategy
from event_selector.domain.models.value_objects import EventAddress


class Mk1Strategy(EventFormatStrategy):
    """Strategy for MK1 format operations."""

    def get_format_type(self) -> FormatType:
        """Get the format type this strategy handles."""
        return FormatType.MK1

    def normalize_key(self, key: str | int) -> EventKey:
        """Normalize an MK1 key to 0xNNN format."""
        try:
            if isinstance(key, str):
                key_str = key.lower().strip()
                # Remove 0x prefix if present
                if key_str.startswith('0x'):
                    addr_value = int(key_str, 16)
                else:
                    # Try as hex without prefix
                    addr_value = int(key_str, 16)
            else:
                addr_value = int(key)

            # Format as 0xNNN (3 hex digits)
            return EventKey(f"0x{addr_value:03x}")

        except (ValueError, TypeError) as e:
            raise ValidationError(f"Invalid MK1 key format: {key}") from e

    def validate_key(self, key: EventKey) -> tuple[bool, Optional[str]]:
        """Validate if an MK1 key is in valid range."""
        try:
            # Parse the normalized key
            addr_str = str(key).lower()
            if addr_str.startswith('0x'):
                addr_value = int(addr_str, 16)
            else:
                addr_value = int(addr_str, 16)

            # Check if in any valid range
            for range_name, addr_range in MK1_RANGES.items():
                if addr_range.contains(addr_value):
                    return True, None

            # Not in any valid range
            return False, (
                f"Address {key} not in valid MK1 ranges. "
                f"Valid: Data(0x000-0x07F), Network(0x200-0x27F), "
                f"Application(0x400-0x47F)"
            )

        except Exception as e:
            return False, f"Invalid key format: {e}"

    def key_to_coordinate(self, key: EventKey) -> EventCoordinate:
        """Convert MK1 key to ID and bit position."""
        # Validate key first
        is_valid, error_msg = self.validate_key(key)
        if not is_valid:
            raise ValidationError(error_msg or f"Invalid key: {key}")

        # Parse address
        addr_str = str(key).lower()
        if addr_str.startswith('0x'):
            addr_value = int(addr_str, 16)
        else:
            addr_value = int(addr_str, 16)

        # Find which range and calculate ID/bit
        for range_name, addr_range in MK1_RANGES.items():
            if addr_range.contains(addr_value):
                # Calculate base ID for this range
                base_id = {
                    "Data": 0,      # IDs 0-3
                    "Network": 4,   # IDs 4-7  
                    "Application": 8  # IDs 8-11
                }[range_name]

                # Calculate offset within range
                offset = addr_value - addr_range.start
                id_num = base_id + (offset // 32)
                bit = offset % 32

                return EventCoordinate(
                    id=EventID(id_num),
                    bit=BitPosition(bit)
                )

        # Should never reach here due to validation
        raise ValidationError(f"Cannot map key {key} to coordinate")

    def coordinate_to_key(self, coord: EventCoordinate) -> EventKey:
        """Convert ID and bit position to MK1 key."""
        # Validate coordinate
        if coord.id > 11:
            raise ValidationError(f"Invalid MK1 ID: {coord.id} (max: 11)")
        if coord.bit > 31:
            raise ValidationError(f"Invalid bit: {coord.bit} (max: 31)")

        # Determine which range this ID belongs to
        if 0 <= coord.id <= 3:
            # Data range
            base_addr = 0x000
            id_offset = coord.id
        elif 4 <= coord.id <= 7:
            # Network range
            base_addr = 0x200
            id_offset = coord.id - 4
        elif 8 <= coord.id <= 11:
            # Application range
            base_addr = 0x400
            id_offset = coord.id - 8
        else:
            raise ValidationError(f"Invalid MK1 ID: {coord.id}")

        # Calculate address
        address = base_addr + (id_offset * 32) + coord.bit

        return EventKey(f"0x{address:03x}")

    def get_max_ids(self) -> int:
        """Get maximum number of IDs for MK1."""
        return 12

    def get_valid_bit_range(self) -> tuple[int, int]:
        """Get valid bit range for MK1."""
        return (0, 31)  # All 32 bits are valid

    def get_bit_mask(self) -> int:
        """Get mask for valid bits in MK1."""
        return 0xFFFFFFFF  # All bits valid
"""Command pattern implementation for undo/redo."""

from abc import ABC, abstractmethod
from typing import List, Optional
from event_selector.infrastructure.logging import get_logger

logger = get_logger(__name__)


class Command(ABC):
    """Abstract base class for commands."""

    def __init__(self, description: str):
        """Initialize command.

        Args:
            description: Human-readable description
        """
        self._description = description
        self._executed = False

    @abstractmethod
    def execute(self) -> None:
        """Execute the command."""
        pass

    @abstractmethod
    def undo(self) -> None:
        """Undo the command."""
        pass

    def get_description(self) -> str:
        """Get command description.

        Returns:
            Description string
        """
        return self._description

    def is_executed(self) -> bool:
        """Check if command has been executed.

        Returns:
            True if executed
        """
        return self._executed


class MacroCommand(Command):
    """Command that groups multiple commands together."""

    def __init__(self, commands: List[Command], description: str):
        """Initialize macro command.

        Args:
            commands: List of commands to execute
            description: Description of the macro
        """
        super().__init__(description)
        self._commands = commands

    def execute(self) -> None:
        """Execute all commands in order."""
        for cmd in self._commands:
            cmd.execute()
        self._executed = True
        logger.debug(f"Executed macro: {self._description}")

    def undo(self) -> None:
        """Undo all commands in reverse order."""
        for cmd in reversed(self._commands):
            cmd.undo()
        self._executed = False
        logger.debug(f"Undone macro: {self._description}")


class CommandStack:
    """Manages undo/redo command history."""

    def __init__(self, max_size: int = 100):
        """Initialize command stack.

        Args:
            max_size: Maximum number of commands to keep
        """
        self._max_size = max_size
        self._undo_stack: List[Command] = []
        self._redo_stack: List[Command] = []

    def push(self, command: Command) -> None:
        """Execute and push a command onto the stack.

        Args:
            command: Command to execute
        """
        # Execute the command
        command.execute()

        # Add to undo stack
        self._undo_stack.append(command)

        # Clear redo stack (new action invalidates redo history)
        self._redo_stack.clear()

        # Enforce size limit
        if len(self._undo_stack) > self._max_size:
            self._undo_stack.pop(0)

        logger.debug(f"Pushed command: {command.get_description()}")

    def undo(self) -> Optional[Command]:
        """Undo the last command.

        Returns:
            The undone command, or None if nothing to undo
        """
        if not self._undo_stack:
            logger.debug("Nothing to undo")
            return None

        # Pop from undo stack
        command = self._undo_stack.pop()

        # Undo the command
        command.undo()

        # Add to redo stack
        self._redo_stack.append(command)

        logger.debug(f"Undone command: {command.get_description()}")
        return command

    def redo(self) -> Optional[Command]:
        """Redo the last undone command.

        Returns:
            The redone command, or None if nothing to redo
        """
        if not self._redo_stack:
            logger.debug("Nothing to redo")
            return None

        # Pop from redo stack
        command = self._redo_stack.pop()

        # Re-execute the command
        command.execute()

        # Add back to undo stack
        self._undo_stack.append(command)

        logger.debug(f"Redone command: {command.get_description()}")
        return command

    def can_undo(self) -> bool:
        """Check if undo is available.

        Returns:
            True if there are commands to undo
        """
        return len(self._undo_stack) > 0

    def can_redo(self) -> bool:
        """Check if redo is available.

        Returns:
            True if there are commands to redo
        """
        return len(self._redo_stack) > 0

    def clear(self) -> None:
        """Clear all command history."""
        self._undo_stack.clear()
        self._redo_stack.clear()
        logger.debug("Cleared command stack")

    def get_undo_description(self) -> Optional[str]:
        """Get description of next undo command.

        Returns:
            Description string or None
        """
        if self._undo_stack:
            return self._undo_stack[-1].get_description()
        return None

    def get_redo_description(self) -> Optional[str]:
        """Get description of next redo command.

        Returns:
            Description string or None
        """
        if self._redo_stack:
            return self._redo_stack[-1].get_description()
        return None

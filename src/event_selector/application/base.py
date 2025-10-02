"""Base command pattern implementation for undo/redo."""

from abc import ABC, abstractmethod
from typing import Optional, List, Any
from dataclasses import dataclass, field
from datetime import datetime


class Command(ABC):
    """Abstract base class for commands."""

    def __init__(self, description: str = ""):
        """Initialize command.

        Args:
            description: Human-readable description
        """
        self.description = description
        self.timestamp = datetime.now()
        self.executed = False

    @abstractmethod
    def execute(self) -> None:
        """Execute the command."""
        pass

    @abstractmethod
    def undo(self) -> None:
        """Undo the command."""
        pass

    def redo(self) -> None:
        """Redo the command (default: re-execute)."""
        self.execute()

    def get_description(self) -> str:
        """Get human-readable description."""
        return self.description or self.__class__.__name__


@dataclass
class CommandStack:
    """Stack for managing command history."""

    undo_stack: List[Command] = field(default_factory=list)
    redo_stack: List[Command] = field(default_factory=list)
    max_size: int = 100

    def push(self, command: Command) -> None:
        """Execute and add command to stack.

        Args:
            command: Command to execute
        """
        # Execute the command
        command.execute()
        command.executed = True

        # Add to undo stack
        self.undo_stack.append(command)

        # Limit stack size
        if len(self.undo_stack) > self.max_size:
            self.undo_stack.pop(0)

        # Clear redo stack when new command is executed
        self.redo_stack.clear()

    def undo(self) -> Optional[Command]:
        """Undo the last command.

        Returns:
            The undone command, or None if stack is empty
        """
        if not self.can_undo():
            return None

        command = self.undo_stack.pop()
        command.undo()
        self.redo_stack.append(command)

        return command

    def redo(self) -> Optional[Command]:
        """Redo the last undone command.

        Returns:
            The redone command, or None if stack is empty
        """
        if not self.can_redo():
            return None

        command = self.redo_stack.pop()
        command.redo()
        self.undo_stack.append(command)

        return command

    def can_undo(self) -> bool:
        """Check if undo is available."""
        return len(self.undo_stack) > 0

    def can_redo(self) -> bool:
        """Check if redo is available."""
        return len(self.redo_stack) > 0

    def clear(self) -> None:
        """Clear all command history."""
        self.undo_stack.clear()
        self.redo_stack.clear()

    def get_undo_description(self) -> Optional[str]:
        """Get description of command that would be undone."""
        if self.can_undo():
            return self.undo_stack[-1].get_description()
        return None

    def get_redo_description(self) -> Optional[str]:
        """Get description of command that would be redone."""
        if self.can_redo():
            return self.redo_stack[-1].get_description()
        return None


class MacroCommand(Command):
    """Composite command for executing multiple commands."""

    def __init__(self, commands: List[Command], description: str = ""):
        """Initialize macro command.

        Args:
            commands: List of commands to execute
            description: Human-readable description
        """
        super().__init__(description or "Macro Command")
        self.commands = commands

    def execute(self) -> None:
        """Execute all commands in order."""
        for command in self.commands:
            command.execute()

    def undo(self) -> None:
        """Undo all commands in reverse order."""
        for command in reversed(self.commands):
            command.undo()

    def get_description(self) -> str:
        """Get description including command count."""
        return f"{self.description} ({len(self.commands)} operations)"
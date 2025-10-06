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

@dataclass
class SubtabContext:
    """Context information for a command executed in a subtab."""
    project_id: str
    subtab_name: str
    subtab_index: int  # For auto-switching


class SubtabCommandStack:
    """Command stack with subtab context awareness.
    
    Manages multiple command stacks - one per subtab - and handles
    auto tab switching when undoing/redoing across subtabs.
    """
    
    def __init__(self, max_size_per_subtab: int = 100):
        """Initialize subtab command stack.
        
        Args:
            max_size_per_subtab: Maximum commands per subtab stack
        """
        self._stacks: Dict[str, CommandStack] = {}
        self._max_size = max_size_per_subtab
        self._last_subtab: Optional[str] = None
        self._tab_switch_callback: Optional[Callable[[str, int], None]] = None
    
    def set_tab_switch_callback(self, callback: Callable[[str, int], None]) -> None:
        """Set callback for when auto tab switching is needed.
        
        Args:
            callback: Function that takes (subtab_name, subtab_index) and switches tabs
        """
        self._tab_switch_callback = callback
    
    def get_stack(self, subtab_name: str) -> CommandStack:
        """Get or create command stack for a subtab.
        
        Args:
            subtab_name: Name of the subtab
            
        Returns:
            CommandStack for this subtab
        """
        if subtab_name not in self._stacks:
            self._stacks[subtab_name] = CommandStack(max_size=self._max_size)
        return self._stacks[subtab_name]
    
    def push(self, command: Command, context: SubtabContext) -> None:
        """Push a command to the appropriate subtab stack.
        
        Args:
            command: Command to push
            context: Subtab context information
        """
        # Tag the command with context
        if not hasattr(command, '_subtab_context'):
            command._subtab_context = context
        
        stack = self.get_stack(context.subtab_name)
        stack.push(command)
        self._last_subtab = context.subtab_name
    
    def undo(self, current_subtab: str, context: SubtabContext) -> Optional[Command]:
        """Undo the last command in the current subtab.
        
        If the last command was in a different subtab, auto-switch to that subtab.
        
        Args:
            current_subtab: Name of currently active subtab
            context: Current subtab context (for tab switching)
            
        Returns:
            The command that was undone, or None if nothing to undo
        """
        # Get the stack for the current subtab
        stack = self.get_stack(current_subtab)
        
        # Check if there's anything to undo in this subtab
        if not stack.can_undo():
            # Try to find the last subtab with undo-able commands
            for subtab_name in reversed(list(self._stacks.keys())):
                if self._stacks[subtab_name].can_undo():
                    # Auto-switch to this subtab
                    if self._tab_switch_callback and subtab_name != current_subtab:
                        # Get the context from the command at top of stack
                        cmd_to_undo = self._stacks[subtab_name]._undo_stack[-1]
                        if hasattr(cmd_to_undo, '_subtab_context'):
                            cmd_context = cmd_to_undo._subtab_context
                            self._tab_switch_callback(subtab_name, cmd_context.subtab_index)
                    
                    # Now undo in that subtab
                    self._last_subtab = subtab_name
                    return self._stacks[subtab_name].undo()
            
            # No commands to undo anywhere
            return None
        
        # Undo in current subtab
        command = stack.undo()
        self._last_subtab = current_subtab
        return command
    
    def redo(self, current_subtab: str, context: SubtabContext) -> Optional[Command]:
        """Redo the last undone command in the current subtab.
        
        Args:
            current_subtab: Name of currently active subtab
            context: Current subtab context
            
        Returns:
            The command that was redone, or None if nothing to redo
        """
        stack = self.get_stack(current_subtab)
        
        if not stack.can_redo():
            # Try to find the last subtab with redo-able commands
            for subtab_name in reversed(list(self._stacks.keys())):
                if self._stacks[subtab_name].can_redo():
                    # Auto-switch to this subtab
                    if self._tab_switch_callback and subtab_name != current_subtab:
                        cmd_to_redo = self._stacks[subtab_name]._redo_stack[-1]
                        if hasattr(cmd_to_redo, '_subtab_context'):
                            cmd_context = cmd_to_redo._subtab_context
                            self._tab_switch_callback(subtab_name, cmd_context.subtab_index)
                    
                    self._last_subtab = subtab_name
                    return self._stacks[subtab_name].redo()
            
            return None
        
        command = stack.redo()
        self._last_subtab = current_subtab
        return command
    
    def can_undo(self, subtab_name: str) -> bool:
        """Check if undo is available for a subtab.
        
        Args:
            subtab_name: Name of the subtab
            
        Returns:
            True if undo is available
        """
        if subtab_name not in self._stacks:
            return False
        return self._stacks[subtab_name].can_undo()
    
    def can_redo(self, subtab_name: str) -> bool:
        """Check if redo is available for a subtab.
        
        Args:
            subtab_name: Name of the subtab
            
        Returns:
            True if redo is available
        """
        if subtab_name not in self._stacks:
            return False
        return self._stacks[subtab_name].can_redo()
    
    def get_undo_description(self, subtab_name: str) -> Optional[str]:
        """Get description of command that would be undone.
        
        Args:
            subtab_name: Name of the subtab
            
        Returns:
            Description string or None
        """
        if not self.can_undo(subtab_name):
            return None
        
        stack = self._stacks[subtab_name]
        if stack._undo_stack:
            return stack._undo_stack[-1].get_description()
        return None
    
    def get_redo_description(self, subtab_name: str) -> Optional[str]:
        """Get description of command that would be redone.
        
        Args:
            subtab_name: Name of the subtab
            
        Returns:
            Description string or None
        """
        if not self.can_redo(subtab_name):
            return None
        
        stack = self._stacks[subtab_name]
        if stack._redo_stack:
            return stack._redo_stack[-1].get_description()
        return None
    
    def clear(self, subtab_name: Optional[str] = None) -> None:
        """Clear command history.
        
        Args:
            subtab_name: If provided, clear only this subtab. Otherwise clear all.
        """
        if subtab_name:
            if subtab_name in self._stacks:
                self._stacks[subtab_name].clear()
        else:
            for stack in self._stacks.values():
                stack.clear()
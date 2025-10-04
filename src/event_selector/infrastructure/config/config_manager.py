"""Configuration management for Event Selector."""

import json
import platform
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict, field


@dataclass
class AppConfig:
    """Application configuration."""
    # UI Settings
    accent_color: str = "#007ACC"
    row_density: str = "comfortable"  # compact | comfortable
    default_mode: str = "event"  # event | capture
    
    # Behavior Settings
    restore_on_start: bool = True
    scan_dir_on_start: bool = True
    confirm_overwrite_on_export: bool = True
    autosave_debounce_ms: int = 1000
    
    # Display Settings
    mk2_hide_28_31: bool = True
    max_problem_entries: int = 200
    
    # Logging
    log_level: str = "INFO"
    
    # Window Settings (will be stored separately in session)
    window_geometry: Optional[Dict[str, int]] = None
    dock_states: Dict[str, bool] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AppConfig':
        """Create from dictionary."""
        # Filter out None values and unknown keys
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {
            k: v for k, v in data.items() 
            if k in valid_fields and v is not None
        }
        return cls(**filtered_data)


class ConfigManager:
    """Manages application configuration."""
    
    _instance: Optional['ConfigManager'] = None
    
    def __new__(cls) -> 'ConfigManager':
        """Ensure singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize configuration manager."""
        if self._initialized:
            return
        
        self._config = AppConfig()
        self._config_file = self._get_config_path()
        self._load_config()
        self._initialized = True
    
    def _get_config_path(self) -> Path:
        """Get platform-specific config file path.
        
        Returns:
            Path to configuration file
        """
        system = platform.system()
        
        if system == "Windows":
            base = Path.home() / "AppData" / "Roaming"
            config_dir = base / "EventSelector"
        elif system == "Darwin":  # macOS
            base = Path.home() / "Library" / "Application Support"
            config_dir = base / "Event Selector"
        else:  # Linux and others
            base = Path.home() / ".config"
            config_dir = base / "event-selector"
        
        # Ensure directory exists
        config_dir.mkdir(parents=True, exist_ok=True)
        
        return config_dir / "config.json"
    
    def _load_config(self) -> None:
        """Load configuration from file."""
        if not self._config_file.exists():
            # Use defaults
            return
        
        try:
            with open(self._config_file, 'r') as f:
                data = json.load(f)
                
            # Merge with defaults
            self._config = AppConfig.from_dict(data)
            
        except (json.JSONDecodeError, IOError) as e:
            # Log error and use defaults
            print(f"Error loading config: {e}")
    
    def save_config(self) -> None:
        """Save configuration to file."""
        try:
            # Convert to dict and remove None values
            data = {k: v for k, v in self._config.to_dict().items() 
                   if v is not None}
            
            # Write atomically
            temp_file = self._config_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            # Replace original
            temp_file.replace(self._config_file)
            
        except IOError as e:
            print(f"Error saving config: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value.
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        return getattr(self._config, key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set configuration value.
        
        Args:
            key: Configuration key
            value: New value
        """
        if hasattr(self._config, key):
            setattr(self._config, key, value)
            self.save_config()
    
    def update(self, **kwargs) -> None:
        """Update multiple configuration values.
        
        Args:
            **kwargs: Key-value pairs to update
        """
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)
        self.save_config()
    
    def get_config(self) -> AppConfig:
        """Get the entire configuration object.
        
        Returns:
            Current configuration
        """
        return self._config
    
    def reset_to_defaults(self) -> None:
        """Reset configuration to defaults."""
        self._config = AppConfig()
        self.save_config()


# Global config instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """Get the global configuration manager.
    
    Returns:
        ConfigManager singleton instance
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def get_config() -> AppConfig:
    """Get the current configuration.
    
    Returns:
        Current application configuration
    """
    return get_config_manager().get_config()
"""
Settings Manager
Simple JSON-based settings with defaults
"""

import json
from pathlib import Path
from typing import Any


class Settings:
    """Application settings manager."""
    
    DEFAULTS = {
        'check_interval': 30,
        'notifications_enabled': True,
        'notification_level': 'normal',  # silent, minimal, normal, verbose
        'battery_saver': True,
        'theme': 'dark',
    }
    
    def __init__(self, data_dir: Path = None):
        """Initialize settings."""
        if data_dir is None:
            data_dir = Path("data")
        
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.file = self.data_dir / "settings.json"
        self.data = self.DEFAULTS.copy()
        
        self._load()
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get setting value."""
        return self.data.get(key, default)
    
    def set(self, key: str, value: Any):
        """Set setting value and save."""
        self.data[key] = value
        self._save()
    
    def _load(self):
        """Load from file."""
        if self.file.exists():
            try:
                with open(self.file, 'r') as f:
                    loaded = json.load(f)
                    self.data.update(loaded)
            except:
                pass
    
    def _save(self):
        """Save to file."""
        try:
            with open(self.file, 'w') as f:
                json.dump(self.data, f, indent=2)
        except:
            pass

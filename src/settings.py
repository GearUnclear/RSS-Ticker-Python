"""
User settings persistence for RSS ticker application.
Saves/loads settings to JSON file alongside article_memory.json.
"""
import json
from pathlib import Path
from typing import List, Optional

try:
    from .logger import logger
except ImportError:
    from logger import logger


class UserSettings:
    """Manages persistent user settings across sessions."""

    def __init__(self, settings_file: str = "rss_ticker_settings.json"):
        self._file = Path(settings_file)
        self._data = {
            'speed_multiplier': 1.0,
            'enabled_categories': None,  # None means "all"
            'show_descriptions': False
        }
        self._load()

    def _load(self):
        if not self._file.exists():
            return
        try:
            with open(self._file, 'r') as f:
                stored = json.load(f)
            if isinstance(stored, dict):
                for key in self._data:
                    if key in stored:
                        self._data[key] = stored[key]
            logger.debug(f"Loaded settings from {self._file}")
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load settings: {e}")

    def _save(self):
        try:
            with open(self._file, 'w') as f:
                json.dump(self._data, f, indent=2)
            logger.debug(f"Saved settings to {self._file}")
        except IOError as e:
            logger.error(f"Failed to save settings: {e}")

    @property
    def speed_multiplier(self) -> float:
        return self._data['speed_multiplier']

    @speed_multiplier.setter
    def speed_multiplier(self, value: float):
        self._data['speed_multiplier'] = value
        self._save()

    @property
    def enabled_categories(self) -> Optional[List[str]]:
        return self._data['enabled_categories']

    @enabled_categories.setter
    def enabled_categories(self, value: Optional[List[str]]):
        self._data['enabled_categories'] = value
        self._save()

    @property
    def show_descriptions(self) -> bool:
        return self._data['show_descriptions']

    @show_descriptions.setter
    def show_descriptions(self, value: bool):
        self._data['show_descriptions'] = value
        self._save()

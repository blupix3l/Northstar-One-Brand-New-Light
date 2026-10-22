"""
Fernway — Atmosphere & Customization Manager for NorthStar
==========================================================
Centralized framework for visual personalization, motion, and performance
scaling. Designed to be lightweight, modular, and atmospheric.
"""

import os
import json
import time
from typing import Any, Dict, Optional
from PyQt6.QtCore import QObject, pyqtSignal

def _data_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "NorthStar")
    os.makedirs(d, exist_ok=True)
    return d

FERNWAY_CONFIG_FILE = os.path.join(_data_dir(), "fernway_config.json")

# Default settings following the atmospheric philosophy
DEFAULT_FERNWAY_SETTINGS = {
    # Performance Mode
    "performance_mode": "balanced",  # minimal, balanced, atmospheric

    # Background Style
    "background_style": "current",  # classic, current, static, atmospheric
    "wallpaper_mode": "static",  # static (constellations), carousel (wallpaper slideshow), video

    # Colors
    "accent_primary": "#4fc3f7",
    "accent_secondary": "#9c6ff7",
    "ambient_tertiary": "#d18ae8",
    "background_tint": "rgba(8, 11, 20, 0.05)",

    # Visual Effects
    "glow_intensity": 0.5,           # 0.0 to 1.0
    "transparency_level": 0.88,      # 0.0 to 1.0
    "blur_strength": 20,             # px
    "shadow_softness": 12,           # px

    # Motion
    "animation_intensity": 1.0,      # 0.0 to 1.5
    "transition_speed_ms": 240,      # ms
    "autohide_delay_ms": 400,        # Delay before hiding bars
    "fade_animations_enabled": True, # Toggle fade effects
    "hover_animations_enabled": True,

    # Layout / UI
    "tab_style": "default",          # default, compact, glass
    "sidebar_style": "default",      # default, floating, minimal
    "sidebar_auto_hide": True,       # Toggle auto-hide for sidebar
    "toolbar_mode": "address",       # address, bookmarks
    "leo_appearance": "glass",       # glass, solid, minimal
    "window_button_style": "native", # native, custom
    "browser_font": "Segoe UI",      # Browser UI font

    # OLED Mode
    "oled_mode": False,              # True-black surfaces + refined gold accents
}

# Presets for performance modes
PERFORMANCE_PRESETS = {
    "minimal": {
        "glow_intensity": 0.0,
        "transparency_level": 1.0,
        "blur_strength": 0,
        "animation_intensity": 0.0,
        "transition_speed_ms": 0,
        "hover_animations_enabled": False,
        "shadow_softness": 0,
    },
    "balanced": {
        "glow_intensity": 0.4,
        "transparency_level": 0.92,
        "blur_strength": 15,
        "animation_intensity": 1.0,
        "transition_speed_ms": 240,
        "hover_animations_enabled": True,
        "shadow_softness": 10,
    },
    "atmospheric": {
        "glow_intensity": 0.8,
        "transparency_level": 0.85,
        "blur_strength": 30,
        "animation_intensity": 1.2,
        "transition_speed_ms": 320,
        "hover_animations_enabled": True,
        "shadow_softness": 20,
    }
}

class FernwayManager(QObject):
    """
    Central manager for NorthStar's visual atmosphere and customization.
    Handles persistence, retrieval, and live notification of setting changes.
    """
    # Signal emitted when any setting changes: (key, value)
    setting_changed = pyqtSignal(str, object)
    # Signal emitted when a performance mode preset is applied: (mode_name)
    mode_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._settings: Dict[str, Any] = {}
        self._cache: Dict[str, Any] = {}
        self.load()

    def load(self):
        """Load settings from disk, falling back to defaults if missing."""
        try:
            if os.path.exists(FERNWAY_CONFIG_FILE):
                with open(FERNWAY_CONFIG_FILE, "r") as f:
                    loaded = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    self._settings = {**DEFAULT_FERNWAY_SETTINGS, **loaded}
                    # Upgrade the previous built-in palette without replacing
                    # colors the user has explicitly customized.
                    previous_defaults = {
                        "accent_primary": "#818cf8",
                        "accent_secondary": "#34d399",
                    }
                    for key, previous_value in previous_defaults.items():
                        if self._settings.get(key) == previous_value:
                            self._settings[key] = DEFAULT_FERNWAY_SETTINGS[key]
            else:
                self._settings = dict(DEFAULT_FERNWAY_SETTINGS)
        except Exception as e:
            print(f"[FERNWAY:ERR] Failed to load config: {e}")
            self._settings = dict(DEFAULT_FERNWAY_SETTINGS)
        
        # Initialize cache
        self._cache = dict(self._settings)

    def save(self):
        """Persist current settings to disk."""
        try:
            with open(FERNWAY_CONFIG_FILE, "w") as f:
                json.dump(self._settings, f, indent=4)
        except Exception as e:
            print(f"[FERNWAY:ERR] Failed to save config: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieve a customization setting. 
        Uses internal cache for near-zero overhead.
        """
        return self._cache.get(key, self._settings.get(key, default))

    def set(self, key: str, value: Any, save_immediately: bool = True):
        """
        Update a setting and notify subscribers.
        """
        if self._settings.get(key) == value:
            return

        self._settings[key] = value
        self._cache[key] = value
        
        if save_immediately:
            self.save()
            
        self.setting_changed.emit(key, value)

    def set_performance_mode(self, mode: str):
        """
        Apply a performance preset.
        Updates multiple settings at once while maintaining the overall identity.
        """
        mode = mode.lower()
        if mode not in PERFORMANCE_PRESETS:
            return

        self._settings["performance_mode"] = mode
        preset = PERFORMANCE_PRESETS[mode]
        
        changed_keys = []
        
        # Batch update settings from preset
        for key, value in preset.items():
            if self._settings.get(key) != value:
                self._settings[key] = value
                self._cache[key] = value
                changed_keys.append(key)
        
        self.save()
        
        # Emit setting_changed only for keys that actually changed
        for key in changed_keys:
            self.setting_changed.emit(key, self._settings[key])
            
        self.mode_changed.emit(mode)

    def get_all_settings(self) -> Dict[str, Any]:
        """Return a copy of all current settings."""
        return dict(self._settings)

    def reset_to_defaults(self):
        """
        Reset all settings to their original NorthStar 0.3 defaults.
        Emits setting_changed for all updated keys.
        """
        changed_keys = []
        
        # Reset to DEFAULT_FERNWAY_SETTINGS
        for key, value in DEFAULT_FERNWAY_SETTINGS.items():
            if self._settings.get(key) != value:
                self._settings[key] = value
                self._cache[key] = value
                changed_keys.append(key)
        
        # Also reset any performance mode effects
        self._settings["performance_mode"] = "balanced"
        self.save()
        
        # Emit signals for changed keys
        for key in changed_keys:
            self.setting_changed.emit(key, self._settings[key])
            
        self.mode_changed.emit("balanced")

# Global singleton instance for easy access across the browser
_instance: Optional[FernwayManager] = None

def get_fernway() -> FernwayManager:
    global _instance
    if _instance is None:
        _instance = FernwayManager()
    return _instance

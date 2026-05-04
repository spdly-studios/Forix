# forix/utils/config.py
"""
Forix — Runtime Settings Manager
Reads/writes the persistent JSON settings file (E:/System/settings.json).
Defaults come from forix/config.py — the master config.
"""

import json
import logging
from pathlib import Path
from typing import Any

import config as C   # master config

log = logging.getLogger("forix.config")

# ── Build defaults dict from master config.py ─────────────────────────
_DEFAULTS: dict = {
    # Paths (stored as strings for JSON portability)
    "root_drive":          str(C.ROOT_DRIVE),

    # Automation
    "automation_level":     C.AUTOMATION_LEVEL,
    "auto_move_files":      C.AUTO_MOVE_FILES,
    "auto_create_projects": C.AUTO_CREATE_PROJECTS,
    "auto_merge_threshold": C.AUTO_MERGE_THRESHOLD,
    "version_debounce_secs":C.VERSION_DEBOUNCE_SECS,
    "max_versions":         C.MAX_VERSIONS_PER_PROJECT,
    "version_size_limit_mb":C.VERSION_SIZE_LIMIT_BYTES // (1024 * 1024),
    "dedup_enabled":        C.DEDUP_ENABLED,

    # Monitoring
    "watch_entire_drive":   C.WATCH_ENTIRE_DRIVE,
    "folder_open_poll_ms":  C.FOLDER_OPEN_POLL_MS,
    "health_refresh_min":   C.HEALTH_REFRESH_INTERVAL_MIN,

    # Background
    "start_with_windows":   C.START_WITH_WINDOWS,
    "minimize_to_tray":     C.MINIMIZE_TO_TRAY,
    "show_notifications":   C.SHOW_NOTIFICATIONS,
    "auto_clean_temp_days": C.AUTO_CLEAN_TEMP_DAYS,

    # Tool paths — flattened from TOOL_PATHS dict
    **{f"{k}_path": v for k, v in C.TOOL_PATHS.items()},
}


class RuntimeConfig:
    """
    Singleton settings manager.
    Merges defaults from config.py with persisted JSON overrides.
    Call get_config() to get the singleton instance.
    """

    def __init__(self):
        self._data: dict = dict(_DEFAULTS)
        self._path: Path = C.SETTINGS_FILE
        self._load()

    def _load(self):
        try:
            C.SYSTEM_DIR.mkdir(parents=True, exist_ok=True)
            if self._path.exists():
                on_disk = json.loads(self._path.read_text(encoding="utf-8"))
                # Merge — on-disk values override defaults
                self._data.update(on_disk)
        except Exception as e:
            log.warning(f"Settings load error: {e} — using defaults from config.py")

    def save(self):
        """Write all current settings to SETTINGS_FILE."""
        try:
            C.SYSTEM_DIR.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._data, indent=2, default=str),
                encoding="utf-8"
            )
        except Exception as e:
            log.error(f"Settings save error: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a setting value. Falls back to _DEFAULTS, then `default`."""
        return self._data.get(key, _DEFAULTS.get(key, default))

    def set(self, key: str, value: Any):
        """Update a setting value and persist immediately."""
        self._data[key] = value
        self.save()

    def set_many(self, updates: dict):
        """Update multiple settings at once and persist once."""
        self._data.update(updates)
        self.save()

    def reset_to_defaults(self):
        """Wipe persisted settings and go back to config.py defaults."""
        self._data = dict(_DEFAULTS)
        self.save()

    def all(self) -> dict:
        return dict(self._data)

    # ── Convenience properties ─────────────────────────────────────────

    @property
    def tool_path(self) -> dict:
        return {k: self.get(f"{k}_path", "") for k in C.TOOL_PATHS}


# ── Singleton ─────────────────────────────────────────────────────────
_instance: RuntimeConfig | None = None


def get_config() -> RuntimeConfig:
    global _instance
    if _instance is None:
        _instance = RuntimeConfig()
    return _instance
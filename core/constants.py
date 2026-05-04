# forix/core/constants.py
"""
Forix — Constants shim.
All real values live in forix/config.py (user settings) and forix/theme.py (colors).
This file re-exports everything so existing imports keep working unchanged.
"""

# ── Re-export from master config ──────────────────────────────────────
from config import (
    ROOT_DRIVE, PROJECTS_DIR, SYSTEM_DIR, BACKUPS_DIR, TEMP_DIR,
    SYSTEM_DB, LOGS_DIR, CACHE_DIR, WATCHERS_DIR, SETTINGS_FILE,
    APP_NAME, APP_VERSION,
    IGNORED_DIRS, IGNORED_EXTENSIONS,
    # Project structure — both old and new names exported
    PROJECT_SUBDIRS, PROJECT_BASE_DIRS,
    PROJECT_TYPE_SRC_DIRS,
    PROJECT_README_TEMPLATE,
    PROJECT_SRC_LAYOUT_DESCRIPTIONS,
    FILE_CATEGORY_MAP, PROJECT_SIGNATURES,
    AUTO_MERGE_THRESHOLD, VERSION_DEBOUNCE_SECS,
    MAX_VERSIONS_PER_PROJECT, VERSION_SIZE_LIMIT_BYTES,
    FOLDER_OPEN_POLL_MS,
)

# Keep old name alive for code that still references VERSION_SIZE_LIMIT
VERSION_SIZE_LIMIT = VERSION_SIZE_LIMIT_BYTES

# Keep old CONFIG_FILE name alive
CONFIG_FILE = SETTINGS_FILE

SUGGEST_MERGE_THRESHOLD = 60

# ── Re-export color dict & layout constants from theme ────────────────
from theme import (
    COLORS, WINDOW_MIN_W, WINDOW_MIN_H, SIDEBAR_WIDTH, SIDEBAR_WIDTH_MIN,
    bg_page, surface, border, accent, text_primary,
)
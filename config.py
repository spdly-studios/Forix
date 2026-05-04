"""
╔══════════════════════════════════════════════════════════════════════╗
║                    FORIX  —  MASTER CONFIGURATION                   ║
║                                                                      ║
║  Edit this file to change any Forix setting.                        ║
║  All other files read from here — never hardcode values elsewhere.  ║
╚══════════════════════════════════════════════════════════════════════╝
"""

# ══════════════════════════════════════════════════════════════════════
#  1. PATHS
# ══════════════════════════════════════════════════════════════════════
from pathlib import Path

# Root drive Forix operates on.
ROOT_DRIVE: Path = Path("E:/")

# All Forix data lives under these directories.
PROJECTS_DIR : Path = ROOT_DRIVE / "Projects"
SYSTEM_DIR   : Path = ROOT_DRIVE / "System"
BACKUPS_DIR  : Path = ROOT_DRIVE / "Backups"
TEMP_DIR     : Path = ROOT_DRIVE / "Temp"

# Internal paths — do not change.
SYSTEM_DB    : Path = SYSTEM_DIR / "system.db"
LOGS_DIR     : Path = SYSTEM_DIR / "logs"
CACHE_DIR    : Path = SYSTEM_DIR / "cache"
WATCHERS_DIR : Path = SYSTEM_DIR / "watchers"

SETTINGS_FILE: Path = SYSTEM_DIR / "settings.json"


# ══════════════════════════════════════════════════════════════════════
#  2. AUTOMATION
# ══════════════════════════════════════════════════════════════════════

# "high"   → moves/organises automatically
# "medium" → copies files, asks on ambiguous cases
# "low"    → only tracks, never moves anything
AUTOMATION_LEVEL        : str  = "high"
AUTO_MOVE_FILES         : bool = False
AUTO_CREATE_PROJECTS    : bool = True
AUTO_MERGE_THRESHOLD    : int  = 80
VERSION_DEBOUNCE_SECS   : int  = 30
MAX_VERSIONS_PER_PROJECT: int  = 50
VERSION_SIZE_LIMIT_BYTES: int  = 100 * 1024 * 1024   # 100 MB
DEDUP_ENABLED           : bool = True


# ══════════════════════════════════════════════════════════════════════
#  3. FILE MONITORING
# ══════════════════════════════════════════════════════════════════════

WATCH_ENTIRE_DRIVE        : bool = True
FOLDER_OPEN_POLL_MS       : int  = 2000
HEALTH_REFRESH_INTERVAL_MIN: int = 5


# ══════════════════════════════════════════════════════════════════════
#  4. BACKGROUND SERVICE
# ══════════════════════════════════════════════════════════════════════

START_WITH_WINDOWS  : bool = False
MINIMIZE_TO_TRAY    : bool = True
SHOW_NOTIFICATIONS  : bool = True
AUTO_CLEAN_TEMP_DAYS: int  = 0   # 0 = disabled


# ══════════════════════════════════════════════════════════════════════
#  5. IDE / TOOL PATHS
# ══════════════════════════════════════════════════════════════════════

TOOL_PATHS: dict = {
    "vscode":    "",
    "arduino":   "",
    "kicad":     "",
    "freecad":   "",
    "pycharm":   "",
    "notepadpp": "",
    "sublime":   "",
    "inkscape":  "",
    "gimp":      "",
    "excel":     "",
    "word":      "",
}


# ══════════════════════════════════════════════════════════════════════
#  6. APPLICATION
# ══════════════════════════════════════════════════════════════════════

APP_NAME   : str = "Forix"
APP_VERSION: str = "1.0.0"


# ══════════════════════════════════════════════════════════════════════
#  7. DEVELOPER / ABOUT
#     These values are used by the About page — edit them here only.
# ══════════════════════════════════════════════════════════════════════

DEV_NAME        : str = "Shivaprasad V"
DEV_TITLE       : str = "Freelancer"
DEV_EMAIL       : str = "spdly.studios@gmail.com"
DEV_LINKEDIN    : str = "https://www.linkedin.com/in/spdly/"
DEV_GITHUB      : str = "https://github.com/SpDly14"
DEV_PROFILE_IMG : str = "profile.png"

APP_TAGLINE     : str = "Intelligent Self-Organizing Project Manager"
APP_DESCRIPTION : str = (
    "Forix is a powerful desktop application designed for makers, engineers, "
    "and developers who need to manage multiple projects without discipline or "
    "manual housekeeping. It watches your drive, auto-classifies files, "
    "snapshots versions, tracks inventory, and keeps everything organised — "
    "automatically."
)
APP_LICENSE     : str = "Free for Personal Use"
APP_YEAR        : str = "2026"
APP_WEBSITE     : str = "https://spdly.xo.je"


# ══════════════════════════════════════════════════════════════════════
#  8. IGNORED PATHS
# ══════════════════════════════════════════════════════════════════════

IGNORED_DIRS: set = {
    "System Volume Information", "$RECYCLE.BIN", "node_modules",
    "__pycache__", ".git", ".svn", ".hg", "Temp", "temp",
    "System", "Backups",
}

IGNORED_EXTENSIONS: set = {".tmp", ".bak", ".swp", ".lock", "~"}


# ══════════════════════════════════════════════════════════════════════
#  9. PROJECT STRUCTURE
# ══════════════════════════════════════════════════════════════════════
#
#  Every project gets this base skeleton regardless of type:
#
#  ProjectName/
#  ├── README.md          ← auto-generated, human-readable overview
#  ├── metadata.json      ← machine-readable (managed by Forix)
#  ├── src/               ← active source files (type-specific layout inside)
#  ├── scratch/           ← dead-end attempts, WIP experiments — NEVER auto-deleted
#  ├── archive/           ← completed or abandoned sub-attempts (zipped or plain)
#  ├── notes/             ← design notes, research, decisions, links
#  ├── assets/            ← images, datasheets, reference material
#  ├── exports/           ← build outputs: gerbers, binaries, compiled PDFs, etc.
#  ├── versions/          ← auto-snapshots managed by Forix (do not edit manually)
#  └── logs/              ← per-project Forix activity log

PROJECT_BASE_DIRS: list[str] = [
    "src", "scratch", "archive", "notes",
    "assets", "exports", "versions", "logs",
]

PROJECT_SUBDIRS: list[str] = PROJECT_BASE_DIRS

PROJECT_TYPE_SRC_DIRS: dict[str, list[str]] = {
    "arduino":  ["src/firmware", "src/libraries", "src/hardware"],
    "kicad":    ["src/schematic", "src/pcb", "src/bom", "src/3d", "src/simulation"],
    "python":   ["src/pkg", "src/tests", "src/scripts", "src/docs"],
    "node":     ["src/src", "src/public", "src/tests", "src/config"],
    "web":      ["src/pages", "src/styles", "src/scripts", "src/media"],
    "cad":      ["src/models", "src/drawings", "src/renders", "src/suppliers"],
    "embedded": ["src/firmware", "src/bsp", "src/drivers", "src/hardware"],
    "document": ["src/drafts", "src/figures", "src/references", "src/templates"],
    "data":     ["src/raw", "src/processed", "src/notebooks", "src/models", "src/outputs"],
    "generic":  ["src/files"],
}

PROJECT_README_TEMPLATE: str = """\
# {name}

**Type:** {type}  |  **Category:** {category}  |  **Created:** {date}

---

## Overview

> _Add a short description of what this project does._

---

## Notes

_Use this section for anything important you want to remember about this project._

---

*This file is managed by [Forix](https://forix.app). Safe to edit — Forix will not overwrite it.*
"""

PROJECT_SRC_LAYOUT_DESCRIPTIONS: dict[str, str] = {
    "arduino":  "```\nsrc/\n├── firmware/\n├── libraries/\n└── hardware/\n```",
    "kicad":    "```\nsrc/\n├── schematic/\n├── pcb/\n├── bom/\n├── 3d/\n└── simulation/\n```",
    "python":   "```\nsrc/\n├── pkg/\n├── tests/\n├── scripts/\n└── docs/\n```",
    "node":     "```\nsrc/\n├── src/\n├── public/\n├── tests/\n└── config/\n```",
    "web":      "```\nsrc/\n├── pages/\n├── styles/\n├── scripts/\n└── media/\n```",
    "cad":      "```\nsrc/\n├── models/\n├── drawings/\n├── renders/\n└── suppliers/\n```",
    "embedded": "```\nsrc/\n├── firmware/\n├── bsp/\n├── drivers/\n└── hardware/\n```",
    "document": "```\nsrc/\n├── drafts/\n├── figures/\n├── references/\n└── templates/\n```",
    "data":     "```\nsrc/\n├── raw/\n├── processed/\n├── notebooks/\n├── models/\n└── outputs/\n```",
    "generic":  "```\nsrc/\n└── files/\n```",
}


# ══════════════════════════════════════════════════════════════════════
#  10. FILE CATEGORY → EXTENSION MAPPING
# ══════════════════════════════════════════════════════════════════════

FILE_CATEGORY_MAP: dict = {
    "code": [
        ".py", ".js", ".ts", ".cpp", ".c", ".h", ".hpp",
        ".java", ".cs", ".go", ".rs", ".rb", ".php",
        ".html", ".css", ".scss", ".vue", ".svelte",
        ".sh", ".bat", ".ps1", ".lua", ".r", ".m", ".ino",
    ],
    "hardware": [
        ".sch", ".brd", ".kicad_sch", ".kicad_pcb", ".kicad_pro",
        ".gbr", ".gerber", ".drl",
        ".stl", ".step", ".stp", ".iges", ".igs",
        ".f3d", ".FCStd", ".lbr",
    ],
    "docs": [
        ".pdf", ".docx", ".doc", ".odt", ".rtf",
        ".txt", ".md", ".rst", ".tex",
        ".xlsx", ".xls", ".ods", ".csv",
        ".pptx", ".ppt",
    ],
    "images": [
        ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff",
        ".svg", ".ico", ".webp", ".heic",
        ".psd", ".ai", ".sketch", ".fig",
    ],
    "binaries": [
        ".exe", ".dll", ".so", ".bin", ".hex", ".elf",
        ".zip", ".rar", ".7z", ".tar", ".gz", ".iso", ".img",
    ],
    "data": [
        ".json", ".xml", ".yaml", ".yml", ".toml",
        ".db", ".sqlite", ".sql",
    ],
}


# ══════════════════════════════════════════════════════════════════════
#  11. PROJECT TYPE SIGNATURES
# ══════════════════════════════════════════════════════════════════════

PROJECT_SIGNATURES: dict = {
    "arduino":  {".ino", "sketch.json"},
    "kicad":    {".kicad_pro", ".kicad_pcb", ".kicad_sch"},
    "python":   {"requirements.txt", "setup.py", "pyproject.toml", ".py"},
    "node":     {"package.json", "node_modules"},
    "web":      {"index.html", ".html", ".css"},
    "cad":      {".stl", ".step", ".stp", ".f3d", ".FCStd"},
    "embedded": {".hex", ".bin", ".elf"},
    "document": {".docx", ".pdf", ".md"},
    "data":     {".csv", ".xlsx", ".json", ".db"},
    "generic":  set(),
}
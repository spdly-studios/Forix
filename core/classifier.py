# forix/core/classifier.py
"""
Forix — Smart File & Project Classifier
Determines: file category, project type, project name inference.
"""

import logging
import os
import re
import hashlib
from pathlib import Path
from typing import Optional, Dict, Set

from core.constants import (
    FILE_CATEGORY_MAP, PROJECT_SIGNATURES, IGNORED_DIRS, IGNORED_EXTENSIONS
)

logger = logging.getLogger(__name__)


# ─── BUILD REVERSE LOOKUP: extension → category ───────────────────────────────
def _build_ext_map() -> Dict[str, str]:
    """Build a reverse lookup from file extension to category."""
    ext_map: Dict[str, str] = {}
    for cat, exts in FILE_CATEGORY_MAP.items():
        for ext in exts:
            ext_map[ext.lower()] = cat
    return ext_map


# Known extensionless filenames → category (e.g. Makefile, Dockerfile)
_BARE_NAME_TO_CAT: Dict[str, str] = {
    "makefile":     "build",
    "dockerfile":   "config",
    "vagrantfile":  "config",
    "jenkinsfile":  "config",
    "gemfile":      "config",
    "procfile":     "config",
    "rakefile":     "build",
}

_EXT_TO_CAT: Dict[str, str] = _build_ext_map()


def classify_file(path: Path) -> str:
    """
    Return the category string for a given file path.
    Falls back to bare-name lookup for extensionless files (e.g. Makefile),
    then to 'misc' if unrecognised.
    """
    ext = path.suffix.lower()
    if ext:
        return _EXT_TO_CAT.get(ext, "misc")
    # No extension — try matching by lowercased filename
    return _BARE_NAME_TO_CAT.get(path.name.lower(), "misc")


def compute_checksum(path: Path, block_size: int = 65536) -> Optional[str]:
    """
    SHA-256 hash of a file. Returns None on any I/O error.
    Logs a warning so silent failures are surfaced during debugging.
    """
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(block_size):
                h.update(chunk)
        return h.hexdigest()
    except OSError as exc:
        logger.warning("compute_checksum: could not read %s — %s", path, exc)
        return None


def _scan_folder(folder: Path) -> tuple[Set[str], Set[str]]:
    """
    Return (found_exts, found_names) for the immediate children of *folder*.
    Raises PermissionError if the directory cannot be read.
    """
    found_exts: Set[str] = set()
    found_names: Set[str] = set()
    for entry in folder.iterdir():
        if entry.is_file():
            found_exts.add(entry.suffix.lower())
            found_names.add(entry.name.lower())
    return found_exts, found_names


def detect_project_type(folder: Path) -> str:
    """
    Look at the files inside a folder and return the most likely project type.
    Checks file extensions AND known sentinel filenames.
    """
    if not folder.is_dir():
        return "generic"

    try:
        found_exts, found_names = _scan_folder(folder)
    except PermissionError:
        return "generic"

    scores: Dict[str, int] = {}
    for ptype, signatures in PROJECT_SIGNATURES.items():
        if ptype == "generic":
            continue
        score = 0
        for sig in signatures:
            if sig.startswith("."):
                if sig.lower() in found_exts:
                    score += 2
            else:
                if sig.lower() in found_names:
                    score += 3
        if score:
            scores[ptype] = score

    if not scores:
        return "generic"
    return max(scores, key=lambda k: scores[k])


# Words that are noise *only* when they are a standalone token, not substrings
_NOISE_WORDS: Set[str] = {
    "new", "copy", "backup", "old", "test", "temp", "draft", "final",
}
_VERSION_RE = re.compile(r"^v\d+(\.\d+)*$", re.IGNORECASE)
_SEPARATOR_RE = re.compile(r"[_\-\.]+")


def infer_project_name(folder: Path) -> str:
    """
    Derive a clean human-readable project name from a folder path.
    Strips common noise tokens, converts separators, title-cases the result.

    Only removes noise words that are isolated tokens, so that names like
    "financial" or "template_engine" are not mangled.
    """
    raw = folder.name

    # Split on separators first so we can filter whole tokens
    tokens = [t for t in _SEPARATOR_RE.split(raw) if t]

    # Drop blank tokens, pure noise words, and bare version strings (v1, v2.0…)
    cleaned_tokens = [
        t for t in tokens
        if t
        and t.lower() not in _NOISE_WORDS
        and not _VERSION_RE.match(t)
    ]

    if not cleaned_tokens or all(len(t) < 2 for t in cleaned_tokens):
        # Fall back to the parent folder name, or a safe default
        fallback = folder.parent.name if folder.parent.name else "Unnamed Project"
        cleaned_tokens = _SEPARATOR_RE.split(fallback) or ["Unnamed Project"]

    return " ".join(w.capitalize() for w in cleaned_tokens if w)


def infer_project_category(project_type: str) -> str:
    """Map project type to a broader category string."""
    mapping = {
        "arduino":      "Embedded",
        "kicad":        "Hardware",
        "python":       "Software",
        "node":         "Software",
        "web":          "Software",
        "cad":          "Mechanical",
        "embedded":     "Embedded",
        "document":     "Documentation",
        "data":         "Data",
        "generic":      "General",
    }
    return mapping.get(project_type, "General")


# Forix internal scaffold dir names — kept here to avoid a circular import
# with project_manager.  Must match PROJECT_BASE_DIRS in config.py.
_FORIX_INTERNAL_DIRS: frozenset = frozenset({
    "src", "scratch", "archive", "notes",
    "assets", "exports", "versions", "logs",
})


def should_ignore(path: Path) -> bool:
    """
    Return True if this path should be completely ignored by Forix.

    Ignores:
      • Parts matching IGNORED_DIRS (OS/tool noise)
      • Parts matching Forix internal scaffold dir names — prevents
        scratch/, versions/, notes/, etc. from being treated as files
        or folders that need to be classified or tracked.
      • Extensions in IGNORED_EXTENSIONS
      • Hidden files/folders (Unix dot-prefix)
    """
    ignored_dirs_lower = {d.lower() for d in IGNORED_DIRS} | _FORIX_INTERNAL_DIRS
    ignored_exts_lower = {e.lower() for e in IGNORED_EXTENSIONS}

    for part in path.parts:
        if part.lower() in ignored_dirs_lower:
            return True
    if path.suffix.lower() in ignored_exts_lower:
        return True
    if path.name.startswith("."):
        return True
    return False


def score_folder_as_project(folder: Path) -> int:
    """
    Heuristic score (0–100) of how likely a folder is a self-contained project.
    Higher = more confident it's a standalone project.

    Reuses a single directory scan to avoid redundant I/O.
    """
    if not folder.is_dir():
        return 0

    try:
        entries = list(folder.iterdir())
    except PermissionError:
        return 0

    files = [e for e in entries if e.is_file()]
    dirs  = [e for e in entries if e.is_dir()]

    score = 0

    # More files → more project-like
    score += min(len(files) * 3, 30)

    # Mixed file types → more project-like
    exts = {f.suffix.lower() for f in files if f.suffix}
    score += min(len(exts) * 4, 20)

    # Has sub-dirs → more project-like
    score += min(len(dirs) * 2, 10)

    # Known project type detected? Reuse already-scanned names/exts to avoid
    # re-iterating the directory inside detect_project_type.
    found_names = {f.name.lower() for f in files}
    found_exts  = {f.suffix.lower() for f in files if f.suffix}
    ptype = _detect_project_type_from_sets(found_exts, found_names)
    if ptype != "generic":
        score += 30

    # Has a third-party project sentinel?
    # readme.md and metadata.json are intentionally excluded: Forix writes
    # both files itself, so their presence would cause every Forix scaffold
    # dir (notes/, scratch/, etc.) to score +10 and cross the detection
    # threshold, producing hundreds of spurious "projects".
    known_meta = {
        "package.json", "pyproject.toml", "requirements.txt",
        "setup.py", "sketch.json", "cargo.toml", "go.mod",
        "makefile", "cmakelists.txt", "readme.txt",
    }
    if known_meta & found_names:
        score += 10

    return min(score, 100)


def _detect_project_type_from_sets(
    found_exts: Set[str],
    found_names: Set[str],
) -> str:
    """
    Internal helper: run project-type scoring against pre-built extension /
    filename sets so callers can avoid redundant directory scans.
    """
    scores: Dict[str, int] = {}
    for ptype, signatures in PROJECT_SIGNATURES.items():
        if ptype == "generic":
            continue
        score = 0
        for sig in signatures:
            if sig.startswith("."):
                if sig.lower() in found_exts:
                    score += 2
            else:
                if sig.lower() in found_names:
                    score += 3
        if score:
            scores[ptype] = score

    if not scores:
        return "generic"
    return max(scores, key=lambda k: scores[k])
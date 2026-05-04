# forix/services/versioning.py
"""
Forix — Semantic Versioning Service

Replaces the raw integer version_num scheme with proper semver (MAJOR.MINOR.PATCH).
The DB Version model keeps version_num (integer) for ordering — semver is derived
from a new `semver` column (VARCHAR 20) and `bump_type` column (patch/minor/major).

Semver rules (same as semver.org):
  PATCH  → backwards-compatible bug fixes, small file changes
  MINOR  → new functionality, new files, new src/ subdirectory
  MAJOR  → breaking change, complete restructure, scratch move

Auto-bump heuristics (when no explicit bump_type is given):
  • No previous version → 0.1.0
  • File count increased significantly (>20%) → minor
  • Only minor changes → patch
  • Scratch move detected (activity log) → major
"""

import datetime
import logging
import re
from pathlib import Path
from typing import Optional

from core.database import ActivityEvent, TrackedFile, Version, get_session

log = logging.getLogger("forix.versioning")

_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def parse_semver(label: str) -> tuple[int, int, int]:
    """Parse "1.2.3" → (1, 2, 3). Falls back to (0, 0, 0) on bad input."""
    if not label:
        return (0, 0, 0)
    # Strip leading 'v' if present
    label = label.lstrip("v").strip()
    m = _SEMVER_RE.match(label)
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    return (0, 0, 0)


def format_semver(major: int, minor: int, patch: int) -> str:
    return f"{major}.{minor}.{patch}"


def bump(current: str, bump_type: str) -> str:
    """
    Bump a semver string.
    bump_type: "patch" | "minor" | "major"
    """
    major, minor, patch = parse_semver(current)
    if bump_type == "major":
        return format_semver(major + 1, 0, 0)
    if bump_type == "minor":
        return format_semver(major, minor + 1, 0)
    # default: patch
    return format_semver(major, minor, patch + 1)


def _auto_detect_bump_type(project_id: int, session) -> str:
    """
    Heuristically determine the appropriate bump type by comparing with
    the previous snapshot and checking recent activity.
    """
    versions = (session.query(Version)
                .filter_by(project_id=project_id)
                .order_by(Version.version_num.desc())
                .limit(2).all())

    if not versions:
        return "minor"   # first real snapshot after 0.1.0

    prev = versions[0]

    # Check for scratch move (major bump trigger)
    since = prev.created_at or datetime.datetime(2000, 1, 1)
    scratch_ev = (session.query(ActivityEvent)
                  .filter(ActivityEvent.project_id == project_id,
                          ActivityEvent.event_type == "scratch_created",
                          ActivityEvent.created_at > since).first())
    if scratch_ev:
        return "major"

    # Compare file counts
    curr_files = (session.query(TrackedFile)
                  .filter_by(project_id=project_id, is_deleted=False).count())
    prev_files = prev.file_count or 0

    if prev_files > 0:
        delta = (curr_files - prev_files) / prev_files
        if delta > 0.20:
            return "minor"

    return "patch"


def get_current_semver(project_id: int, session=None) -> str:
    """Return the latest semver label for a project, or '0.0.0' if none."""
    s = session or get_session()
    own = session is None
    try:
        latest = (s.query(Version)
                  .filter_by(project_id=project_id)
                  .order_by(Version.version_num.desc())
                  .first())
        if not latest:
            return "0.0.0"
        # Use semver column if present, fall back to parsing label
        sv = getattr(latest, "semver", None)
        if sv:
            return sv
        # Try to parse from label (e.g. "v1.2.3" or "v3")
        label = latest.label or ""
        parsed = parse_semver(label)
        if parsed != (0, 0, 0):
            return format_semver(*parsed)
        # Fall back to "0.<version_num>.0"
        return format_semver(0, latest.version_num, 0)
    finally:
        if own:
            s.close()


def next_semver(
    project_id: int,
    bump_type: Optional[str] = None,
    session=None,
) -> tuple[str, str]:
    """
    Compute the next semver for a project.

    Args:
        project_id: project to version
        bump_type:  "patch" | "minor" | "major" | None (auto-detect)

    Returns:
        (semver_string, bump_type_used)  e.g.  ("1.2.0", "minor")
    """
    s = session or get_session()
    own = session is None
    try:
        current = get_current_semver(project_id, s)
        if current == "0.0.0":
            return "0.1.0", "minor"   # always start at 0.1.0
        resolved_type = bump_type or _auto_detect_bump_type(project_id, s)
        return bump(current, resolved_type), resolved_type
    finally:
        if own:
            s.close()


def label_for_semver(sv: str) -> str:
    """Return the display label: "v1.2.0" """
    return f"v{sv}"


def semver_changelog_summary(
    project_id: int,
    semver: str,
    bump_type: str,
    custom_note: str = "",
    session=None,
) -> str:
    """
    Build a human-readable changelog summary for a new version.
    Combines bump type, auto-stats, and optional custom note.
    """
    s = session or get_session()
    own = session is None
    try:
        fc = (s.query(TrackedFile)
              .filter_by(project_id=project_id, is_deleted=False).count())
        prev = (s.query(Version)
                .filter_by(project_id=project_id)
                .order_by(Version.version_num.desc())
                .first())
        prev_fc = prev.file_count if prev else 0
        delta   = fc - prev_fc

        bump_desc = {
            "major": "Major release — significant restructure",
            "minor": "Minor release — new functionality",
            "patch": "Patch release — small fixes and updates",
        }.get(bump_type, "Release")

        parts = [f"{bump_desc}  [{semver}]"]
        if delta > 0:  parts.append(f"+{delta} files added")
        elif delta < 0: parts.append(f"{delta} files removed")
        parts.append(f"{fc} files total")
        if custom_note:
            parts.append(custom_note.strip())
        return "  ·  ".join(parts)
    finally:
        if own:
            s.close()
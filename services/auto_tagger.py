# forix/services/auto_tagger.py
"""
Forix — Auto-Tagger
Analyses a project's folder, file types, activity, and description
to automatically suggest and apply relevant tags.

Called automatically after project creation, import, and health refresh.
Also exposed via UI for manual re-tagging.

Tag categories produced:
  Type tags:      python, arduino, kicad, web, cad, embedded, data, document
  State tags:     active, stale, no-snapshots, needs-attention
  Scale tags:     micro (<5 files), small, medium, large, huge (>500 files)
  Activity tags:  high-activity, low-activity
  Custom tags:    preserved (never auto-removed)
"""

import datetime
import logging
import re
from pathlib import Path
from typing import Optional

from core.database import (
    ActivityEvent, Project, TrackedFile, Version, get_session,
)
from core.classifier import detect_project_type

log = logging.getLogger("forix.auto_tagger")

# Tags that are auto-managed (auto-tagger can add/remove these)
AUTO_TAG_PREFIX = "auto:"
_AUTO_MANAGED = {
    # Scale
    "auto:micro", "auto:small", "auto:medium", "auto:large", "auto:huge",
    # State
    "auto:stale", "auto:active", "auto:no-snapshots", "auto:needs-attention",
    "auto:no-files",
    # Activity
    "auto:high-activity", "auto:low-activity",
    # Type (mirror of project_type)
    "auto:python", "auto:arduino", "auto:kicad", "auto:node", "auto:web",
    "auto:cad", "auto:embedded", "auto:document", "auto:data",
}

# Tags extracted from description text
_DESC_PATTERNS = [
    (r"\b(iot|internet of things)\b",  "iot"),
    (r"\b(machine learning|ml|ai)\b",  "ml"),
    (r"\b(3d print(?:ing)?)\b",        "3d-printing"),
    (r"\b(robot(?:ics)?)\b",           "robotics"),
    (r"\b(home auto(?:mation)?)\b",    "home-automation"),
    (r"\b(raspberry pi|rpi)\b",        "raspberry-pi"),
    (r"\b(esp32|esp8266)\b",           "esp"),
    (r"\b(stm32)\b",                   "stm32"),
    (r"\b(react|vue|angular|svelte)\b","frontend"),
    (r"\b(api|rest|graphql)\b",        "api"),
    (r"\b(docker|container)\b",        "docker"),
    (r"\b(database|sql|postgres|sqlite|mysql)\b", "database"),
]


def _scale_tag(file_count: int) -> str:
    if file_count == 0:   return "auto:no-files"
    if file_count < 5:    return "auto:micro"
    if file_count < 20:   return "auto:small"
    if file_count < 100:  return "auto:medium"
    if file_count < 500:  return "auto:large"
    return "auto:huge"


def _activity_tags(project_id: int, session) -> list[str]:
    """Determine activity level from recent event count."""
    since_7d  = datetime.datetime.utcnow() - datetime.timedelta(days=7)
    since_30d = datetime.datetime.utcnow() - datetime.timedelta(days=30)
    recent_7  = (session.query(ActivityEvent)
                 .filter(ActivityEvent.project_id == project_id,
                         ActivityEvent.created_at >= since_7d).count())
    recent_30 = (session.query(ActivityEvent)
                 .filter(ActivityEvent.project_id == project_id,
                         ActivityEvent.created_at >= since_30d).count())
    tags = []
    if recent_7 >= 10:    tags.append("auto:high-activity")
    elif recent_30 < 3:   tags.append("auto:low-activity")
    return tags


def _state_tags(project: Project, version_count: int) -> list[str]:
    tags = []
    if version_count == 0:
        tags.append("auto:no-snapshots")
    if project.last_activity:
        days_since = (datetime.datetime.utcnow() - project.last_activity).days
        if days_since > 30:
            tags.append("auto:stale")
        elif days_since <= 7:
            tags.append("auto:active")
    health = project.health or 0
    if health < 40:
        tags.append("auto:needs-attention")
    return tags


def _desc_tags(description: str) -> list[str]:
    """Extract technology tags from project description."""
    if not description:
        return []
    desc_lower = description.lower()
    tags = []
    for pattern, tag in _DESC_PATTERNS:
        if re.search(pattern, desc_lower):
            tags.append(tag)
    return tags


def compute_tags(project_id: int, session=None) -> dict:
    """
    Compute all auto-tags for a project.

    Returns:
        {
          "auto_tags":   list[str],   # tags to set (auto-managed)
          "custom_tags": list[str],   # user tags to preserve
          "merged":      list[str],   # final combined list
          "new":         list[str],   # tags that weren't there before
          "removed":     list[str],   # auto-tags that no longer apply
        }
    """
    s = session or get_session()
    own = session is None
    try:
        proj = s.query(Project).filter_by(id=project_id).first()
        if not proj:
            return {}

        existing_tags = list(proj.tags or [])
        custom_tags   = [t for t in existing_tags if t not in _AUTO_MANAGED
                         and not t.startswith(AUTO_TAG_PREFIX)]

        # ── Compute new auto-tags ─────────────────────────────────────────────
        new_auto: list[str] = []

        # Type tag (mirrors project_type)
        if proj.project_type and proj.project_type != "generic":
            new_auto.append(f"auto:{proj.project_type}")

        # File scale
        fc = s.query(TrackedFile).filter_by(project_id=project_id, is_deleted=False).count()
        new_auto.append(_scale_tag(fc))

        # Version state
        vc = s.query(Version).filter_by(project_id=project_id).count()
        new_auto.extend(_state_tags(proj, vc))

        # Activity level
        new_auto.extend(_activity_tags(project_id, s))

        # Description-derived tags
        new_auto.extend(_desc_tags(proj.description or ""))

        # Folder-based type detection (if path exists)
        if proj.path and Path(proj.path).is_dir():
            detected = detect_project_type(Path(proj.path))
            if detected and detected != "generic":
                ft = f"auto:{detected}"
                if ft not in new_auto:
                    new_auto.append(ft)

        # Deduplicate
        new_auto = list(dict.fromkeys(new_auto))

        old_auto   = [t for t in existing_tags if t in _AUTO_MANAGED
                      or t.startswith(AUTO_TAG_PREFIX)]
        added      = [t for t in new_auto if t not in old_auto]
        removed    = [t for t in old_auto if t not in new_auto]
        merged     = custom_tags + new_auto

        return {
            "auto_tags":   new_auto,
            "custom_tags": custom_tags,
            "merged":      merged,
            "new":         added,
            "removed":     removed,
        }
    finally:
        if own:
            s.close()


def apply_tags(project_id: int, session=None) -> list[str]:
    """
    Compute and immediately persist auto-tags for a project.
    Preserves all user-created (non-auto) tags.
    Returns the final merged tag list.
    """
    s = session or get_session()
    own = session is None
    try:
        result = compute_tags(project_id, s)
        if not result:
            return []
        proj = s.query(Project).filter_by(id=project_id).first()
        if proj:
            proj.tags = result["merged"]
            if own:
                s.commit()
            if result["new"]:
                log.info("Auto-tagged project %d: +%s", project_id, result["new"])
            if result["removed"]:
                log.debug("Auto-tag removed from %d: %s", project_id, result["removed"])
        return result["merged"]
    except Exception as exc:
        if own:
            s.rollback()
        log.error("Auto-tag failed for project %d: %s", project_id, exc)
        return []
    finally:
        if own:
            s.close()


def apply_tags_all(session=None) -> dict[int, list[str]]:
    """Apply auto-tags to every non-deleted project. Returns {project_id: tags}."""
    s = session or get_session()
    own = session is None
    results = {}
    try:
        from sqlalchemy import text
        ids = [r[0] for r in s.execute(
            text("SELECT id FROM projects WHERE is_deleted=0 OR is_deleted IS NULL")
        )]
        for pid in ids:
            results[pid] = apply_tags(pid, s)
        if own:
            s.commit()
    finally:
        if own:
            s.close()
    return results
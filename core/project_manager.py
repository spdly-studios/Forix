# forix/core/project_manager.py
"""
Forix — Project Manager
The brain that creates, updates, merges, and health-checks projects.
All DB interaction goes through here.
"""

import datetime
import json
import logging
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from sqlalchemy.exc import IntegrityError

from core.database import ActivityEvent, Project, TrackedFile, Version, get_session
from core.classifier import (
    classify_file,
    compute_checksum,
    detect_project_type,
    infer_project_category,
    infer_project_name,
    score_folder_as_project,
    should_ignore,
)
from core.constants import (
    AUTO_MERGE_THRESHOLD,
    MAX_VERSIONS_PER_PROJECT,
    PROJECT_BASE_DIRS,
    PROJECT_README_TEMPLATE,
    PROJECT_SIGNATURES,
    PROJECT_SRC_LAYOUT_DESCRIPTIONS,
    PROJECT_TYPE_SRC_DIRS,
    PROJECTS_DIR,
    SUGGEST_MERGE_THRESHOLD,
    VERSION_SIZE_LIMIT,
)

log = logging.getLogger("forix.project_manager")


# ── Directory & file scaffold ─────────────────────────────────────────────────

def _src_dirs_for_type(project_type: str) -> list[str]:
    """Return the list of src/ subdirectory paths for the given project type."""
    return PROJECT_TYPE_SRC_DIRS.get(project_type, PROJECT_TYPE_SRC_DIRS["generic"])


def ensure_project_structure(project_path: Path, project_type: str = "generic") -> None:
    """
    Create the full directory scaffold for a project.

    Layout (always):
        ProjectName/
        ├── src/            ← type-specific subdirs created inside
        ├── scratch/        ← dead-end attempts / WIP experiments
        ├── archive/        ← completed or abandoned sub-attempts
        ├── notes/
        ├── assets/
        ├── exports/        ← build artefacts only (binaries, gerbers, PDFs)
        ├── versions/       ← managed by Forix, do not edit manually
        └── logs/

    The scratch/ and archive/ dirs are the key anti-clutter mechanism:
    instead of starting a new project when stuck, the user moves the
    dead-end attempt into scratch/ and continues in src/.
    """
    project_path.mkdir(parents=True, exist_ok=True)

    # Base dirs (same for every project type)
    for d in PROJECT_BASE_DIRS:
        (project_path / d).mkdir(exist_ok=True)

    # Type-specific src/ subdirs
    for rel in _src_dirs_for_type(project_type):
        (project_path / rel).mkdir(parents=True, exist_ok=True)

    # Place a .gitkeep in scratch/ and archive/ so they survive git commits
    # and are immediately visible in file managers.
    for keep_dir in ("scratch", "archive"):
        keep_file = project_path / keep_dir / ".gitkeep"
        if not keep_file.exists():
            keep_file.write_text(
                "# Forix: this folder is intentional — do not delete.\n",
                encoding="utf-8",
            )

    # Place a WORKFLOW.md in scratch/ explaining its purpose to the user.
    scratch_guide = project_path / "scratch" / "WORKFLOW.md"
    if not scratch_guide.exists():
        scratch_guide.write_text(
            "# scratch/\n\n"
            "When you hit a wall or want to try a completely different approach:\n\n"
            "1. Create a subfolder here named after the attempt, e.g. `attempt_01/`\n"
            "2. Move your broken/stuck work into it\n"
            "3. Start fresh in `src/`\n\n"
            "Forix will **never** auto-delete anything in `scratch/` or `archive/`.\n"
            "You can always come back and salvage ideas from earlier attempts.\n",
            encoding="utf-8",
        )


def _render_readme(
    name: str,
    project_type: str,
    category: str,
) -> str:
    """Render the README.md content for a newly created project."""
    src_layout = PROJECT_SRC_LAYOUT_DESCRIPTIONS.get(
        project_type,
        PROJECT_SRC_LAYOUT_DESCRIPTIONS["generic"],
    )
    return PROJECT_README_TEMPLATE.format(
        name=name,
        type=project_type,
        category=category,
        date=datetime.date.today().isoformat(),
        src_layout=src_layout,
    )


def write_metadata(project: Project) -> None:
    """Persist metadata.json inside the project folder."""
    meta_path = Path(project.path) / "metadata.json"
    try:
        meta_path.write_text(
            json.dumps(project.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )
    except Exception as exc:
        log.warning("Could not write metadata for %s: %s", project.name, exc)


def _write_readme(project: Project) -> None:
    """
    Write README.md if it does not already exist.
    Never overwrites — the user may have edited it.
    """
    readme_path = Path(project.path) / "README.md"
    if readme_path.exists():
        return
    try:
        readme_path.write_text(
            _render_readme(project.name, project.project_type, project.category),
            encoding="utf-8",
        )
    except Exception as exc:
        log.warning("Could not write README for %s: %s", project.name, exc)


# ── Project CRUD ──────────────────────────────────────────────────────────────

def get_all_projects(session=None) -> List[Project]:
    """
    Return all non-deleted projects.

    NOTE ON SESSION LIFETIME: when session=None a new session is opened and
    closed here, which means the returned ORM objects become *detached* as
    soon as this function returns.  Callers that only read scalar attributes
    (name, path, id, …) are fine.  Callers that need to traverse
    relationships or pass the objects back into DB calls must supply their
    own session and manage its lifetime themselves.
    """
    s = session or get_session()
    try:
        return s.query(Project).filter(Project.is_deleted.is_(False)).all()
    except Exception as exc:
        log.error("get_all_projects: %s", exc)
        return []
    finally:
        if not session:
            s.close()


def get_project_by_path(path: str, session=None) -> Optional[Project]:
    s = session or get_session()
    try:
        return s.query(Project).filter_by(path=str(path)).first()
    finally:
        if not session:
            s.close()


def get_project_by_id(pid: int, session=None) -> Optional[Project]:
    s = session or get_session()
    try:
        return s.query(Project).filter_by(id=pid).first()
    finally:
        if not session:
            s.close()


def create_project(
    name: str,
    source_path: Optional[Path] = None,
    auto_created: bool = True,
    session=None,
) -> Optional[Project]:
    """
    Create a new managed project under PROJECTS_DIR.
    If source_path is given, files are imported from there after creation.

    The project receives:
      • A full type-aware directory scaffold (src/ subdivided by project type)
      • A README.md with a directory guide tailored to the project type
      • A metadata.json for machine consumption
      • A WORKFLOW.md in scratch/ explaining the anti-clutter workflow
    """
    s = session or get_session()
    try:
        # Sanitise name
        safe_name = "".join(
            c for c in name if c.isalnum() or c in " _-"
        ).strip() or "UnnamedProject"

        # Find a unique path under PROJECTS_DIR
        project_path = PROJECTS_DIR / safe_name
        base_path    = project_path
        counter      = 1
        while project_path.exists() or s.query(Project).filter_by(
            path=str(project_path)
        ).first():
            project_path = base_path.parent / f"{base_path.name}_{counter}"
            counter     += 1

        ptype = detect_project_type(source_path) if source_path else "generic"
        cat   = infer_project_category(ptype)

        ensure_project_structure(project_path, ptype)

        proj = Project(
            name=safe_name,
            path=str(project_path),
            category=cat,
            project_type=ptype,
            auto_created=auto_created,
            tags=[ptype] if ptype != "generic" else [],
        )
        s.add(proj)
        s.commit()
        s.refresh(proj)

        # Human-readable README (never overwritten after initial creation)
        _write_readme(proj)
        # Machine-readable metadata
        write_metadata(proj)

        _log_event(
            proj.id,
            "project_created",
            f"Project '{name}' created (type={ptype})",
            session=s,
        )
        log.info("Created project: %s @ %s (type=%s)", proj.name, proj.path, ptype)

        if source_path and source_path.is_dir():
            import_folder_to_project(source_path, proj, session=s)

        return proj

    except IntegrityError:
        s.rollback()
        log.warning("Duplicate project path for '%s', skipping.", name)
        return None
    except Exception as exc:
        s.rollback()
        log.error("Failed to create project '%s': %s", name, exc, exc_info=True)
        return None
    finally:
        if not session:
            s.close()


# ── File import ───────────────────────────────────────────────────────────────

def import_file_to_project(
    file_path: Path,
    project: Project,
    move: bool = False,
    session=None,
) -> Optional[TrackedFile]:
    """
    Copy (or move) a file into the appropriate src/ subfolder of a project.

    Files land in:
        src/<category>/<filename>

    …where <category> is determined by file extension (see FILE_CATEGORY_MAP).
    If the project type has a matching src/ subdir, files of that type go
    there instead; everything else falls through to src/<category>.
    """
    s = session or get_session()
    try:
        if should_ignore(file_path) or not file_path.is_file():
            return None

        category  = classify_file(file_path)
        # Import into src/ rather than a flat "current/" dir.
        dest_dir  = Path(project.path) / "src" / category
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Resolve name collision
        dest_file = dest_dir / file_path.name
        stem, suffix = file_path.stem, file_path.suffix
        counter = 1
        while dest_file.exists():
            dest_file = dest_dir / f"{stem}_{counter}{suffix}"
            counter  += 1

        if move:
            shutil.move(str(file_path), str(dest_file))
        else:
            shutil.copy2(str(file_path), str(dest_file))

        # Avoid creating a duplicate DB record if somehow the same dest path
        # was already tracked (e.g. after a crash mid-import).
        if s.query(TrackedFile).filter_by(path=str(dest_file)).first():
            return s.query(TrackedFile).filter_by(path=str(dest_file)).first()

        checksum = compute_checksum(dest_file)
        stat     = dest_file.stat()

        tf = TrackedFile(
            project_id=project.id,
            path=str(dest_file),
            original_path=str(file_path),
            name=dest_file.name,
            extension=dest_file.suffix.lower(),
            category=category,
            size_bytes=stat.st_size,
            checksum=checksum,
            modified_at=datetime.datetime.fromtimestamp(stat.st_mtime),
        )
        s.add(tf)

        # Re-query the project within this session to avoid cross-session
        # ORM state issues when the passed-in `project` belongs to a
        # different (or already-closed) session.
        proj = s.query(Project).filter_by(id=project.id).first()
        if proj:
            # updated_at is stamped automatically by the before_flush ORM event
            proj.last_activity = datetime.datetime.utcnow()

        s.commit()
        return tf

    except Exception as exc:
        s.rollback()
        log.error("Failed to import file %s: %s", file_path, exc)
        return None
    finally:
        if not session:
            s.close()


def import_folder_to_project(
    folder: Path,
    project: Project,
    session=None,
) -> None:
    """
    Recursively import all eligible files from folder into a project.
    Skips the project's own subdirectories to prevent circular imports.
    """
    project_root = Path(project.path).resolve()
    for item in folder.rglob("*"):
        # Guard: never import from inside the project itself
        try:
            item.resolve().relative_to(project_root)
            continue   # item is inside the project — skip
        except ValueError:
            pass        # item is outside the project — proceed

        if item.is_file() and not should_ignore(item):
            import_file_to_project(item, project, session=session)


# ── Scratch / archive helpers ─────────────────────────────────────────────────

def move_to_scratch(
    project: Project,
    attempt_name: str,
    files: Optional[List[Path]] = None,
    session=None,
) -> Path:
    """
    Create a named sub-attempt folder in scratch/ and optionally move
    specific files or the entire src/ into it.

    Usage:
        # Archive all of src/ as attempt_02
        move_to_scratch(proj, "attempt_02")

        # Just move specific files
        move_to_scratch(proj, "dead_end_approach", files=[Path("src/pkg/old_algo.py")])

    The user can then restart cleanly in src/ without losing prior work.
    Nothing in scratch/ is ever auto-deleted or snapshotted by Forix.
    """
    project_path  = Path(project.path)
    scratch_dir   = project_path / "scratch" / attempt_name
    scratch_dir.mkdir(parents=True, exist_ok=True)

    if files:
        for f in files:
            rel = f.relative_to(project_path) if f.is_absolute() else f
            src = project_path / rel
            if src.exists():
                dest = scratch_dir / src.name
                shutil.move(str(src), str(dest))
    else:
        # Move the entire src/ tree into scratch/<attempt_name>/src/
        src_dir = project_path / "src"
        if src_dir.exists() and any(src_dir.rglob("*")):
            dest = scratch_dir / "src"
            shutil.copytree(str(src_dir), str(dest), dirs_exist_ok=True)
            # Rebuild a clean src/ scaffold
            shutil.rmtree(str(src_dir), ignore_errors=True)

    # Re-create the src/ scaffold so the user can start fresh immediately
    ptype = project.project_type or "generic"
    for rel in _src_dirs_for_type(ptype):
        (project_path / rel).mkdir(parents=True, exist_ok=True)

    _log_event(
        project.id,
        "scratch_created",
        f"Moved attempt to scratch/{attempt_name}",
        session=session,
    )
    log.info(
        "Project '%s': archived attempt to scratch/%s", project.name, attempt_name
    )
    return scratch_dir


def move_to_archive(
    project: Project,
    attempt_name: str,
    source_subpath: str = "scratch",
    session=None,
) -> Optional[Path]:
    """
    Move a folder from scratch/ (or anywhere inside the project) into archive/.
    Use this for attempts that are truly done — not just paused.
    """
    project_path = Path(project.path)
    src          = project_path / source_subpath / attempt_name
    if not src.exists():
        log.warning(
            "move_to_archive: '%s' not found in project '%s'",
            attempt_name, project.name,
        )
        return None

    dest = project_path / "archive" / attempt_name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest))

    _log_event(
        project.id,
        "archived",
        f"Moved {source_subpath}/{attempt_name} → archive/{attempt_name}",
        session=session,
    )
    return dest


# ── Version control ───────────────────────────────────────────────────────────

def create_version_snapshot(
    project: Project,
    session=None,
) -> Optional[Version]:
    """
    Snapshot the project's src/ directory.

    Changes from the original:
      • Snapshots src/ (not the old "current/") to match the new layout.
      • scratch/ and archive/ are intentionally excluded — they are not
        source-of-truth and would bloat snapshots considerably.
      • Pruning now happens after flush() so the count includes the new
        version, preventing off-by-one accumulation.
    """
    s = session or get_session()
    try:
        proj = s.query(Project).filter_by(id=project.id).first()
        if not proj:
            return None

        src_dir = Path(proj.path) / "src"
        if not src_dir.exists():
            return None

        total_size = sum(
            f.stat().st_size for f in src_dir.rglob("*") if f.is_file()
        )
        if total_size > VERSION_SIZE_LIMIT:
            log.info(
                "Skipping snapshot for '%s' — too large (%s bytes)",
                proj.name, f"{total_size:,}",
            )
            return None

        last_ver = (
            s.query(Version)
            .filter_by(project_id=proj.id)
            .order_by(Version.version_num.desc())
            .first()
        )
        ver_num  = (last_ver.version_num + 1) if last_ver else 1
        label    = f"v{ver_num}"

        rel_path     = f"versions/{label}"
        versions_dir = Path(proj.path) / rel_path
        versions_dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            str(src_dir),
            str(versions_dir / "src"),
            dirs_exist_ok=True,
        )

        file_count = sum(1 for _ in src_dir.rglob("*") if _.is_file())
        summary    = _generate_version_summary(proj, ver_num, s)

        ver = Version(
            project_id=proj.id,
            version_num=ver_num,
            label=label,
            rel_path=rel_path,
            summary=summary,
            file_count=file_count,
            size_bytes=total_size,
        )
        s.add(ver)

        # Flush first so the new version is included in the count, then prune.
        # Without flush() the count would be MAX and we'd never delete the
        # oldest — leading to MAX+N versions after N snapshots.
        s.flush()
        all_vers = (
            s.query(Version)
            .filter_by(project_id=proj.id)
            .order_by(Version.version_num.asc())
            .all()
        )
        while len(all_vers) > MAX_VERSIONS_PER_PROJECT:
            oldest = all_vers.pop(0)
            shutil.rmtree(str(oldest.abs_path(proj)), ignore_errors=True)
            s.delete(oldest)

        s.commit()
        s.refresh(ver)

        _log_event(
            proj.id, "version_created", f"Snapshot {label} created", session=s
        )
        log.info("Created %s for project '%s'", label, proj.name)
        return ver

    except Exception as exc:
        s.rollback()
        log.error(
            "Version snapshot failed for project %s: %s",
            project.id, exc, exc_info=True,
        )
        return None
    finally:
        if not session:
            s.close()


def _generate_version_summary(project: Project, ver_num: int, session) -> str:
    if ver_num == 1:
        return "Initial snapshot"
    count = (
        session.query(TrackedFile)
        .filter_by(project_id=project.id)
        .count()
    )
    return f"Auto-snapshot #{ver_num} — {count} files tracked"


# ── Project health ────────────────────────────────────────────────────────────

def compute_project_health(project: Project, session=None) -> float:
    """
    Score 0–100 based on activity recency, file presence,
    version history, and metadata completeness.
    """
    s = session or get_session()
    try:
        score = 50.0

        if project.last_activity:
            days_since = (datetime.datetime.utcnow() - project.last_activity).days
            if days_since < 7:
                score += 20
            elif days_since < 30:
                score += 10
            elif days_since > 90:
                score -= 20

        fc = s.query(TrackedFile).filter_by(project_id=project.id).count()
        if fc > 0:
            score += min(fc * 2, 20)

        vc = s.query(Version).filter_by(project_id=project.id).count()
        if vc > 0:
            score += min(vc, 10)

        if project.description and len(project.description) > 10:
            score += 5

        return max(0.0, min(100.0, score))
    finally:
        if not session:
            s.close()


def refresh_project_health(project_id: int, session=None) -> None:
    s = session or get_session()
    try:
        proj = s.query(Project).filter_by(id=project_id).first()
        if proj:
            proj.health = compute_project_health(proj, s)
            s.commit()
    finally:
        if not session:
            s.close()


# ── Auto detection ────────────────────────────────────────────────────────────

# Forix internal scaffold directory names.
# Any folder with one of these names is part of a project's internal
# structure and must NEVER be registered as a standalone project.
# Keep in sync with PROJECT_BASE_DIRS in config.py.
_FORIX_SCAFFOLD_DIRS: frozenset = frozenset({
    "src", "scratch", "archive", "notes",
    "assets", "exports", "versions", "logs",
})


def _is_inside_managed_project(folder: Path, session) -> bool:
    """
    Return True if *folder* is a subdirectory of any project already
    tracked in the database.  Prevents scaffold dirs (scratch/, versions/,
    etc.) from being re-registered as independent projects.
    """
    try:
        resolved = folder.resolve()
    except OSError:
        return False
    for parent in resolved.parents:
        if session.query(Project).filter_by(path=str(parent)).first():
            return True
    return False


def auto_detect_and_create_project(
    folder: Path,
    session=None,
) -> Optional[Project]:
    """
    Given an arbitrary folder, decide if it looks like a project
    and create/register it if so.

    Guards applied cheapest-first:
      1. Folder name is a Forix scaffold dir (scratch/, versions/, etc.) → skip.
      2. Folder is already tracked → return existing record.
      3. Folder is inside an already-tracked project tree → skip.
      4. Heuristic score below threshold → skip.
    """
    # Guard 1: never treat a Forix-internal dir as a project, regardless
    # of where it appears on disk.  This is the primary fix for the bug
    # where watchdog fires DirCreatedEvent for scratch/, versions/, etc.
    # and each one ends up registered as its own project.
    if folder.name.lower() in _FORIX_SCAFFOLD_DIRS:
        log.debug("auto_detect: skipping scaffold dir '%s'", folder)
        return None

    s = session or get_session()
    try:
        resolved   = str(folder.resolve())
        unresolved = str(folder)

        # Guard 2: already tracked under either path form.
        existing = (
            s.query(Project).filter_by(path=resolved).first()
            or s.query(Project).filter_by(path=unresolved).first()
        )
        if existing:
            return existing

        # Guard 3: inside an already-tracked project tree.
        # Catches versions/v1/, scratch/attempt_01/, src/pkg/, etc. even
        # if they somehow pass the name check above.
        if _is_inside_managed_project(folder, s):
            log.debug("auto_detect: skipping '%s' — inside a managed project", folder)
            return None

        # Guard 4: heuristic score.
        if score_folder_as_project(folder) < 30:
            return None

        name = infer_project_name(folder)
        return create_project(name, source_path=folder, auto_created=True, session=s)
    finally:
        if not session:
            s.close()


# ── Merge suggestions ─────────────────────────────────────────────────────────

def find_similar_projects(
    session=None,
) -> List[Tuple[Project, Project, int]]:
    """
    Return (proj_a, proj_b, similarity_score) tuples where score >= SUGGEST_MERGE_THRESHOLD.
    Tries rapidfuzz first (faster, actively maintained), falls back to fuzzywuzzy.
    """
    fuzz = None
    for mod_path, attr in [
        ("rapidfuzz.fuzz", "token_sort_ratio"),
        ("fuzzywuzzy.fuzz", "token_sort_ratio"),
    ]:
        try:
            import importlib
            mod  = importlib.import_module(mod_path)
            fuzz = getattr(mod, attr)
            break
        except ImportError:
            continue

    if fuzz is None:
        log.debug(
            "Neither rapidfuzz nor fuzzywuzzy is installed — "
            "merge suggestions unavailable.  Run: pip install rapidfuzz"
        )
        return []

    s = session or get_session()
    try:
        projects = s.query(Project).filter(Project.is_deleted.is_(False)).all()
        pairs: List[Tuple[Project, Project, int]] = []
        for i, a in enumerate(projects):
            for b in projects[i + 1:]:
                score = fuzz(a.name, b.name)
                if score >= SUGGEST_MERGE_THRESHOLD:
                    pairs.append((a, b, score))
        return sorted(pairs, key=lambda x: x[2], reverse=True)
    finally:
        if not session:
            s.close()


# ── Activity log ──────────────────────────────────────────────────────────────

def _log_event(
    project_id: Optional[int],
    event_type: str,
    description: str,
    path: str = "",
    session=None,
) -> None:
    """
    Append an activity event.  Always uses the caller's session when provided
    to avoid opening a second connection for what is essentially a side-effect
    of the caller's operation.
    """
    s = session or get_session()
    own_session = session is None
    try:
        ev = ActivityEvent(
            project_id=project_id,
            event_type=event_type,
            description=description,
            path=path,
        )
        s.add(ev)
        # Only commit if we opened the session ourselves; otherwise let the
        # caller commit everything atomically.
        if own_session:
            s.commit()
    except Exception as exc:
        if own_session:
            s.rollback()
        log.warning("_log_event failed (%s): %s", event_type, exc)
    finally:
        if own_session:
            s.close()


def get_recent_events(limit: int = 50, session=None) -> List[ActivityEvent]:
    s = session or get_session()
    try:
        return (
            s.query(ActivityEvent)
            .order_by(ActivityEvent.created_at.desc())
            .limit(limit)
            .all()
        )
    finally:
        if not session:
            s.close()
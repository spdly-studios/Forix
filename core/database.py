# forix/core/database.py
"""
Forix — Database Layer (SQLAlchemy + SQLite/WAL)

Design principles:
  • Single engine, single session factory, both created once behind a lock.
  • expire_on_commit=True (SQLAlchemy default) — callers use session.refresh()
    when they need post-commit attribute access rather than relying on stale cache.
  • All hot-path filter/order columns are indexed.
  • updated_at is maintained via an ORM event (not onupdate=) so it fires
    reliably on ORM-level commits, not only on Core UPDATE statements.
  • Schema migrations: _migrate() runs lightweight ALTER TABLE ADD COLUMN
    statements on startup so new columns are added to existing databases
    without requiring Alembic for this project's scope.
  • Version snapshot paths stored relative to the project root so that
    moving a project folder doesn't break its version history.
  • is_deleted / deleted_at on Project and TrackedFile for soft deletes.
  • ActivityEvent has a hard row-count cap enforced at insert time.
"""

import datetime
import json
import logging
import threading
from pathlib import Path
from typing import List, Optional

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Index, Integer, JSON, String, Text, event, func, text,
)
from sqlalchemy.orm import Session, declarative_base, relationship, sessionmaker
from sqlalchemy import create_engine

from core.constants import SYSTEM_DB, SYSTEM_DIR

log = logging.getLogger("forix.database")

Base = declarative_base()

# Maximum activity events to retain per project before the oldest are pruned.
# Set to 0 to disable pruning.
MAX_EVENTS_PER_PROJECT: int = 500


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def _utcnow() -> datetime.datetime:
    return datetime.datetime.utcnow()


# ─── MODELS ───────────────────────────────────────────────────────────────────

class Project(Base):
    __tablename__ = "projects"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    name          = Column(String(200), nullable=False)
    path          = Column(String(500), unique=True, nullable=False)
    category      = Column(String(50),  default="generic")
    project_type  = Column(String(50),  default="generic")
    status        = Column(String(30),  default="active")   # active/archived/stale
    health        = Column(Float,       default=100.0)       # 0–100
    tags          = Column(JSON,        default=lambda: [])
    description   = Column(Text,        default="")
    auto_created  = Column(Boolean,     default=True)
    is_deleted    = Column(Boolean,     default=False,  nullable=False)
    deleted_at    = Column(DateTime,    nullable=True)
    created_at    = Column(DateTime,    default=_utcnow, nullable=False)
    # updated_at is managed by the ORM event below — do NOT use onupdate=
    # because SQLAlchemy's onupdate only fires for Core UPDATE statements,
    # not for ORM-level session.commit() calls.
    updated_at    = Column(DateTime,    default=_utcnow, nullable=False)
    last_activity = Column(DateTime,    default=_utcnow)

    files    = relationship("TrackedFile",  back_populates="project",
                            cascade="all, delete-orphan", lazy="select")
    versions = relationship("Version",      back_populates="project",
                            cascade="all, delete-orphan", lazy="select")
    events   = relationship("ActivityEvent", back_populates="project",
                            cascade="all, delete-orphan", lazy="select")

    # ── Indexes ───────────────────────────────────────────────────────────
    __table_args__ = (
        Index("ix_projects_status",      "status"),
        Index("ix_projects_is_deleted",  "is_deleted"),
        Index("ix_projects_last_activity","last_activity"),
    )

    def soft_delete(self) -> None:
        """Mark this project as deleted without removing the DB row."""
        self.is_deleted = True
        self.deleted_at = _utcnow()
        self.status     = "deleted"

    def to_dict(self) -> dict:
        """
        Serialize to a plain dict.  Accesses only scalar columns — never
        traverses relationships — so it is safe to call on detached instances
        (e.g. after a session has been closed).
        """
        return {
            "id":            self.id,
            "name":          self.name,
            "path":          self.path,
            "category":      self.category,
            "type":          self.project_type,
            "status":        self.status,
            "health":        self.health,
            "tags":          self.tags or [],
            "description":   self.description,
            "auto_created":  self.auto_created,
            "is_deleted":    self.is_deleted,
            "created_at":    self.created_at.isoformat() if self.created_at else "",
            "updated_at":    self.updated_at.isoformat() if self.updated_at else "",
            "last_activity": self.last_activity.isoformat() if self.last_activity else "",
            # file_count omitted — requires a relationship load.
            # Callers that need it should query TrackedFile directly.
        }


class TrackedFile(Base):
    __tablename__ = "tracked_files"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    project_id    = Column(Integer, ForeignKey("projects.id"), nullable=True)
    path          = Column(String(1000), unique=True, nullable=False)
    original_path = Column(String(1000))      # where it was before Forix moved it
    name          = Column(String(300))
    extension     = Column(String(20))
    category      = Column(String(30))        # code/docs/images/etc.
    size_bytes    = Column(Integer, default=0)
    checksum      = Column(String(64))        # SHA-256 for duplicate detection
    is_deleted    = Column(Boolean, default=False, nullable=False)
    deleted_at    = Column(DateTime, nullable=True)
    created_at    = Column(DateTime, default=_utcnow)
    modified_at   = Column(DateTime, default=_utcnow)

    project = relationship("Project", back_populates="files")

    __table_args__ = (
        # Dedup lookup: checksum is the primary filter
        Index("ix_tracked_files_checksum",   "checksum"),
        # Most queries filter by project_id
        Index("ix_tracked_files_project_id", "project_id"),
        Index("ix_tracked_files_is_deleted", "is_deleted"),
        Index("ix_tracked_files_extension",  "extension"),
    )

    def soft_delete(self) -> None:
        self.is_deleted = True
        self.deleted_at = _utcnow()

    def to_dict(self) -> dict:
        return {
            "id":          self.id,
            "project_id":  self.project_id,
            "path":        self.path,
            "name":        self.name,
            "extension":   self.extension,
            "category":    self.category,
            "size_bytes":  self.size_bytes,
            "is_deleted":  self.is_deleted,
            "modified_at": self.modified_at.isoformat() if self.modified_at else "",
        }


class Version(Base):
    __tablename__ = "versions"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    project_id  = Column(Integer, ForeignKey("projects.id"), nullable=False)
    version_num = Column(Integer, nullable=False)
    label       = Column(String(20))
    # rel_path stores the snapshot path *relative to the project root*.
    # This means version history survives if the project folder is renamed
    # or moved, as long as the internal structure stays intact.
    # Use Version.abs_path(project) to get the full filesystem path.
    rel_path    = Column(String(500))
    summary     = Column(Text,    default="")
    file_count  = Column(Integer, default=0)
    size_bytes  = Column(Integer, default=0)
    created_at  = Column(DateTime, default=_utcnow)

    project = relationship("Project", back_populates="versions")

    __table_args__ = (
        Index("ix_versions_project_id",  "project_id"),
        Index("ix_versions_version_num", "project_id", "version_num"),
    )

    def abs_path(self, project: "Project") -> Path:
        """Resolve the snapshot to an absolute path via the project root."""
        return Path(project.path) / self.rel_path

    def to_dict(self, project: Optional["Project"] = None) -> dict:
        d: dict = {
            "id":          self.id,
            "project_id":  self.project_id,
            "version_num": self.version_num,
            "label":       self.label,
            "rel_path":    self.rel_path,
            "summary":     self.summary,
            "file_count":  self.file_count,
            "size_bytes":  self.size_bytes,
            "created_at":  self.created_at.isoformat() if self.created_at else "",
        }
        if project:
            d["abs_path"] = str(self.abs_path(project))
        return d


class ActivityEvent(Base):
    __tablename__ = "activity_events"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    project_id  = Column(Integer, ForeignKey("projects.id"), nullable=True)
    event_type  = Column(String(50))
    description = Column(Text)
    path        = Column(String(1000))
    created_at  = Column(DateTime, default=_utcnow, nullable=False)

    project = relationship("Project", back_populates="events")

    __table_args__ = (
        Index("ix_activity_events_project_id", "project_id"),
        # created_at is always used for ORDER BY DESC + LIMIT queries
        Index("ix_activity_events_created_at", "created_at"),
        Index("ix_activity_events_event_type", "event_type"),
    )

    def to_dict(self) -> dict:
        return {
            "id":          self.id,
            "project_id":  self.project_id,
            "event_type":  self.event_type,
            "description": self.description,
            "path":        self.path,
            "created_at":  self.created_at.isoformat() if self.created_at else "",
        }


class InventoryItem(Base):
    __tablename__ = "inventory"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    name          = Column(String(200), nullable=False)
    description   = Column(Text,    default="")
    quantity      = Column(Integer, default=0)
    unit          = Column(String(30),  default="pcs")
    category      = Column(String(50),  default="component")
    low_threshold = Column(Integer, default=2)
    location      = Column(String(200), default="")
    project_refs  = Column(JSON,    default=lambda: [])  # list of project IDs
    image_path    = Column(String(1000), default="")    # filesystem path to item photo
    created_at    = Column(DateTime, default=_utcnow)
    updated_at    = Column(DateTime, default=_utcnow)

    __table_args__ = (
        Index("ix_inventory_category", "category"),
        Index("ix_inventory_name",     "name"),
    )

    def is_low(self) -> bool:
        return self.quantity <= self.low_threshold

    def to_dict(self) -> dict:
        return {
            "id":            self.id,
            "name":          self.name,
            "description":   self.description,
            "quantity":      self.quantity,
            "unit":          self.unit,
            "category":      self.category,
            "low_threshold": self.low_threshold,
            "location":      self.location,
            "is_low":        self.is_low(),
            "image_path":    self.image_path or "",
            "project_refs":  self.project_refs or [],
        }


class DuplicateGroup(Base):
    __tablename__ = "duplicate_groups"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    checksum   = Column(String(64), unique=True, nullable=False)
    paths      = Column(JSON,    default=lambda: [])
    resolved   = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)

    __table_args__ = (
        Index("ix_duplicate_groups_resolved", "resolved"),
    )


# ─── ORM EVENTS ───────────────────────────────────────────────────────────────

def _stamp_updated_at(session: Session, flush_context, instances) -> None:
    """
    Stamp updated_at on every dirty Project or InventoryItem before each flush.
    Registered on the specific SessionFactory in get_session(), not on the
    global Session base class, so it only fires for Forix sessions.
    """
    now = _utcnow()
    for obj in session.dirty:
        if isinstance(obj, (Project, InventoryItem)):
            obj.updated_at = now


@event.listens_for(ActivityEvent, "after_insert")
def _prune_old_events(mapper, connection, target: ActivityEvent) -> None:
    """
    After every ActivityEvent insert, prune the oldest rows for that project
    so the table never exceeds MAX_EVENTS_PER_PROJECT per project.

    Runs via Core (connection), not ORM, so it does not trigger further
    ORM events and is safe inside a flush.
    """
    if MAX_EVENTS_PER_PROJECT <= 0 or target.project_id is None:
        return

    # Count current rows for this project
    count_row = connection.execute(
        text(
            "SELECT COUNT(*) FROM activity_events "
            "WHERE project_id = :pid"
        ),
        {"pid": target.project_id},
    ).scalar()

    overflow = count_row - MAX_EVENTS_PER_PROJECT
    if overflow <= 0:
        return

    # Delete the oldest `overflow` rows
    connection.execute(
        text(
            "DELETE FROM activity_events "
            "WHERE id IN ("
            "  SELECT id FROM activity_events "
            "  WHERE project_id = :pid "
            "  ORDER BY created_at ASC "
            "  LIMIT :n"
            ")"
        ),
        {"pid": target.project_id, "n": overflow},
    )


class StockLog(Base):
    """
    Records every stock adjustment (+/-) for an inventory item.
    Used to show usage history on the item detail panel.
    """
    __tablename__ = "stock_log"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    item_id    = Column(Integer, ForeignKey("inventory.id"), nullable=False)
    delta      = Column(Integer, nullable=False)   # positive = added, negative = removed
    note       = Column(String(200), default="")   # optional reason/note
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    __table_args__ = (
        Index("ix_stock_log_item_id",   "item_id"),
        Index("ix_stock_log_created_at","created_at"),
    )

    def to_dict(self) -> dict:
        return {
            "id":         self.id,
            "item_id":    self.item_id,
            "delta":      self.delta,
            "note":       self.note or "",
            "created_at": self.created_at.isoformat() if self.created_at else "",
        }


# ─── ENGINE / SESSION ─────────────────────────────────────────────────────────

_engine      = None
_SessionFactory = None
_db_lock     = threading.Lock()   # guards both _engine and _SessionFactory


def get_engine():
    """
    Return the shared SQLAlchemy engine, creating it on first call.
    Thread-safe: uses a module-level lock so only one engine is ever created
    even if two threads call get_engine() simultaneously.
    """
    global _engine
    if _engine is not None:
        return _engine

    with _db_lock:
        # Double-checked locking: re-test after acquiring the lock in case
        # another thread already created the engine while we were waiting.
        if _engine is not None:
            return _engine

        SYSTEM_DIR.mkdir(parents=True, exist_ok=True)
        db_url = f"sqlite:///{SYSTEM_DB}"

        engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False, "timeout": 30},
            # pool_size / max_overflow do not apply to StaticPool / NullPool;
            # SQLite uses NullPool by default in SQLAlchemy so each session
            # gets its own connection from the OS.  No pool tuning needed.
            echo=False,
        )

        # Register SQLite PRAGMAs exactly once on the engine (not inside
        # get_engine which can be called multiple times).  Using
        # engine.connect() here would be too early; listen on "connect" so
        # the PRAGMAs are applied to every new low-level connection.
        @event.listens_for(engine, "connect")
        def _apply_pragmas(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            # WAL mode: readers don't block writers, writers don't block readers.
            cursor.execute("PRAGMA journal_mode=WAL")
            # NORMAL sync: safe for WAL (WAL itself is the durability guarantee).
            cursor.execute("PRAGMA synchronous=NORMAL")
            # Cache: negative value = kibibytes.  -16384 = 16 MiB (safe default).
            # The comment in the original said "64 MB" but used -64000 which is
            # 64,000 pages × 4 KiB/page = 256 MiB.  16 MiB is more appropriate
            # for a desktop app; raise if profiling shows cache pressure.
            cursor.execute("PRAGMA cache_size=-16384")
            # Foreign key enforcement (SQLite disables it by default).
            cursor.execute("PRAGMA foreign_keys=ON")
            # Reduce lock contention for concurrent readers.
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

        _engine = engine

    return _engine


def get_session() -> Session:
    """
    Return a new ORM session bound to the shared engine.

    Session lifetime is the caller's responsibility — always use
    a try/finally or a context manager:

        s = get_session()
        try:
            ...
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    expire_on_commit=True (the default) is intentional: attributes are
    expired after commit so the next access issues a fresh SELECT.  Callers
    that need to read attributes after closing the session should call
    session.refresh(obj) before closing, or use obj.to_dict() which only
    reads scalar columns already loaded into the instance state.
    """
    global _SessionFactory
    if _SessionFactory is None:
        with _db_lock:
            if _SessionFactory is None:
                factory = sessionmaker(
                    bind=get_engine(),
                    expire_on_commit=True,   # correct default; was False (wrong)
                    autoflush=True,
                )
                # Scope the updated_at event to our factory's sessions only,
                # not to every Session in the process (which the global
                # @event.listens_for(Session, ...) pattern would do).
                event.listen(factory, "before_flush", _stamp_updated_at)
                _SessionFactory = factory
    return _SessionFactory()


# ─── SCHEMA INIT & MIGRATION ──────────────────────────────────────────────────

# Columns that may be missing in databases created by older Forix versions.
# Format: (table_name, column_name, column_definition_sql)
# ALTER TABLE … ADD COLUMN is idempotent-ish in SQLite (we catch the error).
_MIGRATION_COLUMNS: list[tuple[str, str, str]] = [
    ("projects",       "is_deleted",  "BOOLEAN NOT NULL DEFAULT 0"),
    ("projects",       "deleted_at",  "DATETIME"),
    ("tracked_files",  "is_deleted",  "BOOLEAN NOT NULL DEFAULT 0"),
    ("tracked_files",  "deleted_at",  "DATETIME"),
    ("versions",       "rel_path",    "VARCHAR(500)"),
    ("inventory",      "project_refs","TEXT"),         # JSON stored as TEXT in SQLite
    ("inventory",      "image_path",  "VARCHAR(1000) DEFAULT ''"),
]


def _migrate(connection) -> None:
    """
    Add any missing columns to an existing database.

    SQLite does not support ALTER TABLE … ADD COLUMN IF NOT EXISTS, so we
    attempt each ALTER and silently ignore the "duplicate column" error.
    This keeps the migration self-contained and avoids an Alembic dependency
    for a project of this scope.
    """
    # First collect existing table names so we can skip tables that don't
    # exist yet (fresh install: CREATE ALL runs before _migrate, but if for
    # any reason a table is absent we must not swallow the real error).
    existing_tables = {
        row[0]
        for row in connection.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        )
    }

    for table, column, definition in _MIGRATION_COLUMNS:
        if table not in existing_tables:
            # Table hasn't been created yet — CREATE ALL will add it with the
            # column already defined, so no ALTER TABLE needed.
            continue
        try:
            connection.execute(
                text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            )
            log.info("Migration: added column %s.%s", table, column)
        except Exception as exc:
            msg = str(exc).lower()
            if "duplicate column" in msg or "already exists" in msg:
                pass  # expected on repeat startups — column already present
            else:
                log.warning("Migration: unexpected error on %s.%s: %s", table, column, exc)

    # Back-fill rel_path from the old absolute path column if it exists.
    # This is a best-effort migration; rows where the path doesn't start
    # with the project path are left as NULL.
    try:
        connection.execute(text("""
            UPDATE versions
            SET rel_path = (
                SELECT REPLACE(v.rel_path, p.path || '/', '')
                FROM   projects p
                WHERE  p.id = versions.project_id
            )
            WHERE rel_path IS NULL
              AND EXISTS (SELECT 1 FROM projects WHERE id = versions.project_id)
        """))
    except Exception:
        pass  # Old 'path' column may not exist; safe to skip.


def _add_column_if_missing(connection, table: str, column: str, definition: str) -> None:
    """
    Unconditionally attempt ALTER TABLE … ADD COLUMN and silently swallow
    the 'duplicate column' error.  Used for critical columns that must exist
    before SQLAlchemy touches the table, so they are run directly in init_db()
    before the ORM-based _migrate() pass.
    """
    try:
        connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))
        connection.commit()
        log.info("Schema: added column %s.%s", table, column)
    except Exception as exc:
        msg = str(exc).lower()
        if "duplicate column" in msg or "already exists" in msg:
            pass   # Already present — expected on all runs after the first
        else:
            log.warning("Schema: unexpected ALTER error on %s.%s: %s", table, column, exc)


def init_db() -> None:
    """
    Initialise the database:
      1. Create all tables that don't yet exist (idempotent).
      2. Unconditionally attempt critical column additions (belt-and-suspenders).
      3. Run the full migration pass for any remaining columns.
    """
    engine = get_engine()
    Base.metadata.create_all(engine)

    with engine.connect() as conn:
        # ── Critical columns: run these directly before the ORM touches the
        # table.  Each call is idempotent — 'duplicate column' is suppressed.
        _add_column_if_missing(conn, "inventory", "image_path", "VARCHAR(1000) DEFAULT ''")

        # ── Full migration pass for all other columns
        _migrate(conn)
        conn.commit()

    log.info("Database initialised: %s", SYSTEM_DB)
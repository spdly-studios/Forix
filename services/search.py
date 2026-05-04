# forix/services/search.py
"""
Forix — Natural Language Search Engine  (v2)

Understands plain-English queries like:
  "stale python projects"
  "files modified this week"
  "arduino projects with no snapshots"
  "low stock components"
  "large projects over 50 files"
  "active kicad projects tagged embedded"

Pipeline:
  1. _parse_intent()   — extract structured filters from free text
  2. _db_filter()      — apply filters directly via SQL (fast, no full scan)
  3. _fuzzy_rank()     — fuzzy-score remaining text against labels
  4. Results returned sorted by relevance score
"""

import datetime
import logging
import re
from dataclasses import dataclass, field
from typing import Any, List, Optional

from core.database import (
    ActivityEvent, InventoryItem, Project, TrackedFile, get_session,
)

log = logging.getLogger("forix.search")


# ── Result type ───────────────────────────────────────────────────────────────

@dataclass
class SearchResult:
    kind:       str          # "project" | "file" | "inventory"
    label:      str
    subtitle:   str
    path:       str
    score:      int          # 0–100
    data:       Any
    matched_filters: list[str] = field(default_factory=list)   # human-readable why


# ── Intent parser ─────────────────────────────────────────────────────────────

@dataclass
class SearchIntent:
    """Structured representation of what the user is looking for."""
    # Entity filter
    kinds:          list[str]       # ["project","file","inventory"] or subset
    # Project filters
    project_types:  list[str]       # ["python","arduino", …]
    statuses:       list[str]       # ["active","stale","archived"]
    tags:           list[str]
    # Time filters
    modified_days:  Optional[int]   # files/projects modified in last N days
    created_days:   Optional[int]
    # Quantity filters (inventory)
    low_stock_only: bool
    # Project quality filters
    no_snapshots:   bool
    min_files:      Optional[int]
    max_files:      Optional[int]
    # Remainder text for fuzzy matching
    remainder:      str


# ── Keyword vocabularies ──────────────────────────────────────────────────────

_KIND_WORDS = {
    "project":   {"project","projects","folder","repo","repos","workspace"},
    "file":      {"file","files","document","documents","code","script","scripts"},
    "inventory": {"inventory","item","items","component","components","part","parts",
                  "stock","material","materials"},
}
_TYPE_WORDS = {
    "python":   {"python","py","flask","django","fastapi"},
    "arduino":  {"arduino","ino","microcontroller"},
    "kicad":    {"kicad","pcb","schematic","board","gerber"},
    "node":     {"node","nodejs","javascript","typescript","npm"},
    "web":      {"web","html","css","website","frontend"},
    "cad":      {"cad","freecad","fusion","solidworks","3d","mechanical"},
    "embedded": {"embedded","firmware","mcu","stm32","esp32","avr"},
    "document": {"document","doc","docs","markdown","pdf","report"},
    "data":     {"data","dataset","csv","notebook","jupyter","ml"},
}
_STATUS_WORDS = {
    "active":   {"active","current","working","live","open"},
    "stale":    {"stale","old","inactive","dormant","neglected"},
    "archived": {"archived","archive","done","finished","closed","complete","completed"},
    "on-hold":  {"paused","hold","on-hold","waiting","blocked"},
}
_TIME_PATTERNS = [
    # "this week", "last week", "past 7 days"
    (r"\bthis\s+week\b",        7),
    (r"\blast\s+week\b",        14),
    (r"\bpast\s+week\b",        7),
    (r"\bthis\s+month\b",       30),
    (r"\blast\s+month\b",       60),
    (r"\bpast\s+month\b",       30),
    (r"\bthis\s+year\b",        365),
    (r"\brecent(?:ly)?\b",      14),
    (r"\btoday\b",              1),
    (r"\byesterday\b",          2),
    (r"\bpast\s+(\d+)\s+days?\b",  None),   # dynamic
    (r"\blast\s+(\d+)\s+days?\b",  None),
]
_QUALITY_WORDS = {
    "no_snapshots": {"no snapshot","no snapshots","without snapshot","unversioned",
                     "no version","no versions"},
    "large":        {"large","big","huge","many files"},
    "small":        {"small","tiny","few files"},
    "low_stock":    {"low stock","low","running low","out of","empty","zero stock"},
}


def _parse_intent(query: str) -> SearchIntent:
    """
    Parse a free-text query into a structured SearchIntent.
    Consumes recognised tokens and returns remaining text for fuzzy matching.
    """
    q = query.lower().strip()
    rem = q   # will shrink as tokens are consumed

    kinds:         list[str] = []
    project_types: list[str] = []
    statuses:      list[str] = []
    tags:          list[str] = []
    modified_days: Optional[int] = None
    created_days:  Optional[int] = None
    low_stock:     bool = False
    no_snapshots:  bool = False
    min_files:     Optional[int] = None
    max_files:     Optional[int] = None

    # ── Kind ─────────────────────────────────────────────────────────────────
    for kind, words in _KIND_WORDS.items():
        for w in words:
            if re.search(rf"\b{re.escape(w)}\b", q):
                if kind not in kinds:
                    kinds.append(kind)
                rem = re.sub(rf"\b{re.escape(w)}\b", " ", rem)

    # ── Project type ─────────────────────────────────────────────────────────
    for ptype, words in _TYPE_WORDS.items():
        for w in words:
            if re.search(rf"\b{re.escape(w)}\b", q):
                if ptype not in project_types:
                    project_types.append(ptype)
                rem = re.sub(rf"\b{re.escape(w)}\b", " ", rem)

    # ── Status ───────────────────────────────────────────────────────────────
    for status, words in _STATUS_WORDS.items():
        for w in words:
            if re.search(rf"\b{re.escape(w)}\b", q):
                if status not in statuses:
                    statuses.append(status)
                rem = re.sub(rf"\b{re.escape(w)}\b", " ", rem)

    # ── Time ─────────────────────────────────────────────────────────────────
    for pattern, days in _TIME_PATTERNS:
        m = re.search(pattern, q)
        if m:
            if days is None:
                # Dynamic: extract the number
                try:
                    days = int(m.group(1))
                except (IndexError, ValueError):
                    days = 7
            modified_days = days
            rem = re.sub(pattern, " ", rem)
            break

    # ── Quality filters ───────────────────────────────────────────────────────
    for phrase in _QUALITY_WORDS["no_snapshots"]:
        if phrase in q:
            no_snapshots = True
            rem = rem.replace(phrase, " ")

    # File count: "over 50 files", "more than 20", "less than 5 files"
    m = re.search(r"\bover\s+(\d+)\s+files?\b", q)
    if m: min_files = int(m.group(1)); rem = re.sub(r"\bover\s+\d+\s+files?\b", " ", rem)
    m = re.search(r"\bmore\s+than\s+(\d+)\s+files?\b", q)
    if m: min_files = int(m.group(1)); rem = re.sub(r"\bmore\s+than\s+\d+\s+files?\b", " ", rem)
    m = re.search(r"\bless\s+than\s+(\d+)\s+files?\b", q)
    if m: max_files = int(m.group(1)); rem = re.sub(r"\bless\s+than\s+\d+\s+files?\b", " ", rem)

    for phrase in _QUALITY_WORDS["low_stock"]:
        if phrase in q:
            low_stock = True
            if "inventory" not in kinds:
                kinds.append("inventory")
            rem = rem.replace(phrase, " ")

    # ── Tags: "tagged X" or "tag:X" ─────────────────────────────────────────
    for m in re.finditer(r"\b(?:tagged?|tag:)\s*(\w+)", q):
        tags.append(m.group(1))
        rem = rem.replace(m.group(0), " ")

    # Default kind: if nothing explicit, search all
    if not kinds:
        kinds = ["project", "file", "inventory"]

    # Clean up remainder
    rem = re.sub(r"\b(?:with|without|and|or|the|that|have|has|in|for|of|a|an)\b", " ", rem)
    rem = re.sub(r"\s+", " ", rem).strip()

    return SearchIntent(
        kinds=kinds, project_types=project_types, statuses=statuses, tags=tags,
        modified_days=modified_days, created_days=created_days,
        low_stock_only=low_stock, no_snapshots=no_snapshots,
        min_files=min_files, max_files=max_files, remainder=rem,
    )


# ── Fuzzy scorer ──────────────────────────────────────────────────────────────

def _fuzzy_score(query: str, text: str) -> int:
    if not query:
        return 60   # matched purely by filter — give decent base score
    q = query.lower(); t = text.lower()
    if q == t:        return 100
    if q in t:        return 90
    words = q.split()
    if all(w in t for w in words): return 80
    try:
        from fuzzywuzzy import fuzz
        return max(fuzz.partial_ratio(q, t), fuzz.token_sort_ratio(q, t))
    except ImportError:
        # Simple token overlap
        q_tok = set(q.split()); t_tok = set(t.split())
        if not q_tok: return 0
        overlap = len(q_tok & t_tok) / len(q_tok)
        return int(overlap * 70)


# ── Main search function ──────────────────────────────────────────────────────

def search(query: str, limit: int = 80) -> List[SearchResult]:
    """
    Natural-language search across all entities.

    Examples:
        search("stale python projects")
        search("files modified this week")
        search("arduino projects with no snapshots")
        search("low stock resistors")
        search("active kicad projects over 20 files")
    """
    if not query or not query.strip():
        return []

    intent  = _parse_intent(query.strip())
    results: List[SearchResult] = []
    cutoff  = datetime.datetime.utcnow()
    s       = get_session()

    try:
        # ── PROJECTS ─────────────────────────────────────────────────────────
        if "project" in intent.kinds:
            q = s.query(Project).filter(Project.is_deleted.is_(False))

            if intent.project_types:
                q = q.filter(Project.project_type.in_(intent.project_types))
            if intent.statuses:
                q = q.filter(Project.status.in_(intent.statuses))
            if intent.modified_days:
                since = cutoff - datetime.timedelta(days=intent.modified_days)
                q = q.filter(Project.last_activity >= since)
            if intent.created_days:
                since = cutoff - datetime.timedelta(days=intent.created_days)
                q = q.filter(Project.created_at >= since)

            for proj in q.all():
                # Tag filter (post-DB, JSON column)
                if intent.tags:
                    ptags = [str(t).lower() for t in (proj.tags or [])]
                    if not all(tag in ptags for tag in intent.tags):
                        continue

                # File count filter
                if intent.min_files is not None or intent.max_files is not None:
                    fc = s.query(TrackedFile).filter_by(
                        project_id=proj.id, is_deleted=False).count()
                    if intent.min_files is not None and fc < intent.min_files:
                        continue
                    if intent.max_files is not None and fc > intent.max_files:
                        continue

                # No-snapshots filter
                if intent.no_snapshots:
                    vc = s.query(Project).filter_by(id=proj.id).count()
                    from core.database import Version
                    vc = s.query(Version).filter_by(project_id=proj.id).count()
                    if vc > 0:
                        continue

                # Fuzzy score on remainder text
                text_pool = " ".join(filter(None, [
                    proj.name, proj.description or "",
                    proj.project_type or "", proj.category or "",
                    " ".join(proj.tags or []),
                ]))
                sc = _fuzzy_score(intent.remainder, text_pool)
                if sc < 35 and intent.remainder:
                    continue

                matched = []
                if intent.project_types: matched.append(proj.project_type)
                if intent.statuses:      matched.append(proj.status)
                if intent.modified_days: matched.append(f"active in {intent.modified_days}d")
                if intent.no_snapshots:  matched.append("no snapshots")

                results.append(SearchResult(
                    kind="project", label=proj.name,
                    subtitle=f"{proj.category} · {proj.project_type} · {proj.status}",
                    path=proj.path, score=sc, data=proj, matched_filters=matched,
                ))

        # ── FILES ─────────────────────────────────────────────────────────────
        if "file" in intent.kinds:
            fq = s.query(TrackedFile).filter(TrackedFile.is_deleted.is_(False))
            if intent.modified_days:
                since = cutoff - datetime.timedelta(days=intent.modified_days)
                fq = fq.filter(TrackedFile.modified_at >= since)

            for tf in fq.limit(500).all():   # cap DB reads; fuzzy filters the rest
                sc = _fuzzy_score(intent.remainder, tf.name)
                if sc < 35 and intent.remainder:
                    continue
                proj_name = ""
                if tf.project_id:
                    p = s.query(Project).filter_by(id=tf.project_id).first()
                    proj_name = p.name if p else ""
                results.append(SearchResult(
                    kind="file", label=tf.name,
                    subtitle=f"{tf.category} · {proj_name}",
                    path=tf.path, score=sc, data=tf,
                ))

        # ── INVENTORY ─────────────────────────────────────────────────────────
        if "inventory" in intent.kinds:
            iq = s.query(InventoryItem)
            for item in iq.all():
                if intent.low_stock_only and not item.is_low():
                    continue
                text_pool = " ".join(filter(None, [
                    item.name, item.description or "", item.category or "",
                ]))
                sc = _fuzzy_score(intent.remainder, text_pool)
                if sc < 35 and intent.remainder:
                    continue
                results.append(SearchResult(
                    kind="inventory", label=item.name,
                    subtitle=(f"⚠ LOW — " if item.is_low() else "") +
                              f"Qty: {item.quantity} {item.unit} · {item.category}",
                    path="", score=sc, data=item,
                    matched_filters=["low stock"] if item.is_low() else [],
                ))

    finally:
        s.close()

    results.sort(key=lambda r: (-r.score, r.label.lower()))
    return results[:limit]


# ── Natural language query suggestions ───────────────────────────────────────

EXAMPLE_QUERIES = [
    "stale python projects",
    "arduino projects with no snapshots",
    "files modified this week",
    "active kicad projects over 20 files",
    "archived projects",
    "low stock components",
    "projects tagged embedded",
    "large projects this month",
    "inactive node projects",
    "components running low",
]
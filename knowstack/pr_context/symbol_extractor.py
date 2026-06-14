"""Resolve changed-file hunks into the smallest containing graph nodes.

For every (file, hunk) pair we look up nodes whose source span overlaps the
hunk's line range and pick the narrowest containing one — a `Method` beats
its enclosing `Class` beats its enclosing `File`. The result is a deduplicated
list of seed nodes that drive downstream neighborhood expansion.
"""
from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from knowstack.graph.store import GraphStore
from knowstack.pr_context.models import ChangedFile, Hunk

log = logging.getLogger(__name__)

# Tables searched for symbol-level hits. Order matters: earlier = narrower,
# so when two nodes both contain a hunk, the earlier one wins.
_SYMBOL_TABLES: tuple[str, ...] = (
    "Method", "Function", "Test", "ApiEndpoint", "DbModel",
    "Class", "Interface", "TypeAlias",
)
_FILE_TABLES: tuple[str, ...] = ("File", "ConfigFile")


@dataclass(frozen=True)
class Seed:
    """A node selected as a seed for neighborhood expansion."""
    node_id: str
    fqn: str
    name: str
    node_type: str
    file_path: str
    start_line: int
    end_line: int
    tags: tuple[str, ...] = ()


def extract_seeds(
    store: GraphStore,
    files: Iterable[ChangedFile],
    repo_id: str | None = None,
) -> list[Seed]:
    """Return seed nodes for every changed file, narrowest first.

    Skips files that aren't indexed (e.g. new files added in this PR — they
    can't yet be in the graph because the index runs on `main`).
    """
    seen: dict[str, Seed] = {}
    seeds: list[Seed] = []

    for cf in files:
        if cf.is_deleted:
            # Deleted files: surface the File node if it's still indexed.
            for fseed in _lookup_file_nodes(store, cf.path, repo_id):
                if fseed.node_id not in seen:
                    seen[fseed.node_id] = fseed
                    seeds.append(fseed)
            continue

        if not cf.hunks:
            continue

        for hunk in cf.hunks:
            picked = _narrowest_for_hunk(store, cf.path, hunk, repo_id)
            if picked is None:
                continue
            if picked.node_id not in seen:
                seen[picked.node_id] = picked
                seeds.append(picked)

    return seeds


# ── internals ────────────────────────────────────────────────────────────────


def _narrowest_for_hunk(
    store: GraphStore, file_path: str, hunk: Hunk, repo_id: str | None,
) -> Seed | None:
    """Find the smallest symbol-level node whose span overlaps the hunk."""
    for table in _SYMBOL_TABLES:
        hits = _overlap_query(store, table, file_path, hunk.start_line, hunk.end_line, repo_id)
        if not hits:
            continue
        # Narrowest = smallest line span among overlapping nodes.
        hits.sort(key=lambda s: (s.end_line - s.start_line, s.start_line))
        return hits[0]

    # Fall back to the File node so we at least anchor the hunk somewhere.
    fallback = _lookup_file_nodes(store, file_path, repo_id)
    return fallback[0] if fallback else None


def _overlap_query(
    store: GraphStore, table: str, file_path: str,
    h_start: int, h_end: int, repo_id: str | None,
) -> list[Seed]:
    """Symbols in `table` whose [start_line..end_line] overlaps [h_start..h_end]."""
    params: dict[str, object] = {
        "fp": file_path, "hs": int(h_start), "he": int(h_end),
    }
    repo_clause = ""
    if repo_id:
        repo_clause = " AND n.repo_id = $rid"
        params["rid"] = repo_id

    cypher = f"""
        MATCH (n:{table})
        WHERE n.file_path = $fp{repo_clause}
          AND n.start_line <= $he AND n.end_line >= $hs
        RETURN n.node_id AS node_id, n.fqn AS fqn, n.name AS name,
               n.start_line AS sl, n.end_line AS el, n.tags AS tags
    """
    try:
        rows = store.cypher(cypher, params)
    except Exception as exc:
        log.debug("overlap query on %s failed: %s", table, exc)
        return []

    return [_row_to_seed(r, table, file_path) for r in rows if r.get("node_id")]


def _lookup_file_nodes(
    store: GraphStore, file_path: str, repo_id: str | None,
) -> list[Seed]:
    """Resolve a file path to its File/ConfigFile node (whichever exists)."""
    results: list[Seed] = []
    for table in _FILE_TABLES:
        params: dict[str, object] = {"fp": file_path}
        repo_clause = ""
        if repo_id:
            repo_clause = " AND n.repo_id = $rid"
            params["rid"] = repo_id
        cypher = f"""
            MATCH (n:{table})
            WHERE n.file_path = $fp{repo_clause}
            RETURN n.node_id AS node_id, n.fqn AS fqn, n.name AS name,
                   n.tags AS tags
            LIMIT 1
        """
        try:
            rows = store.cypher(cypher, params)
        except Exception as exc:
            log.debug("file lookup on %s failed: %s", table, exc)
            continue
        for r in rows:
            results.append(_row_to_seed(r, table, file_path, file_node=True))
    return results


def _row_to_seed(
    row: dict[str, Any], table: str, file_path: str, *, file_node: bool = False,
) -> Seed:
    return Seed(
        node_id=str(row.get("node_id", "")),
        fqn=str(row.get("fqn") or row.get("name") or file_path),
        name=str(row.get("name") or ""),
        node_type=table,
        file_path=file_path,
        start_line=0 if file_node else int(row.get("sl") or 0),
        end_line=0 if file_node else int(row.get("el") or 0),
        tags=_parse_tags(row.get("tags")),
    )


def _parse_tags(raw: object) -> tuple[str, ...]:
    """Tags are stored as a JSON-encoded string in Kuzu STRING columns."""
    if not raw:
        return ()
    if isinstance(raw, list):
        return tuple(str(t) for t in raw)
    import json
    try:
        parsed = json.loads(str(raw))
        if isinstance(parsed, list):
            return tuple(str(t) for t in parsed)
    except Exception:
        pass
    return ()

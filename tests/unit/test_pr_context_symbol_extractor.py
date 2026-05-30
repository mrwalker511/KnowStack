"""Unit tests for pr_context.symbol_extractor.

These tests use a fake GraphStore-shaped stub so no Kuzu DB is touched. The
stub serves canned rows keyed by the table name in the Cypher query.
"""
from __future__ import annotations

import re
from typing import Any

from knowstack.pr_context.models import ChangedFile, Hunk
from knowstack.pr_context.symbol_extractor import extract_seeds


class FakeStore:
    """Minimal duck-typed stand-in for GraphStore.

    `rows_by_table` maps a node-table name (e.g. "Method", "Function") to the
    rows that should be returned when that table is queried. The query is
    inspected with a regex to find the table label.
    """

    _TABLE_RE = re.compile(r"MATCH \(n:([A-Za-z_]+)\)")

    def __init__(self, rows_by_table: dict[str, list[dict[str, Any]]]):
        self.rows_by_table = rows_by_table
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def cypher(self, query: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        self.calls.append((query, params or {}))
        m = self._TABLE_RE.search(query)
        if not m:
            return []
        table = m.group(1)
        rows = self.rows_by_table.get(table, [])
        if params and "fp" in params:
            rows = [r for r in rows if r.get("_file_path", params["fp"]) == params["fp"]]
        if params and "hs" in params and "he" in params:
            rows = [
                r for r in rows
                if r.get("sl", 0) <= params["he"] and r.get("el", 0) >= params["hs"]
            ]
        return rows


def _row(node_id: str, fqn: str, sl: int, el: int, *, file_path: str = "src/auth.py") -> dict[str, Any]:
    return {
        "node_id": node_id, "fqn": fqn, "name": fqn.split(".")[-1],
        "sl": sl, "el": el, "tags": "[]", "_file_path": file_path,
    }


def test_picks_narrowest_containing_node():
    # Class spans 1–100, Method spans 30–40; a hunk on line 35 should pick the Method.
    store = FakeStore({
        "Method": [_row("m1", "auth.AuthService.login", 30, 40)],
        "Function": [],
        "Class": [_row("c1", "auth.AuthService", 1, 100)],
    })
    cf = ChangedFile(path="src/auth.py", hunks=(Hunk(35, 35, "modified"),))
    seeds = extract_seeds(store, [cf])

    assert len(seeds) == 1
    assert seeds[0].node_id == "m1"
    assert seeds[0].fqn == "auth.AuthService.login"


def test_falls_back_to_file_node_when_no_symbol_overlaps():
    store = FakeStore({
        "Method": [], "Function": [], "Class": [],
        "File": [{"node_id": "f1", "fqn": "src/auth.py", "name": "auth.py", "tags": "[]"}],
    })
    cf = ChangedFile(path="src/auth.py", hunks=(Hunk(500, 510, "modified"),))
    seeds = extract_seeds(store, [cf])

    assert len(seeds) == 1
    assert seeds[0].node_id == "f1"
    assert seeds[0].node_type == "File"


def test_deleted_file_surfaces_file_node_when_indexed():
    store = FakeStore({
        "File": [{"node_id": "f1", "fqn": "src/old.py", "name": "old.py", "tags": "[]"}],
    })
    cf = ChangedFile(path="src/old.py", hunks=(), is_deleted=True)
    seeds = extract_seeds(store, [cf])

    assert [s.node_id for s in seeds] == ["f1"]


def test_new_unindexed_file_is_silently_skipped():
    store = FakeStore({})  # nothing indexed yet
    cf = ChangedFile(path="src/brand_new.py", hunks=(Hunk(1, 20, "added"),), is_new=True)
    seeds = extract_seeds(store, [cf])

    assert seeds == []


def test_dedupes_same_node_across_multiple_hunks():
    store = FakeStore({
        "Method": [_row("m1", "auth.AuthService.login", 30, 60)],
    })
    cf = ChangedFile(
        path="src/auth.py",
        hunks=(Hunk(35, 36, "modified"), Hunk(45, 50, "modified"), Hunk(55, 58, "modified")),
    )
    seeds = extract_seeds(store, [cf])

    assert len(seeds) == 1
    assert seeds[0].node_id == "m1"


def test_multiple_files_produce_one_seed_each():
    store = FakeStore({
        "Function": [
            _row("a", "auth.login", 5, 15, file_path="src/auth.py"),
            _row("b", "models.User", 1, 30, file_path="src/models.py"),
        ],
    })
    seeds = extract_seeds(store, [
        ChangedFile(path="src/auth.py", hunks=(Hunk(10, 12, "modified"),)),
        ChangedFile(path="src/models.py", hunks=(Hunk(5, 8, "modified"),)),
    ])
    assert {s.node_id for s in seeds} == {"a", "b"}

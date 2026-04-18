"""GraphStore — the single abstraction over the Kuzu embedded graph database.

All code that reads or writes the graph goes through this class.
Swapping the underlying store would only require changing this file.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import kuzu

from .schema import ALL_DDL, SCHEMA_VERSION

log = logging.getLogger(__name__)


class GraphStore:
    """Thread-safe (read) wrapper around a Kuzu embedded database.

    Usage::

        store = GraphStore(Path(".knowstack/graph.kuzu"))
        store.initialize_schema()
        store.upsert_nodes("Function", [{"node_id": "abc", "name": "auth", ...}])
        rows = store.cypher("MATCH (n:Function) RETURN n LIMIT 10")
        store.close()
    """

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = kuzu.Database(str(db_path))
        self._conn = kuzu.Connection(self._db)
        log.debug("Opened Kuzu database at %s", db_path)

    # ── Schema ───────────────────────────────────────────────────────────────

    def initialize_schema(self) -> None:
        """Create all node/relationship tables if they do not already exist."""
        for ddl in ALL_DDL:
            self._conn.execute(ddl.strip())
        self._set_meta("schema_version", str(SCHEMA_VERSION))
        log.debug("Schema initialized (version %d)", SCHEMA_VERSION)

    def schema_version(self) -> int:
        try:
            rows = self.cypher("MATCH (m:_SchemaMeta {key: 'schema_version'}) RETURN m.value")
            return int(rows[0]["m.value"]) if rows else 0
        except Exception:
            return 0

    def _set_meta(self, key: str, value: str) -> None:
        self._conn.execute(
            "MERGE (m:_SchemaMeta {key: $key}) SET m.value = $value",
            {"key": key, "value": value},
        )

    # ── Write ────────────────────────────────────────────────────────────────

    def upsert_nodes(self, table: str, rows: list[dict[str, Any]], batch_size: int = 500) -> int:
        """Upsert nodes into a node table. Returns total rows written."""
        if not rows:
            return 0
        # Build per-property SET clause from first row's keys (all rows share same schema)
        non_pk_cols = [k for k in rows[0].keys() if k != "node_id"]
        set_clause = ", ".join(f"n.{col} = row.{col}" for col in non_pk_cols)
        q = f"""
            UNWIND $rows AS row
            MERGE (n:{table} {{node_id: row.node_id}})
            SET {set_clause}
        """
        total = 0
        for i in range(0, len(rows), batch_size):
            batch = rows[i : i + batch_size]
            self._conn.execute(q, {"rows": batch})
            total += len(batch)
        log.debug("Upserted %d %s nodes", total, table)
        return total

    def upsert_edges(
        self,
        rel_type: str,
        src_table: str,
        dst_table: str,
        rows: list[dict[str, Any]],
        batch_size: int = 1000,
    ) -> int:
        """Upsert directed edges. Returns total rows written."""
        if not rows:
            return 0
        # Build per-property SET clause; src_id/dst_id are for MATCH only, not stored on r
        extra_cols = [k for k in rows[0].keys() if k not in ("src_id", "dst_id", "edge_id")]
        set_parts = [f"r.{col} = row.{col}" for col in extra_cols]
        set_clause = ("SET " + ", ".join(set_parts)) if set_parts else ""
        q = f"""
            UNWIND $rows AS row
            MATCH (src:{src_table} {{node_id: row.src_id}})
            MATCH (dst:{dst_table} {{node_id: row.dst_id}})
            MERGE (src)-[r:{rel_type} {{edge_id: row.edge_id}}]->(dst)
            {set_clause}
        """
        total = 0
        for i in range(0, len(rows), batch_size):
            batch = rows[i : i + batch_size]
            self._conn.execute(q, {"rows": batch})
            total += len(batch)
        log.debug("Upserted %d %s edges", total, rel_type)
        return total

    def delete_nodes_by_file(self, file_path: str) -> None:
        """Remove all nodes whose file_path matches (used during incremental re-index)."""
        for table in ["Function", "Method", "Class", "Interface", "TypeAlias",
                      "ApiEndpoint", "DbModel", "Test"]:
            self._conn.execute(
                f"MATCH (n:{table} {{file_path: $fp}}) DETACH DELETE n",
                {"fp": file_path},
            )
        self._conn.execute(
            "MATCH (n:File {file_path: $fp}) DETACH DELETE n",
            {"fp": file_path},
        )

    # ── Read ─────────────────────────────────────────────────────────────────

    def cypher(self, query: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Execute a Cypher query and return results as a list of dicts."""
        result = self._conn.execute(query, params or {})
        rows: list[dict[str, Any]] = []
        while result.has_next():
            row = result.get_next()
            # Kuzu returns rows as lists; zip with column names
            if not rows:
                cols = result.get_column_names()
            rows.append(dict(zip(cols, row)))  # type: ignore[possibly-undefined]
        return rows

    def node_count(self, table: str | None = None) -> int:
        if table:
            rows = self.cypher(f"MATCH (n:{table}) RETURN count(n) AS c")
        else:
            total = 0
            for t in ["File", "Directory", "Class", "Function", "Method",
                      "Interface", "TypeAlias", "ApiEndpoint", "DbModel", "Test", "ConfigFile"]:
                r = self.cypher(f"MATCH (n:{t}) RETURN count(n) AS c")
                total += r[0]["c"] if r else 0
            return total
        return rows[0]["c"] if rows else 0

    def edge_count(self, rel_type: str | None = None) -> int:
        if rel_type:
            rows = self.cypher(f"MATCH ()-[r:{rel_type}]->() RETURN count(r) AS c")
            return rows[0]["c"] if rows else 0
        total = 0
        for rt in ["CONTAINS", "IMPORTS", "CALLS", "INHERITS", "IMPLEMENTS",
                   "READS_FROM", "WRITES_TO", "TESTED_BY", "EXPOSES_ENDPOINT", "DEFINES"]:
            try:
                r = self.cypher(f"MATCH ()-[r:{rt}]->() RETURN count(r) AS c")
                total += r[0]["c"] if r else 0
            except Exception:
                pass
        return total

    # ── Serialization helpers ─────────────────────────────────────────────────

    @staticmethod
    def serialize_list(values: list[str]) -> str:
        """Serialize a list to a JSON string for storage in Kuzu STRING columns."""
        return json.dumps(values)

    @staticmethod
    def deserialize_list(raw: str | None) -> list[str]:
        if not raw:
            return []
        try:
            return json.loads(raw)
        except Exception:
            return []

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def close(self) -> None:
        self._conn.close()
        log.debug("Kuzu connection closed")

    def __enter__(self) -> "GraphStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

"""Graph-based retrieval via Cypher queries.

Handles FIND, DEPENDENTS, PATH, and IMPACT query types by compiling
the KnowStack DSL (or pre-compiled Cypher) against Kuzu.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from knowstack.graph import GraphStore
from knowstack.retrieval.ranker import RankedNode

log = logging.getLogger(__name__)

# ── DSL tokeniser ─────────────────────────────────────────────────────────────

_TOKEN_RE = re.compile(
    r'"[^"]*"'          # quoted string
    r"|'[^']*'"         # single-quoted string
    r"|[A-Za-z_][A-Za-z0-9_]*"  # identifier / keyword
    r"|\d+"             # integer
    r"|[=~><]"          # operators
    r"|\S"              # any other non-space
)

_NODE_TYPE_MAP = {
    "function": "Function", "method": "Method", "class": "Class",
    "file": "File", "interface": "Interface", "type": "TypeAlias",
    "endpoint": "ApiEndpoint", "model": "DbModel", "test": "Test",
    "config": "ConfigFile", "directory": "Directory",
    "*": None,
}


def _tokens(query: str) -> list[str]:
    return [m.group() for m in _TOKEN_RE.finditer(query)]


class GraphRetriever:
    """Translate KnowStack DSL queries to Cypher and execute them."""

    def __init__(self, store: GraphStore, default_limit: int = 20) -> None:
        self._store = store
        self._limit = default_limit

    # ── Public interface ──────────────────────────────────────────────────────

    def find(self, node_type: str | None, filters: list[tuple[str, str, str]], limit: int | None = None, repo_id: str | None = None) -> list[RankedNode]:
        """Execute a FIND query."""
        lim = limit or self._limit
        table = _NODE_TYPE_MAP.get((node_type or "*").lower()) if node_type else None

        where_clauses: list[str] = []
        params: dict[str, Any] = {"limit": lim}

        if repo_id:
            where_clauses.append("n.repo_id = $repo_id")
            params["repo_id"] = repo_id

        for field, op, value in filters:
            val = value.strip("\"'")
            if field == "tag":
                where_clauses.append(f"n.tags CONTAINS $tag_{len(params)}")
                params[f"tag_{len(params)}"] = f'"{val}"'
            elif field == "file":
                where_clauses.append(f"n.file_path CONTAINS $file_{len(params)}")
                params[f"file_{len(params)}"] = val
            elif field == "name":
                if op == "=":
                    where_clauses.append(f"n.name = $name_{len(params)}")
                    params[f"name_{len(params)}"] = val
                else:
                    where_clauses.append(f"n.name CONTAINS $name_{len(params)}")
                    params[f"name_{len(params)}"] = val
            elif field == "fqn":
                where_clauses.append(f"n.fqn CONTAINS $fqn_{len(params)}")
                params[f"fqn_{len(params)}"] = val
            elif field == "language":
                where_clauses.append(f"n.language = $lang_{len(params)}")
                params[f"lang_{len(params)}"] = val

        match_clause = f"MATCH (n:{table})" if table else "MATCH (n)"
        where = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        cypher = f"{match_clause} {where} RETURN n ORDER BY n.importance_score DESC LIMIT $limit"

        try:
            rows = self._store.cypher(cypher, params)
            return [RankedNode.from_graph_row(self._flatten_node_row(r)) for r in rows]
        except Exception as exc:
            log.warning("FIND query failed: %s — %s", cypher, exc)
            return []

    def dependents(self, target: str, depth: int = 3, limit: int | None = None, repo_id: str | None = None) -> list[RankedNode]:
        """Find all nodes that depend on target (reverse reachability)."""
        lim = limit or self._limit
        node_id = self._resolve_target(target, repo_id=repo_id)
        if not node_id:
            return []

        cypher = """
            MATCH (n {node_id: $id})<-[*1..$depth]-(dep)
            RETURN DISTINCT dep
            ORDER BY dep.importance_score DESC
            LIMIT $limit
        """
        try:
            rows = self._store.cypher(cypher, {"id": node_id, "depth": depth, "limit": lim})
            return [RankedNode.from_graph_row(self._flatten_node_row(r)) for r in rows]
        except Exception as exc:
            log.warning("DEPENDENTS query failed: %s", exc)
            return []

    def impact(self, target: str, depth: int = 3, limit: int | None = None, repo_id: str | None = None) -> list[RankedNode]:
        """Impact analysis: what could break if target changes."""
        return self.dependents(target, depth=depth, limit=limit, repo_id=repo_id)

    def path(self, src: str, dst: str, max_depth: int = 6, repo_id: str | None = None) -> list[list[RankedNode]]:
        """Find shortest paths between two symbols."""
        src_id = self._resolve_target(src, repo_id=repo_id)
        dst_id = self._resolve_target(dst, repo_id=repo_id)
        if not src_id or not dst_id:
            return []

        cypher = """
            MATCH p = shortestPath((s {node_id: $src})-[*1..$depth]-(d {node_id: $dst}))
            RETURN nodes(p) AS path_nodes
            LIMIT 3
        """
        try:
            rows = self._store.cypher(cypher, {"src": src_id, "dst": dst_id, "depth": max_depth})
            paths: list[list[RankedNode]] = []
            for row in rows:
                path_nodes = row.get("path_nodes") or []
                paths.append([
                    RankedNode.from_graph_row(self._flatten_node_row({"n": n}))
                    for n in path_nodes
                ])
            return paths
        except Exception as exc:
            log.warning("PATH query failed: %s", exc)
            return []

    def neighbourhood(self, target: str, depth: int = 2, limit: int | None = None) -> list[RankedNode]:
        """Return the subgraph around a node."""
        lim = limit or self._limit
        node_id = self._resolve_target(target)
        if not node_id:
            return []

        cypher = """
            MATCH (n {node_id: $id})-[*1..$depth]-(neighbor)
            RETURN DISTINCT neighbor
            ORDER BY neighbor.importance_score DESC
            LIMIT $limit
        """
        try:
            rows = self._store.cypher(cypher, {"id": node_id, "depth": depth, "limit": lim})
            return [RankedNode.from_graph_row(self._flatten_node_row(r)) for r in rows]
        except Exception as exc:
            log.warning("Neighbourhood query failed: %s", exc)
            return []

    # ── DSL parser ────────────────────────────────────────────────────────────

    def execute_dsl(self, query: str, repo_id: str | None = None) -> list[RankedNode]:
        """Parse and execute a KnowStack DSL query string."""
        toks = _tokens(query.strip())
        if not toks:
            return []

        keyword = toks[0].upper()
        if keyword == "FIND":
            return self._parse_find(toks[1:], repo_id=repo_id)
        elif keyword == "DEPENDENTS":
            target = toks[1].strip("\"'") if len(toks) > 1 else ""
            return self.dependents(target, repo_id=repo_id)
        elif keyword == "IMPACT":
            target = toks[1].strip("\"'") if len(toks) > 1 else ""
            depth = int(toks[3]) if len(toks) > 3 and toks[2].upper() == "DEPTH" else 3
            return self.impact(target, depth=depth, repo_id=repo_id)
        elif keyword == "PATH":
            return self._parse_path(toks[1:], repo_id=repo_id)
        else:
            log.warning("Unknown DSL keyword: %s", keyword)
            return []

    def _parse_find(self, toks: list[str], repo_id: str | None = None) -> list[RankedNode]:
        node_type: str | None = None
        filters: list[tuple[str, str, str]] = []
        limit = self._limit

        i = 0
        if i < len(toks) and toks[i].lower() in _NODE_TYPE_MAP:
            node_type = toks[i]
            i += 1

        while i < len(toks):
            tok = toks[i].upper()
            if tok == "WHERE" and i + 3 < len(toks):
                i += 1
                while i + 3 <= len(toks):
                    field, op, value = toks[i], toks[i + 1], toks[i + 2]
                    filters.append((field.lower(), op, value))
                    i += 3
                    if i < len(toks) and toks[i].upper() == "AND":
                        i += 1
                    else:
                        break
            elif tok == "LIMIT" and i + 1 < len(toks):
                limit = int(toks[i + 1])
                i += 2
            else:
                i += 1

        return self.find(node_type, filters, limit=limit, repo_id=repo_id)

    def _parse_path(self, toks: list[str], repo_id: str | None = None) -> list[RankedNode]:
        # PATH FROM "src" TO "dst"
        src = dst = ""
        i = 0
        while i < len(toks):
            tok = toks[i].upper()
            if tok == "FROM" and i + 1 < len(toks):
                src = toks[i + 1].strip("\"'")
                i += 2
            elif tok == "TO" and i + 1 < len(toks):
                dst = toks[i + 1].strip("\"'")
                i += 2
            else:
                i += 1
        paths = self.path(src, dst, repo_id=repo_id)
        return [node for path in paths for node in path]

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _resolve_target(self, target: str, repo_id: str | None = None) -> str | None:
        """Resolve a symbol name or FQN to a node_id."""
        if not target:
            return None
        repo_clause = " AND n.repo_id = $rid" if repo_id else ""
        base_params: dict[str, Any] = {"t": target}
        if repo_id:
            base_params["rid"] = repo_id
        rows = self._store.cypher(
            f"MATCH (n) WHERE (n.fqn = $t OR n.name = $t){repo_clause} RETURN n.node_id AS id LIMIT 1",
            base_params,
        )
        if rows:
            return str(rows[0]["id"])
        rows = self._store.cypher(
            f"MATCH (n) WHERE (n.fqn CONTAINS $t OR n.name CONTAINS $t){repo_clause} "
            "RETURN n.node_id AS id ORDER BY n.importance_score DESC LIMIT 1",
            base_params,
        )
        return str(rows[0]["id"]) if rows else None

    @staticmethod
    def _flatten_node_row(row: dict[str, Any]) -> dict[str, Any]:
        """Kuzu returns node as an object; flatten its properties."""
        flat: dict[str, Any] = {}
        for k, v in row.items():
            if hasattr(v, "__dict__"):  # Kuzu Node object
                # Preserve the node's table name as node_type before flattening
                table_name = getattr(v, "_label", None) or type(v).__name__
                flat["node_type"] = table_name
                for prop_k, prop_v in v.__dict__.items():
                    if not prop_k.startswith("_"):
                        flat[prop_k] = prop_v
            elif isinstance(v, dict):
                flat.update(v)
            else:
                flat[k.lstrip("n.")] = v
        return flat

"""Stage 5 — GraphWriter: upsert nodes and edges into Kuzu.

Converts Pydantic node/edge models into the flat dict representation
required by Kuzu's UNWIND MERGE queries, with proper type coercion
(lists → JSON strings, Optional[str] → empty string, etc.).
"""
from __future__ import annotations

import json
import logging
from typing import Any

from knowstack.graph.store import GraphStore
from knowstack.ingestion.normalizer import NormalizedGraph
from knowstack.models.edges import (
    BaseEdge, CallsEdge, ContainsEdge, DefinesEdge, ExposesEndpointEdge,
    ImportsEdge, InheritsEdge, ImplementsEdge, ReadsFromEdge,
    TestedByEdge, WritesToEdge,
)
from knowstack.models.enums import EdgeType, NodeType
from knowstack.models.nodes import (
    ApiEndpointNode, BaseNode, ClassNode, ConfigFileNode, DbModelNode,
    DirectoryNode, FileNode, FunctionNode, InterfaceNode, MethodNode,
    TestNode, TypeAliasNode,
)

log = logging.getLogger(__name__)

# Map NodeType → (Kuzu table name, row-builder function)
_NODE_TABLE_MAP: dict[NodeType, str] = {
    NodeType.FILE: "File",
    NodeType.DIRECTORY: "Directory",
    NodeType.CLASS: "Class",
    NodeType.FUNCTION: "Function",
    NodeType.METHOD: "Method",
    NodeType.INTERFACE: "Interface",
    NodeType.TYPE_ALIAS: "TypeAlias",
    NodeType.API_ENDPOINT: "ApiEndpoint",
    NodeType.DB_MODEL: "DbModel",
    NodeType.TEST: "Test",
    NodeType.CONFIG_FILE: "ConfigFile",
}

_EDGE_TABLE_MAP: dict[EdgeType, tuple[str, str, str]] = {
    # edge_type → (rel_table, src_table, dst_table)
    EdgeType.CONTAINS: ("CONTAINS", "File", "Function"),  # overridden dynamically
    EdgeType.IMPORTS: ("IMPORTS", "File", "File"),
    EdgeType.CALLS: ("CALLS", "Function", "Function"),
    EdgeType.INHERITS: ("INHERITS", "Class", "Class"),
    EdgeType.IMPLEMENTS: ("IMPLEMENTS", "Class", "Interface"),
    EdgeType.READS_FROM: ("READS_FROM", "Function", "DbModel"),
    EdgeType.WRITES_TO: ("WRITES_TO", "Function", "DbModel"),
    EdgeType.TESTED_BY: ("TESTED_BY", "Function", "Test"),
    EdgeType.EXPOSES_ENDPOINT: ("EXPOSES_ENDPOINT", "Function", "ApiEndpoint"),
    EdgeType.DEFINES: ("DEFINES", "File", "Function"),
}


class GraphWriter:
    def __init__(self, store: GraphStore, repo_id: str = "") -> None:
        self._store = store
        self._repo_id = repo_id

    def write(self, graph: NormalizedGraph) -> dict[str, int]:
        """Write all nodes and edges. Returns counts per table."""
        counts: dict[str, int] = {}

        # Group nodes by table
        by_table: dict[str, list[dict[str, Any]]] = {}
        for node in graph.nodes.values():
            table = _NODE_TABLE_MAP.get(node.node_type)
            if table is None:
                continue
            row = self._node_to_row(node)
            by_table.setdefault(table, []).append(row)

        for table, rows in by_table.items():
            n = self._store.upsert_nodes(table, rows)
            counts[table] = n

        # Group edges and write with src/dst table hints
        counts.update(self._write_edges(graph))

        total_nodes = sum(counts.get(t, 0) for t in _NODE_TABLE_MAP.values())
        total_edges = sum(v for k, v in counts.items() if k not in _NODE_TABLE_MAP.values())
        log.info("Wrote %d nodes, %d edges to graph", total_nodes, total_edges)
        return counts

    def _write_edges(self, graph: NormalizedGraph) -> dict[str, int]:
        """Write edges with correct src/dst table resolution."""
        counts: dict[str, int] = {}
        node_table_lookup = {
            nid: _NODE_TABLE_MAP.get(n.node_type, "Function")
            for nid, n in graph.nodes.items()
        }

        # Group by (rel_type, src_table, dst_table)
        grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}

        for edge in graph.edges:
            rel_table, _, _ = _EDGE_TABLE_MAP.get(
                edge.edge_type, ("CALLS", "Function", "Function")
            )
            src_table = node_table_lookup.get(edge.src_id, "Function")
            dst_table = node_table_lookup.get(edge.dst_id, "Function")
            key = (rel_table, src_table, dst_table)
            row = self._edge_to_row(edge)
            grouped.setdefault(key, []).append(row)

        for (rel_type, src_table, dst_table), rows in grouped.items():
            try:
                n = self._store.upsert_edges(rel_type, src_table, dst_table, rows)
                counts[rel_type] = counts.get(rel_type, 0) + n
            except Exception as exc:
                log.warning("Failed to write %s edges (%s→%s): %s", rel_type, src_table, dst_table, exc)

        return counts

    # ── Row builders ─────────────────────────────────────────────────────────

    def _node_to_row(self, node: BaseNode) -> dict[str, Any]:
        """Convert a node model to a flat dict for Kuzu UNWIND."""
        row: dict[str, Any] = {
            "node_id": node.node_id,
            "name": node.name,
            "fqn": node.fqn,
            "language": str(node.language),
            "repo_id": self._repo_id or node.repo_id,
            "docstring": node.docstring or "",
            "tags": json.dumps(node.tags),
            "change_frequency": node.change_frequency,
            "centrality_score": node.centrality_score,
            "importance_score": node.importance_score,
            "last_modified_commit": node.last_modified_commit or "",
        }

        span = node.source_span
        if span:
            row["file_path"] = span.file_path
            row["start_line"] = span.start_line
            row["end_line"] = span.end_line
        else:
            row["file_path"] = getattr(node, "file_path", "")
            # File/Directory nodes have no start_line/end_line columns in the schema
            if not isinstance(node, (FileNode, DirectoryNode)):
                row["start_line"] = 0
                row["end_line"] = 0

        # Type-specific fields
        if isinstance(node, FileNode):
            row.update({
                "extension": node.extension,
                "size_bytes": node.size_bytes,
                "content_hash": node.content_hash,
            })
        elif isinstance(node, DirectoryNode):
            row["dir_path"] = node.dir_path
        elif isinstance(node, ClassNode):
            row.update({
                "is_abstract": node.is_abstract,
                "decorator_names": json.dumps(node.decorator_names),
                "bases": json.dumps(node.bases),
            })
        elif isinstance(node, (FunctionNode, MethodNode)):
            row.update({
                "signature": node.signature,
                "is_async": node.is_async,
                "is_generator": node.is_generator,
                "return_type": node.return_type or "",
                "decorator_names": json.dumps(node.decorator_names),
                "parameter_names": json.dumps(node.parameter_names),
            })
            if isinstance(node, MethodNode):
                row.update({
                    "class_fqn": node.class_fqn,
                    "is_static": node.is_static,
                    "is_classmethod": node.is_classmethod,
                    "is_property": node.is_property,
                })
        elif isinstance(node, InterfaceNode):
            row["extends"] = json.dumps(node.extends)
        elif isinstance(node, TypeAliasNode):
            row["type_expression"] = node.type_expression
        elif isinstance(node, ApiEndpointNode):
            row.update({
                "http_method": node.http_method,
                "path_pattern": node.path_pattern,
                "framework": node.framework,
            })
        elif isinstance(node, DbModelNode):
            row.update({
                "table_name": node.table_name or "",
                "orm_framework": node.orm_framework,
                "fields": json.dumps(node.fields),
            })
        elif isinstance(node, TestNode):
            row.update({
                "test_framework": node.test_framework,
                "is_parametrized": node.is_parametrized,
                "targets": json.dumps(node.targets),
            })
        elif isinstance(node, ConfigFileNode):
            row["format"] = node.format

        return row

    def _edge_to_row(self, edge: BaseEdge) -> dict[str, Any]:
        row: dict[str, Any] = {
            "edge_id": edge.edge_id,
            "src_id": edge.src_id,
            "dst_id": edge.dst_id,
            "confidence": edge.confidence,
        }
        if isinstance(edge, ImportsEdge):
            row["imported_names"] = json.dumps(edge.imported_names)
            row["is_dynamic"] = edge.is_dynamic
        elif isinstance(edge, CallsEdge):
            row["is_conditional"] = edge.is_conditional
            row["is_dynamic"] = edge.is_dynamic
        elif isinstance(edge, InheritsEdge):
            row["is_mixin"] = edge.is_mixin
        elif isinstance(edge, (ReadsFromEdge, WritesToEdge)):
            row["access_pattern"] = edge.access_pattern or ""
        return row

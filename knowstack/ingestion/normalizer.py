"""Stage 3 — Normalizer: resolve cross-file references and deduplicate edges.

After parsing, edges have unresolved dst_id values (raw import paths or
callee name strings). The Normalizer builds a symbol table from all emitted
nodes and resolves those placeholders to stable node_ids.

Unresolvable references become stubs marked with confidence=0.4.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from knowstack.ingestion.parsers.base import ParseResult
from knowstack.models.edges import BaseEdge, ImportsEdge
from knowstack.models.nodes import BaseNode

log = logging.getLogger(__name__)


@dataclass
class NormalizedGraph:
    """The merged, resolved graph produced by the Normalizer."""

    nodes: dict[str, BaseNode] = field(default_factory=dict)  # node_id → node
    edges: list[BaseEdge] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)


class Normalizer:
    """Merge ParseResults and resolve cross-file references."""

    def normalize(self, results: list[ParseResult]) -> NormalizedGraph:
        graph = NormalizedGraph()

        # Pass 1: collect all nodes
        for pr in results:
            for node in pr.nodes:
                if node.node_id in graph.nodes:
                    log.debug("Duplicate node_id %s — keeping first", node.node_id)
                else:
                    graph.nodes[node.node_id] = node

        # Build lookup indices
        fqn_to_id: dict[str, str] = {n.fqn: n.node_id for n in graph.nodes.values()}
        name_to_ids: dict[str, list[str]] = {}
        for n in graph.nodes.values():
            name_to_ids.setdefault(n.name, []).append(n.node_id)

        # Build file path index (rel_path → node_id for File nodes)
        file_path_to_id: dict[str, str] = {}
        for n in graph.nodes.values():
            fp = getattr(n, "file_path", None)
            if fp:
                file_path_to_id[fp] = n.node_id

        # Pass 2: resolve edges
        seen_edges: set[str] = set()
        for pr in results:
            for edge in pr.edges:
                resolved = self._resolve_edge(
                    edge, fqn_to_id, name_to_ids, file_path_to_id, graph
                )
                if resolved is None:
                    continue
                if resolved.edge_id in seen_edges:
                    continue
                seen_edges.add(resolved.edge_id)
                graph.edges.append(resolved)

        log.info(
            "Normalized graph: %d nodes, %d edges (%d errors)",
            graph.node_count,
            graph.edge_count,
            len(graph.errors),
        )
        return graph

    def _resolve_edge(
        self,
        edge: BaseEdge,
        fqn_to_id: dict[str, str],
        name_to_ids: dict[str, list[str]],
        file_path_to_id: dict[str, str],
        graph: NormalizedGraph,
    ) -> BaseEdge | None:
        """Resolve src/dst placeholders to actual node_ids."""
        src_id = edge.src_id
        dst_id = edge.dst_id

        # Src is always a real node_id from the parse phase
        if src_id not in graph.nodes:
            return None  # Drop edge with unknown src

        # Dst may be a placeholder (FQN string, import path, callee name)
        if dst_id in graph.nodes:
            return edge  # Already resolved

        # Try FQN lookup
        if dst_id in fqn_to_id:
            return edge.model_copy(update={"dst_id": fqn_to_id[dst_id]})

        # For imports: convert module path (dot-separated) to file path
        if isinstance(edge, ImportsEdge):
            file_path = dst_id.replace(".", "/") + ".py"
            if file_path in file_path_to_id:
                return edge.model_copy(update={"dst_id": file_path_to_id[file_path]})
            # TypeScript: try without extension
            for ext in (".ts", ".tsx", ".js", ".jsx"):
                ts_path = dst_id.replace(".", "/") + ext
                if ts_path in file_path_to_id:
                    return edge.model_copy(update={"dst_id": file_path_to_id[ts_path]})
            # External dependency — drop (we don't index node_modules)
            return None

        # Try name lookup (ambiguous — keep with lower confidence)
        candidates = name_to_ids.get(dst_id, [])
        if len(candidates) == 1:
            return edge.model_copy(
                update={"dst_id": candidates[0], "confidence": min(edge.confidence, 0.7)}
            )

        # Unresolvable — drop with a debug trace so the gap is visible
        log.debug(
            "Dropping unresolvable edge %s (%s → %s)",
            edge.edge_type,
            edge.src_id,
            dst_id,
        )
        return None

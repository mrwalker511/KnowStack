"""Node relevance ranking.

Combines five signals into a single [0, 1] relevance score:

    score = 0.35 * semantic_score       # cosine similarity from vector search
          + 0.25 * centrality_score     # PageRank in CALLS+IMPORTS graph
          + 0.20 * name_match           # exact/fuzzy FQN match to query terms
          + 0.10 * recency_score        # 1 / (1 + days_since_last_change)
          + 0.10 * path_proximity       # 1 / (graph_distance + 1)

All signals are normalised to [0, 1] before combination.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RankedNode:
    node_id: str
    fqn: str
    name: str
    node_type: str
    file_path: str
    language: str
    repo_id: str = ""
    signature: str = ""
    docstring: str = ""
    start_line: int = 0
    end_line: int = 0
    importance_score: float = 0.0

    # Ranking signals
    semantic_score: float = 0.0
    centrality_score: float = 0.0
    name_match_score: float = 0.0
    recency_score: float = 0.0
    path_proximity_score: float = 0.0

    # Populated by context packer
    related_edges: list[dict[str, Any]] = field(default_factory=list)

    @property
    def final_score(self) -> float:
        return (
            0.35 * self.semantic_score
            + 0.25 * self.centrality_score
            + 0.20 * self.name_match_score
            + 0.10 * self.recency_score
            + 0.10 * self.path_proximity_score
        )

    @classmethod
    def from_graph_row(cls, row: dict[str, Any]) -> "RankedNode":
        """Build a RankedNode from a Kuzu query result row."""
        # Kuzu returns node properties prefixed with "n."
        def g(key: str) -> Any:
            return row.get(f"n.{key}") or row.get(key) or ""

        cs = float(g("centrality_score") or 0)
        return cls(
            node_id=str(g("node_id")),
            fqn=str(g("fqn")),
            name=str(g("name")),
            node_type=str(g("node_type") or ""),
            file_path=str(g("file_path")),
            language=str(g("language")),
            repo_id=str(g("repo_id") or ""),
            signature=str(g("signature") or ""),
            docstring=str(g("docstring") or ""),
            start_line=int(g("start_line") or 0),
            end_line=int(g("end_line") or 0),
            importance_score=float(g("importance_score") or 0),
            centrality_score=cs,
        )


class Ranker:
    """Score and sort a mixed set of candidate nodes."""

    def rank(
        self,
        nodes: list[RankedNode],
        query_terms: list[str] | None = None,
    ) -> list[RankedNode]:
        """Return nodes sorted by final_score descending."""
        if not nodes:
            return []

        # Normalise centrality across this result set
        max_centrality = max((n.centrality_score for n in nodes), default=1.0) or 1.0

        for node in nodes:
            # Normalised centrality
            node.centrality_score = node.centrality_score / max_centrality

            # Name match
            if query_terms:
                node.name_match_score = self._name_match(node, query_terms)

            # Recency (change_frequency is 0-1; map to recency proxy)
            node.recency_score = node.importance_score  # already incorporates freq

        return sorted(nodes, key=lambda n: n.final_score, reverse=True)

    @staticmethod
    def _name_match(node: RankedNode, terms: list[str]) -> float:
        """Exact/substring name match score (0 or 1)."""
        combined = (node.fqn + " " + node.name).lower()
        hits = sum(1 for t in terms if t.lower() in combined)
        return min(1.0, hits / max(len(terms), 1))

"""Hybrid retrieval: fuse graph and vector results via Reciprocal Rank Fusion.

RRF score: sum(1 / (k + rank_i)) for each result list i.
k=60 is a well-established constant that reduces the impact of high ranks.
"""
from __future__ import annotations

from knowstack.retrieval.ranker import RankedNode

_K = 60


class HybridRetriever:
    def fuse(
        self,
        graph_results: list[RankedNode],
        vector_results: list[RankedNode],
        top_k: int = 20,
    ) -> list[RankedNode]:
        """Merge two ranked lists using Reciprocal Rank Fusion."""
        scores: dict[str, float] = {}
        node_map: dict[str, RankedNode] = {}

        for rank, node in enumerate(graph_results):
            scores[node.node_id] = scores.get(node.node_id, 0) + 1 / (_K + rank + 1)
            node_map[node.node_id] = node

        for rank, node in enumerate(vector_results):
            scores[node.node_id] = scores.get(node.node_id, 0) + 1 / (_K + rank + 1)
            if node.node_id not in node_map:
                node_map[node.node_id] = node
            else:
                # Merge semantic score into the graph node
                existing = node_map[node.node_id]
                node_map[node.node_id] = RankedNode(
                    **{
                        **existing.__dict__,
                        "semantic_score": max(existing.semantic_score, node.semantic_score),
                    }
                )

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [node_map[nid] for nid, _ in ranked[:top_k]]

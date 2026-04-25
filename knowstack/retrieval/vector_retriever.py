"""Semantic vector retrieval via ChromaDB."""
from __future__ import annotations

import logging
from typing import Any

from knowstack.ingestion.embedder import Embedder
from knowstack.retrieval.ranker import RankedNode

log = logging.getLogger(__name__)


class VectorRetriever:
    def __init__(self, embedder: Embedder) -> None:
        self._embedder = embedder

    def search(
        self,
        query: str,
        top_k: int = 20,
        node_type_filter: str | None = None,
        language_filter: str | None = None,
        repo_id: str | None = None,
    ) -> list[RankedNode]:
        where: dict[str, Any] = {}
        if repo_id:
            where["repo_id"] = repo_id
        if node_type_filter:
            where["node_type"] = node_type_filter
        if language_filter:
            where["language"] = language_filter

        hits = self._embedder.search(query, top_k=top_k, where=where or None)
        nodes: list[RankedNode] = []
        for hit in hits:
            node = RankedNode(
                node_id=hit["node_id"],
                fqn=str(hit.get("fqn") or ""),
                name=str(hit.get("fqn", "").split(".")[-1]),
                node_type=str(hit.get("node_type") or ""),
                file_path=str(hit.get("file_path") or ""),
                language=str(hit.get("language") or ""),
                importance_score=float(hit.get("importance_score") or 0),
                semantic_score=float(hit.get("semantic_score") or 0),
            )
            nodes.append(node)
        return nodes

"""QueryEngine — the single external-facing retrieval API.

All CLI commands, the HTTP server, and LLM integrations go through here.
It routes queries to the appropriate retrieval strategy and returns
structured results with token-efficient context packing.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from knowstack.config.schema import KnowStackConfig
from knowstack.graph.store import GraphStore
from knowstack.ingestion.embedder import Embedder
from knowstack.retrieval.context_packer import ContextPacker
from knowstack.retrieval.graph_retriever import GraphRetriever
from knowstack.retrieval.hybrid_retriever import HybridRetriever
from knowstack.retrieval.ranker import RankedNode, Ranker
from knowstack.retrieval.vector_retriever import VectorRetriever

log = logging.getLogger(__name__)


class QueryIntent(StrEnum):
    STRUCTURAL = "structural"   # DSL query / exact graph traversal
    SEMANTIC = "semantic"       # Embedding similarity
    HYBRID = "hybrid"           # Graph + embedding fusion
    IMPACT = "impact"           # Reverse reachability
    PATH = "path"               # Shortest path between two nodes
    NL = "nl"                   # Natural language → auto-routed


@dataclass
class QueryResult:
    query: str
    intent: QueryIntent
    nodes: list[RankedNode] = field(default_factory=list)
    paths: list[list[RankedNode]] = field(default_factory=list)
    context: str = ""  # Packed context for LLM consumption
    error: str = ""

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    def as_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "intent": str(self.intent),
            "node_count": self.node_count,
            "nodes": [
                {
                    "fqn": n.fqn,
                    "node_type": n.node_type,
                    "file_path": n.file_path,
                    "score": round(n.final_score, 4),
                    "signature": n.signature,
                }
                for n in self.nodes
            ],
            "error": self.error,
        }


class QueryEngine:
    """Unified query interface for the KnowStack knowledge graph."""

    def __init__(self, config: KnowStackConfig) -> None:
        self._config = config
        self._store = GraphStore(config.db_path)
        self._embedder = Embedder(
            str(config.vector_db_path),
            model_name=config.embedding_model,
            device=config.embedding_device,
        )
        self._graph = GraphRetriever(self._store, default_limit=config.default_top_k)
        self._vector = VectorRetriever(self._embedder)
        self._hybrid = HybridRetriever()
        self._ranker = Ranker()
        self._packer = ContextPacker(max_tokens=config.context_max_tokens)

    # ── Public API ────────────────────────────────────────────────────────────

    def query_dsl(self, dsl: str, repo_id: str | None = None) -> QueryResult:
        """Execute a KnowStack DSL query (FIND / DEPENDENTS / IMPACT / PATH)."""
        try:
            nodes = self._graph.execute_dsl(dsl, repo_id=repo_id)
            ranked = self._ranker.rank(nodes)
            context = self._packer.pack(ranked, query=dsl)
            return QueryResult(query=dsl, intent=QueryIntent.STRUCTURAL,
                               nodes=ranked, context=context)
        except Exception as exc:
            log.error("DSL query error: %s", exc)
            return QueryResult(query=dsl, intent=QueryIntent.STRUCTURAL, error=str(exc))

    def query_semantic(self, text: str, top_k: int | None = None) -> QueryResult:
        """Semantic similarity search over embedded nodes."""
        k = top_k or self._config.default_top_k
        try:
            nodes = self._vector.search(text, top_k=k)
            ranked = self._ranker.rank(nodes, query_terms=text.split())
            context = self._packer.pack(ranked, query=text)
            return QueryResult(query=text, intent=QueryIntent.SEMANTIC,
                               nodes=ranked, context=context)
        except Exception as exc:
            log.error("Semantic query error: %s", exc)
            return QueryResult(query=text, intent=QueryIntent.SEMANTIC, error=str(exc))

    def query_hybrid(self, text: str, top_k: int | None = None) -> QueryResult:
        """Hybrid: graph structural + semantic vector fusion."""
        k = top_k or self._config.default_top_k
        graph_results: list[RankedNode] = []
        vec_results: list[RankedNode] = []

        try:
            graph_results = self._graph.find(None, [], limit=k)
        except Exception as exc:
            log.warning("Hybrid query: graph retriever failed, continuing with vectors only: %s", exc)

        try:
            vec_results = self._vector.search(text, top_k=k)
        except Exception as exc:
            log.warning("Hybrid query: vector retriever failed, continuing with graph only: %s", exc)

        if not graph_results and not vec_results:
            return QueryResult(query=text, intent=QueryIntent.HYBRID,
                               error="Both retrievers failed — check that the index has been built.")
        try:
            fused = self._hybrid.fuse(graph_results, vec_results, top_k=k)
            ranked = self._ranker.rank(fused, query_terms=text.split())
            context = self._packer.pack(ranked, query=text)
            return QueryResult(query=text, intent=QueryIntent.HYBRID,
                               nodes=ranked, context=context)
        except Exception as exc:
            log.error("Hybrid query fusion error: %s", exc)
            return QueryResult(query=text, intent=QueryIntent.HYBRID, error=str(exc))

    def query_impact(self, target: str, depth: int = 3) -> QueryResult:
        """Impact analysis: what depends on target."""
        try:
            nodes = self._graph.dependents(target, depth=depth)
            ranked = self._ranker.rank(nodes)
            context = self._packer.pack(ranked, query=f"Impact of changing: {target}")
            return QueryResult(query=target, intent=QueryIntent.IMPACT,
                               nodes=ranked, context=context)
        except Exception as exc:
            return QueryResult(query=target, intent=QueryIntent.IMPACT, error=str(exc))

    def query_path(self, src: str, dst: str, max_depth: int = 6) -> QueryResult:
        """Find paths between two symbols."""
        try:
            paths = self._graph.path(src, dst, max_depth=max_depth)
            all_nodes = [n for path in paths for n in path]
            context = self._packer.pack(all_nodes, query=f"Path: {src} → {dst}")
            return QueryResult(query=f"{src} -> {dst}", intent=QueryIntent.PATH,
                               nodes=all_nodes, paths=paths, context=context)
        except Exception as exc:
            return QueryResult(query=f"{src} -> {dst}", intent=QueryIntent.PATH, error=str(exc))

    def query_nl(self, question: str) -> QueryResult:
        """Natural language question → auto-routed query (Phase 3: requires LLM config)."""
        try:
            from knowstack.nl.query_builder import NLQueryBuilder
            builder = NLQueryBuilder(self._config, self._store)
            intent, dsl = builder.build(question)
            if intent == QueryIntent.SEMANTIC or not dsl:
                return self.query_semantic(question)
            return self.query_dsl(dsl)
        except ImportError:
            # NL layer not yet available — fall back to semantic
            log.debug("NL layer not available, falling back to semantic search")
            return self.query_semantic(question)
        except Exception as exc:
            return QueryResult(query=question, intent=QueryIntent.NL, error=str(exc))

    def pack_context(self, result: QueryResult, max_tokens: int | None = None) -> str:
        """Re-pack a query result with a different token budget."""
        packer = ContextPacker(max_tokens or self._config.context_max_tokens)
        return packer.pack(result.nodes, query=result.query)

    def close(self) -> None:
        self._store.close()

    def __enter__(self) -> QueryEngine:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

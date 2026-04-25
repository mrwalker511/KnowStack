"""Stage 6 — Embedder: encode nodes and store in ChromaDB.

Each node is represented as a short text document (type + fqn + signature +
docstring + file path) and embedded with a local sentence-transformers model.
ChromaDB stores vectors alongside metadata for pre-filtered ANN search.
"""
from __future__ import annotations

import logging
from typing import Any

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

from knowstack.graph.store import GraphStore
from knowstack.models.enums import NodeType

log = logging.getLogger(__name__)

_COLLECTION_NAME = "nodes"

# Node types we embed — skip pure structural containers like Directory
_EMBEDDABLE_TYPES = {
    NodeType.FILE, NodeType.CLASS, NodeType.FUNCTION, NodeType.METHOD,
    NodeType.INTERFACE, NodeType.TYPE_ALIAS, NodeType.API_ENDPOINT,
    NodeType.DB_MODEL, NodeType.TEST, NodeType.CONFIG_FILE,
}

_NODE_TABLES = ["File", "Class", "Function", "Method", "Interface",
                "TypeAlias", "ApiEndpoint", "DbModel", "Test", "ConfigFile"]


class Embedder:
    def __init__(
        self,
        vector_db_path: str,
        model_name: str = "BAAI/bge-small-en-v1.5",
        device: str = "cpu",
        batch_size: int = 64,
        embed_limit: int = 0,
    ) -> None:
        self._batch_size = batch_size
        self._embed_limit = embed_limit
        log.info("Loading embedding model: %s (device=%s)", model_name, device)
        self._model = SentenceTransformer(model_name, device=device)

        self._client = chromadb.PersistentClient(
            path=vector_db_path,
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def embed_all(self, store: GraphStore) -> int:
        """Embed all embeddable nodes from the graph store. Returns count embedded."""
        total = 0
        for table in _NODE_TABLES:
            try:
                limit_clause = f" LIMIT {self._embed_limit}" if self._embed_limit > 0 else ""
                rows = store.cypher(
                    f"MATCH (n:{table}) RETURN n.node_id AS id, n.fqn AS fqn, "
                    f"n.name AS name, n.language AS lang, n.file_path AS file_path, "
                    f"n.docstring AS doc, n.importance_score AS score, "
                    f"n.repo_id AS repo_id{limit_clause}"
                )
            except Exception as exc:
                log.warning("Failed to fetch %s nodes for embedding: %s", table, exc)
                continue

            for i in range(0, len(rows), self._batch_size):
                batch = rows[i : i + self._batch_size]
                total += self._embed_batch(table, batch)

        log.info("Embedded %d nodes into ChromaDB", total)
        return total

    def embed_by_files(self, store: GraphStore, file_paths: list[str]) -> int:
        """Embed only nodes whose file_path is in the given set. Returns count embedded."""
        total = 0
        fps = list(file_paths)
        if not fps:
            return 0
        for table in _NODE_TABLES:
            try:
                rows = store.cypher(
                    f"MATCH (n:{table}) WHERE n.file_path IN $fps "
                    f"RETURN n.node_id AS id, n.fqn AS fqn, n.name AS name, "
                    f"n.language AS lang, n.file_path AS file_path, "
                    f"n.docstring AS doc, n.importance_score AS score, "
                    f"n.repo_id AS repo_id",
                    {"fps": fps},
                )
            except Exception as exc:
                log.warning("Failed to fetch %s nodes for embedding: %s", table, exc)
                continue
            for i in range(0, len(rows), self._batch_size):
                total += self._embed_batch(table, rows[i : i + self._batch_size])
        log.info("Embedded %d nodes (targeted, %d files)", total, len(fps))
        return total

    def embed_nodes(self, nodes: list[dict[str, Any]]) -> int:
        """Embed a specific list of node dicts (used during incremental re-index)."""
        return self._embed_batch("mixed", nodes)

    def _embed_batch(self, table: str, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0

        ids: list[str] = []
        docs: list[str] = []
        metas: list[dict[str, Any]] = []

        for row in rows:
            node_id = row.get("id") or row.get("node_id")
            if not node_id:
                continue
            doc = _make_doc_from_row(row, table)
            ids.append(node_id)
            docs.append(doc)
            metas.append({
                "node_type": table,
                "fqn": str(row.get("fqn", "")),
                "file_path": str(row.get("file_path", "")),
                "language": str(row.get("lang", "")),
                "importance_score": float(row.get("score") or 0.0),
                "repo_id": str(row.get("repo_id") or ""),
            })

        if not ids:
            return 0

        embeddings = self._model.encode(docs, batch_size=self._batch_size, show_progress_bar=False)
        self._collection.upsert(
            ids=ids,
            embeddings=embeddings.tolist(),
            documents=docs,
            metadatas=metas,  # type: ignore[arg-type]
        )
        return len(ids)

    def search(
        self,
        query: str,
        top_k: int = 20,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Semantic search. Returns list of {id, fqn, file_path, score, metadata}."""
        q_emb = self._model.encode([query], show_progress_bar=False)
        kwargs: dict[str, Any] = {
            "query_embeddings": q_emb.tolist(),
            "n_results": min(top_k, self._collection.count() or 1),
            "include": ["metadatas", "distances", "documents"],
        }
        if where:
            kwargs["where"] = where
        result = self._collection.query(**kwargs)

        hits: list[dict[str, Any]] = []
        if result["ids"]:
            for idx, nid in enumerate(result["ids"][0]):
                meta = result["metadatas"][0][idx]  # type: ignore[index]
                dist = result["distances"][0][idx]  # type: ignore[index]
                hits.append({
                    "node_id": nid,
                    "fqn": meta.get("fqn"),
                    "file_path": meta.get("file_path"),
                    "node_type": meta.get("node_type"),
                    "language": meta.get("language"),
                    "importance_score": meta.get("importance_score", 0.0),
                    "semantic_score": 1.0 - dist,  # cosine distance → similarity
                    "document": result["documents"][0][idx],  # type: ignore[index]
                })
        return hits

    def delete_by_file(self, file_path: str) -> None:
        """Remove all embeddings for a given file (incremental re-index)."""
        self._collection.delete(where={"file_path": file_path})


def _make_doc_from_row(row: dict[str, Any], table: str) -> str:
    parts = [f"{table}: {row.get('fqn', row.get('name', ''))}"]
    doc = row.get("doc") or row.get("docstring")
    if doc:
        parts.append(f"Doc: {str(doc)[:300]}")
    fp = row.get("file_path")
    if fp:
        parts.append(f"File: {fp}")
    return "\n".join(parts)

"""Partial pipeline: re-index only changed files.

Steps:
1. Delete all nodes/edges for changed files from Kuzu and ChromaDB.
2. Run Stages 1-6 restricted to the changed file set.
3. Recompute centrality only for the affected subgraph.
"""
from __future__ import annotations

import logging
import time

from knowstack.config.schema import KnowStackConfig
from knowstack.graph.store import GraphStore
from knowstack.incremental.change_detector import ChangeSet
from knowstack.ingestion.embedder import Embedder
from knowstack.ingestion.enricher import Enricher
from knowstack.ingestion.normalizer import Normalizer
from knowstack.ingestion.parsers import ConfigParser, PythonParser, TypeScriptParser
from knowstack.ingestion.pipeline import IngestionReport
from knowstack.ingestion.scanner import Scanner
from knowstack.ingestion.writer import GraphWriter

log = logging.getLogger(__name__)


class PartialPipeline:
    def __init__(self, config: KnowStackConfig, store: GraphStore) -> None:
        self._config = config
        self._store = store
        self._parsers = [PythonParser(), TypeScriptParser(), ConfigParser()]

    def run(self, change_set: ChangeSet) -> IngestionReport:
        start = time.monotonic()
        report = IngestionReport(repo_path=str(self._config.repo_path))

        embedder = Embedder(
            str(self._config.vector_db_path),
            model_name=self._config.embedding_model,
            device=self._config.embedding_device,
        )

        # Step 1: Delete stale data
        changed_rel_paths = (
            [str(p.relative_to(self._config.repo_path)) for p in change_set.modified]
            + change_set.deleted
        )
        for rel_path in changed_rel_paths:
            log.debug("Removing stale data for %s", rel_path)
            self._store.delete_nodes_by_file(rel_path)
            embedder.delete_by_file(rel_path)

        # Step 2: Re-index added + modified files
        if change_set.all_changed():
            scanner = Scanner(self._config.repo_path, self._config)
            all_records = scanner.scan()
            changed_abs = {p.resolve() for p in change_set.all_changed()}
            records = [r for r in all_records if r.abs_path in changed_abs]
            report.files_scanned = len(records)

            parse_results = []
            for record in records:
                parser = next((p for p in self._parsers if p.can_parse(record)), None)
                if parser:
                    try:
                        parse_results.append(parser.parse(record))
                    except Exception as exc:
                        report.errors.append(str(exc))

            report.files_parsed = len(parse_results)

            normalizer = Normalizer()
            graph = normalizer.normalize(parse_results)

            enricher = Enricher(self._config.repo_path)
            graph = enricher.enrich(graph)

            repo_id = self._config.repo_id or str(self._config.repo_path)
            writer = GraphWriter(self._store, repo_id=repo_id)
            writer.write(graph)
            report.nodes_written = graph.node_count
            report.edges_written = graph.edge_count

            added_rel = [str(p.relative_to(self._config.repo_path)) for p in change_set.added]
            modified_rel = [str(p.relative_to(self._config.repo_path)) for p in change_set.modified]
            report.nodes_embedded = embedder.embed_by_files(self._store, added_rel + modified_rel)

        # Step 3: Recompute centrality on the full graph (PageRank is a global property)
        self._recompute_centrality()

        report.duration_seconds = time.monotonic() - start
        log.info("Incremental re-index done: %s", report.summary())
        return report

    def _recompute_centrality(self) -> None:
        """Recompute PageRank from the full Kuzu graph and write scores back."""
        try:
            import networkx as nx

            from knowstack.ingestion.writer import _NODE_TABLE_MAP

            G: nx.DiGraph = nx.DiGraph()
            for rel in ("CALLS", "IMPORTS"):
                try:
                    rows = self._store.cypher(
                        f"MATCH (a)-[:{rel}]->(b) RETURN a.node_id AS src, b.node_id AS dst"
                    )
                    for r in rows:
                        G.add_edge(r["src"], r["dst"])
                except Exception:
                    pass

            if G.number_of_nodes() == 0:
                return

            pr = nx.pagerank(G, alpha=0.85, max_iter=100)

            for table in _NODE_TABLE_MAP.values():
                try:
                    rows = self._store.cypher(
                        f"MATCH (n:{table}) RETURN n.node_id AS id, n.change_frequency AS cf"
                    )
                except Exception:
                    continue
                for row in rows:
                    nid = row["id"]
                    if nid not in pr:
                        continue
                    score = pr[nid]
                    cf = float(row["cf"] or 0.0)
                    self._store.cypher(
                        f"MATCH (n:{table} {{node_id: $id}}) "
                        "SET n.centrality_score = $cs, n.importance_score = $is",
                        {"id": nid, "cs": score, "is": score * (1 + cf)},
                    )
            log.debug("Centrality recomputed across %d nodes", len(pr))
        except Exception as exc:
            log.warning("Centrality recomputation failed: %s", exc)

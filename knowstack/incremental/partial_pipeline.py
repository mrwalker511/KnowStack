"""Partial pipeline: re-index only changed files.

Steps:
1. Delete all nodes/edges for changed files from Kuzu and ChromaDB.
2. Run Stages 1-6 restricted to the changed file set.
3. Recompute centrality only for the affected subgraph.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

from knowstack.config.schema import KnowStackConfig
from knowstack.graph.store import GraphStore
from knowstack.incremental.change_detector import ChangeSet
from knowstack.ingestion.embedder import Embedder
from knowstack.ingestion.enricher import Enricher
from knowstack.ingestion.normalizer import Normalizer
from knowstack.ingestion.pipeline import IngestionReport
from knowstack.ingestion.parsers import ConfigParser, PythonParser, TypeScriptParser
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
        all_changed_paths = change_set.modified + change_set.deleted
        for rel_path in [str(p.relative_to(self._config.repo_path)) for p in change_set.modified] + change_set.deleted:
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

            writer = GraphWriter(self._store)
            writer.write(graph)
            report.nodes_written = graph.node_count
            report.edges_written = graph.edge_count

            report.nodes_embedded = embedder.embed_all(self._store)

        report.duration_seconds = time.monotonic() - start
        log.info("Incremental re-index done: %s", report.summary())
        return report

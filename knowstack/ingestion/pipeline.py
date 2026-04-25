"""Ingestion pipeline orchestrator.

Wires the six stages together and exposes a clean run() interface.
Each stage produces its output before the next begins — no lazy evaluation
because the Normalizer needs all nodes before it can resolve references.

For large repos (>50k files), set workers > 1 to parallelise parsing.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import networkx as nx
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskID, TaskProgressColumn, TextColumn

from knowstack.config.schema import KnowStackConfig
from knowstack.graph.store import GraphStore
from knowstack.ingestion.embedder import Embedder
from knowstack.ingestion.enricher import Enricher
from knowstack.ingestion.normalizer import NormalizedGraph, Normalizer
from knowstack.ingestion.parsers import ConfigParser, PythonParser, TypeScriptParser
from knowstack.ingestion.parsers.base import BaseParser, ParseResult
from knowstack.ingestion.scanner import FileRecord, Scanner
from knowstack.ingestion.writer import GraphWriter

log = logging.getLogger(__name__)


@dataclass
class IngestionReport:
    repo_path: str
    duration_seconds: float = 0.0
    files_scanned: int = 0
    files_parsed: int = 0
    nodes_written: int = 0
    edges_written: int = 0
    nodes_embedded: int = 0
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"Indexed {self.repo_path} in {self.duration_seconds:.1f}s: "
            f"{self.files_parsed} files → {self.nodes_written} nodes, "
            f"{self.edges_written} edges, {self.nodes_embedded} embedded"
        )


class IngestionPipeline:
    """Full or incremental ingestion pipeline."""

    def __init__(self, config: KnowStackConfig) -> None:
        self._config = config
        self._parsers: list[BaseParser] = [
            PythonParser(),
            TypeScriptParser(),
            ConfigParser(),
        ]

    def run(self, show_progress: bool = True) -> IngestionReport:
        """Run the full pipeline against config.repo_path."""
        start = time.monotonic()
        report = IngestionReport(repo_path=str(self._config.repo_path))

        with _maybe_progress(show_progress) as progress:
            # Stage 1: Scan
            task = progress.add_task("Scanning files…", total=None)
            scanner = Scanner(self._config.repo_path, self._config)
            records = scanner.scan()
            report.files_scanned = len(records)
            progress.update(task, completed=1, total=1, description=f"Scanned {len(records)} files")

            # Stage 2: Parse
            task = progress.add_task("Parsing…", total=len(records))
            parse_results = self._parse_all(records, progress, task)
            report.files_parsed = len(parse_results)
            for pr in parse_results:
                report.errors.extend(pr.errors)

            # Stage 3: Normalize
            progress.update(task, description="Normalizing…")
            normalizer = Normalizer()
            graph = normalizer.normalize(parse_results)

            # Stage 4: Enrich
            progress.update(task, description="Enriching (git + tags)…")
            enricher = Enricher(
                self._config.repo_path,
                git_history_limit=self._config.git_history_limit,
            )
            graph = enricher.enrich(graph)

            # Stage 5: Write to Kuzu
            progress.update(task, description="Writing graph…")
            store = GraphStore(self._config.db_path)
            store.initialize_schema()
            repo_id = self._config.repo_id or str(self._config.repo_path)
            writer = GraphWriter(store, repo_id=repo_id)
            writer.write(graph)
            report.nodes_written = graph.node_count
            report.edges_written = graph.edge_count

            # Post-process: compute centrality
            progress.update(task, description="Computing centrality…")
            self._compute_centrality(store, graph)

            # Stage 6: Embed
            progress.update(task, description="Embedding nodes…")
            embedder = Embedder(
                str(self._config.vector_db_path),
                model_name=self._config.embedding_model,
                device=self._config.embedding_device,
                batch_size=self._config.embedding_batch_size,
            )
            report.nodes_embedded = embedder.embed_all(store)
            store.close()

        report.duration_seconds = time.monotonic() - start
        log.info(report.summary())
        return report

    def run_files(self, files: list[Path], store: GraphStore) -> IngestionReport:
        """Run pipeline on a specific set of files (used by incremental indexer)."""
        start = time.monotonic()
        report = IngestionReport(repo_path=str(self._config.repo_path))

        scanner = Scanner(self._config.repo_path, self._config)
        all_records = scanner.scan()
        records = [r for r in all_records if r.abs_path in {f.resolve() for f in files}]
        report.files_scanned = len(records)

        parse_results = self._parse_all(records, _NullProgress(), None)
        report.files_parsed = len(parse_results)

        normalizer = Normalizer()
        graph = normalizer.normalize(parse_results)

        enricher = Enricher(self._config.repo_path)
        graph = enricher.enrich(graph)

        repo_id = self._config.repo_id or str(self._config.repo_path)
        writer = GraphWriter(store, repo_id=repo_id)
        writer.write(graph)
        report.nodes_written = graph.node_count
        report.edges_written = graph.edge_count

        report.duration_seconds = time.monotonic() - start
        return report

    def _parse_all(
        self,
        records: list[FileRecord],
        progress: object,
        task: object,
    ) -> list[ParseResult]:
        results: list[ParseResult] = []
        for record in records:
            parser = self._find_parser(record)
            if parser is None:
                continue
            try:
                pr = parser.parse(record)
                results.append(pr)
            except Exception as exc:
                log.warning("Parser crashed on %s: %s", record.rel_path, exc)
            if hasattr(progress, "advance") and task is not None:
                progress.advance(task)
        return results

    def _find_parser(self, record: FileRecord) -> BaseParser | None:
        for parser in self._parsers:
            if parser.can_parse(record):
                return parser
        return None

    def _compute_centrality(self, store: GraphStore, graph: NormalizedGraph) -> None:
        """Compute PageRank on the CALLS+IMPORTS subgraph and write scores back."""
        try:
            G = nx.DiGraph()
            # Build from in-memory graph (faster than Kuzu query at this point)
            from knowstack.models.enums import EdgeType as ET
            for edge in graph.edges:
                if edge.edge_type in (ET.CALLS, ET.IMPORTS):
                    G.add_edge(edge.src_id, edge.dst_id)

            if G.number_of_nodes() == 0:
                return

            pr = nx.pagerank(G, alpha=0.85, max_iter=100)

            # Write centrality back to each node table
            # Group by node_type for batch updates
            from collections import defaultdict
            by_table: dict[str, list[dict[str, Any]]] = defaultdict(list)
            from knowstack.ingestion.writer import _NODE_TABLE_MAP
            for node_id, score in pr.items():
                node = graph.nodes.get(node_id)
                if node is None:
                    continue
                table = _NODE_TABLE_MAP.get(node.node_type)
                if table:
                    importance = score * (1 + node.change_frequency)
                    by_table[table].append({
                        "node_id": node_id,
                        "centrality_score": score,
                        "importance_score": importance,
                    })

            for table, rows in by_table.items():
                for row in rows:
                    store.cypher(
                        f"MATCH (n:{table} {{node_id: $id}}) "
                        f"SET n.centrality_score = $cs, n.importance_score = $is",
                        {"id": row["node_id"], "cs": row["centrality_score"], "is": row["importance_score"]},
                    )
            log.debug("Centrality computed for %d nodes", len(pr))
        except Exception as exc:
            log.warning("Centrality computation failed: %s", exc)


class _NullProgress:
    """No-op progress sink used in non-interactive runs."""
    def add_task(self, *a: object, **kw: object) -> TaskID: return TaskID(0)
    def advance(self, *a: object) -> None: pass
    def update(self, *a: object, **kw: object) -> None: pass


def _maybe_progress(enabled: bool) -> Progress | _NullProgressContext:
    if enabled:
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            transient=True,
        )
    return _NullProgressContext()


class _NullProgressContext:
    def __enter__(self) -> _NullProgress:
        return _NullProgress()
    def __exit__(self, *_: object) -> None: pass

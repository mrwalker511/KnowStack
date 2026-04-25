"""WorkspaceIndexer — index multiple repos into a shared Kuzu + ChromaDB store."""
from __future__ import annotations

import logging

from knowstack.config.schema import KnowStackConfig
from knowstack.graph.migrations import migrate
from knowstack.graph.store import GraphStore
from knowstack.ingestion.pipeline import IngestionPipeline, IngestionReport
from knowstack.workspace.config import RepoEntry, WorkspaceConfig

log = logging.getLogger(__name__)


class WorkspaceIndexer:
    """Index one or all repos in a workspace into the shared graph database."""

    def __init__(self, workspace: WorkspaceConfig) -> None:
        self._ws = workspace

    def run(self, repo_id: str | None = None) -> dict[str, IngestionReport]:
        """Index all repos (or just repo_id if specified).

        Returns a mapping of repo_id → IngestionReport.
        """
        targets = (
            [self._ws.get_repo(repo_id)] if repo_id else self._ws.repos
        )
        if not targets:
            log.warning("No repos registered in workspace")
            return {}

        # Ensure shared schema is up to date before first write
        store = GraphStore(self._ws.db_path)
        store.initialize_schema()
        migrate(store)
        store.close()

        reports: dict[str, IngestionReport] = {}
        for entry in targets:
            log.info("Indexing %s (%s)", entry.id, entry.path)
            report = self._index_repo(entry)
            reports[entry.id] = report
            log.info("  → %s", report.summary())

        return reports

    def _index_repo(self, entry: RepoEntry) -> IngestionReport:
        config = KnowStackConfig(
            repo_path=entry.path,
            repo_id=entry.id,
            db_path=self._ws.db_path,
            vector_db_path=self._ws.vector_db_path,
        )
        config = config.model_copy(update={"repo_path": entry.path.resolve()})
        pipeline = IngestionPipeline(config)
        return pipeline.run(show_progress=False)

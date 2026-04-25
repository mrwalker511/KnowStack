"""Unit tests for PartialPipeline."""
from unittest.mock import MagicMock, patch

from knowstack.graph.store import GraphStore
from knowstack.incremental.change_detector import ChangeSet
from knowstack.incremental.partial_pipeline import PartialPipeline

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pipeline(tmp_config) -> tuple[PartialPipeline, MagicMock]:
    store = MagicMock(spec=GraphStore)
    pp = PartialPipeline(tmp_config, store)
    return pp, store


def _empty_normalized_graph():
    """Return a NormalizedGraph-like stub with zero nodes/edges."""
    g = MagicMock()
    g.node_count = 0
    g.edge_count = 0
    return g


# ---------------------------------------------------------------------------
# Empty changeset
# ---------------------------------------------------------------------------

class TestEmptyChangeset:
    def test_no_delete_calls(self, tmp_config):
        pp, store = _make_pipeline(tmp_config)
        with patch("knowstack.incremental.partial_pipeline.Embedder") as MockEmb:
            pp.run(ChangeSet())
        store.delete_nodes_by_file.assert_not_called()
        MockEmb.return_value.delete_by_file.assert_not_called()

    def test_files_scanned_is_zero(self, tmp_config):
        pp, store = _make_pipeline(tmp_config)
        with patch("knowstack.incremental.partial_pipeline.Embedder"):
            report = pp.run(ChangeSet())
        assert report.files_scanned == 0

    def test_no_scanner_created(self, tmp_config):
        pp, store = _make_pipeline(tmp_config)
        with (
            patch("knowstack.incremental.partial_pipeline.Embedder"),
            patch("knowstack.incremental.partial_pipeline.Scanner") as MockScanner,
        ):
            pp.run(ChangeSet())
        MockScanner.assert_not_called()


# ---------------------------------------------------------------------------
# Deleted files
# ---------------------------------------------------------------------------

class TestDeletedFiles:
    def test_store_delete_called_for_deleted_rel_path(self, tmp_config):
        pp, store = _make_pipeline(tmp_config)
        with patch("knowstack.incremental.partial_pipeline.Embedder"):
            pp.run(ChangeSet(deleted=["auth.py"]))
        store.delete_nodes_by_file.assert_called_once_with("auth.py")

    def test_embedder_delete_called_for_deleted_rel_path(self, tmp_config):
        pp, store = _make_pipeline(tmp_config)
        with patch("knowstack.incremental.partial_pipeline.Embedder") as MockEmb:
            pp.run(ChangeSet(deleted=["auth.py"]))
        MockEmb.return_value.delete_by_file.assert_called_once_with("auth.py")

    def test_multiple_deleted_files_all_cleaned(self, tmp_config):
        pp, store = _make_pipeline(tmp_config)
        with patch("knowstack.incremental.partial_pipeline.Embedder") as MockEmb:
            pp.run(ChangeSet(deleted=["a.py", "b.py"]))
        assert store.delete_nodes_by_file.call_count == 2
        assert MockEmb.return_value.delete_by_file.call_count == 2

    def test_deleted_files_do_not_trigger_reindex(self, tmp_config):
        pp, store = _make_pipeline(tmp_config)
        with (
            patch("knowstack.incremental.partial_pipeline.Embedder"),
            patch("knowstack.incremental.partial_pipeline.Scanner") as MockScanner,
        ):
            pp.run(ChangeSet(deleted=["old.py"]))
        MockScanner.assert_not_called()


# ---------------------------------------------------------------------------
# Modified files
# ---------------------------------------------------------------------------

class TestModifiedFiles:
    def _run_with_modified(self, tmp_config, modified_paths):
        pp, store = _make_pipeline(tmp_config)
        g = _empty_normalized_graph()
        with (
            patch("knowstack.incremental.partial_pipeline.Embedder") as MockEmb,
            patch("knowstack.incremental.partial_pipeline.Scanner") as MockScanner,
            patch("knowstack.incremental.partial_pipeline.Normalizer") as MockNorm,
            patch("knowstack.incremental.partial_pipeline.Enricher") as MockEnrich,
            patch("knowstack.incremental.partial_pipeline.GraphWriter"),
        ):
            MockScanner.return_value.scan.return_value = []
            MockNorm.return_value.normalize.return_value = g
            MockEnrich.return_value.enrich.return_value = g
            MockEmb.return_value.embed_by_files.return_value = 0
            MockEmb.return_value.embed_all.return_value = 0
            cs = ChangeSet(modified=modified_paths)
            report = pp.run(cs)
        return report, store, MockEmb, MockScanner

    def test_store_delete_called_for_modified_file(self, tmp_config):
        mod = tmp_config.repo_path / "auth.py"
        _, store, _, _ = self._run_with_modified(tmp_config, [mod])
        store.delete_nodes_by_file.assert_called_once_with("auth.py")

    def test_embedder_delete_called_for_modified_file(self, tmp_config):
        mod = tmp_config.repo_path / "auth.py"
        _, _, MockEmb, _ = self._run_with_modified(tmp_config, [mod])
        MockEmb.return_value.delete_by_file.assert_called_once_with("auth.py")

    def test_scanner_is_created_for_modified_files(self, tmp_config):
        mod = tmp_config.repo_path / "auth.py"
        _, _, _, MockScanner = self._run_with_modified(tmp_config, [mod])
        MockScanner.assert_called_once()


# ---------------------------------------------------------------------------
# Added files
# ---------------------------------------------------------------------------

class TestAddedFiles:
    def _run_with_added(self, tmp_config, added_paths):
        pp, store = _make_pipeline(tmp_config)
        g = _empty_normalized_graph()
        with (
            patch("knowstack.incremental.partial_pipeline.Embedder") as MockEmb,
            patch("knowstack.incremental.partial_pipeline.Scanner") as MockScanner,
            patch("knowstack.incremental.partial_pipeline.Normalizer") as MockNorm,
            patch("knowstack.incremental.partial_pipeline.Enricher") as MockEnrich,
            patch("knowstack.incremental.partial_pipeline.GraphWriter"),
        ):
            MockScanner.return_value.scan.return_value = []
            MockNorm.return_value.normalize.return_value = g
            MockEnrich.return_value.enrich.return_value = g
            MockEmb.return_value.embed_by_files.return_value = 0
            MockEmb.return_value.embed_all.return_value = 0
            cs = ChangeSet(added=added_paths)
            report = pp.run(cs)
        return report, store, MockEmb, MockScanner

    def test_added_files_not_passed_to_delete(self, tmp_config):
        added = tmp_config.repo_path / "new.py"
        _, store, MockEmb, _ = self._run_with_added(tmp_config, [added])
        store.delete_nodes_by_file.assert_not_called()
        MockEmb.return_value.delete_by_file.assert_not_called()

    def test_scanner_is_created_for_added_files(self, tmp_config):
        added = tmp_config.repo_path / "new.py"
        _, _, _, MockScanner = self._run_with_added(tmp_config, [added])
        MockScanner.assert_called_once()


# ---------------------------------------------------------------------------
# Lazy embedding (Step E — passes after Step C+D are implemented)
# ---------------------------------------------------------------------------

class TestLazyEmbedding:
    def test_embed_by_files_called_not_embed_all(self, tmp_config):
        """After Step D, embed_by_files replaces embed_all in PartialPipeline."""
        pp, store = _make_pipeline(tmp_config)
        g = _empty_normalized_graph()
        added = tmp_config.repo_path / "new_file.py"
        modified = tmp_config.repo_path / "auth.py"
        with (
            patch("knowstack.incremental.partial_pipeline.Embedder") as MockEmb,
            patch("knowstack.incremental.partial_pipeline.Scanner") as MockScanner,
            patch("knowstack.incremental.partial_pipeline.Normalizer") as MockNorm,
            patch("knowstack.incremental.partial_pipeline.Enricher") as MockEnrich,
            patch("knowstack.incremental.partial_pipeline.GraphWriter"),
        ):
            MockScanner.return_value.scan.return_value = []
            MockNorm.return_value.normalize.return_value = g
            MockEnrich.return_value.enrich.return_value = g
            MockEmb.return_value.embed_by_files.return_value = 3
            cs = ChangeSet(added=[added], modified=[modified])
            report = pp.run(cs)

        mock_emb = MockEmb.return_value
        mock_emb.embed_all.assert_not_called()
        mock_emb.embed_by_files.assert_called_once()
        called_paths = mock_emb.embed_by_files.call_args[0][1]
        assert "new_file.py" in called_paths
        assert "auth.py" in called_paths
        assert report.nodes_embedded == 3

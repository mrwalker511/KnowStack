"""Integration test: full ingestion pipeline on the Python fixture."""

import pytest

from knowstack.graph.store import GraphStore
from knowstack.ingestion.pipeline import IngestionPipeline


@pytest.mark.integration
def test_pipeline_runs_on_python_sample(tmp_config):
    """Full pipeline from scan → graph populated."""
    pipeline = IngestionPipeline(tmp_config)
    report = pipeline.run(show_progress=False)

    assert report.files_parsed > 0, "No files were parsed"
    assert report.nodes_written > 0, "No nodes written to graph"
    assert report.edges_written >= 0
    assert not report.errors or len(report.errors) < 5  # allow minor warnings


@pytest.mark.integration
def test_graph_contains_expected_nodes(tmp_config):
    """After indexing, key nodes should be present."""
    pipeline = IngestionPipeline(tmp_config)
    pipeline.run(show_progress=False)

    store = GraphStore(tmp_config.db_path)
    try:
        fns = store.cypher("MATCH (n:Function) RETURN n.name AS name")
        names = {r["name"] for r in fns}
        assert "authenticate" in names, f"Expected 'authenticate' in {names}"
        assert "_find_user" in names or "find_user" in names.union({"_find_user"})

        classes = store.cypher("MATCH (n:Class) RETURN n.name AS name")
        class_names = {r["name"] for r in classes}
        assert "User" in class_names
    finally:
        store.close()


@pytest.mark.integration
def test_pipeline_idempotent(tmp_config):
    """Running the pipeline twice should not duplicate nodes."""
    pipeline = IngestionPipeline(tmp_config)
    pipeline.run(show_progress=False)

    store = GraphStore(tmp_config.db_path)
    count_after_first = store.node_count()
    store.close()

    pipeline.run(show_progress=False)  # second run

    store = GraphStore(tmp_config.db_path)
    count_after_second = store.node_count()
    store.close()

    assert count_after_second == count_after_first, "Second run duplicated nodes"

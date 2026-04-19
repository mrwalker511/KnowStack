"""Integration tests: incremental change detection and partial re-index."""
from pathlib import Path

import pytest

from knowstack.graph.store import GraphStore
from knowstack.incremental.change_detector import ChangeDetector, ChangeSet
from knowstack.incremental.partial_pipeline import PartialPipeline


# ---------------------------------------------------------------------------
# Change detection
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_no_changes_after_full_index(indexed_repo):
    repo_dir, config = indexed_repo
    with GraphStore(config.db_path) as store:
        cs = ChangeDetector(repo_dir, store).detect()
    assert cs.is_empty(), f"Expected no changes but got: {cs}"


@pytest.mark.integration
def test_detects_added_file(indexed_repo):
    repo_dir, config = indexed_repo
    new_file = repo_dir / "brand_new.py"
    new_file.write_text('def hello(): pass\n')
    with GraphStore(config.db_path) as store:
        cs = ChangeDetector(repo_dir, store).detect()
    added_names = [p.name for p in cs.added]
    assert "brand_new.py" in added_names
    assert cs.modified == []
    assert cs.deleted == []


@pytest.mark.integration
def test_detects_modified_file(indexed_repo):
    repo_dir, config = indexed_repo
    target = repo_dir / "auth.py"
    original = target.read_text()
    target.write_text(original + "\n# modified\n")
    with GraphStore(config.db_path) as store:
        cs = ChangeDetector(repo_dir, store).detect()
    modified_names = [p.name for p in cs.modified]
    assert "auth.py" in modified_names
    assert cs.added == []
    assert cs.deleted == []


@pytest.mark.integration
def test_detects_deleted_file(indexed_repo):
    repo_dir, config = indexed_repo
    (repo_dir / "models.py").unlink()
    with GraphStore(config.db_path) as store:
        cs = ChangeDetector(repo_dir, store).detect()
    assert "models.py" in cs.deleted
    assert cs.added == []
    assert cs.modified == []


# ---------------------------------------------------------------------------
# Partial pipeline — node mutations
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_added_file_node_exists_after_partial_run(indexed_repo):
    repo_dir, config = indexed_repo
    new_file = repo_dir / "extra_module.py"
    new_file.write_text(
        'def extra_function(x: int) -> str:\n    """Extra helper."""\n    return str(x)\n'
    )
    cs = ChangeSet(added=[new_file])
    with GraphStore(config.db_path) as store:
        PartialPipeline(config, store).run(cs)
        rows = store.cypher("MATCH (n:Function {name: 'extra_function'}) RETURN n.name AS name")
    assert any(r["name"] == "extra_function" for r in rows), "extra_function not found after partial index"


@pytest.mark.integration
def test_deleted_file_nodes_removed_after_partial_run(indexed_repo):
    repo_dir, config = indexed_repo
    (repo_dir / "auth.py").unlink()
    cs = ChangeSet(deleted=["auth.py"])
    with GraphStore(config.db_path) as store:
        PartialPipeline(config, store).run(cs)
        rows = store.cypher("MATCH (n:Function {name: 'authenticate'}) RETURN n.name AS name")
    assert rows == [], "authenticate should have been deleted"


@pytest.mark.integration
def test_modified_file_updates_docstring(indexed_repo):
    repo_dir, config = indexed_repo
    target = repo_dir / "auth.py"
    original = target.read_text()
    # Append a unique docstring to the first function
    modified = original.replace(
        'def authenticate(',
        'def authenticate(  # pragma: no cover\n',
        1,
    )
    # Simpler: just append a new standalone function with a known unique docstring
    new_content = original + '\ndef updated_marker():\n    """UNIQUE_DOCSTRING_9z8y7x."""\n    pass\n'
    target.write_text(new_content)
    cs = ChangeSet(modified=[target])
    with GraphStore(config.db_path) as store:
        PartialPipeline(config, store).run(cs)
        rows = store.cypher(
            "MATCH (n:Function {name: 'updated_marker'}) RETURN n.docstring AS doc"
        )
    assert rows, "updated_marker function not found after partial re-index"
    assert "UNIQUE_DOCSTRING_9z8y7x" in (rows[0]["doc"] or "")


@pytest.mark.integration
def test_partial_pipeline_idempotent(indexed_repo):
    repo_dir, config = indexed_repo
    new_file = repo_dir / "idempotent_test.py"
    new_file.write_text('def idempotent_fn(): pass\n')
    cs = ChangeSet(added=[new_file])

    with GraphStore(config.db_path) as store:
        PartialPipeline(config, store).run(cs)
        count_1 = store.node_count("Function")

    with GraphStore(config.db_path) as store:
        PartialPipeline(config, store).run(cs)
        count_2 = store.node_count("Function")

    assert count_1 == count_2, "Duplicate nodes after second partial run"


# ---------------------------------------------------------------------------
# Lazy embedding
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_incremental_embed_count_less_than_full(indexed_repo):
    """nodes_embedded from partial run should be < total nodes in graph."""
    repo_dir, config = indexed_repo
    new_file = repo_dir / "small_module.py"
    new_file.write_text('def only_func(): pass\n')
    cs = ChangeSet(added=[new_file])

    with GraphStore(config.db_path) as store:
        total_before = store.node_count()
        report = PartialPipeline(config, store).run(cs)

    assert report.nodes_embedded > 0
    assert report.nodes_embedded < total_before, (
        f"Expected targeted embed ({report.nodes_embedded}) < total nodes ({total_before})"
    )

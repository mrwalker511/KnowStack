"""Unit tests for Phase 6 workspace support."""
from pathlib import Path

import pytest

# ── WorkspaceConfig ───────────────────────────────────────────────────────────

def test_workspace_init_creates_toml(tmp_path):
    from knowstack.workspace.config import WorkspaceConfig
    ws = WorkspaceConfig.init(tmp_path)
    assert (tmp_path / "workspace.toml").exists()
    assert ws.repos == []


def test_workspace_add_repo(tmp_path):
    from knowstack.workspace.config import WorkspaceConfig
    ws = WorkspaceConfig.init(tmp_path)
    repo_dir = tmp_path / "repo-a"
    repo_dir.mkdir()
    entry = ws.add_repo(repo_dir, repo_id="org/repo-a")
    assert entry.id == "org/repo-a"
    assert entry.path == repo_dir.resolve()
    assert len(ws.repos) == 1


def test_workspace_add_repo_default_id(tmp_path):
    from knowstack.workspace.config import WorkspaceConfig
    ws = WorkspaceConfig.init(tmp_path)
    repo_dir = tmp_path / "my-service"
    repo_dir.mkdir()
    entry = ws.add_repo(repo_dir)
    assert entry.id == "my-service"


def test_workspace_add_repo_duplicate_id_raises(tmp_path):
    from knowstack.workspace.config import WorkspaceConfig
    ws = WorkspaceConfig.init(tmp_path)
    repo_dir = tmp_path / "repo-a"
    repo_dir.mkdir()
    ws.add_repo(repo_dir, repo_id="dup")
    with pytest.raises(ValueError, match="already registered"):
        ws.add_repo(repo_dir, repo_id="dup")


def test_workspace_remove_repo(tmp_path):
    from knowstack.workspace.config import WorkspaceConfig
    ws = WorkspaceConfig.init(tmp_path)
    repo_dir = tmp_path / "repo-a"
    repo_dir.mkdir()
    ws.add_repo(repo_dir, repo_id="org/repo-a")
    ws.remove_repo("org/repo-a")
    assert len(ws.repos) == 0


def test_workspace_remove_unknown_raises(tmp_path):
    from knowstack.workspace.config import WorkspaceConfig
    ws = WorkspaceConfig.init(tmp_path)
    with pytest.raises(KeyError):
        ws.remove_repo("does-not-exist")


def test_workspace_save_and_reload(tmp_path):
    from knowstack.workspace.config import WorkspaceConfig
    ws = WorkspaceConfig.init(tmp_path)
    repo_dir = tmp_path / "svc"
    repo_dir.mkdir()
    ws.add_repo(repo_dir, repo_id="org/svc")
    ws.save()

    loaded = WorkspaceConfig.load(tmp_path)
    assert len(loaded.repos) == 1
    assert loaded.repos[0].id == "org/svc"


def test_workspace_load_missing_raises(tmp_path):
    from knowstack.workspace.config import WorkspaceConfig
    with pytest.raises(FileNotFoundError):
        WorkspaceConfig.load(tmp_path)


def test_workspace_get_repo(tmp_path):
    from knowstack.workspace.config import WorkspaceConfig
    ws = WorkspaceConfig.init(tmp_path)
    repo_dir = tmp_path / "svc"
    repo_dir.mkdir()
    ws.add_repo(repo_dir, repo_id="org/svc")
    entry = ws.get_repo("org/svc")
    assert entry.id == "org/svc"


def test_workspace_get_repo_unknown_raises(tmp_path):
    from knowstack.workspace.config import WorkspaceConfig
    ws = WorkspaceConfig.init(tmp_path)
    with pytest.raises(KeyError):
        ws.get_repo("missing")


# ── Schema / model ────────────────────────────────────────────────────────────

def test_base_node_has_repo_id():
    from knowstack.models.enums import Language, NodeType
    from knowstack.models.nodes import FunctionNode, make_node_id
    node = FunctionNode(
        node_id=make_node_id("/repo", "mod.fn"),
        node_type=NodeType.FUNCTION,
        name="fn",
        fqn="mod.fn",
        language=Language.PYTHON,
        repo_id="org/my-repo",
    )
    assert node.repo_id == "org/my-repo"


def test_base_node_repo_id_defaults_empty():
    from knowstack.models.enums import Language, NodeType
    from knowstack.models.nodes import FunctionNode, make_node_id
    node = FunctionNode(
        node_id=make_node_id("/repo", "mod.fn"),
        node_type=NodeType.FUNCTION,
        name="fn",
        fqn="mod.fn",
        language=Language.PYTHON,
    )
    assert node.repo_id == ""


# ── Schema version ────────────────────────────────────────────────────────────

def test_schema_version_is_2():
    from knowstack.graph.schema import SCHEMA_VERSION
    assert SCHEMA_VERSION == 2


def test_schema_includes_repo_id():
    from knowstack.graph.schema import _COMMON_NODE_COLS
    assert "repo_id" in _COMMON_NODE_COLS


# ── Isolation: path serialization ─────────────────────────────────────────────

def test_workspace_save_reload_out_of_tree_repo(tmp_path):
    """Repos outside workspace_path must survive a save/load round-trip."""
    from knowstack.workspace.config import WorkspaceConfig
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()
    # Repo lives outside the workspace directory (sibling pattern)
    repo_dir = tmp_path / "repo-outside"
    repo_dir.mkdir()

    ws = WorkspaceConfig.init(workspace_dir)
    ws.add_repo(repo_dir, repo_id="org/outside")
    ws.save()

    loaded = WorkspaceConfig.load(workspace_dir)
    assert len(loaded.repos) == 1
    assert loaded.repos[0].path == repo_dir.resolve()
    assert loaded.repos[0].id == "org/outside"


def test_workspace_save_path_relative_for_in_tree_repo(tmp_path):
    """Repos inside workspace_path are stored as relative paths in TOML."""
    from knowstack.workspace.config import WorkspaceConfig
    ws = WorkspaceConfig.init(tmp_path)
    repo_dir = tmp_path / "inner-svc"
    repo_dir.mkdir()
    ws.add_repo(repo_dir, repo_id="inner")
    ws.save()

    toml_text = (tmp_path / "workspace.toml").read_text()
    assert "inner-svc" in toml_text
    assert str(tmp_path) not in toml_text  # absolute path must not appear


# ── Isolation: ChangeDetector repo_id filtering ───────────────────────────────

def test_change_detector_passes_repo_id_to_query():
    """ChangeDetector._load_indexed_hashes must filter by repo_id."""
    from knowstack.incremental.change_detector import ChangeDetector

    queries: list[str] = []

    class _MockStore:
        def cypher(self, q: str, params=None):
            queries.append(q)
            return []

    detector = ChangeDetector(Path("/tmp/repo"), _MockStore(), repo_id="org/svc")  # type: ignore[arg-type]
    detector._load_indexed_hashes()
    assert queries, "cypher() was not called"
    assert "repo_id" in queries[0], "repo_id filter missing from Cypher query"


def test_change_detector_no_repo_id_fetches_all():
    """Without repo_id, ChangeDetector fetches all File nodes (single-repo mode)."""
    from knowstack.incremental.change_detector import ChangeDetector

    queries: list[str] = []

    class _MockStore:
        def cypher(self, q: str, params=None):
            queries.append(q)
            return []

    detector = ChangeDetector(Path("/tmp/repo"), _MockStore())  # type: ignore[arg-type]
    detector._load_indexed_hashes()
    assert "WHERE" not in queries[0], "Unexpected WHERE clause when no repo_id given"


# ── Isolation: VectorRetriever repo_id filtering ─────────────────────────────

def test_vector_retriever_passes_repo_id_to_embedder():
    """VectorRetriever.search() must forward repo_id into the ChromaDB where dict."""
    from knowstack.retrieval.vector_retriever import VectorRetriever

    captured: dict = {}

    class _MockEmbedder:
        def search(self, query, top_k, where):
            captured["where"] = where
            return []

    vr = VectorRetriever(_MockEmbedder())  # type: ignore[arg-type]
    vr.search("authenticate", top_k=5, repo_id="org/svc")
    assert captured.get("where", {}).get("repo_id") == "org/svc"


def test_vector_retriever_no_repo_id_omits_filter():
    """VectorRetriever.search() without repo_id passes None (no filter) to embedder."""
    from knowstack.retrieval.vector_retriever import VectorRetriever

    captured: dict = {}

    class _MockEmbedder:
        def search(self, query, top_k, where):
            captured["where"] = where
            return []

    vr = VectorRetriever(_MockEmbedder())  # type: ignore[arg-type]
    vr.search("authenticate", top_k=5)
    assert captured.get("where") is None

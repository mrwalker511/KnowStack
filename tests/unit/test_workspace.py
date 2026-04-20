"""Unit tests for Phase 6 workspace support."""
import pytest
from pathlib import Path


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
    from knowstack.models.nodes import FunctionNode, make_node_id
    from knowstack.models.enums import Language, NodeType
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
    from knowstack.models.nodes import FunctionNode, make_node_id
    from knowstack.models.enums import Language, NodeType
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

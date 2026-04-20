"""WorkspaceConfig — multi-repo manifest loaded from workspace.toml.

Example workspace.toml:

    [workspace]
    db_path = ".knowstack/workspace.kuzu"
    vector_db_path = ".knowstack/workspace-vectors"

    [[workspace.repos]]
    path = "../service-a"
    id = "org/service-a"

    [[workspace.repos]]
    path = "../service-b"
    id = "org/service-b"
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


WORKSPACE_FILE = "workspace.toml"


@dataclass
class RepoEntry:
    path: Path               # Absolute path to the repository root
    id: str                  # Unique identifier, e.g. "org/service-a"


@dataclass
class WorkspaceConfig:
    workspace_path: Path                  # Dir containing workspace.toml
    db_path: Path                         # Shared Kuzu graph database
    vector_db_path: Path                  # Shared ChromaDB vectors
    repos: list[RepoEntry] = field(default_factory=list)

    # ── Persistence ───────────────────────────────────────────────────────────

    @classmethod
    def load(cls, workspace_path: Path) -> "WorkspaceConfig":
        """Load from workspace_path/workspace.toml."""
        toml_path = workspace_path / WORKSPACE_FILE
        if not toml_path.exists():
            raise FileNotFoundError(f"No workspace.toml found at {toml_path}")
        with open(toml_path, "rb") as f:
            data = tomllib.load(f)
        ws = data.get("workspace", {})
        db = workspace_path / ws.get("db_path", ".knowstack/workspace.kuzu")
        vec = workspace_path / ws.get("vector_db_path", ".knowstack/workspace-vectors")
        repos = [
            RepoEntry(
                path=(workspace_path / r["path"]).resolve(),
                id=r.get("id") or Path(r["path"]).name,
            )
            for r in ws.get("repos", [])
        ]
        return cls(workspace_path=workspace_path, db_path=db.resolve(),
                   vector_db_path=vec.resolve(), repos=repos)

    def save(self) -> None:
        """Write current state back to workspace.toml."""
        toml_path = self.workspace_path / WORKSPACE_FILE
        repos_toml = "\n".join(
            f'\n[[workspace.repos]]\npath = "{r.path}"\nid = "{r.id}"'
            for r in self.repos
        )
        content = (
            f'[workspace]\n'
            f'db_path = "{self.db_path.relative_to(self.workspace_path)}"\n'
            f'vector_db_path = "{self.vector_db_path.relative_to(self.workspace_path)}"\n'
            f'{repos_toml}\n'
        )
        toml_path.write_text(content)

    # ── Mutation ──────────────────────────────────────────────────────────────

    def add_repo(self, path: Path, repo_id: str | None = None) -> RepoEntry:
        """Register a new repo. Returns the added RepoEntry."""
        abs_path = path.resolve()
        effective_id = repo_id or abs_path.name
        if any(r.id == effective_id for r in self.repos):
            raise ValueError(f"Repo id '{effective_id}' already registered")
        entry = RepoEntry(path=abs_path, id=effective_id)
        self.repos.append(entry)
        return entry

    def remove_repo(self, repo_id: str) -> None:
        """Unregister a repo by id."""
        before = len(self.repos)
        self.repos = [r for r in self.repos if r.id != repo_id]
        if len(self.repos) == before:
            raise KeyError(f"Repo id '{repo_id}' not found in workspace")

    def get_repo(self, repo_id: str) -> RepoEntry:
        for r in self.repos:
            if r.id == repo_id:
                return r
        raise KeyError(f"Repo id '{repo_id}' not found")

    # ── Factory ───────────────────────────────────────────────────────────────

    @classmethod
    def init(cls, workspace_path: Path) -> "WorkspaceConfig":
        """Create a new empty workspace and write workspace.toml."""
        ws = cls(
            workspace_path=workspace_path,
            db_path=(workspace_path / ".knowstack/workspace.kuzu").resolve(),
            vector_db_path=(workspace_path / ".knowstack/workspace-vectors").resolve(),
        )
        ws.save()
        return ws

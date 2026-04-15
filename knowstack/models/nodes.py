"""Node models for the KnowStack knowledge graph.

Every symbol extracted from a codebase is represented as a node.
All nodes share BaseNode. Subclasses add type-specific fields.

Node IDs are deterministic: sha256(repo_root + ":" + fqn)[:16].
This ensures stable identity across re-indexing runs.
"""
from __future__ import annotations

import hashlib
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from .enums import Language, NodeType
from .source_span import SourceSpan


def make_node_id(repo_root: str, fqn: str) -> str:
    """Stable, deterministic node ID derived from repository context and FQN."""
    raw = f"{repo_root}:{fqn}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class BaseNode(BaseModel):
    """All nodes stored in the knowledge graph."""

    model_config = ConfigDict(frozen=True)

    node_id: str
    node_type: NodeType
    name: str  # Short unqualified name: "authenticate"
    fqn: str  # Fully-qualified name: "src.auth.service.AuthService.authenticate"
    language: Language
    source_span: Optional[SourceSpan] = None
    docstring: Optional[str] = None  # First docstring/comment, ≤512 chars
    tags: list[str] = Field(default_factory=list)  # auto-detected + user-defined

    # Enrichment — populated by Enricher and post-processing steps
    change_frequency: float = 0.0  # Commit touches / total commits (0–1)
    last_modified_commit: Optional[str] = None
    centrality_score: float = 0.0  # PageRank on CALLS+IMPORTS subgraph
    importance_score: float = 0.0  # centrality * (1 + change_frequency)

    def with_enrichment(self, **kwargs: object) -> "BaseNode":
        """Return a copy with enrichment fields applied (frozen-safe update)."""
        return self.model_copy(update=kwargs)


class FileNode(BaseNode):
    node_type: NodeType = NodeType.FILE
    file_path: str
    extension: str
    size_bytes: int
    content_hash: str  # SHA-256 of raw file bytes — used for incremental diffing


class DirectoryNode(BaseNode):
    node_type: NodeType = NodeType.DIRECTORY
    dir_path: str


class ClassNode(BaseNode):
    node_type: NodeType = NodeType.CLASS
    bases: list[str] = Field(default_factory=list)  # Unresolved base names from source
    is_abstract: bool = False
    decorator_names: list[str] = Field(default_factory=list)


class FunctionNode(BaseNode):
    node_type: NodeType = NodeType.FUNCTION
    signature: str = ""  # "def auth(user: str) -> Token"
    is_async: bool = False
    is_generator: bool = False
    decorator_names: list[str] = Field(default_factory=list)
    parameter_names: list[str] = Field(default_factory=list)
    return_type: Optional[str] = None


class MethodNode(FunctionNode):
    node_type: NodeType = NodeType.METHOD
    class_fqn: str  # FQN of the containing class
    is_static: bool = False
    is_classmethod: bool = False
    is_property: bool = False


class InterfaceNode(BaseNode):
    node_type: NodeType = NodeType.INTERFACE
    extends: list[str] = Field(default_factory=list)


class TypeAliasNode(BaseNode):
    node_type: NodeType = NodeType.TYPE_ALIAS
    type_expression: str = ""  # RHS as string: "Union[str, int]"


class ApiEndpointNode(BaseNode):
    node_type: NodeType = NodeType.API_ENDPOINT
    http_method: str = ""  # "GET", "POST", …
    path_pattern: str = ""  # "/api/v1/users/{id}"
    framework: str = ""  # "fastapi", "express", "flask"


class DbModelNode(BaseNode):
    node_type: NodeType = NodeType.DB_MODEL
    table_name: Optional[str] = None
    orm_framework: str = ""  # "sqlalchemy", "django", "prisma", "typeorm"
    fields: list[str] = Field(default_factory=list)


class TestNode(BaseNode):
    node_type: NodeType = NodeType.TEST
    test_framework: str = ""  # "pytest", "jest", "unittest"
    is_parametrized: bool = False
    targets: list[str] = Field(default_factory=list)  # FQNs of symbols under test


class ConfigFileNode(BaseNode):
    node_type: NodeType = NodeType.CONFIG_FILE
    file_path: str = ""
    format: str = ""  # "toml", "json", "yaml", "env"

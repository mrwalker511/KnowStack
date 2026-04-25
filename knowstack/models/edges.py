"""Edge models for the KnowStack knowledge graph.

Edges represent relationships between nodes. Each edge has a stable ID,
a confidence score (1.0 = proven static analysis, 0.4 = heuristic inference),
and optional metadata specific to the relationship type.
"""
from __future__ import annotations

import hashlib

from pydantic import BaseModel, ConfigDict

from .enums import EdgeType


def make_edge_id(src_id: str, edge_type: EdgeType, dst_id: str) -> str:
    raw = f"{src_id}:{edge_type}:{dst_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class BaseEdge(BaseModel):
    model_config = ConfigDict(frozen=True)

    edge_id: str
    edge_type: EdgeType
    src_id: str
    dst_id: str
    confidence: float = 1.0  # 0–1: proven=1.0, heuristic=0.7, inferred=0.4
    source_span: str | None = None  # "file.py:42" where relationship observed


class ContainsEdge(BaseEdge):
    edge_type: EdgeType = EdgeType.CONTAINS


class DefinesEdge(BaseEdge):
    edge_type: EdgeType = EdgeType.DEFINES


class ImportsEdge(BaseEdge):
    edge_type: EdgeType = EdgeType.IMPORTS
    imported_names: list[str] = []  # ["authenticate", "TokenError"] or ["*"]
    is_dynamic: bool = False  # importlib.import_module(…)


class CallsEdge(BaseEdge):
    edge_type: EdgeType = EdgeType.CALLS
    is_conditional: bool = False  # Call inside an if-branch
    is_dynamic: bool = False  # Call via variable/getattr/reflection


class InheritsEdge(BaseEdge):
    edge_type: EdgeType = EdgeType.INHERITS
    is_mixin: bool = False


class ImplementsEdge(BaseEdge):
    edge_type: EdgeType = EdgeType.IMPLEMENTS


class ReferencesEdge(BaseEdge):
    edge_type: EdgeType = EdgeType.REFERENCES


class InstantiatesEdge(BaseEdge):
    edge_type: EdgeType = EdgeType.INSTANTIATES


class ReadsFromEdge(BaseEdge):
    edge_type: EdgeType = EdgeType.READS_FROM
    access_pattern: str | None = None  # "SELECT", "filter()", "findMany()"


class WritesToEdge(BaseEdge):
    edge_type: EdgeType = EdgeType.WRITES_TO
    access_pattern: str | None = None  # "INSERT", "save()", "create()"


class TestedByEdge(BaseEdge):
    edge_type: EdgeType = EdgeType.TESTED_BY


class ExposesEndpointEdge(BaseEdge):
    edge_type: EdgeType = EdgeType.EXPOSES_ENDPOINT


class DependsOnEdge(BaseEdge):
    edge_type: EdgeType = EdgeType.DEPENDS_ON

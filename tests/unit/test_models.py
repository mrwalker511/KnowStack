"""Unit tests for core data models."""
import pytest
from knowstack.models.enums import EdgeType, Language, NodeType
from knowstack.models.nodes import FunctionNode, ClassNode, make_node_id
from knowstack.models.edges import CallsEdge, make_edge_id
from knowstack.models.source_span import SourceSpan


def test_make_node_id_deterministic():
    id1 = make_node_id("/repo", "src.auth.authenticate")
    id2 = make_node_id("/repo", "src.auth.authenticate")
    assert id1 == id2


def test_make_node_id_different_fqns():
    id1 = make_node_id("/repo", "src.auth.authenticate")
    id2 = make_node_id("/repo", "src.auth.logout")
    assert id1 != id2


def test_make_edge_id_deterministic():
    id1 = make_edge_id("abc", EdgeType.CALLS, "def")
    id2 = make_edge_id("abc", EdgeType.CALLS, "def")
    assert id1 == id2


def test_function_node_frozen():
    fn = FunctionNode(
        node_id="abc",
        name="auth",
        fqn="src.auth",
        language=Language.PYTHON,
        signature="def auth()",
    )
    with pytest.raises(Exception):  # ValidationError or TypeError
        fn.name = "other"  # type: ignore


def test_function_node_with_enrichment():
    fn = FunctionNode(
        node_id="abc",
        name="auth",
        fqn="src.auth",
        language=Language.PYTHON,
    )
    enriched = fn.with_enrichment(change_frequency=0.5, centrality_score=0.8)
    assert enriched.change_frequency == 0.5
    assert enriched.centrality_score == 0.8
    assert fn.change_frequency == 0.0  # original unchanged


def test_source_span_str():
    span = SourceSpan(file_path="src/auth.py", start_line=10, end_line=25)
    assert str(span) == "src/auth.py:10-25"
    assert span.line_count == 16


def test_language_from_extension():
    assert Language.from_extension(".py") == Language.PYTHON
    assert Language.from_extension(".ts") == Language.TYPESCRIPT
    assert Language.from_extension(".tsx") == Language.TYPESCRIPT
    assert Language.from_extension(".json") == Language.JSON
    assert Language.from_extension(".xyz") == Language.UNKNOWN

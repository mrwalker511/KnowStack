"""Unit tests for core data models and config file parser."""
from pathlib import Path

import pytest

from knowstack.models.edges import make_edge_id
from knowstack.models.enums import EdgeType, Language, NodeType
from knowstack.models.nodes import FunctionNode, make_node_id
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


# ── Config parser ─────────────────────────────────────────────────────────────

def _make_config_record(filename: str, content: bytes, lang: Language):
    from knowstack.ingestion.scanner import FileRecord
    from knowstack.utils.hashing import content_hash
    path = Path(f"/tmp/{filename}")
    return FileRecord(
        abs_path=path,
        rel_path=filename,
        language=lang,
        size_bytes=len(content),
        content=content,
        content_hash=content_hash(content),
    )


def test_config_parser_json_emits_config_node():
    from knowstack.ingestion.parsers.config_parser import ConfigParser
    record = _make_config_record("package.json", b'{"name": "app"}', Language.JSON)
    result = ConfigParser().parse(record)
    config_nodes = [n for n in result.nodes if n.node_type == NodeType.CONFIG_FILE]
    assert len(config_nodes) == 1
    assert config_nodes[0].format == "json"  # type: ignore[attr-defined]


def test_config_parser_yaml_emits_config_node():
    from knowstack.ingestion.parsers.config_parser import ConfigParser
    record = _make_config_record("config.yaml", b"key: value\n", Language.YAML)
    result = ConfigParser().parse(record)
    config_nodes = [n for n in result.nodes if n.node_type == NodeType.CONFIG_FILE]
    assert len(config_nodes) == 1
    assert config_nodes[0].format == "yaml"  # type: ignore[attr-defined]


def test_config_parser_emits_file_node():
    from knowstack.ingestion.parsers.config_parser import ConfigParser
    record = _make_config_record("pyproject.toml", b"[tool]\n", Language.TOML)
    result = ConfigParser().parse(record)
    file_nodes = [n for n in result.nodes if n.node_type == NodeType.FILE]
    assert len(file_nodes) == 1


def test_config_parser_emits_contains_edge():
    from knowstack.ingestion.parsers.config_parser import ConfigParser
    record = _make_config_record("settings.json", b"{}", Language.JSON)
    result = ConfigParser().parse(record)
    file_nodes = [n for n in result.nodes if n.node_type == NodeType.FILE]
    config_nodes = [n for n in result.nodes if n.node_type == NodeType.CONFIG_FILE]
    contains_edges = [e for e in result.edges if e.edge_type == EdgeType.CONTAINS]
    assert file_nodes and config_nodes and contains_edges
    edge = contains_edges[0]
    assert edge.src_id == file_nodes[0].node_id
    assert edge.dst_id == config_nodes[0].node_id

"""Unit tests for the TypeScript tree-sitter parser."""
from pathlib import Path

import pytest

from knowstack.ingestion.parsers.typescript_parser import TypeScriptParser
from knowstack.ingestion.scanner import FileRecord
from knowstack.models.enums import EdgeType, Language, NodeType
from knowstack.utils.hashing import content_hash

_TS_SAMPLE = Path(__file__).parent.parent / "fixtures" / "typescript_sample"


def _make_record(filename: str) -> FileRecord:
    path = _TS_SAMPLE / filename
    raw = path.read_bytes()
    return FileRecord(
        abs_path=path,
        rel_path=filename,
        language=Language.TYPESCRIPT,
        size_bytes=len(raw),
        content=raw,
        content_hash=content_hash(raw),
    )


@pytest.fixture
def auth_ts_record() -> FileRecord:
    return _make_record("auth.ts")


@pytest.fixture
def types_ts_record() -> FileRecord:
    return _make_record("types.ts")


# ── can_parse ────────────────────────────────────────────────────────────────

def test_parser_can_parse_typescript(auth_ts_record: FileRecord) -> None:
    assert TypeScriptParser().can_parse(auth_ts_record)


def test_parser_rejects_python() -> None:
    py_path = Path(__file__).parent.parent / "fixtures" / "python_sample" / "auth.py"
    raw = py_path.read_bytes()
    record = FileRecord(
        abs_path=py_path,
        rel_path="auth.py",
        language=Language.PYTHON,
        size_bytes=len(raw),
        content=raw,
        content_hash=content_hash(raw),
    )
    assert not TypeScriptParser().can_parse(record)


# ── file node ────────────────────────────────────────────────────────────────

def test_parser_emits_file_node(auth_ts_record: FileRecord) -> None:
    result = TypeScriptParser().parse(auth_ts_record)
    file_nodes = [n for n in result.nodes if n.node_type == NodeType.FILE]
    assert len(file_nodes) == 1
    assert file_nodes[0].fqn == "auth.ts"


# ── class extraction ─────────────────────────────────────────────────────────

def test_parser_extracts_class(auth_ts_record: FileRecord) -> None:
    result = TypeScriptParser().parse(auth_ts_record)
    names = {n.name for n in result.nodes if n.node_type == NodeType.CLASS}
    assert "AuthService" in names


def test_parser_class_has_correct_fqn(auth_ts_record: FileRecord) -> None:
    result = TypeScriptParser().parse(auth_ts_record)
    fqns = {n.fqn for n in result.nodes if n.node_type == NodeType.CLASS}
    assert "auth.AuthService" in fqns


# ── method extraction ────────────────────────────────────────────────────────

def test_parser_extracts_methods(auth_ts_record: FileRecord) -> None:
    result = TypeScriptParser().parse(auth_ts_record)
    names = {n.name for n in result.nodes if n.node_type == NodeType.METHOD}
    assert "authenticate" in names
    assert "logout" in names


def test_parser_methods_have_class_parent_containment(auth_ts_record: FileRecord) -> None:
    """CONTAINS edges for methods must originate from a class node, not the file."""
    result = TypeScriptParser().parse(auth_ts_record)
    class_ids = {n.node_id for n in result.nodes if n.node_type == NodeType.CLASS}
    method_ids = {n.node_id for n in result.nodes if n.node_type == NodeType.METHOD}
    contains = [e for e in result.edges if e.edge_type == EdgeType.CONTAINS]

    assert method_ids, "fixture must have at least one method"
    for edge in contains:
        if edge.dst_id in method_ids:
            assert edge.src_id in class_ids, (
                f"Method CONTAINS edge src {edge.src_id!r} is not a class node"
            )


def test_parser_detects_async_methods(auth_ts_record: FileRecord) -> None:
    result = TypeScriptParser().parse(auth_ts_record)
    all_methods = [n for n in result.nodes if n.node_type == NodeType.METHOD]
    authenticate = next((m for m in all_methods if m.name == "authenticate"), None)
    assert authenticate is not None, "authenticate method not found"
    assert getattr(authenticate, "is_async", False) is True


# ── interface / type alias extraction ────────────────────────────────────────

def test_parser_extracts_interfaces(types_ts_record: FileRecord) -> None:
    result = TypeScriptParser().parse(types_ts_record)
    names = {n.name for n in result.nodes if n.node_type == NodeType.INTERFACE}
    assert "User" in names
    assert "Token" in names


def test_parser_extracts_type_aliases(types_ts_record: FileRecord) -> None:
    result = TypeScriptParser().parse(types_ts_record)
    names = {n.name for n in result.nodes if n.node_type == NodeType.TYPE_ALIAS}
    assert "AuthResult" in names


# ── import extraction ─────────────────────────────────────────────────────────

def test_parser_extracts_imports(auth_ts_record: FileRecord) -> None:
    result = TypeScriptParser().parse(auth_ts_record)
    imports = [e for e in result.edges if e.edge_type == EdgeType.IMPORTS]
    assert len(imports) > 0


def test_parser_import_names_include_domain_types(auth_ts_record: FileRecord) -> None:
    result = TypeScriptParser().parse(auth_ts_record)
    imports = [e for e in result.edges if e.edge_type == EdgeType.IMPORTS]
    all_names: list[str] = []
    for imp in imports:
        all_names.extend(getattr(imp, "imported_names", []))
    assert any(name in all_names for name in ("User", "Token", "AuthResult"))


# ── containment edges ────────────────────────────────────────────────────────

def test_parser_emits_file_contains_class(auth_ts_record: FileRecord) -> None:
    result = TypeScriptParser().parse(auth_ts_record)
    file_id = next(n.node_id for n in result.nodes if n.node_type == NodeType.FILE)
    class_ids = {n.node_id for n in result.nodes if n.node_type == NodeType.CLASS}
    contains = [e for e in result.edges if e.edge_type == EdgeType.CONTAINS]
    assert any(e.src_id == file_id and e.dst_id in class_ids for e in contains)


# ── no errors ────────────────────────────────────────────────────────────────

def test_parser_no_errors_on_auth_file(auth_ts_record: FileRecord) -> None:
    assert TypeScriptParser().parse(auth_ts_record).errors == []


def test_parser_no_errors_on_types_file(types_ts_record: FileRecord) -> None:
    assert TypeScriptParser().parse(types_ts_record).errors == []

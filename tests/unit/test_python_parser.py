"""Unit tests for the Python tree-sitter parser."""

from knowstack.ingestion.parsers.python_parser import PythonParser
from knowstack.models.enums import Language, NodeType


def test_parser_can_parse_python(auth_file_record):
    parser = PythonParser()
    assert parser.can_parse(auth_file_record)


def test_parser_emits_file_node(auth_file_record):
    parser = PythonParser()
    result = parser.parse(auth_file_record)
    file_nodes = [n for n in result.nodes if n.node_type == NodeType.FILE]
    assert len(file_nodes) == 1
    assert file_nodes[0].fqn == "auth.py"


def test_parser_extracts_functions(auth_file_record):
    parser = PythonParser()
    result = parser.parse(auth_file_record)
    fns = [n for n in result.nodes if n.node_type == NodeType.FUNCTION]
    names = {n.name for n in fns}
    assert "authenticate" in names
    assert "_find_user" in names
    assert "_create_token" in names
    assert "logout" in names


def test_parser_extracts_classes(models_file_record):
    parser = PythonParser()
    result = parser.parse(models_file_record)
    classes = [n for n in result.nodes if n.node_type == NodeType.CLASS]
    names = {n.name for n in classes}
    assert "User" in names
    assert "Token" in names


def test_parser_extracts_methods(models_file_record):
    parser = PythonParser()
    result = parser.parse(models_file_record)
    methods = [n for n in result.nodes if n.node_type == NodeType.METHOD]
    names = {n.name for n in methods}
    assert "verify_password" in names


def test_parser_extracts_imports(auth_file_record):
    parser = PythonParser()
    result = parser.parse(auth_file_record)
    from knowstack.models.enums import EdgeType
    imports = [e for e in result.edges if e.edge_type == EdgeType.IMPORTS]
    assert len(imports) > 0


def test_parser_extracts_docstrings(auth_file_record):
    parser = PythonParser()
    result = parser.parse(auth_file_record)
    fns = [n for n in result.nodes if n.name == "authenticate"]
    assert fns, "authenticate function not found"
    assert fns[0].docstring is not None
    assert "Authenticate" in fns[0].docstring


def test_parser_extracts_test_nodes():
    from pathlib import Path

    from knowstack.ingestion.scanner import FileRecord
    from knowstack.utils.hashing import content_hash

    path = Path(__file__).parent.parent / "fixtures" / "python_sample" / "test_auth.py"
    content = path.read_bytes()
    record = FileRecord(
        abs_path=path,
        rel_path="test_auth.py",
        language=Language.PYTHON,
        size_bytes=len(content),
        content=content,
        content_hash=content_hash(content),
    )
    parser = PythonParser()
    result = parser.parse(record)
    tests = [n for n in result.nodes if n.node_type == NodeType.TEST]
    assert len(tests) >= 2
    names = {n.name for n in tests}
    assert "test_authenticate_returns_token" in names


def test_parser_no_errors_on_valid_file(auth_file_record):
    parser = PythonParser()
    result = parser.parse(auth_file_record)
    assert result.errors == []

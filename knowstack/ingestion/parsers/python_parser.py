"""Python parser using tree-sitter.

Extracts: classes, functions, methods, imports, calls, decorators,
docstrings, ORM models (SQLAlchemy/Django), FastAPI/Flask endpoints,
and pytest test functions.
"""
from __future__ import annotations

import logging
import re

import tree_sitter_python as tspython
from tree_sitter import Language as TSLanguage
from tree_sitter import Node, Parser

from knowstack.ingestion.scanner import FileRecord
from knowstack.models.edges import (
    CallsEdge,
    ContainsEdge,
    ExposesEndpointEdge,
    ImportsEdge,
    make_edge_id,
)
from knowstack.models.enums import EdgeType, Language, NodeType
from knowstack.models.nodes import (
    ApiEndpointNode,
    ClassNode,
    DbModelNode,
    FileNode,
    FunctionNode,
    MethodNode,
    TestNode,
    make_node_id,
)
from knowstack.models.source_span import SourceSpan
from knowstack.utils.text import clean_docstring

from .base import BaseParser, ParseResult

log = logging.getLogger(__name__)

_PY_LANGUAGE = TSLanguage(tspython.language())

# ORM base class names that signal a DbModel
_ORM_BASES = {
    "Base", "DeclarativeBase", "DeclarativeBaseNoMeta",  # SQLAlchemy
    "Model",  # Django (models.Model) and Flask-SQLAlchemy
}

# FastAPI / Flask decorator patterns
_ENDPOINT_DECORATORS = re.compile(
    r"^(?:app|router|blueprint|api)\.(get|post|put|patch|delete|head|options|route)$",
    re.IGNORECASE,
)


class PythonParser(BaseParser):
    def __init__(self) -> None:
        self._parser = Parser(_PY_LANGUAGE)

    def can_parse(self, record: FileRecord) -> bool:
        return record.language == Language.PYTHON

    def parse(self, record: FileRecord) -> ParseResult:
        result = ParseResult(file_record=record)
        try:
            tree = self._parser.parse(record.content)
            ctx = _ParseContext(record, result)
            ctx.visit(tree.root_node)
        except Exception as exc:
            result.errors.append(f"Parse error: {exc}")
            log.debug("Python parse error in %s: %s", record.rel_path, exc)
        return result


class _ParseContext:
    """Stateful visitor that walks a tree-sitter Python CST."""

    def __init__(self, record: FileRecord, result: ParseResult) -> None:
        self._rec = record
        self._res = result
        self._module_fqn = record.rel_path.replace("/", ".").removesuffix(".py")
        self._class_stack: list[str] = []  # FQN stack for nested classes

        # Emit the FileNode
        self._file_node = FileNode(
            node_id=make_node_id(record.rel_path, record.rel_path),
            node_type=NodeType.FILE,
            name=record.abs_path.name,
            fqn=record.rel_path,
            language=Language.PYTHON,
            file_path=record.rel_path,
            extension=record.extension,
            size_bytes=record.size_bytes,
            content_hash=record.content_hash,
        )
        result.nodes.append(self._file_node)

    # ── Tree walking ─────────────────────────────────────────────────────────

    def visit(self, node: Node) -> None:
        if node.type == "class_definition":
            self._visit_class(node)
        elif node.type in ("function_definition", "async_function_definition"):
            self._visit_function(node, inside_class=bool(self._class_stack))
        elif node.type in ("import_statement", "import_from_statement"):
            self._visit_import(node)
        elif node.type == "decorated_definition":
            self._visit_decorated(node)
        else:
            for child in node.children:
                self.visit(child)

    def _visit_class(self, node: Node, decorators: list[str] | None = None) -> None:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return
        name = self._text(name_node)
        fqn = self._make_fqn(name)
        span = self._span(node)

        bases = self._extract_bases(node)
        is_orm = (
            any(b in _ORM_BASES or b.endswith(".Model") for b in bases)
            and self._has_orm_body(node)
        )

        docstring = self._extract_docstring(node.child_by_field_name("body"))

        cls_node: DbModelNode | ClassNode
        if is_orm:
            cls_node = DbModelNode(
                node_id=make_node_id(self._rec.rel_path, fqn),
                node_type=NodeType.DB_MODEL,
                name=name,
                fqn=fqn,
                language=Language.PYTHON,
                source_span=span,
                docstring=clean_docstring(docstring),
                orm_framework="sqlalchemy",
                fields=self._extract_class_variables(node),
            )
        else:
            cls_node = ClassNode(
                node_id=make_node_id(self._rec.rel_path, fqn),
                node_type=NodeType.CLASS,
                name=name,
                fqn=fqn,
                language=Language.PYTHON,
                source_span=span,
                docstring=clean_docstring(docstring),
                bases=bases,
                decorator_names=decorators or [],
            )

        self._res.nodes.append(cls_node)
        self._emit_contains(self._file_node.node_id, cls_node.node_id)

        # Walk class body for methods
        body = node.child_by_field_name("body")
        if body:
            self._class_stack.append(fqn)
            for child in body.children:
                if child.type in ("function_definition", "async_function_definition"):
                    self._visit_function(child, inside_class=True)
                elif child.type == "decorated_definition":
                    self._visit_decorated(child, inside_class=True)
            self._class_stack.pop()

    def _visit_function(
        self,
        node: Node,
        inside_class: bool = False,
        decorators: list[str] | None = None,
    ) -> None:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return
        name = self._text(name_node)
        fqn = self._make_fqn(name)
        span = self._span(node)
        is_async = node.type == "async_function_definition"
        params = self._extract_params(node)
        return_type = self._extract_return_type(node)
        docstring = self._extract_docstring(node.child_by_field_name("body"))
        sig = self._build_signature(name, params, return_type, is_async)
        dec_names = decorators or []

        is_test = name.startswith("test_") or "test" in (d.lower() for d in dec_names)
        fn_node: MethodNode | TestNode | FunctionNode
        is_endpoint, http_method, path_pattern, framework = self._detect_endpoint(dec_names)

        if inside_class and self._class_stack:
            fn_node = MethodNode(
                node_id=make_node_id(self._rec.rel_path, fqn),
                node_type=NodeType.METHOD,
                name=name,
                fqn=fqn,
                language=Language.PYTHON,
                source_span=span,
                docstring=clean_docstring(docstring),
                signature=sig,
                is_async=is_async,
                decorator_names=dec_names,
                parameter_names=params,
                return_type=return_type,
                class_fqn=self._class_stack[-1],
                is_static="staticmethod" in dec_names,
                is_classmethod="classmethod" in dec_names,
                is_property="property" in dec_names,
            )
        elif is_test:
            fn_node = TestNode(
                node_id=make_node_id(self._rec.rel_path, fqn),
                node_type=NodeType.TEST,
                name=name,
                fqn=fqn,
                language=Language.PYTHON,
                source_span=span,
                docstring=clean_docstring(docstring),
                test_framework="pytest",
                is_parametrized="pytest.mark.parametrize" in " ".join(dec_names),
            )
        else:
            fn_node = FunctionNode(
                node_id=make_node_id(self._rec.rel_path, fqn),
                node_type=NodeType.FUNCTION,
                name=name,
                fqn=fqn,
                language=Language.PYTHON,
                source_span=span,
                docstring=clean_docstring(docstring),
                signature=sig,
                is_async=is_async,
                decorator_names=dec_names,
                parameter_names=params,
                return_type=return_type,
            )

        self._res.nodes.append(fn_node)
        parent_id = (
            make_node_id(self._rec.rel_path, self._class_stack[-1])
            if inside_class and self._class_stack
            else self._file_node.node_id
        )
        self._emit_contains(parent_id, fn_node.node_id)

        if is_endpoint:
            ep_node = ApiEndpointNode(
                node_id=make_node_id(self._rec.rel_path, fqn + ":endpoint"),
                node_type=NodeType.API_ENDPOINT,
                name=f"{http_method} {path_pattern}",
                fqn=fqn + ":endpoint",
                language=Language.PYTHON,
                source_span=span,
                http_method=http_method,
                path_pattern=path_pattern,
                framework=framework,
            )
            self._res.nodes.append(ep_node)
            self._res.edges.append(
                ExposesEndpointEdge(
                    edge_id=make_edge_id(fn_node.node_id, EdgeType.EXPOSES_ENDPOINT, ep_node.node_id),
                    src_id=fn_node.node_id,
                    dst_id=ep_node.node_id,
                )
            )

        # Extract calls from body
        body = node.child_by_field_name("body")
        if body:
            self._extract_calls(body, fn_node.node_id)

    def _visit_decorated(self, node: Node, inside_class: bool = False) -> None:
        decorators: list[str] = []
        body_node: Node | None = None
        for child in node.children:
            if child.type == "decorator":
                decorators.append(self._text(child).lstrip("@"))
            elif child.type in ("function_definition", "async_function_definition"):
                body_node = child
            elif child.type == "class_definition":
                self._visit_class(child, decorators=decorators)
                return
        if body_node:
            self._visit_function(body_node, inside_class=inside_class, decorators=decorators)
        else:
            for child in node.children:
                self.visit(child)

    def _visit_import(self, node: Node) -> None:
        if node.type == "import_statement":
            # import foo, bar.baz
            for child in node.children:
                if child.type in ("dotted_name", "aliased_import"):
                    module = self._text(child.child_by_field_name("name") or child)
                    self._emit_import(module, [])
        elif node.type == "import_from_statement":
            module_node = node.child_by_field_name("module_name")
            module = self._text(module_node) if module_node else ""
            names: list[str] = []
            for child in node.children:
                if child.type == "import_as_names":
                    for n in child.children:
                        if n.type in ("identifier", "aliased_import"):
                            names.append(self._text(n.child_by_field_name("name") or n))
                elif child.type == "wildcard_import":
                    names = ["*"]
            self._emit_import(module, names)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _emit_contains(self, src_id: str, dst_id: str) -> None:
        self._res.edges.append(
            ContainsEdge(
                edge_id=make_edge_id(src_id, EdgeType.CONTAINS, dst_id),
                src_id=src_id,
                dst_id=dst_id,
            )
        )

    def _emit_import(self, module: str, names: list[str]) -> None:
        if not module:
            return
        # Destination is a placeholder FQN; resolved later in Normalizer
        dst_fqn = module
        self._res.edges.append(
            ImportsEdge(
                edge_id=make_edge_id(self._file_node.node_id, EdgeType.IMPORTS, dst_fqn),
                src_id=self._file_node.node_id,
                dst_id=dst_fqn,  # unresolved — Normalizer will fix
                imported_names=names,
                confidence=1.0,
            )
        )

    def _extract_calls(self, body: Node, caller_id: str) -> None:
        """Walk body and emit CALLS edges for direct call expressions."""
        for child in body.children:
            self._find_calls(child, caller_id)

    def _find_calls(self, node: Node, caller_id: str) -> None:
        if node.type == "call":
            fn_node = node.child_by_field_name("function")
            if fn_node:
                callee_name = self._text(fn_node).split("(")[0]
                callee_id = callee_name  # unresolved — Normalizer will fix
                self._res.edges.append(
                    CallsEdge(
                        edge_id=make_edge_id(caller_id, EdgeType.CALLS, callee_id + caller_id),
                        src_id=caller_id,
                        dst_id=callee_id,  # placeholder
                        confidence=0.7,
                    )
                )
        for child in node.children:
            self._find_calls(child, caller_id)

    def _make_fqn(self, name: str) -> str:
        parts = [self._module_fqn] + self._class_stack + [name]
        return ".".join(parts)

    def _text(self, node: Node) -> str:
        return node.text.decode("utf-8", errors="replace") if node.text else ""

    def _span(self, node: Node) -> SourceSpan:
        return SourceSpan(
            file_path=self._rec.rel_path,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            start_byte=node.start_byte,
            end_byte=node.end_byte,
        )

    def _extract_bases(self, class_node: Node) -> list[str]:
        bases: list[str] = []
        args = class_node.child_by_field_name("superclasses")
        if args:
            for child in args.children:
                if child.type not in (",", "(", ")"):
                    bases.append(self._text(child))
        return bases

    def _has_orm_body(self, class_node: Node) -> bool:
        """Return True only if the class body has SQLAlchemy/Django ORM markers."""
        body = class_node.child_by_field_name("body")
        if not body:
            return False
        body_text = self._text(body)
        return "__tablename__" in body_text or "Column(" in body_text

    def _extract_params(self, fn_node: Node) -> list[str]:
        params: list[str] = []
        p_node = fn_node.child_by_field_name("parameters")
        if p_node:
            for child in p_node.children:
                if child.type in ("identifier", "typed_parameter", "default_parameter"):
                    name_n = child.child_by_field_name("name") or child
                    if name_n.type == "identifier":
                        params.append(self._text(name_n))
        return params

    def _extract_return_type(self, fn_node: Node) -> str | None:
        rt = fn_node.child_by_field_name("return_type")
        return self._text(rt).lstrip("->").strip() if rt else None

    def _extract_docstring(self, body: Node | None) -> str | None:
        if not body:
            return None
        for child in body.children:
            if child.type == "expression_statement":
                for sub in child.children:
                    if sub.type == "string":
                        raw = self._text(sub)
                        return raw.strip("\"'").strip()
        return None

    def _extract_class_variables(self, class_node: Node) -> list[str]:
        """Extract field names from class variable assignments."""
        fields: list[str] = []
        body = class_node.child_by_field_name("body")
        if not body:
            return fields
        for child in body.children:
            if child.type == "expression_statement":
                for sub in child.children:
                    if sub.type == "assignment":
                        lhs = sub.child_by_field_name("left")
                        if lhs and lhs.type == "identifier":
                            fields.append(self._text(lhs))
        return fields

    def _build_signature(
        self, name: str, params: list[str], return_type: str | None, is_async: bool
    ) -> str:
        prefix = "async def " if is_async else "def "
        rt = f" -> {return_type}" if return_type else ""
        return f"{prefix}{name}({', '.join(params)}){rt}"

    def _detect_endpoint(
        self, decorators: list[str]
    ) -> tuple[bool, str, str, str]:
        """Return (is_endpoint, http_method, path_pattern, framework)."""
        for dec in decorators:
            m = _ENDPOINT_DECORATORS.match(dec)
            if m:
                method = m.group(1).upper()
                # Try to extract path from decorator argument (simplified)
                return True, method, "/unknown", "fastapi"
        return False, "", "", ""

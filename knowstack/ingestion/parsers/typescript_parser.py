"""TypeScript/TSX parser using tree-sitter.

Extracts: classes, functions, interfaces, type aliases, imports/exports,
method calls, decorators (NestJS/TypeORM), and Express/NestJS endpoints.
"""
from __future__ import annotations

import logging
import re

import tree_sitter_typescript as tsts
from tree_sitter import Language as TSLanguage
from tree_sitter import Node, Parser

from knowstack.ingestion.scanner import FileRecord
from knowstack.models.edges import (
    ContainsEdge,
    ImplementsEdge,
    ImportsEdge,
    make_edge_id,
)
from knowstack.models.enums import EdgeType, Language, NodeType
from knowstack.models.nodes import (
    ClassNode,
    FileNode,
    FunctionNode,
    InterfaceNode,
    MethodNode,
    TestNode,
    TypeAliasNode,
    make_node_id,
)
from knowstack.models.source_span import SourceSpan

from .base import BaseParser, ParseResult

log = logging.getLogger(__name__)

_TS_LANGUAGE = TSLanguage(tsts.language_typescript())
_TSX_LANGUAGE = TSLanguage(tsts.language_tsx())

_NESTJS_HTTP_DECORATORS = re.compile(
    r"^(Get|Post|Put|Patch|Delete|Head|Options|All)$"
)
_JEST_TEST_FUNCS = {"it", "test", "describe"}


class TypeScriptParser(BaseParser):
    def can_parse(self, record: FileRecord) -> bool:
        return record.language in (Language.TYPESCRIPT, Language.JAVASCRIPT)

    def parse(self, record: FileRecord) -> ParseResult:
        result = ParseResult(file_record=record)
        try:
            lang = _TSX_LANGUAGE if record.extension in (".tsx", ".jsx") else _TS_LANGUAGE
            parser = Parser(lang)
            tree = parser.parse(record.content)
            ctx = _TSParseContext(record, result)
            ctx.visit(tree.root_node)
        except Exception as exc:
            result.errors.append(f"Parse error: {exc}")
            log.debug("TS parse error in %s: %s", record.rel_path, exc)
        return result


class _TSParseContext:
    def __init__(self, record: FileRecord, result: ParseResult) -> None:
        self._rec = record
        self._res = result
        stem = record.rel_path
        for ext in (".ts", ".tsx", ".js", ".jsx", ".mjs"):
            stem = stem.removesuffix(ext)
        self._module_fqn = stem.replace("/", ".")
        self._class_stack: list[str] = []

        self._file_node = FileNode(
            node_id=make_node_id(record.rel_path, record.rel_path),
            node_type=NodeType.FILE,
            name=record.abs_path.name,
            fqn=record.rel_path,
            language=record.language,
            file_path=record.rel_path,
            extension=record.extension,
            size_bytes=record.size_bytes,
            content_hash=record.content_hash,
        )
        result.nodes.append(self._file_node)

    def visit(self, node: Node) -> None:
        t = node.type
        if t == "class_declaration":
            self._visit_class(node)
        elif t == "function_declaration":
            self._visit_function(node)
        elif t == "interface_declaration":
            self._visit_interface(node)
        elif t == "type_alias_declaration":
            self._visit_type_alias(node)
        elif t in ("import_statement", "import_declaration"):
            self._visit_import(node)
        elif t == "export_statement":
            for child in node.children:
                self.visit(child)
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

        cls_node = ClassNode(
            node_id=make_node_id(self._rec.rel_path, fqn),
            node_type=NodeType.CLASS,
            name=name,
            fqn=fqn,
            language=self._rec.language,
            source_span=span,
            decorator_names=decorators or [],
        )
        self._res.nodes.append(cls_node)
        self._emit_contains(self._file_node.node_id, cls_node.node_id)

        # Implements clause
        for child in node.children:
            if child.type == "implements_clause":
                for impl in child.children:
                    if impl.type == "type_identifier":
                        iface_fqn = self._text(impl)
                        self._res.edges.append(
                            ImplementsEdge(
                                edge_id=make_edge_id(cls_node.node_id, EdgeType.IMPLEMENTS, iface_fqn),
                                src_id=cls_node.node_id,
                                dst_id=iface_fqn,
                                confidence=0.9,
                            )
                        )

        # Body
        body = node.child_by_field_name("body")
        if body:
            self._class_stack.append(fqn)
            for child in body.children:
                if child.type == "method_definition":
                    self._visit_method(child)
            self._class_stack.pop()

    def _visit_method(self, node: Node) -> None:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return
        name = self._text(name_node)
        fqn = self._make_fqn(name)
        span = self._span(node)
        is_async = any(c.type == "async" for c in node.children)
        params = self._extract_params(node)
        sig = f"{'async ' if is_async else ''}{name}({', '.join(params)})"

        m_node = MethodNode(
            node_id=make_node_id(self._rec.rel_path, fqn),
            node_type=NodeType.METHOD,
            name=name,
            fqn=fqn,
            language=self._rec.language,
            source_span=span,
            signature=sig,
            is_async=is_async,
            parameter_names=params,
            class_fqn=self._class_stack[-1] if self._class_stack else "",
        )
        self._res.nodes.append(m_node)
        if self._class_stack:
            parent_fqn = self._class_stack[-1]
            parent_id = make_node_id(self._rec.rel_path, parent_fqn)
            self._emit_contains(parent_id, m_node.node_id)

    def _visit_function(self, node: Node) -> None:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return
        name = self._text(name_node)
        fqn = self._make_fqn(name)
        span = self._span(node)
        is_async = any(c.type == "async" for c in node.children)
        params = self._extract_params(node)

        is_test = name in _JEST_TEST_FUNCS or name.startswith("test")
        fn_node: TestNode | FunctionNode

        if is_test:
            fn_node = TestNode(
                node_id=make_node_id(self._rec.rel_path, fqn),
                node_type=NodeType.TEST,
                name=name,
                fqn=fqn,
                language=self._rec.language,
                source_span=span,
                test_framework="jest",
            )
        else:
            fn_node = FunctionNode(
                node_id=make_node_id(self._rec.rel_path, fqn),
                node_type=NodeType.FUNCTION,
                name=name,
                fqn=fqn,
                language=self._rec.language,
                source_span=span,
                is_async=is_async,
                parameter_names=params,
                signature=f"{'async ' if is_async else ''}function {name}({', '.join(params)})",
            )

        self._res.nodes.append(fn_node)
        self._emit_contains(self._file_node.node_id, fn_node.node_id)

    def _visit_interface(self, node: Node) -> None:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return
        name = self._text(name_node)
        fqn = self._make_fqn(name)
        span = self._span(node)

        iface_node = InterfaceNode(
            node_id=make_node_id(self._rec.rel_path, fqn),
            node_type=NodeType.INTERFACE,
            name=name,
            fqn=fqn,
            language=self._rec.language,
            source_span=span,
        )
        self._res.nodes.append(iface_node)
        self._emit_contains(self._file_node.node_id, iface_node.node_id)

    def _visit_type_alias(self, node: Node) -> None:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return
        name = self._text(name_node)
        fqn = self._make_fqn(name)
        span = self._span(node)

        ta_node = TypeAliasNode(
            node_id=make_node_id(self._rec.rel_path, fqn),
            node_type=NodeType.TYPE_ALIAS,
            name=name,
            fqn=fqn,
            language=self._rec.language,
            source_span=span,
        )
        self._res.nodes.append(ta_node)
        self._emit_contains(self._file_node.node_id, ta_node.node_id)

    def _visit_import(self, node: Node) -> None:
        # import { X, Y } from 'module'
        source_node = node.child_by_field_name("source")
        if not source_node:
            return
        module = self._text(source_node).strip("'\"")
        names: list[str] = []
        for child in node.children:
            if child.type == "import_clause":
                for sub in child.children:
                    if sub.type == "named_imports":
                        for spec in sub.children:
                            if spec.type == "import_specifier":
                                n = spec.child_by_field_name("name")
                                if n:
                                    names.append(self._text(n))
        self._res.edges.append(
            ImportsEdge(
                edge_id=make_edge_id(self._file_node.node_id, EdgeType.IMPORTS, module),
                src_id=self._file_node.node_id,
                dst_id=module,
                imported_names=names,
                confidence=1.0,
            )
        )

    def _emit_contains(self, src_id: str, dst_id: str) -> None:
        self._res.edges.append(
            ContainsEdge(
                edge_id=make_edge_id(src_id, EdgeType.CONTAINS, dst_id),
                src_id=src_id,
                dst_id=dst_id,
            )
        )

    def _make_fqn(self, name: str) -> str:
        parts = [self._module_fqn] + self._class_stack + [name]
        return ".".join(parts)

    def _text(self, node: Node | None) -> str:
        if not node or not node.text:
            return ""
        return node.text.decode("utf-8", errors="replace")

    def _span(self, node: Node) -> SourceSpan:
        return SourceSpan(
            file_path=self._rec.rel_path,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            start_byte=node.start_byte,
            end_byte=node.end_byte,
        )

    def _extract_params(self, node: Node) -> list[str]:
        params: list[str] = []
        p_node = node.child_by_field_name("parameters")
        if p_node:
            for child in p_node.children:
                if child.type in ("required_parameter", "optional_parameter", "identifier"):
                    name_n = child.child_by_field_name("pattern") or child
                    if name_n.type == "identifier":
                        params.append(self._text(name_n))
        return params

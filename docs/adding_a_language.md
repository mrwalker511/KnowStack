# Adding a New Language

KnowStack is designed to be extended to any language supported by tree-sitter. Adding a new language requires four changes: installing the grammar, registering the file extension, implementing the parser, and registering the parser in the pipeline.

This guide walks through adding Go support as a concrete example. The same pattern applies to any other language.

## Step 1: Install the grammar package

```bash
pip install tree-sitter-go
```

Check the [tree-sitter GitHub organization](https://github.com/tree-sitter) for the full list of available grammar packages. Most popular languages are available.

## Step 2: Register the file extension

Open `knowstack/models/enums.py` and make two additions.

First, add the language value to the `Language` enum:

```python
class Language(StrEnum):
    PYTHON = "python"
    TYPESCRIPT = "typescript"
    JAVASCRIPT = "javascript"
    GO = "go"          # ← add this
    # ...
```

Second, add the extension mapping in `Language.from_extension()`:

```python
@classmethod
def from_extension(cls, ext: str) -> "Language":
    _MAP = {
        ".py": cls.PYTHON,
        ".ts": cls.TYPESCRIPT,
        ".go": cls.GO,   # ← add this
        # ...
    }
    return _MAP.get(ext.lower(), cls.UNKNOWN)
```

Also add `.go` to the `include_extensions` default in `knowstack/config/schema.py`:

```python
include_extensions: list[str] = Field(
    default_factory=lambda: [
        ".py", ".ts", ".tsx", ".js", ".jsx",
        ".go",                              # ← add this
        ".json", ".yaml", ".yml", ".toml",
    ]
)
```

## Step 3: Implement the parser

Create `knowstack/ingestion/parsers/go_parser.py`. The file below is a complete, working starting point that extracts functions, imports, and their containment relationships. Extend it to cover structs, interfaces, method receivers, and call edges as needed.

```python
"""Go parser using tree-sitter.

Extracts: functions, imports. Extend to cover struct types, interfaces,
method receivers, and call edges.
"""
from __future__ import annotations

import logging

import tree_sitter_go as tsgo
from tree_sitter import Language as TSLanguage, Node, Parser

from knowstack.ingestion.parsers.base import BaseParser, ParseResult
from knowstack.ingestion.scanner import FileRecord
from knowstack.models.edges import ContainsEdge, ImportsEdge, make_edge_id
from knowstack.models.enums import EdgeType, Language, NodeType
from knowstack.models.nodes import FileNode, FunctionNode, make_node_id
from knowstack.models.source_span import SourceSpan

log = logging.getLogger(__name__)

_GO_LANGUAGE = TSLanguage(tsgo.language())


class GoParser(BaseParser):
    def __init__(self) -> None:
        self._parser = Parser(_GO_LANGUAGE)

    def can_parse(self, record: FileRecord) -> bool:
        return record.language == Language.GO

    def parse(self, record: FileRecord) -> ParseResult:
        result = ParseResult(file_record=record)
        try:
            tree = self._parser.parse(record.content)
            ctx = _GoParseContext(record, result)
            ctx.visit(tree.root_node)
        except Exception as exc:
            result.errors.append(f"Parse error: {exc}")
            log.debug("Go parse error in %s: %s", record.rel_path, exc)
        return result


class _GoParseContext:
    def __init__(self, record: FileRecord, result: ParseResult) -> None:
        self._rec = record
        self._res = result
        stem = record.rel_path.removesuffix(".go")
        self._module_fqn = stem.replace("/", ".")

        self._file_node = FileNode(
            node_id=make_node_id(record.rel_path, record.rel_path),
            node_type=NodeType.FILE,
            name=record.abs_path.name,
            fqn=record.rel_path,
            language=Language.GO,
            file_path=record.rel_path,
            extension=record.extension,
            size_bytes=record.size_bytes,
            content_hash=record.content_hash,
        )
        result.nodes.append(self._file_node)

    def visit(self, node: Node) -> None:
        if node.type == "function_declaration":
            self._visit_function(node)
        elif node.type == "import_declaration":
            self._visit_import(node)
        else:
            for child in node.children:
                self.visit(child)

    def _visit_function(self, node: Node) -> None:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return
        name = self._text(name_node)
        fqn = f"{self._module_fqn}.{name}"

        fn_node = FunctionNode(
            node_id=make_node_id(self._rec.rel_path, fqn),
            node_type=NodeType.FUNCTION,
            name=name,
            fqn=fqn,
            language=Language.GO,
            source_span=SourceSpan(
                file_path=self._rec.rel_path,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                start_byte=node.start_byte,
                end_byte=node.end_byte,
            ),
        )
        self._res.nodes.append(fn_node)
        self._res.edges.append(
            ContainsEdge(
                edge_id=make_edge_id(
                    self._file_node.node_id, EdgeType.CONTAINS, fn_node.node_id
                ),
                src_id=self._file_node.node_id,
                dst_id=fn_node.node_id,
            )
        )

    def _visit_import(self, node: Node) -> None:
        # Go: import "pkg/path" or import ( "a" \n "b" )
        for child in node.children:
            if child.type == "import_spec":
                path_node = child.child_by_field_name("path")
                if path_node:
                    module = self._text(path_node).strip('"')
                    self._res.edges.append(
                        ImportsEdge(
                            edge_id=make_edge_id(
                                self._file_node.node_id, EdgeType.IMPORTS, module
                            ),
                            src_id=self._file_node.node_id,
                            dst_id=module,
                            imported_names=[],
                            confidence=1.0,
                        )
                    )

    def _text(self, node: Node) -> str:
        return node.text.decode("utf-8", errors="replace") if node.text else ""
```

### Reference implementations

Study these parsers before writing a new one — they cover all supported extraction patterns:

- `knowstack/ingestion/parsers/python_parser.py` — classes, methods, decorators, ORM models, API endpoints, test functions, async detection
- `knowstack/ingestion/parsers/typescript_parser.py` — classes, interfaces, type aliases, NestJS decorators

## Step 4: Register the parser in the pipeline

Open `knowstack/ingestion/pipeline.py` and add the new parser to the list:

```python
from knowstack.ingestion.parsers.go_parser import GoParser

# Inside IngestionPipeline.__init__():
self._parsers = [
    PythonParser(),
    TypeScriptParser(),
    GoParser(),         # ← add here
    ConfigParser(),
]
```

## What to extract — priority order

Focus on high-signal extractions first:

1. **Functions and methods** — most query-relevant; enables call-graph traversal
2. **Imports** — required for cross-file reference resolution in the Normalizer
3. **Types and interfaces** — enables `IMPLEMENTS` edges
4. **Call expressions** — powers `PATH` and `DEPENDENTS` queries
5. **Docstrings / comments** — improves semantic search quality
6. **Decorators and annotations** — enables ORM model and endpoint detection

## Testing your parser

Add a fixture directory `tests/fixtures/go_sample/` with a small but representative Go file (a service with a struct, a method, and a few imports). Then write parser unit tests mirroring `tests/unit/test_python_parser.py` or `tests/unit/test_typescript_parser.py`.

```bash
# Run just your new tests during development
pytest tests/unit/test_go_parser.py -v

# Run the full suite before submitting
make test
```

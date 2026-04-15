# Adding a New Language

KnowStack is designed to be extended to any language supported by tree-sitter.
Adding a new language requires three changes.

## Step 1: Install the grammar

```bash
pip install tree-sitter-go   # example: Go support
```

Check [tree-sitter GitHub organization](https://github.com/tree-sitter) for
available grammar packages.

## Step 2: Add the extension mapping

In `knowstack/models/enums.py`, add to `Language.from_extension()`:

```python
"go": cls.GO,
```

And add `GO = "go"` to the `Language` enum.

## Step 3: Implement the parser

Create `knowstack/ingestion/parsers/go_parser.py`:

```python
import tree_sitter_go as tsgo
from tree_sitter import Language as TSLanguage, Parser

from knowstack.ingestion.parsers.base import BaseParser, ParseResult
from knowstack.ingestion.scanner import FileRecord
from knowstack.models.enums import Language

_GO_LANGUAGE = TSLanguage(tsgo.language())


class GoParser(BaseParser):
    def __init__(self) -> None:
        self._parser = Parser(_GO_LANGUAGE)

    def can_parse(self, record: FileRecord) -> bool:
        return record.language == Language.GO

    def parse(self, record: FileRecord) -> ParseResult:
        result = ParseResult(file_record=record)
        tree = self._parser.parse(record.content)
        # Walk tree.root_node and emit nodes/edges
        # ... implement visitors for func_declaration, type_declaration, etc.
        return result
```

## Step 4: Register the parser

In `knowstack/ingestion/pipeline.py`, add to the parsers list:

```python
from knowstack.ingestion.parsers.go_parser import GoParser

self._parsers = [
    PythonParser(),
    TypeScriptParser(),
    GoParser(),         # ← add here
    ConfigParser(),
]
```

## What to extract

Focus on the highest-signal extractions first:

1. **Functions/methods** — most query-relevant, most call edges
2. **Imports** — critical for cross-file dependency resolution
3. **Types/interfaces** — essential for IMPLEMENTS edges
4. **Calls** — enables PATH and DEPENDENTS queries

Docstrings, decorators, and ORM patterns can come later.

## Testing

Add a fixture directory `tests/fixtures/go_sample/` with a small but
representative Go file set, then write parser unit tests mirroring
`tests/unit/test_python_parser.py`.

Run: `pytest tests/unit/test_go_parser.py -v`

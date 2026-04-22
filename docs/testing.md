# Testing

KnowStack has two test tiers: fast unit tests that run with no I/O and slower integration tests that build a real in-process graph. Both are in the `tests/` directory.

## Running tests

```bash
# Full suite with coverage report (slowest — runs all tiers)
make test

# Fast iteration — stop on first failure, no coverage overhead
make test-fast

# Unit tests only (no I/O, no embedding model download)
make test-unit

# Integration tests only (builds real Kuzu + ChromaDB instances)
make test-integration
```

### Running a single test file or function

```bash
# All tests in a file
pytest tests/unit/test_python_parser.py -v

# A single test function
pytest tests/unit/test_python_parser.py::test_parser_extracts_functions -v

# All tests matching a keyword
pytest -k "parser" -v
```

### Filtering by marker

Integration tests are marked with `@pytest.mark.integration`. Unit tests carry no marker.

```bash
# Only integration tests
pytest -m integration -v

# Everything except integration tests
pytest -m "not integration" -q
```

## Test structure

```
tests/
├── conftest.py                   # Shared fixtures (file records, configs, indexed repo)
├── fixtures/
│   ├── python_sample/            # Synthetic Python repo (auth, models, API)
│   └── typescript_sample/        # Synthetic TypeScript repo (AuthService, types)
├── unit/                         # Fast tests — no I/O
│   ├── test_python_parser.py
│   ├── test_typescript_parser.py
│   ├── test_models.py            # Includes config parser tests
│   ├── test_normalizer.py
│   ├── test_context_packer.py
│   ├── test_ranker.py
│   ├── test_intent_classifier.py
│   └── test_query_builder.py
└── integration/                  # Slower tests — builds real graph
    ├── test_ingestion_pipeline.py
    ├── test_incremental_pipeline.py
    └── test_incremental_correctness.py
```

## Writing new tests

### Unit tests

Unit tests use the `FileRecord` fixtures from `conftest.py` and never touch the filesystem beyond reading fixture files.

```python
def test_my_parser_extracts_something(auth_file_record):
    from knowstack.ingestion.parsers.python_parser import PythonParser
    result = PythonParser().parse(auth_file_record)
    names = {n.name for n in result.nodes}
    assert "authenticate" in names
```

### Integration tests

Integration tests use the `indexed_repo` fixture, which copies the Python sample into a temporary directory, runs a full pipeline, and returns `(repo_dir, config)`.

```python
@pytest.mark.integration
def test_pipeline_idempotent(indexed_repo):
    repo_dir, config = indexed_repo
    from knowstack.graph.store import GraphStore
    store = GraphStore(config.db_path)
    rows = store.cypher("MATCH (n:Function) RETURN count(n) AS c")
    assert rows[0]["c"] > 0
    store.close()
```

### Adding a language fixture

1. Create `tests/fixtures/<lang>_sample/` with representative source files
2. Add a `<lang>_sample_dir` fixture to `tests/conftest.py`
3. Write `tests/unit/test_<lang>_parser.py` mirroring `test_python_parser.py`

## Coverage

The `make test` target generates a terminal coverage report via `pytest-cov`. The source under measurement is the `knowstack/` package.

To generate an HTML report:

```bash
pytest --cov=knowstack --cov-report=html
open htmlcov/index.html
```

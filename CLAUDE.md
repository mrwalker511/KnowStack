# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

KnowStack converts codebases into queryable knowledge graphs for LLM context
retrieval and developer exploration.

## Commands

```bash
make install-dev      # pip install -e ".[dev,serve]"
make test             # pytest (full suite with coverage)
make test-fast        # pytest -x -q --no-cov (fast iteration)
make lint             # ruff check
make fmt              # ruff format
make typecheck        # mypy
make clean            # remove .knowstack/, dist/, caches
```

Run a single test:
```bash
pytest tests/unit/test_python_parser.py::test_function_name
pytest -m integration   # integration tests only
```

## Architecture in 30 seconds

Six-stage pipeline: **Scanner → Parsers → Normalizer → Enricher → Writer → Embedder**

Two storage backends: **Kuzu** (property graph, Cypher) at `.knowstack/graph.kuzu` + **ChromaDB** (vectors) at `.knowstack/vectors`

Hybrid retrieval: **DSL graph queries + semantic search + RRF fusion + context packing**

## Key files

| File | Purpose |
|---|---|
| `knowstack/models/nodes.py` | All node types — the canonical data contract |
| `knowstack/models/edges.py` | All edge types |
| `knowstack/graph/store.py` | `GraphStore` — the only abstraction over Kuzu |
| `knowstack/graph/schema.py` | Kuzu DDL — edit this to change the graph schema |
| `knowstack/ingestion/pipeline.py` | Pipeline orchestrator — wires all 6 stages |
| `knowstack/ingestion/parsers/python_parser.py` | Python tree-sitter extractor |
| `knowstack/ingestion/parsers/typescript_parser.py` | TS/JS tree-sitter extractor |
| `knowstack/ingestion/normalizer.py` | Cross-file reference resolution |
| `knowstack/retrieval/query_engine.py` | Public retrieval API |
| `knowstack/retrieval/context_packer.py` | Token-budget-aware context formatting |
| `knowstack/nl/query_builder.py` | NL → DSL translation (rule-based + optional LLM) |
| `knowstack/cli/main.py` | CLI entry point |

## Node ID convention

```python
node_id = sha256(f"{repo_root}:{fqn}").hexdigest()[:16]
```

Same file + same FQN = same ID across re-index runs. Required for idempotent upserts.

## Programmatic API

```python
from knowstack.retrieval.query_engine import QueryEngine
from knowstack.config.schema import KnowStackConfig

config = KnowStackConfig(repo_path=Path("."))
engine = QueryEngine(config)
result = engine.query_dsl("FIND function WHERE tag = auth")
# result.nodes, result.paths, result.context (LLM-ready string), result.intent
```

## Adding a language

1. `pip install tree-sitter-<lang>`
2. Add extension → `Language` mapping in `knowstack/models/enums.py`
3. Create `knowstack/ingestion/parsers/<lang>_parser.py` implementing `BaseParser`
4. Register in `knowstack/ingestion/pipeline.py`

See `docs/adding_a_language.md` for a full walkthrough.

## Test structure

```
tests/
├── conftest.py               # shared fixtures
├── fixtures/                 # small synthetic repos (Python + TypeScript)
├── unit/                     # isolated component tests (fast, no I/O)
│   ├── test_python_parser.py
│   ├── test_models.py
│   ├── test_normalizer.py
│   ├── test_context_packer.py
│   ├── test_ranker.py
│   └── test_intent_classifier.py
└── integration/              # end-to-end pipeline tests (slower)
    └── test_ingestion_pipeline.py
```

Integration tests are marked `@pytest.mark.integration`. Unit tests have no I/O and run against `tests/fixtures/` synthetic repos.

## Design principles

- **Correctness > completeness**: drop unresolvable edges rather than guess
- **Embeddable > server-based**: Kuzu + ChromaDB need no daemon
- **Frozen models**: all `BaseNode` subclasses use `ConfigDict(frozen=True)` — no mutation in pipeline
- **Idempotent writes**: `MERGE` (not `CREATE`) throughout the writer
- **Offline-first**: embeddings use a local model (BAAI/bge-small-en-v1.5); no API key required for basic use. `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` are optional for LLM-powered query building only.

## Current phase: MVP (Phase 1-3 complete)

- ✅ Phase 1: Core ingestion (Python parser, Kuzu, ChromaDB)
- ✅ Phase 2: Query layer (DSL, hybrid retrieval, context packing)
- ✅ Phase 3: NL integration (rule-based + LLM-optional)
- 🔲 Phase 4: Scale & incremental hardening (partial pipeline exists in `knowstack/incremental/`, needs benchmarking)
- 🔲 Phase 5: HTTP API (`knowstack serve` — FastAPI + Uvicorn, install with `.[serve]`)
- 🔲 Phase 6: Multi-repo / org-wide support

# KnowStack

Turn any codebase into a queryable knowledge graph — optimized for LLM context retrieval, developer exploration, and change-impact analysis.

## What it does

KnowStack reads your code, extracts every meaningful symbol and relationship, stores them in an embedded property graph, and lets you ask questions about your codebase in plain English or a simple DSL.

```
# Index your repo (one-time, ~60s for a 50k-line codebase)
knowstack index ./myapp

# Ask a structural question
knowstack query "DEPENDENTS PaymentService"

# Ask in natural language
knowstack query "How does authentication flow through the app?" --mode nl

# Explore a symbol's neighbourhood
knowstack inspect node AuthService --depth 2

# Get an LLM-ready context block
knowstack query "FIND function WHERE tag = auth" --context
```

## Quick Start

```bash
pip install knowstack
knowstack index .
knowstack query --interactive
```

See **[docs/quickstart.md](docs/quickstart.md)** for a full walkthrough.

## Answers questions like

- *"How does authentication flow through this app?"*
- *"What code paths write to the customer table?"*
- *"Which services depend on FeatureFlagManager?"*
- *"What breaks if I change this interface?"*
- *"Where is retry logic implemented?"*
- *"Which files are most central to the checkout pipeline?"*

## What gets indexed

**Node types:** files, directories, classes, functions, methods, interfaces, type aliases, API endpoints, database models, tests, config files

**Relationships:** `CONTAINS`, `IMPORTS`, `CALLS`, `INHERITS`, `IMPLEMENTS`, `READS_FROM`, `WRITES_TO`, `TESTED_BY`, `EXPOSES_ENDPOINT`, `DEFINES`

**Languages:** Python, TypeScript/JavaScript (more via tree-sitter grammars)

## Architecture in one diagram

```
Repository
    │
    ▼
┌──────────┐    ┌───────────┐    ┌────────────┐    ┌──────────┐
│  Scanner  │───▶│  Parsers  │───▶│ Normalizer │───▶│ Enricher │
│ (Stage 1) │    │ (Stage 2) │    │ (Stage 3)  │    │ (Stage 4)│
└──────────┘    └───────────┘    └────────────┘    └──────────┘
                                                         │
                              ┌──────────────────────────┤
                              │                          │
                              ▼                          ▼
                        ┌──────────┐             ┌───────────┐
                        │  Kuzu    │             │ ChromaDB  │
                        │  Graph   │             │  Vectors  │
                        │ (Stage 5)│             │ (Stage 6) │
                        └──────────┘             └───────────┘
                              │                          │
                              └──────────┬───────────────┘
                                         │
                                    ┌────▼─────┐
                                    │  Query   │
                                    │  Engine  │
                                    └──────────┘
```

## Documentation

| Document | What it covers |
|---|---|
| [docs/quickstart.md](docs/quickstart.md) | Install, first index, first query |
| [docs/query_dsl.md](docs/query_dsl.md) | DSL grammar and all query types |
| [docs/architecture.md](docs/architecture.md) | Full system design, data model, design decisions |
| [docs/adding_a_language.md](docs/adding_a_language.md) | How to add a new language parser |
| [docs/llm_integration.md](docs/llm_integration.md) | Using KnowStack with LLM APIs |

## Configuration

Drop a `knowstack.toml` in your repo root:

```toml
[knowstack]
embedding_model = "BAAI/bge-small-en-v1.5"
context_max_tokens = 6000
exclude_patterns = ["**/generated/**", "**/vendor/**"]
```

See [docs/configuration.md](docs/configuration.md) for all options.

## Technology choices

| Concern | Choice | Why |
|---|---|---|
| Graph store | Kuzu (embedded) | Zero-config, native Cypher, typed schemas |
| Parser | tree-sitter | Multi-language, error-tolerant, byte offsets |
| Vectors | ChromaDB (embedded) | Persistent, metadata-filtered ANN, no server |
| Embeddings | bge-small-en-v1.5 | CPU-fast, high quality, no API dependency |
| Language | Python 3.11+ | Rich ecosystem for all three concerns |

## License

MIT

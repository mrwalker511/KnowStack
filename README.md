# KnowStack

Turn any codebase into a queryable knowledge graph — built for LLM context retrieval, developer exploration, and change-impact analysis.

## Overview

KnowStack reads your source code, extracts every meaningful symbol and relationship, and stores them in an embedded property graph. You can then ask questions about your codebase in plain English or a simple DSL, and receive structured results or token-efficient context blocks ready for any LLM.

```
# Index a repository (one-time; ~60 seconds for a 50,000-line codebase)
knowstack index ./myapp

# Structural query
knowstack query "DEPENDENTS PaymentService"

# Natural-language query
knowstack query "How does authentication flow through the app?" --mode nl

# Change-impact analysis
knowstack query "IMPACT UserService DEPTH 4"

# LLM-ready context block
knowstack query "FIND function WHERE tag = auth" --context
```

## Prerequisites

- Python 3.11 or later
- No external services required — all storage is embedded (Kuzu + ChromaDB)
- An internet connection on first run to download the embedding model (~130 MB, cached automatically)

## Installation

```bash
# Core package (ingestion + retrieval)
pip install knowstack

# Development extras (tests, linter, type checker)
pip install "knowstack[dev]"

# HTTP API extras (FastAPI server)
pip install "knowstack[serve]"
```

## Quick Start

```bash
# 1. Index your repository
knowstack index .

# 2. Run an interactive query session
knowstack query --interactive
```

See **[docs/quickstart.md](docs/quickstart.md)** for a complete walkthrough, including first-query examples and configuration.

## What KnowStack can answer

- *"How does authentication flow through this application?"*
- *"Which code paths write to the customer table?"*
- *"What depends on FeatureFlagManager? What breaks if it changes?"*
- *"Where is retry logic implemented?"*
- *"Which files are most central to the checkout pipeline?"*
- *"Show me all API endpoints exposed by the user service."*

## What gets indexed

**Node types:** files, classes, functions, methods, interfaces, type aliases, API endpoints, database models, test functions, configuration files

**Relationships:** `CONTAINS`, `IMPORTS`, `CALLS`, `INHERITS`, `IMPLEMENTS`, `READS_FROM`, `WRITES_TO`, `TESTED_BY`, `EXPOSES_ENDPOINT`, `DEFINES`

**Languages:** Python, TypeScript, JavaScript. Additional languages can be added via tree-sitter grammars — see [docs/adding_a_language.md](docs/adding_a_language.md).

## Architecture

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

See [docs/architecture.md](docs/architecture.md) for a detailed description of each stage, the data model, and design decisions.

## Documentation

| Document | Description |
|---|---|
| [docs/quickstart.md](docs/quickstart.md) | Installation, first index, first query |
| [docs/query_dsl.md](docs/query_dsl.md) | Full DSL grammar and all query types |
| [docs/architecture.md](docs/architecture.md) | System design, data model, design decisions |
| [docs/configuration.md](docs/configuration.md) | All configuration options with defaults |
| [docs/llm_integration.md](docs/llm_integration.md) | Connecting Anthropic, OpenAI, or Ollama |
| [docs/adding_a_language.md](docs/adding_a_language.md) | Step-by-step guide to adding a new language |
| [docs/testing.md](docs/testing.md) | Running and writing tests |
| [docs/troubleshooting.md](docs/troubleshooting.md) | Common issues and solutions |

## Configuration

Place a `knowstack.toml` file in your repository root:

```toml
[knowstack]
embedding_model = "BAAI/bge-small-en-v1.5"
context_max_tokens = 6000
exclude_patterns = ["**/generated/**", "**/vendor/**"]
```

See [docs/configuration.md](docs/configuration.md) for the full reference.

## Programmatic API

```python
from pathlib import Path
from knowstack.retrieval.query_engine import QueryEngine
from knowstack.config.schema import KnowStackConfig

config = KnowStackConfig(repo_path=Path("."))
with QueryEngine(config) as engine:
    result = engine.query_dsl("FIND function WHERE tag = auth")
    print(result.context)   # LLM-ready context string
    print(result.nodes)     # Ranked list of matching nodes
```

## Technology

| Concern | Choice | Rationale |
|---|---|---|
| Graph store | Kuzu (embedded) | Zero-config, native Cypher, typed schemas |
| Parser | tree-sitter | Multi-language, error-tolerant, byte-accurate offsets |
| Vectors | ChromaDB (embedded) | Persistent, metadata-filtered ANN, no server required |
| Embeddings | BAAI/bge-small-en-v1.5 | CPU-fast, high quality, no API key required |
| LLM (optional) | Ollama / Anthropic / OpenAI | NL→DSL translation; Ollama runs fully offline |
| Language | Python 3.11+ | Rich ecosystem for all three storage and ML concerns |

## Support

File issues and feature requests at the project issue tracker.

## License

MIT

# Quickstart

## Installation

```bash
pip install knowstack
# or from source:
git clone https://github.com/you/knowstack
cd knowstack
pip install -e ".[dev]"
```

Python 3.11+ required.

## Index your first repo

```bash
cd ~/projects/myapp
knowstack index .
```

This runs the full pipeline:
1. Scans all `.py`, `.ts`, `.tsx`, `.js`, `.json`, `.yaml`, `.toml` files
2. Parses each file with tree-sitter, extracting symbols and relationships
3. Resolves cross-file imports and calls
4. Enriches with git history (change frequency, last commit)
5. Stores everything in `.knowstack/graph.kuzu`
6. Embeds all nodes into `.knowstack/vectors` (ChromaDB)
7. Computes PageRank centrality scores

Output: `.knowstack/` directory in your repo root (git-ignored by default).

**Typical times:**
- 1k files: ~10s
- 10k files: ~90s
- 50k files: ~8min (most time is embedding)

Skip embedding to index faster: `knowstack index . --no-embed`

## Your first queries

### DSL queries (precise, graph-based)

```bash
# Find all authentication-tagged functions
knowstack query "FIND function WHERE tag = auth"

# What depends on PaymentService?
knowstack query "DEPENDENTS PaymentService"

# Impact analysis: what breaks if UserRepository changes?
knowstack query "IMPACT UserRepository DEPTH 4"

# Path from login endpoint to database writes
knowstack query "PATH FROM login TO database"

# Find all API endpoints
knowstack query "FIND endpoint LIMIT 50"
```

### Semantic queries (fuzzy, concept-based)

```bash
knowstack query "retry logic with exponential backoff" --mode semantic
knowstack query "authentication and session management" --mode semantic
```

### Natural language (requires LLM config for best results)

```bash
knowstack query "How does auth flow through this app?" --mode nl
knowstack query "What writes to the orders table?" --mode nl
```

### Get LLM-ready context

```bash
# Print a packed context block you can paste into any LLM
knowstack query "FIND function WHERE tag = checkout" --context

# Pipe directly into a prompt
knowstack query "DEPENDENTS PaymentProcessor" --context | pbcopy
```

### Interactive REPL

```bash
knowstack query --interactive
```

## Explore the graph

```bash
# Inspect a specific symbol
knowstack inspect node AuthService
knowstack inspect node "src.auth.service.AuthService" --depth 2

# Path between two symbols
knowstack inspect path login database

# Graph statistics
knowstack inspect stats
```

## Incremental re-indexing

After code changes, re-index only what changed:

```bash
knowstack index . --incremental
```

This hashes each file, diffs against the stored state, and only re-processes changed files. Fast even on large repos.

## Next steps

- [Query DSL reference](query_dsl.md) — all DSL syntax
- [Architecture](architecture.md) — how it works under the hood
- [Configuration](configuration.md) — all config options
- [LLM integration](llm_integration.md) — connect to Claude or GPT

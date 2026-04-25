# Architecture

## System overview

KnowStack is a six-stage ingestion pipeline feeding two storage backends
(graph + vector), with a hybrid retrieval layer on top.

```
┌─────────────────────────────────────────────────────────────────┐
│                      Ingestion Pipeline                         │
│                                                                 │
│  Scanner → Parsers → Normalizer → Enricher → Writer → Embedder │
│  (Stage 1) (Stage 2)  (Stage 3)   (Stage 4) (Stage 5) (Stage 6)│
└───────────────────────────────────┬─────────────────────────────┘
                                    │
                    ┌───────────────┴──────────────┐
                    │                              │
               ┌────▼─────┐                 ┌─────▼────┐
               │   Kuzu   │                 │ ChromaDB │
               │  (graph) │                 │ (vectors)│
               └────┬─────┘                 └─────┬────┘
                    │                              │
                    └───────────────┬──────────────┘
                                    │
                         ┌──────────▼──────────┐
                         │    Query Engine      │
                         │  DSL / semantic /    │
                         │  hybrid / NL         │
                         └──────────┬──────────┘
                                    │
                    ┌───────────────┼──────────────┐
                    │               │              │
               ┌────▼───┐    ┌─────▼────┐   ┌────▼────┐
               │  CLI   │    │ HTTP API │   │  LLM    │
               │        │    │(optional)│   │ Context │
               └────────┘    └──────────┘   └─────────┘
```

## Pipeline stages

### Stage 1: Scanner (`knowstack/ingestion/scanner.py`)

Walks the repo, respects `.gitignore` and configured exclude patterns, enforces
a file size limit (default 512 KB), and emits `FileRecord` objects with raw
bytes and a SHA-256 content hash.

### Stage 2: Parsers (`knowstack/ingestion/parsers/`)

Each language gets a `BaseParser` subclass. The current implementations:

- **`PythonParser`** — tree-sitter-python: classes, functions, methods, imports, calls, decorators, docstrings, ORM models, FastAPI/Flask endpoints, pytest tests
- **`TypeScriptParser`** — tree-sitter-typescript: classes, interfaces, type aliases, methods, imports, NestJS/TypeORM patterns
- **`ConfigParser`** — JSON/YAML/TOML: emits a single `ConfigFileNode` per file

Parsers are isolated: they only see one file and emit unresolved edge targets
(import paths, callee names). Cross-file resolution is Stage 3's job.

### Stage 3: Normalizer (`knowstack/ingestion/normalizer.py`)

Builds a global symbol table from all emitted nodes, then resolves:
- Relative and absolute Python imports → target `FileNode` node_ids
- TypeScript path imports → target node_ids
- Callee names → function/method node_ids (with confidence degradation for ambiguous matches)

Unresolvable edges (external dependencies, dynamic imports) are dropped silently.

### Stage 4: Enricher (`knowstack/ingestion/enricher.py`)

Adds non-structural metadata:
- **Git history** (GitPython): `change_frequency` (0–1), `last_modified_commit`
- **Auto-tagging**: path/name heuristics → semantic tags like `authentication`, `payments`
- **Preliminary importance score**: `centrality_score * (1 + change_frequency)` (centrality = 0 at this point; recomputed post-storage)

### Stage 5: Writer (`knowstack/ingestion/writer.py`)

Converts Pydantic node/edge models to flat dicts and upserts them into Kuzu
via `UNWIND MERGE` queries. Idempotent: re-indexing the same file produces
the same `node_id` (deterministic SHA-256 of repo_root + FQN) and overwrites.

After all nodes/edges are written, `compute_centrality()` runs PageRank on the
in-memory `CALLS + IMPORTS` graph (via NetworkX) and writes scores back.

### Stage 6: Embedder (`knowstack/ingestion/embedder.py`)

For each node, builds a short text representation:
```
{NodeType}: {fqn}
Signature: {signature}
Doc: {docstring[:300]}
File: {file_path}:{start_line}
```

Encodes with `BAAI/bge-small-en-v1.5` (33M params, 512-dim, CPU-fast) in
batches of 64. Stores vectors + metadata in ChromaDB for filtered ANN search.

## Storage

### Kuzu (graph)

- Embedded property graph database (no server process)
- Native Cypher query language
- One node table per `NodeType`, one relationship table per `EdgeType`
- Schema initialized on first run; idempotent `CREATE IF NOT EXISTS`
- Stored at `.knowstack/graph.kuzu`

### ChromaDB (vectors)

- Embedded, SQLite-backed vector store
- Single collection `"nodes"` with cosine distance metric
- Metadata fields: `node_type`, `fqn`, `file_path`, `language`, `importance_score`, `repo_id`
- Supports pre-filtering (e.g., `language = "python"`) before ANN search
- Stored at `.knowstack/vectors/`

## Retrieval

### Graph retrieval (`knowstack/retrieval/graph_retriever.py`)

Translates DSL queries to Cypher. Handles FIND, DEPENDENTS, IMPACT, and PATH.
Target symbol resolution uses exact FQN match → name contains → fuzzy fallback.

### Vector retrieval (`knowstack/retrieval/vector_retriever.py`)

Encodes the query string with the same embedding model and queries ChromaDB.
Returns cosine-similarity-ranked nodes with optional pre-filters.

### Hybrid retrieval (`knowstack/retrieval/hybrid_retriever.py`)

Fuses graph and vector results using Reciprocal Rank Fusion (RRF) with k=60.
Produces a combined ranking without requiring score normalization.

### Ranker (`knowstack/retrieval/ranker.py`)

Five-signal weighted score:

```
final = 0.35 * semantic_score      # cosine similarity
      + 0.25 * centrality_score    # PageRank (normalized within result set)
      + 0.20 * name_match_score    # exact/substring match to query terms
      + 0.10 * recency_score       # change frequency proxy
      + 0.10 * path_proximity      # graph distance from query anchor
```

### Context packer (`knowstack/retrieval/context_packer.py`)

Formats ranked nodes into a compact Markdown block within a token budget
(default 6000 tokens). Each node block contains: type, FQN, signature,
docstring excerpt, file location, and up to 5 direct relationships.
Most-relevant nodes appear first so truncation cuts the least signal.

## NL query layer

```
Question
   │
   ├── IntentClassifier (rule-based)
   │   → PATH | IMPACT | STRUCTURAL | SEMANTIC
   │
   ├── EntityExtractor (difflib fuzzy match against all FQNs)
   │   → ["UserRepository", "authenticate"]
   │
   └── QueryBuilder
       ├── Rule-based: intent + entities → DSL string
       └── LLM-based (optional): zero-shot DSL generation via Anthropic/OpenAI
```

## Data model

### Node ID generation

```python
node_id = sha256(f"{repo_root}:{fqn}").hexdigest()[:16]
```

Deterministic across runs. Same code in the same repo always gets the same ID.

### Edge confidence

| Source | Confidence |
|---|---|
| Proven static analysis (explicit import/call) | 1.0 |
| Heuristic (decorator-based endpoint detection) | 0.7 |
| Ambiguous name resolution | 0.4 |

### Importance score

```
importance = centrality_score * (1 + change_frequency)
```

Where `centrality_score` is PageRank on the `CALLS + IMPORTS` subgraph,
and `change_frequency` is the fraction of recent commits that touched the file.

## Incremental indexing

```
ChangeDetector:
  1. Load {file_path: content_hash} from Kuzu
  2. Walk filesystem, compute current hashes
  3. Diff → added, modified, deleted

PartialPipeline:
  1. Delete stale nodes (DETACH DELETE) from Kuzu
  2. Delete stale embeddings from ChromaDB (by file_path metadata filter)
  3. Run Stages 1-6 on changed files only
  4. Cross-file edge resolution still runs globally (changed files may affect others)
```

## Multi-Repo Workspaces

A workspace indexes multiple repositories into a **single shared Kuzu database and ChromaDB collection**. Every node and embedding carries a `repo_id` field that is used as a filter on every query path, guaranteeing per-repo isolation with no data leakage.

### Workspace manifest (`workspace.toml`)

```toml
[workspace]
db_path    = ".knowstack/workspace.kuzu"
vector_db_path = ".knowstack/workspace-vectors"

[[workspace.repos]]
path = "../service-a"          # relative or absolute
id   = "org/service-a"

[[workspace.repos]]
path = "/absolute/path/to/svc-b"
id   = "org/service-b"
```

### CLI commands

```bash
knowstack workspace init                          # create workspace.toml
knowstack workspace add /path/to/repo --id org/repo   # register a repo
knowstack workspace index                         # index all repos
knowstack workspace index org/repo-a              # index one repo
knowstack workspace query "authenticate" --repo org/service-a --mode semantic
knowstack workspace query "FIND function WHERE tag = auth" --repo org/service-a
knowstack workspace list
```

### Isolation guarantee

| Query path | repo_id threading |
|---|---|
| DSL (`FIND`, `DEPENDENTS`, `IMPACT`, `PATH`) | `WHERE n.repo_id = $rid` in every Cypher clause |
| Semantic vector search | ChromaDB `where={"repo_id": ...}` pre-filter |
| Hybrid (graph + vector) | Both paths scoped as above |
| NL | Delegates to semantic or DSL, both scoped |
| Incremental `ChangeDetector` | `WHERE f.repo_id = $rid` on hash load |

Omitting `--repo` returns results from all registered repos (cross-repo search).

## Design decisions and tradeoffs

| Decision | Choice | Alternative considered | Why chosen |
|---|---|---|---|
| Graph store | Kuzu | Neo4j, NetworkX+SQLite | Embedded + Cypher + typed schemas |
| Parser | tree-sitter | language-specific AST modules | Single API, error-tolerant, multi-language |
| Vector store | ChromaDB | FAISS, Qdrant | Embeddable, persistent, metadata-filtered |
| Embeddings | bge-small local | text-embedding-ada-002 | No API cost, works offline, 95% quality |
| Calls resolution | In-memory Normalizer | Runtime Cypher queries | Batch resolution is 10x faster |
| Centrality | Post-ingestion NetworkX PageRank | Online Kuzu graph algorithms | Avoids N+1 queries; runs once |

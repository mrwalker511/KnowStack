# Configuration Reference

KnowStack is configured via `knowstack.toml` (or `.knowstack.toml`) placed in
your repo root. All fields are optional — the defaults work for most repos.

## Full reference

```toml
[knowstack]

# ── Storage ──────────────────────────────────────────────────────────────────
# Where to store the graph database (relative to repo root)
db_path = ".knowstack/graph.kuzu"

# Where to store vector embeddings
vector_db_path = ".knowstack/vectors"

# ── Embedding ─────────────────────────────────────────────────────────────────
# Sentence-transformers model name (local, no API key needed)
embedding_model = "BAAI/bge-small-en-v1.5"

# "cpu" or "cuda" (if GPU available)
embedding_device = "cpu"

# Batch size for encoding — increase if you have GPU memory
embedding_batch_size = 64

# Maximum nodes to embed per node table; 0 = no limit (default)
# Set to a positive integer for very large repositories to cap memory usage
embed_limit = 0

# ── Ingestion ─────────────────────────────────────────────────────────────────
# Max file size to parse (bytes). Larger files are skipped with a warning.
max_file_size_bytes = 524288  # 512 KB

# Which file extensions to include
include_extensions = [".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".yaml", ".yml", ".toml"]

# Glob patterns to exclude (relative to repo root)
exclude_patterns = [
    "**/node_modules/**",
    "**/.git/**",
    "**/__pycache__/**",
    "**/dist/**",
    "**/build/**",
    "**/.venv/**",
    "**/venv/**",
    "**/*.min.js",
    "**/coverage/**",
    "**/vendor/**",        # add your own
    "**/generated/**",
]

# Parallel parser processes (increase for large repos on multi-core machines)
parse_workers = 4

# ── Git enrichment ────────────────────────────────────────────────────────────
# Set false to skip git history analysis (faster cold start)
enable_git_enrichment = true

# How many recent commits to analyse for change_frequency
git_history_limit = 500

# ── Retrieval ─────────────────────────────────────────────────────────────────
# Max tokens in a packed context block
context_max_tokens = 6000

# Default number of results returned
default_top_k = 20

# Max hops for PATH queries
max_call_depth = 10

# ── LLM (optional — enables --mode nl and DSL generation) ────────────────────
# "anthropic", "openai", or "ollama" — Ollama requires no API key
llm_provider = "anthropic"
# Model name for DSL generation. When omitted, a sensible default is chosen
# per provider: claude-haiku-4-5-20251001 (Anthropic), gpt-4o-mini (OpenAI),
# qwen2.5-coder:7b (Ollama).
# llm_model = "claude-haiku-4-5-20251001"
# API key: prefer the ANTHROPIC_API_KEY or OPENAI_API_KEY environment variable
# Ollama base URL (only used when llm_provider = "ollama")
# llm_ollama_base_url = "http://localhost:11434"

# ── Logging ───────────────────────────────────────────────────────────────────
log_level = "INFO"  # DEBUG | INFO | WARNING | ERROR
```

## Minimal config for a Python-only repo

```toml
[knowstack]
exclude_patterns = [
    "**/__pycache__/**",
    "**/.git/**",
    "**/migrations/**",
    "**/tests/fixtures/**",
]
```

## Minimal config for a TypeScript monorepo

```toml
[knowstack]
exclude_patterns = [
    "**/node_modules/**",
    "**/.git/**",
    "**/dist/**",
    "**/build/**",
    "**/__generated__/**",
]
parse_workers = 8
embedding_device = "cpu"
```

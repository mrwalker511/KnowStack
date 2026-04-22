# Troubleshooting

This page covers the most common issues encountered when installing, indexing, and querying KnowStack.

## Installation

### `pip install knowstack` fails with a build error

tree-sitter grammar packages require a C compiler. On Linux, install `build-essential`. On macOS, install the Xcode command-line tools:

```bash
xcode-select --install
```

### ImportError after installation

If you see `ModuleNotFoundError: No module named 'kuzu'` or similar, ensure you installed the correct extras:

```bash
pip install "knowstack[dev]"      # development extras
pip install "knowstack[serve]"    # HTTP API extras
```

---

## Indexing

### No nodes found after indexing

**Check 1 — file extensions.** KnowStack only indexes files whose extensions are in `include_extensions`. The defaults are `.py`, `.ts`, `.tsx`, `.js`, `.jsx`, `.json`, `.yaml`, `.yml`, `.toml`. If your codebase uses non-standard extensions (e.g., `.pyx`, `.mts`), add them to `knowstack.toml`:

```toml
[knowstack]
include_extensions = [".py", ".pyx", ".ts", ".mts"]
```

**Check 2 — exclude patterns.** Verify that your source files are not matched by `exclude_patterns`. Run `knowstack index . --verbose` to see which files are scanned.

**Check 3 — file size.** Files larger than `max_file_size_bytes` (default 512 KB) are skipped. Increase the limit for repositories with large generated files you want indexed:

```toml
[knowstack]
max_file_size_bytes = 2097152   # 2 MB
```

### Embedding model downloads on first run

This is expected behavior. KnowStack downloads `BAAI/bge-small-en-v1.5` (~130 MB) from Hugging Face on first use and caches it in `~/.cache/huggingface/`. Subsequent runs use the cached model.

If your environment has no internet access, pre-download the model on a connected machine and set `SENTENCE_TRANSFORMERS_HOME` to point to the local cache directory.

### Indexing is slow

- Increase `parse_workers` (default 4) to match your core count.
- Set `enable_git_enrichment = false` to skip `git log` analysis on the first run, then re-enable it later.
- For large repositories (>100k lines), use incremental re-indexing after the first full index:

```bash
knowstack index . --incremental
```

### Index seems stale after code changes

Run `knowstack index . --incremental` to re-index only changed files. If the graph still looks wrong, run a full re-index to rebuild from scratch:

```bash
make clean    # removes .knowstack/ entirely
knowstack index .
```

---

## Queries

### "No results" for a query I expect to match

- Verify the symbol was indexed: `knowstack query "FIND * WHERE name = MyClass"`.
- Check the exact node type: use `knowstack query "FIND class"` to list all classes.
- For semantic queries, rephrase using terms that appear in docstrings or function signatures.

### LLM-powered queries failing (`--mode nl`)

**Check 1 — API key.** Set the correct environment variable:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
```

**Check 2 — provider config.** Confirm `llm_provider` is set in `knowstack.toml`:

```toml
[knowstack]
llm_provider = "anthropic"
```

**Check 3 — Ollama.** If using Ollama, verify it is running and the model is pulled:

```bash
ollama serve
ollama pull qwen2.5-coder:7b
```

### `PATH FROM x TO y` returns no results

This query finds the shortest path between two symbols in the graph. Ensure:

1. Both symbols are indexed: `FIND * WHERE name = x` and `FIND * WHERE name = y`.
2. A reachable path exists within `max_call_depth` hops (default 10).
3. CALLS edges were resolved — check for "Dropping unresolvable edge" messages with debug logging enabled (see below).

---

## Debug logging

Set the `KNOWSTACK_LOG_LEVEL` environment variable to `DEBUG` for verbose output:

```bash
KNOWSTACK_LOG_LEVEL=DEBUG knowstack index .
KNOWSTACK_LOG_LEVEL=DEBUG knowstack query "DEPENDENTS authenticate"
```

Or set `log_level = "DEBUG"` in `knowstack.toml` to persist the setting.

Debug output includes:
- Files scanned and skipped during indexing
- Edges dropped by the Normalizer (unresolvable cross-file references)
- Kuzu Cypher queries executed during retrieval
- Embedding batch progress

---

## Getting help

If none of the above resolves your issue, file a bug report at the project issue tracker. Include:

- KnowStack version (`pip show knowstack`)
- Python version (`python --version`)
- Operating system
- The command you ran and the full error output
- The contents of your `knowstack.toml` (redact any secrets)

# KnowStack Vibe Coding Prompts

Copy any prompt below into Claude, ChatGPT, or your LLM of choice — paste in relevant file contents or error messages where indicated by `[brackets]`.

---

## Explore the Codebase

```
Summarize the KnowStack codebase in 3 bullet points and tell me the best place to start reading.
```

```
Explain how the 6-stage ingestion pipeline works (Scanner → Parsers → Normalizer → Enricher → Writer → Embedder). What does each stage produce and consume?
```

```
Walk me through what happens when a single Python file is ingested: from the Scanner picking it up to the node being stored in Kuzu and embedded in ChromaDB.
```

```
What does GraphStore (knowstack/graph/store.py) do? List its key methods and explain when each is called.
```

```
How does the normalizer (knowstack/ingestion/normalizer.py) resolve cross-file references? What does it do when a reference can't be resolved?
```

```
Explain the node ID convention used throughout KnowStack. Why is it SHA256-based and what guarantees does it provide?
```

---

## Write & Run Queries

```
Show me how to write a KnowStack DSL query to find all functions tagged with 'auth'. Then show me how to run it using the Python API.
```

```
Translate this natural-language question into a KnowStack DSL query: [your question here]
```

```
What DSL query would find all callers of a function named `[function_name]`?
```

```
Give me a complete Python snippet that initializes QueryEngine, runs a hybrid retrieval query for "[topic]", and prints the LLM-ready context string.
```

```
What's the difference between FIND, DEPENDENTS, IMPACT, and PATH queries in the KnowStack DSL? Give me a one-line example of each.
```

---

## Add a Language Parser

```
Walk me through adding a [language] parser to KnowStack, following the pattern of the existing Python parser at knowstack/ingestion/parsers/python_parser.py. List every file I need to create or edit.
```

```
I want to add [language] support to KnowStack. The tree-sitter package is `tree-sitter-[lang]`. Generate the parser file, the enum entry in knowstack/models/enums.py, and the pipeline registration in knowstack/ingestion/pipeline.py.
```

---

## Write Tests

```
Write a unit test for [parser or component], following the fixture and assertion patterns in tests/unit/test_python_parser.py. Use the synthetic repos in tests/fixtures/ as test data.
```

```
Add an integration test for [feature] following the pattern in tests/integration/test_ingestion_pipeline.py. The test should run the full pipeline against a fixture repo and assert [expected outcome].
```

```
I wrote [function/class]. Generate a pytest unit test for it with edge cases. The test should have no I/O and run without a live Kuzu or ChromaDB instance.
```

---

## Debug & Fix

```
I'm getting this error in KnowStack: [paste error + stack trace]. Help me trace it through the pipeline and identify the root cause.
```

```
Why might a node ID change between re-index runs? Walk me through the node ID formula (knowstack/models/nodes.py) and what inputs could vary.
```

```
The normalizer isn't resolving cross-file references for [symbol]. What should I check in knowstack/ingestion/normalizer.py and what log output should I look for?
```

```
My DSL query returns no results but I expect it to match nodes. Here's my query: [query]. Walk me through how QueryEngine (knowstack/retrieval/query_engine.py) processes it and where it might fail silently.
```

---

## Extend the API / CLI

```
Add a new CLI subcommand `knowstack [name]` that [does X]. Follow the Typer patterns in knowstack/cli/main.py and include a --help string.
```

```
Add a new FastAPI endpoint to knowstack/serve/ that [does X]. Follow the existing route patterns and return a Pydantic response model.
```

```
I want to add a new node type for [concept]. Show me what to add in knowstack/models/nodes.py, the Kuzu DDL in knowstack/graph/schema.py, and any writer changes needed in the pipeline.
```

---

## Understand a Specific Symbol

```
Using the key files listed in CLAUDE.md, explain what `[ClassName or function_name]` does, where it's called from, and what I'd need to change to modify its behavior.
```

```
What is the call chain from `knowstack/cli/main.py` down to `[symbol]`? Trace through the layers and note which module owns each step.
```

---

## Multi-Repo Workspace

```
Explain how KnowStack workspaces work. How does `workspace.toml` relate to the shared Kuzu + ChromaDB stores, and how does per-repo isolation via `repo_id` prevent results from leaking across repos?
```

```
Walk me through setting up a workspace for these repos: [repo-a path], [repo-b path]. Show every command I need to run (workspace init, add, index) and then demonstrate a cross-repo query.
```

```
I want to query only [repo_id] within a workspace. Show the CLI command and the equivalent Python API call using QueryEngine with the `repo_id` parameter.
```

```
How does WorkspaceIndexer (knowstack/workspace/indexer.py) set repo_id on each ingested node, and how does GraphRetriever (knowstack/retrieval/graph_retriever.py) use it to scope results?
```

```
I removed a repo from the workspace with `knowstack workspace remove [repo_id]`. Does the indexed data get deleted? How would I clean it up if not?
```

---

## Incremental Indexing

```
Explain how KnowStack detects which files changed since the last index. Walk through ChangeDetector (knowstack/incremental/change_detector.py): what hashes does it store, where, and how does it classify files into added/modified/deleted?
```

```
Walk me through what PartialPipeline (knowstack/incremental/partial_pipeline.py) does with a ChangeSet. What happens to stale nodes in Kuzu and ChromaDB, and why is PageRank recomputed globally even for a partial re-index?
```

```
I'm running `knowstack index --incremental` but it's re-indexing files that haven't changed. Help me diagnose why — what should I check in the stored content hashes and the git enrichment path?
```

```
How does the optional git-based optimization in ChangeDetector speed up change detection? When would it be inaccurate, and when should I disable it?
```

---

## HTTP API

```
Show me how to start the KnowStack HTTP API and then use curl to run a DSL query, a semantic search, and a natural-language question. Include the full request/response shapes.
```

```
What are all the endpoints exposed by `knowstack serve`? For each one, show the route, the request body fields, and what the response contains.
```

```
Write a Python snippet using `httpx` that queries the KnowStack HTTP API at `http://localhost:8000` with a hybrid retrieval request for "[topic]" and prints the packed context string.
```

```
I want to add authentication (API key header) to `knowstack/serve/app.py`. Walk me through adding FastAPI middleware that checks a configured key, without breaking the existing endpoint contract.
```

```
The `/v1/info` endpoint returns node_count and edge_count. I want to add a `languages` field showing which languages are indexed. Walk me through the change in knowstack/serve/app.py and the Kuzu query needed to count by language.
```

---

## Retrieval & Ranking

```
Explain the 5-signal scoring formula used by Ranker (knowstack/retrieval/ranker.py). What does each signal measure, what are its weights, and how would I change the weights to prioritize recently modified code over structurally central code?
```

```
How does RRF (Reciprocal Rank Fusion) work in HybridRetriever (knowstack/retrieval/hybrid_retriever.py)? Walk through the math with k=60 and explain why k=60 reduces the impact of rank position.
```

```
Walk me through how ContextPacker (knowstack/retrieval/context_packer.py) decides what goes into the LLM context string. How does it estimate token count, and what does it do when adding the next node would exceed the budget?
```

```
My hybrid query for "[topic]" returns irrelevant results. Walk me through the retrieval path: VectorRetriever → GraphRetriever → HybridRetriever.fuse() → Ranker. Where are the most likely points of failure?
```

```
How does QueryEngine route an incoming query — what decides whether it runs DSL, semantic, hybrid, impact, path, or NL? Walk through the intent routing logic in knowstack/retrieval/query_engine.py.
```

---

## Auto-Tags & Enrichment

```
Explain the 13 auto-tag patterns in Enricher (knowstack/ingestion/enricher.py). How does it decide which tag(s) to assign to a node? Can a node get multiple tags?
```

```
I want to add a custom auto-tag for nodes in [my domain] matching the pattern "[regex]". Show me exactly what to change in knowstack/ingestion/enricher.py.
```

```
How is `importance_score` calculated? Walk me through the formula `centrality_score * (1 + change_frequency)` and explain how git commit history feeds into it. What happens for repos with no git history?
```

```
I want to tag nodes based on directory structure (e.g., everything under `src/payments/` gets tagged "payments"). Show me how to add a path-based tagging rule to the Enricher without breaking the existing regex-based rules.
```

```
What git metadata does Enricher store per node, and how do I use it in a DSL query or Python retrieval call to find the most frequently changed functions?
```

---

## NL + LLM Configuration

```
Explain how NLQueryBuilder (knowstack/nl/query_builder.py) decides whether to use LLM-based DSL generation or the rule-based fallback. Under what conditions does the fallback trigger?
```

```
Walk me through the rule-based fallback in NLQueryBuilder. How does it use IntentClassifier and EntityExtractor to construct a DSL query without an LLM?
```

```
How does EntityExtractor (knowstack/nl/entity_extractor.py) find symbol names in a natural-language question? What fuzzy-matching algorithm does it use and what cutoff score does it apply?
```

```
I want to configure KnowStack to use Ollama with the `llama3.1:8b` model running locally. Show me the knowstack.toml settings and confirm which environment variables I do or don't need.
```

```
The LLM-generated DSL from NLQueryBuilder is occasionally malformed. How does the system handle that — does it fall back, raise, or return empty results? Where in query_builder.py should I add validation or retry logic?
```

---

## Config Tuning

```
Walk me through every field in KnowStackConfig (knowstack/config/schema.py). For each field, tell me the default, what it controls, and when I'd want to change it.
```

```
I'm indexing a large monorepo and the initial index is slow. Which config knobs should I adjust — `parse_workers`, `embedding_batch_size`, `embed_limit`, `max_file_size_bytes`? What are the trade-offs of each?
```

```
I want to reduce ChromaDB storage by only embedding the most important nodes. How do `embed_limit` and `importance_score` interact, and what value should I set for a repo with ~5000 nodes?
```

```
My context window for LLM queries is 16k tokens, not 6000. Show me how to update `context_max_tokens` in knowstack.toml and explain how ContextPacker will behave differently.
```

```
How do `include_extensions` and `exclude_patterns` interact in the Scanner stage? Show me a knowstack.toml snippet that indexes only Python files under `src/`, skipping `src/migrations/` and `src/scripts/`.
```

---

## Inspect & Explore the Graph

```
Show me how to use `knowstack inspect node [symbol]` to explore a specific function or class. What information does it return, and how does `--depth` change the neighbourhood it shows?
```

```
I want to see all paths between `[symbol_a]` and `[symbol_b]`. Show the CLI command and the equivalent QueryEngine Python call, and explain what edges (CALLS, IMPORTS) the path traversal follows.
```

```
Run `knowstack inspect stats` and explain each row of the output. What does the node type breakdown tell me about the structure of my codebase?
```

```
I want to find the most central nodes in my graph (highest PageRank / centrality_score). Show me a Kuzu Cypher query I can run against `.knowstack/graph.kuzu` to retrieve the top 10 nodes by centrality_score.
```

```
How do I explore the raw Kuzu graph outside of KnowStack? Show me how to open `.knowstack/graph.kuzu` directly with the Kuzu Python client and run a custom Cypher query to inspect node properties.
```

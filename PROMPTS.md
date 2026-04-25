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

# Query DSL Reference

KnowStack's DSL is a minimal, readable query language that compiles to Cypher
under the hood. It is designed to be typed by hand and understood at a glance.

## Query types

### FIND — search for nodes

```
FIND [node_type] [WHERE filter [AND filter ...]] [LIMIT n]
```

**Node types:** `function`, `method`, `class`, `file`, `interface`, `type`, `endpoint`, `model`, `test`, `config`, `*`

**Filters:**

| Field | Operators | Example |
|---|---|---|
| `name` | `=` `~` | `name = "authenticate"` |
| `fqn` | `=` `contains` | `fqn contains "auth"` |
| `file` | `contains` | `file contains "checkout"` |
| `tag` | `=` | `tag = "auth"` |
| `language` | `=` | `language = "python"` |

**Examples:**

```
FIND function WHERE tag = auth
FIND class WHERE file contains checkout
FIND endpoint LIMIT 50
FIND * WHERE name = "retry" LIMIT 5
FIND function WHERE tag = auth AND language = python
```

---

### DEPENDENTS — reverse reachability

*"Who depends on this symbol?"*

```
DEPENDENTS "symbol_name"
```

Returns all nodes that reach the target through any combination of `CALLS`, `IMPORTS`, `INHERITS`, or `IMPLEMENTS` edges.

```
DEPENDENTS "UserRepository"
DEPENDENTS "FeatureFlagManager"
DEPENDENTS "IAuthProvider"
```

---

### IMPACT — change impact analysis

*"What breaks if I change this?"*

```
IMPACT "symbol_name" [DEPTH n]
```

Same as DEPENDENTS but with explicit depth control (default: 3).

```
IMPACT "PaymentService" DEPTH 4
IMPACT "BaseModel"
IMPACT "config.settings" DEPTH 2
```

---

### PATH — call/import paths between symbols

*"How does X reach Y?"*

```
PATH FROM "source_symbol" TO "destination_symbol"
```

Returns the shortest paths (up to 3) between two symbols, traversing any edge type.

```
PATH FROM "login" TO "database"
PATH FROM "AuthController" TO "UserRepository"
PATH FROM "checkout" TO "send_invoice"
```

---

## Query modes

| Mode | Flag | When to use |
|---|---|---|
| DSL (auto-detected) | `--mode dsl` | Structural questions, exact graph traversal |
| Semantic | `--mode semantic` | Conceptual questions, fuzzy symbol lookup |
| Hybrid | `--mode hybrid` | Best of both — slower |
| Natural language | `--mode nl` | Conversational questions (requires LLM config) |

KnowStack auto-detects DSL vs natural language: if the first token is `FIND`, `DEPENDENTS`, `IMPACT`, or `PATH`, it uses DSL mode.

---

## Output options

```bash
# Default: Rich table
knowstack query "FIND function WHERE tag = auth"

# JSON (for piping / scripting)
knowstack query "FIND function WHERE tag = auth" --json

# Packed LLM context block
knowstack query "FIND function WHERE tag = auth" --context

# Limit results
knowstack query "FIND class" --top-k 5
```

---

## Auto-detected tags

The enricher automatically applies tags based on file paths and symbol names:

| Tag | Applied when |
|---|---|
| `authentication` | "auth" in path or name |
| `payments` | "payment", "billing", "invoice", "checkout" |
| `data-model` | "model", "schema", "entity", "orm" |
| `test` | "test", "spec" in path or name |
| `api` | "api", "endpoint", "route", "handler", "controller" |
| `database` | "db", "database", "repo", "repository" |
| `config` | "config", "setting", "env" |
| `utility` | "util", "helper", "common", "shared" |
| `middleware` | "middleware", "interceptor", "filter", "guard" |
| `async-worker` | "queue", "worker", "job", "task", "celery" |
| `cache` | "cache", "redis", "memcache" |
| `observability` | "log", "monitor", "metric", "trace" |

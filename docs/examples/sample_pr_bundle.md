<!-- knowstack-pr-context -->
### KnowStack PR review context

**Saved ~20,163 tokens (87%)** vs. pasting the full changed files into your reviewer (this bundle: 2,996 tokens, files in full: 23,159).

**Budget:** 2,996 / 4,000 tokens (75%) • **Selected:** 64 nodes • **Dropped:** 0

**Touched symbols**
- `.github.actions.pr-context.format_comment.main`
- `.github.actions.pr-context.format_comment._render`
- `knowstack.ingestion.parsers.python_parser._ParseContext._visit_class`
- `knowstack.ingestion.parsers.python_parser._ParseContext._visit_function`
- `knowstack.ingestion.parsers.python_parser._ParseContext._current_class_fqn`
- `knowstack.pr_context.budget.estimate_tokens`
- `knowstack.pr_context.builder.build_pr_review_context`
- `knowstack.pr_context.builder._empty_bundle`
- `knowstack.pr_context.models.SeedSymbol.is_symbol`
- `knowstack.pr_context.models.PRContextBundle.to_dict`
- … and 13 more

**Changed files** (no symbol-level context — non-code, config, or a new file the index hasn't seen yet)
- `.github/workflows/pr-context.yml`
- `knowstack/pr_context/budget.py`
- `knowstack/pr_context/builder.py`
- `knowstack/pr_context/symbol_extractor.py`
- `pyproject.toml`
- `tests/unit/test_pr_context_budget.py`

<details><summary>Touched symbol locations</summary>

- `.github.actions.pr-context.format_comment._render` — `.github/actions/pr-context/format_comment.py:62-183`
- `.github.actions.pr-context.format_comment.main` — `.github/actions/pr-context/format_comment.py:42-56`
- `.github/workflows/pr-context.yml` — `.github/workflows/pr-context.yml`
- `knowstack.ingestion.parsers.python_parser._ParseContext._current_class_fqn` — `knowstack/ingestion/parsers/python_parser.py:366-367`
- `knowstack.ingestion.parsers.python_parser._ParseContext._visit_class` — `knowstack/ingestion/parsers/python_parser.py:114-171`
- `knowstack.ingestion.parsers.python_parser._ParseContext._visit_function` — `knowstack/ingestion/parsers/python_parser.py:173-275`
- `knowstack.pr_context.budget.estimate_tokens` — `knowstack/pr_context/budget.py:48-52`
- `knowstack.pr_context.builder._empty_bundle` — `knowstack/pr_context/builder.py:148-159`
- `knowstack.pr_context.builder.build_pr_review_context` — `knowstack/pr_context/builder.py:31-84`
- `knowstack.pr_context.models.PRContextBundle.to_dict` — `knowstack/pr_context/models.py:99-123`
- `knowstack.pr_context.models.SeedSymbol.is_symbol` — `knowstack/pr_context/models.py:79-81`
- `knowstack.pr_context.neighborhood._callees_of` — `knowstack/pr_context/neighborhood.py:139-145`
- `knowstack.pr_context.neighborhood._callers_of` — `knowstack/pr_context/neighborhood.py:130-136`
- `knowstack.pr_context.neighborhood._collect` — `knowstack/pr_context/neighborhood.py:200-217`
- `knowstack.pr_context.neighborhood._related_configs` — `knowstack/pr_context/neighborhood.py:163-194`
- `knowstack.pr_context.neighborhood._tests_of` — `knowstack/pr_context/neighborhood.py:120-127`
- `knowstack.pr_context.symbol_extractor._row_to_seed` — `knowstack/pr_context/symbol_extractor.py:155-167`
- `knowstack.retrieval.graph_retriever.GraphRetriever.dependents` — `knowstack/retrieval/graph_retriever.py:110-135`
- `knowstack.retrieval.graph_retriever.GraphRetriever.neighbourhood` — `knowstack/retrieval/graph_retriever.py:168-187`
- `knowstack.retrieval.graph_retriever.GraphRetriever.path` — `knowstack/retrieval/graph_retriever.py:141-166`
- `knowstack.retrieval.graph_retriever._safe_depth` — `knowstack/retrieval/graph_retriever.py:18-30`
- `knowstack/pr_context/budget.py` — `knowstack/pr_context/budget.py`
- `knowstack/pr_context/builder.py` — `knowstack/pr_context/builder.py`
- `knowstack/pr_context/symbol_extractor.py` — `knowstack/pr_context/symbol_extractor.py`
- `pyproject.toml` — `pyproject.toml`
- `tests.unit.test_pr_context_budget.test_baseline_tolerates_missing_files` — `tests/unit/test_pr_context_budget.py:157-162`
- `tests.unit.test_python_parser.test_parser_can_parse_python` — `tests/unit/test_python_parser.py:8-10`
- `tests.unit.test_python_parser.test_parser_no_errors_on_valid_file` — `tests/unit/test_python_parser.py:90-93`
- `tests/unit/test_pr_context_budget.py` — `tests/unit/test_pr_context_budget.py`

</details>

<details><summary>LLM-ready context (paste into your reviewer model)</summary>

```markdown
# Code Context
**Query:** PR (no number) — (untitled) — 29 touched symbol(s)

## Function: `.github.actions.pr-context.format_comment.main`
**Doc:** [selected as: touched, distance=0]
**File:** `.github/actions/pr-context/format_comment.py:42-56`

---

## Function: `.github.actions.pr-context.format_comment._render`
**Doc:** [selected as: touched, distance=0]
**File:** `.github/actions/pr-context/format_comment.py:62-183`

---

## File: `.github/workflows/pr-context.yml`
**Doc:** [selected as: touched, distance=0]
**File:** `.github/workflows/pr-context.yml`

---

## Method: `knowstack.ingestion.parsers.python_parser._ParseContext._visit_class`
**Doc:** [selected as: touched, distance=0]
**File:** `knowstack/ingestion/parsers/python_parser.py:114-171`

---

## Method: `knowstack.ingestion.parsers.python_parser._ParseContext._visit_function`
**Doc:** [selected as: touched, distance=0]
**File:** `knowstack/ingestion/parsers/python_parser.py:173-275`

---

## Method: `knowstack.ingestion.parsers.python_parser._ParseContext._current_class_fqn`
**Doc:** [selected as: touched, distance=0]
**File:** `knowstack/ingestion/parsers/python_parser.py:366-367`

---

## File: `knowstack/pr_context/budget.py`
**Doc:** [selected as: touched, distance=0]
**File:** `knowstack/pr_context/budget.py`

---

## Function: `knowstack.pr_context.budget.estimate_tokens`
**Doc:** [selected as: touched, distance=0]
**File:** `knowstack/pr_context/budget.py:48-52`

---

## File: `knowstack/pr_context/builder.py`
**Doc:** [selected as: touched, distance=0]
**File:** `knowstack/pr_context/builder.py`

---

## Function: `knowstack.pr_context.builder.build_pr_review_context`
**Doc:** [selected as: touched, distance=0]
**File:** `knowstack/pr_context/builder.py:31-84`

---

## Function: `knowstack.pr_context.builder._empty_bundle`
**Doc:** [selected as: touched, distance=0]
**File:** `knowstack/pr_context/builder.py:148-159`

---

## Method: `knowstack.pr_context.models.SeedSymbol.is_symbol`
**Doc:** [selected as: touched, distance=0]
**File:** `knowstack/pr_context/models.py:79-81`

---

## Method: `knowstack.pr_context.models.PRContextBundle.to_dict`
**Doc:** [selected as: touched, distance=0]
**File:** `knowstack/pr_context/models.py:99-123`

---

## Function: `knowstack.pr_context.neighborhood._tests_of`
**Doc:** [selected as: touched, distance=0]
**File:** `knowstack/pr_context/neighborhood.py:120-127`

---

## Function: `knowstack.pr_context.neighborhood._callers_of`
**Doc:** [selected as: touched, distance=0]
**File:** `knowstack/pr_context/neighborhood.py:130-136`

---

## Function: `knowstack.pr_context.neighborhood._callees_of`
**Doc:** [selected as: touched, distance=0]
**File:** `knowstack/pr_context/neighborhood.py:139-145`

---

## Function: `knowstack.pr_context.neighborhood._related_configs`
**Doc:** [selected as: touched, distance=0]
**File:** `knowstack/pr_context/neighborhood.py:163-194`

---

## Function: `knowstack.pr_context.neighborhood._collect`
**Doc:** [selected as: touched, distance=0]
**File:** `knowstack/pr_context/neighborhood.py:200-217`

---

## File: `knowstack/pr_context/symbol_extractor.py`
**Doc:** [selected as: touched, distance=0]
**File:** `knowstack/pr_context/symbol_extractor.py`

---

## Function: `knowstack.pr_context.symbol_extractor._row_to_seed`
**Doc:** [selected as: touched, distance=0]
**File:** `knowstack/pr_context/symbol_extractor.py:155-167`

---

## Function: `knowstack.retrieval.graph_retriever._safe_depth`
**Doc:** [selected as: touched, distance=0]
**File:** `knowstack/retrieval/graph_retriever.py:18-30`

---

## Method: `knowstack.retrieval.graph_retriever.GraphRetriever.dependents`
**Doc:** [selected as: touched, distance=0]
**File:** `knowstack/retrieval/graph_retriever.py:110-135`

---

## Method: `knowstack.retrieval.graph_retriever.GraphRetriever.path`
**Doc:** [selected as: touched, distance=0]
**File:** `knowstack/retrieval/graph_retriever.py:141-166`

---

## Method: `knowstack.retrieval.graph_retriever.GraphRetriever.neighbourhood`
**Doc:** [selected as: touched, distance=0]
**File:** `knowstack/retrieval/graph_retriever.py:168-187`

---

## File: `pyproject.toml`
**Doc:** [selected as: touched, distance=0]
**File:** `pyproject.toml`

---

## File: `tests/unit/test_pr_context_budget.py`
**Doc:** [selected as: touched, distance=0]
**File:** `tests/unit/test_pr_context_budget.py`

---

## Test: `tests.unit.test_pr_context_budget.test_baseline_tolerates_missing_files`
**Doc:** [selected as: touched, distance=0]
**File:** `tests/unit/test_pr_context_budget.py:157-162`

---

## Test: `tests.unit.test_python_parser.test_parser_can_parse_python`
**Doc:** [selected as: touched, distance=0]
**File:** `tests/unit/test_python_parser.py:8-10`

---

## Test: `tests.unit.test_python_parser.test_parser_no_errors_on_valid_file`
**Doc:** [selected as: touched, distance=0]
**File:** `tests/unit/test_python_parser.py:90-93`

---

## Function: `knowstack.pr_context.symbol_extractor._lookup_file_nodes`
**Doc:** [selected as: caller, distance=1]
**File:** `knowstack/pr_context/symbol_extractor.py:127-152`

---

## Function: `knowstack.pr_context.symbol_extractor._overlap_query`
**Doc:** [selected as: caller, distance=1]
**File:** `knowstack/pr_context/symbol_extractor.py:98-124`

---

## Function: `knowstack.pr_context.neighborhood.expand_neighborhood`
**Doc:** [selected as: caller, distance=1]
**File:** `knowstack/pr_context/neighborhood.py:35-79`

---

## Function: `knowstack.pr_context.cli.main`
**Doc:** [selected as: caller, distance=1]
**File:** `knowstack/pr_context/cli.py:22-63`

---

## Function: `knowstack.cli.pr_context.pr_context`
**Doc:** [selected as: caller, distance=1]
**File:** `knowstack/cli/pr_context.py:22-56`

---

## Function: `knowstack.models.nodes.make_node_id`
**Doc:** [selected as: callee, distance=1]
**File:** `knowstack/models/nodes.py:19-22`

---

## Function: `knowstack.models.edges.make_edge_id`
**Doc:** [selected as: callee, distance=1]
**File:** `knowstack/models/edges.py:16-18`

---

## Function: `knowstack.pr_context.neighborhood._row_to_ranked`
**Doc:** [selected as: callee, distance=1]
**File:** `knowstack/pr_context/neighborhood.py:220-250`

---

## Function: `knowstack.pr_context.symbol_extractor._parse_tags`
**Doc:** [selected as: callee, distance=1]
**File:** `knowstack/pr_context/symbol_extractor.py:170-183`

---

## Function: `knowstack.pr_context.budget.rank_and_trim`
**Doc:** [selected as: callee, distance=1]
**File:** `knowstack/pr_context/budget.py:82-112`

---

## Function: `knowstack.pr_context.budget.chars_per_token`
**Doc:** [selected as: callee, distance=1]
**File:** `knowstack/pr_context/budget.py:39-45`

---

## Function: `knowstack.pr_context.symbol_extractor.extract_seeds`
**Doc:** [selected as: callee, distance=1]
**File:** `knowstack/pr_context/symbol_extractor.py:42-75`

---

## Function: `.github.actions.pr-context.format_comment._loc`
**Doc:** [selected as: callee, distance=1]
**File:** `.github/actions/pr-context/format_comment.py:186-194`

---

## Function: `knowstack.pr_context.budget.naive_file_baseline_tokens`
**Doc:** [selected as: callee, distance=1]
**File:** `knowstack/pr_context/budget.py:55-71`

---

## Function: `knowstack.utils.text.clean_docstring`
**Doc:** [selected as: callee, distance=1]
**File:** `knowstack/utils/text.py:15-22`

---

## Function: `.github.actions.pr-context.format_comment._empty_comment`
**Doc:** [selected as: callee, distance=1]
**File:** `.github/actions/pr-context/format_comment.py:197-205`

---

## Function: `.github.actions.pr-context.format_comment._read_input`
**Doc:** [selected as: callee, distance=1]
**File:** `.github/actions/pr-context/format_comment.py:211-214`

---

## Function: `knowstack.pr_context.builder._format_context`
**Doc:** [selected as: callee, distance=1]
**File:** `knowstack/pr_context/builder.py:90-109`

---

## File: `knowstack/retrieval/query_engine.py`
**Doc:** [selected as: impacted, distance=2]
**File:** `knowstack/retrieval/query_engine.py`

---

## File: `knowstack/pr_context/models.py`
**Doc:** [selected as: impacted, distance=2]
**File:** `knowstack/pr_context/models.py`

---

## File: `knowstack/retrieval/graph_retriever.py`
**Doc:** [selected as: impacted, distance=2]
**File:** `knowstack/retrieval/graph_retriever.py`

---

## File: `knowstack/pr_context/cli.py`
**Doc:** [selected as: impacted, distance=2]
**File:** `knowstack/pr_context/cli.py`

---

## File: `knowstack/ingestion/parsers/python_parser.py`
**Doc:** [selected as: impacted, distance=2]
**File:** `knowstack/ingestion/parsers/python_parser.py`

---

## Class: `knowstack.pr_context.models.PRContextBundle`
**Doc:** [selected as: impacted, distance=2]
**File:** `knowstack/pr_context/models.py:85-123`

---

## Function: `knowstack.pr_context.symbol_extractor._narrowest_for_hunk`
**Doc:** [selected as: impacted, distance=2]
**File:** `knowstack/pr_context/symbol_extractor.py:81-95`

---

## File: `knowstack/pr_context/neighborhood.py`
**Doc:** [selected as: impacted, distance=2]
**File:** `knowstack/pr_context/neighborhood.py`

---

## Class: `knowstack.ingestion.parsers.python_parser._ParseContext`
**Doc:** [selected as: impacted, distance=2]
**File:** `knowstack/ingestion/parsers/python_parser.py:76-456`

---

## Class: `knowstack.retrieval.graph_retriever.GraphRetriever`
**Doc:** [selected as: impacted, distance=2]
**File:** `knowstack/retrieval/graph_retriever.py:56-299`

---

## Class: `knowstack.pr_context.models.SeedSymbol`
**Doc:** [selected as: impacted, distance=2]
**File:** `knowstack/pr_context/models.py:73-81`

---

## File: `tests/unit/test_python_parser.py`
**Doc:** [selected as: impacted, distance=2]
**File:** `tests/unit/test_python_parser.py`

---

## File: `knowstack/cli/pr_context.py`
**Doc:** [selected as: impacted, distance=2]
**File:** `knowstack/cli/pr_context.py`

---

## File: `knowstack/pr_context/__init__.py`
**Doc:** [selected as: impacted, distance=2]
**File:** `knowstack/pr_context/__init__.py`

---

## File: `knowstack/pr_context/__main__.py`
**Doc:** [selected as: impacted, distance=2]
**File:** `knowstack/pr_context/__main__.py`

---

## File: `tests/unit/test_pr_context_symbol_extractor.py`
**Doc:** [selected as: impacted, distance=2]
**File:** `tests/unit/test_pr_context_symbol_extractor.py`

---

## File: `.github/actions/pr-context/format_comment.py`
**Doc:** [selected as: impacted, distance=2]
**File:** `.github/actions/pr-context/format_comment.py`
```

</details>

<details><summary>Selection breakdown</summary>

| Reason | Count |
|---|---|
| Touched (the diff itself) | 29 |
| Direct callers | 5 |
| Direct callees | 13 |
| Transitively impacted | 17 |

</details>

<sub>Generated by `knowstack pr-context` — edit `.github/workflows/pr-context.yml` to tune the token budget or model.</sub>

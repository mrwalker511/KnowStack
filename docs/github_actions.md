# Using KnowStack in GitHub Actions

The `pr-context` workflow runs `knowstack pr-context` on every pull request
and posts a token-budgeted, LLM-ready review-context bundle as a PR comment.
Reviewers (and downstream LLM bots) can paste the bundle into a model instead
of feeding it whole files or the raw diff.

## What the comment looks like

Each PR comment contains:

- A one-line **budget header** (`used / budget tokens`, selected node count, dropped count).
- The list of **touched symbols** (the symbols whose source span overlaps the diff).
- A collapsible **LLM-ready context block** — the actual markdown to paste into your reviewer model.
- A **selection breakdown** table that explains why each node was picked
  (`touched`, `test`, `caller`, `callee`, `impacted`, `related_config`).

The comment is **upserted**: on every push to the PR, the same comment is updated
in place instead of stacking a new one.

## Enabling on another repository

1. Copy two files into the target repo, preserving paths:
   - `.github/workflows/pr-context.yml`
   - `.github/actions/pr-context/format_comment.py`
2. Make sure the repo's default `GITHUB_TOKEN` has `pull-requests: write`
   (the workflow declares this in its `permissions:` block — no extra setup
   needed unless your org locks tokens down further).
3. Install KnowStack as a dependency the workflow can `pip install` — the
   included workflow does `pip install -e .`, which assumes KnowStack is the
   repo being indexed. For a repo that just *uses* KnowStack, change that
   step to `pip install knowstack`.

## Tuning

Edit the `env:` block at the top of `.github/workflows/pr-context.yml`:

```yaml
env:
  TOKEN_BUDGET: "4000"           # cap on the packed context block
  MODEL: "claude-sonnet-4-6"     # influences chars-per-token estimation
```

Lower the budget for cheaper models or terser comments; raise it for deeper
reviews. The CLI itself is the single source of truth — every flag the
workflow passes is documented under `knowstack pr-context --help`.

## How indexing is cached

The workflow caches `.knowstack/` (Kuzu graph + Chroma vectors) and the
HuggingFace model cache, keyed on the PR's base SHA with a fallback to the
most recent index for the OS. Typical timing:

- **Cold cache** (first PR after a fresh main): ~60 s for a 50,000-line repo,
  dominated by the embedding model download and full index.
- **Warm cache**: ~15–30 s; the `--incremental` flag only re-indexes files
  that changed since the cached base SHA.

The index is read-only at PR time — `knowstack pr-context` never writes to
the graph, so two concurrent PR jobs cannot corrupt each other.

## Failure mode

The action is **advisory** and never fails CI. If the CLI returns a non-zero
exit code (e.g. an empty diff), the formatter renders a small "no context
to show" comment and the job exits 0. To make it fail-loud, change the
`Build PR context bundle` step in the workflow to remove the `|| echo ...`
fallback.

## Local dry-run

To preview the comment for the current branch before opening a PR:

```bash
knowstack index .
git diff main...HEAD > /tmp/pr.diff
knowstack pr-context --diff /tmp/pr.diff --json > /tmp/bundle.json
python .github/actions/pr-context/format_comment.py /tmp/bundle.json
```

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

Drop a single workflow file at `.github/workflows/pr-context.yml`:

```yaml
name: PR Context
on:
  pull_request:
    types: [opened, synchronize, reopened]

permissions:
  contents: read
  pull-requests: write

jobs:
  pr-context:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
        with:
          fetch-depth: 0
      - uses: mrwalker511/KnowStack/.github/actions/pr-context@main
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          budget: "4000"
          model: claude-sonnet-4-6
```

The composite action lives in this repo under
`.github/actions/pr-context/` — GitHub resolves `uses:` against a path on
any public repository, so external users don't need to copy any files.

### Pinning the KnowStack version

`knowstack-spec` is the string passed to `pip install`. The default
(`knowstack`) installs the latest published version from PyPI. Other
common choices:

| Use case | `knowstack-spec` value |
|---|---|
| Pin a release | `knowstack==0.1.0` |
| Track this repo's `main` | `git+https://github.com/mrwalker511/KnowStack@main` |
| Use a fork | `git+https://github.com/yourname/KnowStack@your-branch` |
| Develop in-tree (this repo only) | `.` |

### Tuning

Inputs on the composite action:

| Input | Default | Effect |
|---|---|---|
| `budget` | `4000` | Maximum tokens in the rendered context block. |
| `model` | `claude-sonnet-4-6` | Drives the chars-per-token estimator. |
| `knowstack-spec` | `knowstack` | What to `pip install` (see table above). |
| `python-version` | `3.11` | Interpreter the action sets up. |
| `cache-key-prefix` | `knowstack` | Lets you partition caches if you run the action in multiple repos that share a runner. |

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

## What "savings" means in the comment

The headline (`Saved ~N tokens (X%)`) compares the bundle's estimated
token count against a naive baseline: the sum of tokens you would have
spent if you'd dropped every changed file in full into your reviewer
model. Deleted files contribute zero. The estimator is char-based and
per-model (see `MODEL_CHARS_PER_TOKEN` in `knowstack/pr_context/budget.py`)
— it's intentionally conservative so the displayed savings under-claim
rather than over-claim.

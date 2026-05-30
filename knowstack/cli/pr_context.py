"""CLI: knowstack pr-context — build a PR review context bundle from a diff."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

from knowstack.pr_context.builder import (
    DEFAULT_MODEL,
    DEFAULT_TOKEN_BUDGET,
    build_pr_review_context,
)
from knowstack.pr_context.cli import _parse_unified_diff
from knowstack.pr_context.models import PRMetadata

app = typer.Typer(help="Build a token-budgeted LLM review context for a PR.")


@app.callback(invoke_without_command=True)
def pr_context(
    diff: Path = typer.Option(..., "--diff", help="Unified diff file."),
    repo: Path = typer.Option(Path("."), "--repo", help="Repo root (contains .knowstack/)."),
    budget: int = typer.Option(DEFAULT_TOKEN_BUDGET, "--budget", help="Token budget."),
    model: str = typer.Option(DEFAULT_MODEL, "--model", help="Target LLM model name."),
    pr_number: int | None = typer.Option(None, "--pr", help="PR number."),
    title: str = typer.Option("", "--title", help="PR title."),
    json_out: bool = typer.Option(False, "--json", help="Output structured JSON."),
) -> None:
    diff_text = diff.read_text(encoding="utf-8", errors="replace")
    files = _parse_unified_diff(diff_text)
    if not files:
        typer.echo("No file changes detected in diff.", err=True)
        raise typer.Exit(code=2)

    pr = PRMetadata(
        repo_path=repo.resolve(),
        files=tuple(files),
        pr_number=pr_number,
        title=title,
    )
    bundle = build_pr_review_context(pr, token_budget=budget, model_name=model)

    if json_out:
        typer.echo(json.dumps(bundle.to_dict(), indent=2))
        return

    for note in bundle.notes:
        print(f"# note: {note}", file=sys.stderr)
    print(
        f"# tokens={bundle.estimated_tokens}/{bundle.budget_tokens} "
        f"nodes={len(bundle.nodes)} dropped={bundle.dropped_count}",
        file=sys.stderr,
    )
    typer.echo(bundle.context_text)

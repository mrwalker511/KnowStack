"""Local smoke-test CLI: parse a unified diff, build a context bundle, print it.

Usage:
    python -m knowstack.pr_context --repo . --diff /tmp/pr.diff --budget 4000
    python -m knowstack.pr_context --repo . --diff /tmp/pr.diff --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from knowstack.pr_context.builder import (
    DEFAULT_MODEL,
    DEFAULT_TOKEN_BUDGET,
    build_pr_review_context,
)
from knowstack.pr_context.models import ChangedFile, Hunk, PRMetadata


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="knowstack.pr_context",
        description="Build an LLM-ready PR review context from a diff.",
    )
    parser.add_argument("--repo", type=Path, required=True, help="Repo root (must contain .knowstack/).")
    parser.add_argument("--diff", type=Path, required=True, help="Unified diff file (e.g. `git diff main...HEAD`).")
    parser.add_argument("--budget", type=int, default=DEFAULT_TOKEN_BUDGET, help="Token budget.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Target LLM model name.")
    parser.add_argument("--pr-number", type=int, default=None)
    parser.add_argument("--title", default="")
    parser.add_argument("--json", action="store_true", help="Print structured JSON instead of text.")
    args = parser.parse_args(argv)

    diff_text = args.diff.read_text(encoding="utf-8", errors="replace")
    files = _parse_unified_diff(diff_text)
    if not files:
        print("No file changes detected in diff.", file=sys.stderr)
        return 2

    pr = PRMetadata(
        repo_path=args.repo.resolve(),
        files=tuple(files),
        pr_number=args.pr_number,
        title=args.title,
    )
    bundle = build_pr_review_context(
        pr, token_budget=args.budget, model_name=args.model,
    )

    if args.json:
        print(json.dumps(bundle.to_dict(), indent=2))
    else:
        for note in bundle.notes:
            print(f"# note: {note}", file=sys.stderr)
        print(
            f"# tokens={bundle.estimated_tokens}/{bundle.budget_tokens} "
            f"nodes={len(bundle.nodes)} dropped={bundle.dropped_count}",
            file=sys.stderr,
        )
        print(bundle.context_text)
    return 0


# ── tiny unified-diff parser ────────────────────────────────────────────────
#
# `unidiff` would be cleaner but is an optional dep; for the smoke-test CLI a
# hand-rolled parser keeps the package zero-dependency. It handles the common
# cases: `diff --git`, `+++ b/path`, `@@ -a,b +c,d @@`, `new file mode`,
# `deleted file mode`. Renames are treated as a delete + add.


def _parse_unified_diff(diff: str) -> list[ChangedFile]:
    files: list[ChangedFile] = []
    cur_path: str | None = None
    is_new = False
    is_deleted = False
    hunks: list[Hunk] = []

    def flush() -> None:
        nonlocal cur_path, is_new, is_deleted, hunks
        if cur_path is not None and (hunks or is_deleted or is_new):
            files.append(ChangedFile(
                path=cur_path,
                hunks=tuple(hunks),
                is_new=is_new,
                is_deleted=is_deleted,
            ))
        cur_path = None
        is_new = False
        is_deleted = False
        hunks = []

    for line in diff.splitlines():
        if line.startswith("diff --git"):
            flush()
        elif line.startswith("new file mode"):
            is_new = True
        elif line.startswith("deleted file mode"):
            is_deleted = True
        elif line.startswith("+++ "):
            target = line[4:].strip()
            if target == "/dev/null":
                is_deleted = True
            else:
                cur_path = target[2:] if target.startswith("b/") else target
        elif line.startswith("--- ") and cur_path is None:
            # Some diffs only have --- (e.g. deletions); use it as a fallback.
            target = line[4:].strip()
            if target != "/dev/null":
                cur_path = target[2:] if target.startswith("a/") else target
        elif line.startswith("@@"):
            hunk = _parse_hunk_header(line, is_new=is_new, is_deleted=is_deleted)
            if hunk is not None:
                hunks.append(hunk)
    flush()
    return files


def _parse_hunk_header(line: str, *, is_new: bool, is_deleted: bool) -> Hunk | None:
    # Format: `@@ -old_start,old_count +new_start,new_count @@ optional context`
    try:
        body = line.split("@@")[1].strip()
        new_part = next(p for p in body.split() if p.startswith("+"))
        new_part = new_part[1:]  # drop the '+'
        if "," in new_part:
            start_s, count_s = new_part.split(",", 1)
            start, count = int(start_s), int(count_s)
        else:
            start, count = int(new_part), 1
    except (IndexError, StopIteration, ValueError):
        return None
    if count <= 0:
        # Pure deletion hunk — anchor at the old position via a single-line range.
        return Hunk(start_line=max(start, 1), end_line=max(start, 1), change_type="deleted")
    change: str = "added" if is_new else ("deleted" if is_deleted else "modified")
    return Hunk(start_line=start, end_line=start + count - 1, change_type=change)  # type: ignore[arg-type]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

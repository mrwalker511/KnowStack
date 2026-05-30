"""PR Review Context Minimizer — bounded, high-signal context bundles for PR review.

Given a PR's changed files and hunks, this package uses KnowStack's existing graph
index to assemble a small, ranked, token-budgeted context block suitable for an
LLM reviewer — instead of pasting whole files or full diffs.

Public surface:

    from knowstack.pr_context import (
        build_pr_review_context,
        PRMetadata, ChangedFile, Hunk,
        PRContextBundle, SelectedNode,
        NeighborhoodPolicy,
    )
"""
from knowstack.pr_context.builder import build_pr_review_context
from knowstack.pr_context.models import (
    ChangedFile,
    Hunk,
    NeighborhoodPolicy,
    PRContextBundle,
    PRMetadata,
    SelectedNode,
)

__all__ = [
    "ChangedFile",
    "Hunk",
    "NeighborhoodPolicy",
    "PRContextBundle",
    "PRMetadata",
    "SelectedNode",
    "build_pr_review_context",
]

"""Orchestrator: PR metadata → bounded LLM-ready context bundle."""
from __future__ import annotations

import logging

from knowstack.config.schema import KnowStackConfig
from knowstack.pr_context.budget import (
    estimate_tokens,
    naive_file_baseline_tokens,
    rank_and_trim,
)
from knowstack.pr_context.models import (
    NeighborhoodPolicy,
    PRContextBundle,
    PRMetadata,
    SeedSymbol,
    SelectedNode,
)
from knowstack.pr_context.neighborhood import Candidate, expand_neighborhood
from knowstack.pr_context.symbol_extractor import extract_seeds
from knowstack.retrieval.context_packer import ContextPacker
from knowstack.retrieval.query_engine import QueryEngine
from knowstack.retrieval.ranker import RankedNode

log = logging.getLogger(__name__)

DEFAULT_TOKEN_BUDGET = 4000
DEFAULT_MODEL = "claude-sonnet-4-6"


def build_pr_review_context(
    pr: PRMetadata,
    *,
    token_budget: int = DEFAULT_TOKEN_BUDGET,
    model_name: str = DEFAULT_MODEL,
    config: KnowStackConfig | None = None,
    neighborhood: NeighborhoodPolicy | None = None,
) -> PRContextBundle:
    """Return a budgeted, ranked context bundle for an LLM PR reviewer.

    The index at `config.db_path` is read-only — this function never writes
    to the graph. If a touched file isn't indexed (e.g. it's brand new) it's
    silently skipped and noted in `bundle.notes`.
    """
    cfg = config or KnowStackConfig(repo_path=pr.repo_path)
    policy = neighborhood or NeighborhoodPolicy()
    notes: list[str] = []

    engine = QueryEngine(cfg)
    try:
        store = engine._store  # private but stable; avoids opening a 2nd Kuzu conn

        seeds = extract_seeds(store, pr.files, repo_id=cfg.repo_id or None)
        if not seeds:
            notes.append("No touched symbols found in the index — is it up to date?")
            return _empty_bundle(token_budget, notes)

        seed_cands, neighbor_cands = expand_neighborhood(
            seeds, engine, store, policy, repo_id=cfg.repo_id or None,
        )
        selected, dropped = rank_and_trim(
            seed_cands, neighbor_cands,
            token_budget=token_budget, model_name=model_name,
        )

        context_text = _format_context(selected, seed_cands, pr)
        estimated = estimate_tokens(context_text, model_name)
        baseline = naive_file_baseline_tokens(pr, model_name)
        return PRContextBundle(
            context_text=context_text,
            nodes=tuple(selected),
            estimated_tokens=estimated,
            budget_tokens=token_budget,
            seeds=tuple(
                SeedSymbol(fqn=s.node.fqn, node_type=s.node.node_type)
                for s in seed_cands
            ),
            dropped_count=dropped,
            notes=tuple(notes),
            baseline_tokens=baseline,
            tokens_saved=max(0, baseline - estimated),
        )
    finally:
        engine.close()


# ── helpers ─────────────────────────────────────────────────────────────────


def _format_context(
    selected: list[SelectedNode],
    seed_cands: list[Candidate],
    pr: PRMetadata,
) -> str:
    """Render selected nodes into markdown using KnowStack's ContextPacker.

    We do our own token budgeting upstream, so the packer is asked for an
    effectively unlimited block; truncation only happens via our trimming.
    """
    if not selected:
        return ""

    # Build a lookup so we can attach the (reason, distance) provenance.
    selected_by_id = {n.node_id: n for n in selected}
    nodes = [_selected_to_ranked(s, seed_cands) for s in selected]

    header_query = _pr_header(pr, selected_by_id)
    packer = ContextPacker(max_tokens=10**9)
    return packer.pack(nodes, query=header_query)


def _pr_header(pr: PRMetadata, by_id: dict[str, SelectedNode]) -> str:
    """One-line summary that appears in the packer's `# Code Context` header."""
    pr_ref = f"PR #{pr.pr_number}" if pr.pr_number is not None else "PR (no number)"
    title = pr.title or "(untitled)"
    touched_count = sum(1 for n in by_id.values() if n.reason == "touched")
    return f"{pr_ref} — {title} — {touched_count} touched symbol(s)"


def _selected_to_ranked(
    sel: SelectedNode, seed_cands: list[Candidate],
) -> RankedNode:
    """Reconstruct a RankedNode for the packer, tagging the docstring with reason.

    The packer doesn't know about `reason`, so we splice it into the docstring
    field — it's the easiest way to surface "why this is in the context" to
    the LLM without modifying the packer.
    """
    seed_node = next((c.node for c in seed_cands if c.node.node_id == sel.node_id), None)
    if seed_node is not None:
        base = seed_node
    else:
        base = RankedNode(
            node_id=sel.node_id,
            fqn=sel.fqn,
            name=sel.fqn.rsplit(".", 1)[-1],
            node_type=sel.node_type,
            file_path=sel.file_path or "",
            language="",
            start_line=sel.start_line or 0,
            end_line=sel.end_line or 0,
        )
    tag = f"[selected as: {sel.reason}, distance={sel.distance}]"
    base.docstring = f"{tag} {base.docstring}".strip() if base.docstring else tag
    return base


def _empty_bundle(token_budget: int, notes: list[str]) -> PRContextBundle:
    return PRContextBundle(
        context_text="",
        nodes=(),
        estimated_tokens=0,
        budget_tokens=token_budget,
        seeds=(),
        dropped_count=0,
        notes=tuple(notes),
        baseline_tokens=0,
        tokens_saved=0,
    )

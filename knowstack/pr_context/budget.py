"""Rank candidates and trim to a token budget.

Ranking is deterministic and explainable: it combines (1) the reason the node
was selected, (2) graph distance from the nearest touched seed, and (3) the
node's pre-computed importance score from the KnowStack enricher. Touched
seeds are always kept (they're the diff itself); everything else competes
for whatever budget is left.
"""
from __future__ import annotations

from knowstack.pr_context.models import SelectedNode, SelectionReason
from knowstack.pr_context.neighborhood import Candidate
from knowstack.retrieval.context_packer import ContextPacker
from knowstack.retrieval.ranker import RankedNode

# Chars-per-token by model family. Conservative defaults so we under-fill
# rather than overflow; refined later if/when we wire `tiktoken`.
MODEL_CHARS_PER_TOKEN: dict[str, float] = {
    "claude": 3.5,
    "gpt": 4.0,
    "default": 3.5,
}

# Higher = more important. Touched seeds dominate; tests and direct callers
# come next because they tell a reviewer what a change can break.
REASON_WEIGHT: dict[SelectionReason, float] = {
    "touched": 1.0,
    "test": 0.65,
    "caller": 0.55,
    "callee": 0.40,
    "impacted": 0.30,
    "related_config": 0.20,
}

DISTANCE_WEIGHT = 0.20
IMPORTANCE_WEIGHT = 0.20


def chars_per_token(model_name: str) -> float:
    """Look up a chars-per-token ratio by model-name prefix."""
    name = (model_name or "").lower()
    for key, ratio in MODEL_CHARS_PER_TOKEN.items():
        if key in name:
            return ratio
    return MODEL_CHARS_PER_TOKEN["default"]


def estimate_tokens(text: str, model_name: str) -> int:
    """Char-based token estimate for `text` under the given model."""
    if not text:
        return 0
    return max(1, int(len(text) / chars_per_token(model_name)))


def score_candidate(c: Candidate) -> float:
    """Deterministic ranking score for a single candidate."""
    reason_w = REASON_WEIGHT.get(c.reason, 0.1)
    distance_w = DISTANCE_WEIGHT / (1 + max(c.distance, 0))
    importance_w = IMPORTANCE_WEIGHT * float(c.node.importance_score or 0.0)
    return reason_w + distance_w + importance_w


def rank_and_trim(
    seeds: list[Candidate],
    neighbors: list[Candidate],
    *,
    token_budget: int,
    model_name: str,
) -> tuple[list[SelectedNode], int]:
    """Greedily fill the budget; seeds first, then neighbors by score.

    Returns (selected_in_order, dropped_count). Order is rank-descending, so
    the packer can truncate the tail without losing the highest-signal nodes.
    """
    packer = ContextPacker(max_tokens=10**9)  # we do our own budgeting

    # Always keep seeds — they ARE the diff. If even the seeds overflow the
    # budget we still include them all so the reviewer sees the actual change.
    ordered_seeds = sorted(seeds, key=score_candidate, reverse=True)
    ordered_neighbors = sorted(neighbors, key=score_candidate, reverse=True)

    selected: list[Candidate] = list(ordered_seeds)

    dropped = 0
    for cand in ordered_neighbors:
        trial = selected + [cand]
        trial_tokens = _estimate_block_tokens(packer, [c.node for c in trial], model_name)
        if trial_tokens <= token_budget:
            selected = trial
        else:
            dropped += 1

    return [_to_selected(c) for c in selected], dropped


def _estimate_block_tokens(
    packer: ContextPacker, nodes: list[RankedNode], model_name: str,
) -> int:
    text = packer.pack(nodes, query="")
    return estimate_tokens(text, model_name)


def _to_selected(c: Candidate) -> SelectedNode:
    n = c.node
    return SelectedNode(
        node_id=n.node_id,
        fqn=n.fqn,
        node_type=n.node_type,
        file_path=n.file_path or None,
        start_line=n.start_line or None,
        end_line=n.end_line or None,
        score=score_candidate(c),
        reason=c.reason,
        distance=c.distance,
    )

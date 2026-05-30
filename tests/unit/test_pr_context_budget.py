"""Unit tests for pr_context.budget — rank, trim, and token accounting."""
from __future__ import annotations

from knowstack.pr_context.budget import (
    chars_per_token,
    estimate_tokens,
    rank_and_trim,
    score_candidate,
)
from knowstack.pr_context.models import SelectionReason
from knowstack.pr_context.neighborhood import Candidate
from knowstack.retrieval.ranker import RankedNode


def _cand(
    fqn: str,
    reason: SelectionReason,
    distance: int = 1,
    importance: float = 0.0,
    doc: str = "",
) -> Candidate:
    node = RankedNode(
        node_id=fqn,
        fqn=fqn,
        name=fqn.rsplit(".", 1)[-1],
        node_type="Function",
        file_path=f"src/{fqn.split('.')[0]}.py",
        language="python",
        signature=f"def {fqn.rsplit('.', 1)[-1]}() -> None",
        docstring=doc,
        start_line=10,
        end_line=20,
        importance_score=importance,
    )
    return Candidate(node=node, reason=reason, distance=distance)


def test_chars_per_token_recognizes_claude_and_gpt():
    assert chars_per_token("claude-sonnet-4-6") == 3.5
    assert chars_per_token("gpt-4o") == 4.0
    assert chars_per_token("some-unknown-model") == 3.5  # default


def test_estimate_tokens_scales_with_chars_per_token():
    text = "x" * 350
    assert estimate_tokens(text, "claude") == 100  # 350 / 3.5
    assert estimate_tokens(text, "gpt-4") < estimate_tokens(text, "claude")


def test_score_orders_touched_above_everything():
    touched = _cand("a.touched", "touched", distance=0, importance=0.1)
    test = _cand("a.test", "test", distance=1, importance=0.9)
    caller = _cand("a.caller", "caller", distance=1, importance=0.9)
    callee = _cand("a.callee", "callee", distance=1, importance=0.9)
    impacted = _cand("a.imp", "impacted", distance=2, importance=0.9)
    cfg = _cand("a.cfg", "related_config", distance=2, importance=0.9)

    scores = [
        ("touched", score_candidate(touched)),
        ("test", score_candidate(test)),
        ("caller", score_candidate(caller)),
        ("callee", score_candidate(callee)),
        ("impacted", score_candidate(impacted)),
        ("related_config", score_candidate(cfg)),
    ]
    assert scores == sorted(scores, key=lambda kv: kv[1], reverse=True), scores


def test_rank_and_trim_keeps_all_seeds_even_with_zero_budget():
    seeds = [_cand("a.s1", "touched", 0), _cand("a.s2", "touched", 0)]
    neighbors = [_cand("a.n1", "caller", 1)]

    selected, dropped = rank_and_trim(
        seeds, neighbors, token_budget=0, model_name="claude",
    )
    assert {s.fqn for s in selected} == {"a.s1", "a.s2"}
    assert dropped == 1  # the lone neighbor didn't fit


def test_rank_and_trim_is_deterministic():
    seeds = [_cand("a.s1", "touched", 0)]
    neighbors = [
        _cand(f"a.n{i}", "caller", 1, importance=i * 0.01)
        for i in range(10)
    ]
    a, _ = rank_and_trim(seeds, neighbors, token_budget=4000, model_name="claude")
    b, _ = rank_and_trim(seeds, neighbors, token_budget=4000, model_name="claude")
    assert [s.node_id for s in a] == [s.node_id for s in b]


def test_rank_and_trim_higher_priority_reason_displaces_lower():
    seeds = [_cand("a.s1", "touched", 0)]
    # Same node count, but tests should be picked before related_configs.
    neighbors = [
        _cand("a.cfg", "related_config", 2),
        _cand("a.test", "test", 1),
    ]
    selected, _ = rank_and_trim(
        seeds, neighbors, token_budget=4000, model_name="claude",
    )
    fqns_in_order = [s.fqn for s in selected]
    assert fqns_in_order.index("a.test") < fqns_in_order.index("a.cfg")


def test_rank_and_trim_respects_budget_when_neighbors_are_large():
    seeds = [_cand("a.s1", "touched", 0)]
    # Each neighbor carries a hefty docstring → packer output grows.
    fat_doc = "lorem ipsum " * 200
    neighbors = [_cand(f"a.n{i}", "caller", 1, doc=fat_doc) for i in range(20)]

    selected, dropped = rank_and_trim(
        seeds, neighbors, token_budget=500, model_name="claude",
    )
    assert dropped > 0
    assert len(selected) - 1 < len(neighbors)  # at least some were trimmed

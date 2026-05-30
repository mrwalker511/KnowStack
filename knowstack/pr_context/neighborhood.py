"""Expand seed nodes into a bounded neighborhood with explicit reasons.

Each seed produces up to `policy.max_neighbors_per_seed` neighbors drawn from:
  - tests:    TESTED_BY edges into the seed
  - callers:  reverse CALLS edges (depth 1)
  - callees:  forward CALLS edges (depth 1)
  - impacted: QueryEngine.query_impact (depth > 1)
  - related_config: ConfigFile nodes sharing a tag with the seed

Every candidate carries a (reason, distance) pair so the budgeter can rank
by structural relevance, not just KnowStack's generic importance score.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from knowstack.graph.store import GraphStore
from knowstack.pr_context.models import NeighborhoodPolicy, SelectionReason
from knowstack.pr_context.symbol_extractor import Seed
from knowstack.retrieval.query_engine import QueryEngine
from knowstack.retrieval.ranker import RankedNode

log = logging.getLogger(__name__)


@dataclass
class Candidate:
    """A node under consideration plus its provenance from a seed."""
    node: RankedNode
    reason: SelectionReason
    distance: int


def expand_neighborhood(
    seeds: list[Seed],
    engine: QueryEngine,
    store: GraphStore,
    policy: NeighborhoodPolicy,
    repo_id: str | None = None,
) -> tuple[list[Candidate], list[Candidate]]:
    """Return (seed_candidates, neighbor_candidates).

    Seeds are returned as distance-0 `touched` candidates. Neighbors are
    deduplicated across seeds, keeping the smallest distance and the
    highest-priority reason (touched > test > caller > callee > impacted > config).
    """
    seed_candidates = [_seed_to_candidate(s) for s in seeds]

    by_id: dict[str, Candidate] = {c.node.node_id: c for c in seed_candidates}

    for seed in seeds:
        per_seed: list[Candidate] = []

        if policy.include_tests:
            per_seed.extend(_tests_of(store, seed.node_id, repo_id))
        if policy.include_callers:
            per_seed.extend(_callers_of(store, seed.node_id, repo_id))
        if policy.include_callees:
            per_seed.extend(_callees_of(store, seed.node_id, repo_id))
        if policy.impact_depth > 1:
            per_seed.extend(_impacted_by(engine, seed.fqn, policy.impact_depth))
        if policy.include_related_configs and seed.tags:
            per_seed.extend(_related_configs(store, seed.tags, repo_id))

        # Cap per seed before global merge so one huge seed can't crowd out
        # the others.
        per_seed.sort(key=lambda c: (_REASON_PRIORITY[c.reason], c.distance))
        for cand in per_seed[: policy.max_neighbors_per_seed]:
            existing = by_id.get(cand.node.node_id)
            if existing is None:
                by_id[cand.node.node_id] = cand
            else:
                # Keep the higher-priority record (smaller priority value wins).
                if _better(cand, existing):
                    by_id[cand.node.node_id] = cand

    neighbors = [c for c in by_id.values() if c.distance > 0]
    return seed_candidates, neighbors


# ── reason ordering ──────────────────────────────────────────────────────────

_REASON_PRIORITY: dict[SelectionReason, int] = {
    "touched": 0,
    "test": 1,
    "caller": 2,
    "callee": 3,
    "impacted": 4,
    "related_config": 5,
}


def _better(a: Candidate, b: Candidate) -> bool:
    pa = (_REASON_PRIORITY[a.reason], a.distance)
    pb = (_REASON_PRIORITY[b.reason], b.distance)
    return pa < pb


# ── seed → candidate ────────────────────────────────────────────────────────


def _seed_to_candidate(seed: Seed) -> Candidate:
    node = RankedNode(
        node_id=seed.node_id,
        fqn=seed.fqn,
        name=seed.name,
        node_type=seed.node_type,
        file_path=seed.file_path,
        language="",
        start_line=seed.start_line,
        end_line=seed.end_line,
    )
    return Candidate(node=node, reason="touched", distance=0)


# ── neighbor queries ────────────────────────────────────────────────────────


def _tests_of(store: GraphStore, node_id: str, repo_id: str | None) -> list[Candidate]:
    cypher = """
        MATCH (t:Test)-[:TESTED_BY]->(n {node_id: $id})
        RETURN t
    """
    return _collect(store, cypher, {"id": node_id}, repo_id, reason="test", distance=1)


def _callers_of(store: GraphStore, node_id: str, repo_id: str | None) -> list[Candidate]:
    cypher = """
        MATCH (caller)-[:CALLS]->(n {node_id: $id})
        WHERE caller.node_id <> $id
        RETURN caller AS n
    """
    return _collect(store, cypher, {"id": node_id}, repo_id, reason="caller", distance=1)


def _callees_of(store: GraphStore, node_id: str, repo_id: str | None) -> list[Candidate]:
    cypher = """
        MATCH (n {node_id: $id})-[:CALLS]->(callee)
        WHERE callee.node_id <> $id
        RETURN callee AS n
    """
    return _collect(store, cypher, {"id": node_id}, repo_id, reason="callee", distance=1)


def _impacted_by(engine: QueryEngine, fqn: str, depth: int) -> list[Candidate]:
    """Use the public IMPACT query for transitive dependents."""
    try:
        result = engine.query_impact(fqn, depth=depth)
    except Exception as exc:
        log.debug("IMPACT query failed for %s: %s", fqn, exc)
        return []
    if result.error:
        return []
    return [
        Candidate(node=n, reason="impacted", distance=2)
        for n in result.nodes
    ]


def _related_configs(
    store: GraphStore, tags: tuple[str, ...], repo_id: str | None,
) -> list[Candidate]:
    """Up to 2 config files per matching tag, deduplicated by node_id."""
    out: list[Candidate] = []
    seen: set[str] = set()
    for tag in tags[:3]:  # cap tag fan-out to keep query cost bounded
        # Tags are stored as JSON-encoded strings, hence the quoted needle.
        needle = f'"{tag}"'
        params: dict[str, object] = {"needle": needle}
        repo_clause = ""
        if repo_id:
            repo_clause = " AND c.repo_id = $rid"
            params["rid"] = repo_id
        cypher = f"""
            MATCH (c:ConfigFile)
            WHERE c.tags CONTAINS $needle{repo_clause}
            RETURN c AS n
            LIMIT 2
        """
        try:
            rows = store.cypher(cypher, params)
        except Exception as exc:
            log.debug("related-config query failed: %s", exc)
            continue
        for r in rows:
            node = _row_to_ranked(r)
            if node is None or node.node_id in seen:
                continue
            seen.add(node.node_id)
            out.append(Candidate(node=node, reason="related_config", distance=2))
    return out


# ── shared row → RankedNode plumbing ────────────────────────────────────────


def _collect(
    store: GraphStore, cypher: str, params: dict, repo_id: str | None,
    *, reason: SelectionReason, distance: int,
) -> list[Candidate]:
    try:
        rows = store.cypher(cypher, params)
    except Exception as exc:
        log.debug("neighbor query failed (%s): %s", reason, exc)
        return []
    out: list[Candidate] = []
    for r in rows:
        node = _row_to_ranked(r)
        if node is None:
            continue
        if repo_id and node.repo_id and node.repo_id != repo_id:
            continue
        out.append(Candidate(node=node, reason=reason, distance=distance))
    return out


def _row_to_ranked(row: dict) -> RankedNode | None:
    """Flatten a Kuzu node object into a RankedNode (any column name)."""
    flat: dict = {}
    table_label: str | None = None
    for v in row.values():
        if hasattr(v, "__dict__") and not isinstance(v, (str, int, float, bool)):
            table_label = getattr(v, "_label", None) or table_label
            for k, val in v.__dict__.items():
                if not k.startswith("_"):
                    flat[k] = val
        elif isinstance(v, dict):
            flat.update(v)
    if not flat.get("node_id"):
        return None
    node = RankedNode.from_graph_row(flat)
    if not node.node_type and table_label:
        node.node_type = str(table_label)
    return node

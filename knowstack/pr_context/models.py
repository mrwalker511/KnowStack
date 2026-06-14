"""Frozen data structures for PR context inputs and outputs."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

ChangeType = Literal["added", "modified", "deleted"]

SelectionReason = Literal[
    "touched",          # symbol's source span overlaps a hunk
    "caller",           # 1-hop reverse CALLS of a touched symbol
    "callee",           # 1-hop forward CALLS of a touched symbol
    "test",             # TESTED_BY edge into a touched symbol
    "impacted",         # reachable via IMPACT at depth > 1
    "related_config",   # config file sharing a tag with a touched symbol
]


@dataclass(frozen=True)
class Hunk:
    """A contiguous changed line range in a file (1-indexed, inclusive)."""
    start_line: int
    end_line: int
    change_type: ChangeType = "modified"


@dataclass(frozen=True)
class ChangedFile:
    """A file changed by a PR, with the line ranges of its hunks."""
    path: str                       # repo-relative, forward slashes
    hunks: tuple[Hunk, ...] = ()
    is_new: bool = False
    is_deleted: bool = False


@dataclass(frozen=True)
class PRMetadata:
    """Minimal PR description sufficient to drive context selection."""
    repo_path: Path
    files: tuple[ChangedFile, ...]
    pr_number: int | None = None
    title: str = ""
    labels: tuple[str, ...] = ()


@dataclass(frozen=True)
class NeighborhoodPolicy:
    """Knobs governing how far we expand from each touched symbol."""
    impact_depth: int = 2
    include_callers: bool = True
    include_callees: bool = True
    include_tests: bool = True
    include_related_configs: bool = True
    max_neighbors_per_seed: int = 8


@dataclass(frozen=True)
class SelectedNode:
    """A node chosen for inclusion in the bundle, with provenance."""
    node_id: str
    fqn: str
    node_type: str
    file_path: str | None
    start_line: int | None
    end_line: int | None
    score: float
    reason: SelectionReason
    distance: int                   # graph hops from nearest seed; 0 = touched


@dataclass(frozen=True)
class SeedSymbol:
    """A touched-symbol seed, carrying its node type for downstream display."""
    fqn: str
    node_type: str                  # "Method"/"Function"/.../"File"/"ConfigFile"

    @property
    def is_symbol(self) -> bool:
        """True if this seed is a code symbol (not a bare file or config)."""
        return self.node_type not in ("", "File", "Directory", "ConfigFile")


@dataclass(frozen=True)
class PRContextBundle:
    """The full result: LLM-ready text plus structured metadata."""
    context_text: str
    nodes: tuple[SelectedNode, ...]
    estimated_tokens: int
    budget_tokens: int
    seeds: tuple[SeedSymbol, ...]   # touched symbols, with node_type
    dropped_count: int              # candidates considered but trimmed for budget
    notes: tuple[str, ...] = field(default_factory=tuple)
    # Naive-baseline metrics for the demo headline. Both default to 0 so
    # older callers that don't compute them still produce valid bundles.
    baseline_tokens: int = 0        # tokens if you pasted every changed file in full
    tokens_saved: int = 0           # max(0, baseline_tokens - estimated_tokens)

    def to_dict(self) -> dict[str, object]:
        return {
            "context_text": self.context_text,
            "estimated_tokens": self.estimated_tokens,
            "budget_tokens": self.budget_tokens,
            "baseline_tokens": self.baseline_tokens,
            "tokens_saved": self.tokens_saved,
            "seeds": [{"fqn": s.fqn, "node_type": s.node_type} for s in self.seeds],
            "dropped_count": self.dropped_count,
            "notes": list(self.notes),
            "nodes": [
                {
                    "node_id": n.node_id,
                    "fqn": n.fqn,
                    "node_type": n.node_type,
                    "file_path": n.file_path,
                    "start_line": n.start_line,
                    "end_line": n.end_line,
                    "score": round(n.score, 4),
                    "reason": n.reason,
                    "distance": n.distance,
                }
                for n in self.nodes
            ],
        }

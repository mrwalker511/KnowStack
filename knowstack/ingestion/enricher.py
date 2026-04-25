"""Stage 4 — Enricher: add git metadata, auto-tags, and importance hints.

Enrichment is non-destructive: it returns updated copies of nodes
(frozen Pydantic models) with additional fields filled in.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from knowstack.ingestion.normalizer import NormalizedGraph
from knowstack.models.nodes import BaseNode

log = logging.getLogger(__name__)

# Tag inference rules: (pattern, tag)
_PATH_TAGS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"auth", re.I), "authentication"),
    (re.compile(r"pay(ment)?|billing|invoice|checkout", re.I), "payments"),
    (re.compile(r"model|schema|entity|orm", re.I), "data-model"),
    (re.compile(r"test|spec", re.I), "test"),
    (re.compile(r"api|endpoint|route|handler|controller", re.I), "api"),
    (re.compile(r"db|database|repo|repositor", re.I), "database"),
    (re.compile(r"config|setting|env", re.I), "config"),
    (re.compile(r"util|helper|common|shared", re.I), "utility"),
    (re.compile(r"middleware|interceptor|filter|guard", re.I), "middleware"),
    (re.compile(r"migration", re.I), "migration"),
    (re.compile(r"queue|worker|job|task|celery", re.I), "async-worker"),
    (re.compile(r"cache|redis|memcache", re.I), "cache"),
    (re.compile(r"log|monitor|metric|trace|observ", re.I), "observability"),
]


class Enricher:
    def __init__(self, repo_path: Path, git_history_limit: int = 500) -> None:
        self._root = repo_path
        self._git_history_limit = git_history_limit
        self._file_change_freq: dict[str, float] = {}
        self._file_last_commit: dict[str, str] = {}
        self._git_available = self._load_git_stats()

    def enrich(self, graph: NormalizedGraph) -> NormalizedGraph:
        enriched_nodes: dict[str, BaseNode] = {}
        for node_id, node in graph.nodes.items():
            enriched = self._enrich_node(node)
            enriched_nodes[node_id] = enriched
        graph.nodes = enriched_nodes
        return graph

    def _enrich_node(self, node: BaseNode) -> BaseNode:
        updates: dict[str, object] = {}

        # Git metadata
        fp = getattr(node, "file_path", None)
        if fp and self._git_available:
            updates["change_frequency"] = self._file_change_freq.get(fp, 0.0)
            last = self._file_last_commit.get(fp)
            if last:
                updates["last_modified_commit"] = last

        # Auto-tagging from file path + node name
        tags = list(node.tags)
        search_text = (fp or "") + " " + node.name + " " + node.fqn
        for pattern, tag in _PATH_TAGS:
            if pattern.search(search_text) and tag not in tags:
                tags.append(tag)
        if tags != node.tags:
            updates["tags"] = tags

        # Preliminary importance (centrality added post-ingestion)
        freq = updates.get("change_frequency", node.change_frequency)
        updates["importance_score"] = node.centrality_score * (1 + float(freq))

        if updates:
            return node.model_copy(update=updates)
        return node

    def _load_git_stats(self) -> bool:
        """Compute per-file change frequency from git log. Returns False if git unavailable."""
        try:
            import git  # GitPython

            repo = git.Repo(self._root, search_parent_directories=True)
            commits = list(repo.iter_commits(max_count=self._git_history_limit))
            if not commits:
                return False

            total = len(commits)
            file_counts: dict[str, int] = {}
            last_commit: dict[str, str] = {}

            for commit in commits:
                for file_path in commit.stats.files:
                    file_counts[file_path] = file_counts.get(file_path, 0) + 1
                    if file_path not in last_commit:
                        last_commit[file_path] = commit.hexsha[:8]

            self._file_change_freq = {fp: count / total for fp, count in file_counts.items()}
            self._file_last_commit = last_commit
            log.debug(
                "Git enrichment: %d commits, %d files tracked", total, len(file_counts)
            )
            return True
        except Exception as exc:
            log.debug("Git enrichment unavailable: %s", exc)
            return False

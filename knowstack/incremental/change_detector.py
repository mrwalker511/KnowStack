"""Change detector: compute the diff between the last indexed state and now.

Strategy:
1. Read content_hash for every FileNode in the graph store.
2. Walk the filesystem, compute current hashes.
3. Classify files as: added, modified, deleted, unchanged.

Optionally uses git diff for speed (avoids re-hashing untracked files).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from knowstack.graph.store import GraphStore
from knowstack.models.enums import Language
from knowstack.utils.hashing import file_hash
from knowstack.utils.language_detect import detect_language

log = logging.getLogger(__name__)


@dataclass
class ChangeSet:
    added: list[Path] = field(default_factory=list)
    modified: list[Path] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)  # rel_path strings

    def is_empty(self) -> bool:
        return not (self.added or self.modified or self.deleted)

    def all_changed(self) -> list[Path]:
        return self.added + self.modified


class ChangeDetector:
    def __init__(self, repo_path: Path, store: GraphStore, repo_id: str | None = None) -> None:
        self._root = repo_path.resolve()
        self._store = store
        self._repo_id = repo_id

    def detect(self) -> ChangeSet:
        """Compare indexed state against current filesystem."""
        indexed = self._load_indexed_hashes()
        current = self._scan_current_hashes()

        added = [self._root / p for p in current if p not in indexed]
        modified = [
            self._root / p for p in current
            if p in indexed and indexed[p] != current[p]
        ]
        deleted = [p for p in indexed if p not in current]

        cs = ChangeSet(added=added, modified=modified, deleted=deleted)
        log.info(
            "ChangeDetector: +%d added, ~%d modified, -%d deleted",
            len(added), len(modified), len(deleted)
        )
        return cs

    def _load_indexed_hashes(self) -> dict[str, str]:
        """Load {rel_path: content_hash} from the graph store."""
        try:
            where = " WHERE f.repo_id = $rid" if self._repo_id else ""
            params: dict[str, str] = {"rid": self._repo_id} if self._repo_id else {}
            rows = self._store.cypher(
                f"MATCH (f:File){where} RETURN f.file_path AS path, f.content_hash AS hash",
                params,
            )
            return {str(r["path"]): str(r["hash"]) for r in rows if r.get("path")}
        except Exception as exc:
            log.warning("Could not load indexed hashes: %s", exc)
            return {}

    def _scan_current_hashes(self) -> dict[str, str]:
        """Walk repo and compute current file hashes."""
        hashes: dict[str, str] = {}
        for path in self._root.rglob("*"):
            if not path.is_file():
                continue
            if detect_language(path) == Language.UNKNOWN:
                continue
            rel = str(path.relative_to(self._root))
            try:
                hashes[rel] = file_hash(path)
            except OSError:
                pass
        return hashes

"""Stage 1 — Scanner: walk the filesystem and emit FileRecords.

Respects .gitignore patterns and the configured include/exclude filters.
Emits a FileRecord for each parseable file, complete with raw content
and a content hash for incremental change detection.
"""
from __future__ import annotations

import fnmatch
import logging
import os
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from knowstack.config.schema import KnowStackConfig
from knowstack.models.enums import Language
from knowstack.utils.hashing import content_hash
from knowstack.utils.language_detect import detect_language

log = logging.getLogger(__name__)

# Directories always skipped — even if no .gitignore exists
_ALWAYS_SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    ".mypy_cache", ".ruff_cache", ".pytest_cache", "dist", "build",
    "coverage", ".tox", ".eggs",
}


@dataclass
class FileRecord:
    abs_path: Path
    rel_path: str  # relative to repo_root
    language: Language
    size_bytes: int
    content: bytes
    content_hash: str
    extension: str = field(init=False)

    def __post_init__(self) -> None:
        self.extension = self.abs_path.suffix.lower()

    @property
    def text(self) -> str:
        """Decode content as UTF-8, replacing errors."""
        return self.content.decode("utf-8", errors="replace")


class Scanner:
    def __init__(self, repo_path: Path, config: KnowStackConfig) -> None:
        self._root = repo_path.resolve()
        self._config = config
        self._gitignore_patterns = self._load_gitignore_patterns()

    def scan(self) -> list[FileRecord]:
        """Walk the repo and return all parseable FileRecords."""
        records: list[FileRecord] = []
        for abs_path in self._walk():
            try:
                data = abs_path.read_bytes()
            except OSError as exc:
                log.warning("Cannot read %s: %s", abs_path, exc)
                continue

            if len(data) > self._config.max_file_size_bytes:
                log.debug("Skipping oversized file: %s (%d bytes)", abs_path, len(data))
                continue

            lang = detect_language(abs_path)
            if lang == Language.UNKNOWN:
                continue

            rel = str(abs_path.relative_to(self._root))
            records.append(
                FileRecord(
                    abs_path=abs_path,
                    rel_path=rel,
                    language=lang,
                    size_bytes=len(data),
                    content=data,
                    content_hash=content_hash(data),
                )
            )

        log.info("Scanner found %d files in %s", len(records), self._root)
        return records

    def _walk(self) -> Iterator[Path]:
        """Yield all file paths that pass all filters."""
        for dirpath_str, dirnames, filenames in os.walk(self._root):
            dirpath = Path(dirpath_str)
            # Prune directories in-place (modifies dirnames to control recursion)
            dirnames[:] = [
                d for d in dirnames
                if d not in _ALWAYS_SKIP_DIRS
                and not self._is_excluded(dirpath / d)
            ]
            for filename in filenames:
                fpath = dirpath / filename
                if not self._is_excluded(fpath):
                    yield fpath

    def _is_excluded(self, path: Path) -> bool:
        rel = str(path.relative_to(self._root))
        for pattern in self._config.exclude_patterns:
            if fnmatch.fnmatch(rel, pattern):
                return True
            # Also check basename against simple patterns
            if fnmatch.fnmatch(path.name, pattern):
                return True
        return any(fnmatch.fnmatch(rel, pattern) for pattern in self._gitignore_patterns)

    def _load_gitignore_patterns(self) -> list[str]:
        patterns: list[str] = []
        gitignore = self._root / ".gitignore"
        if gitignore.is_file():
            for line in gitignore.read_text(errors="replace").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    patterns.append(line)
        return patterns

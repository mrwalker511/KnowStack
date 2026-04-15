"""Entity extractor: pull symbol names from natural-language questions.

Uses difflib fuzzy matching against all indexed FQNs and names.
No ML required — fast, works offline, surprisingly accurate for
camelCase / snake_case symbol names mentioned in user questions.
"""
from __future__ import annotations

import difflib
import logging
import re

from knowstack.graph.store import GraphStore

log = logging.getLogger(__name__)

# Patterns that suggest a word is a code symbol (CamelCase or snake_case with underscores)
_SYMBOL_RE = re.compile(r'\b([A-Z][a-z]+[A-Za-z0-9]*|[a-z]+_[a-z_]+[a-z0-9]*)\b')


class EntityExtractor:
    def __init__(self, store: GraphStore) -> None:
        self._store = store
        self._all_names: list[str] = []
        self._all_fqns: list[str] = []
        self._loaded = False

    def _load_index(self) -> None:
        if self._loaded:
            return
        try:
            rows = self._store.cypher(
                "MATCH (n) RETURN n.name AS name, n.fqn AS fqn LIMIT 100000"
            )
            self._all_names = [str(r.get("name") or "") for r in rows if r.get("name")]
            self._all_fqns = [str(r.get("fqn") or "") for r in rows if r.get("fqn")]
        except Exception as exc:
            log.warning("Entity extractor index load failed: %s", exc)
        self._loaded = True

    def extract(self, question: str, top_n: int = 3) -> list[str]:
        """Return the most likely symbol FQNs mentioned in the question."""
        self._load_index()
        if not self._all_names:
            return []

        # Extract candidate tokens from question
        candidates = _SYMBOL_RE.findall(question)
        # Also include quoted identifiers
        quoted = re.findall(r'["\']([^"\']+)["\']', question)
        candidates.extend(quoted)

        if not candidates:
            return []

        matched_fqns: list[str] = []
        for candidate in candidates[:5]:  # Cap to avoid O(n²) on long questions
            # Try exact name match first
            exact = [fqn for name, fqn in zip(self._all_names, self._all_fqns)
                     if name == candidate]
            if exact:
                matched_fqns.extend(exact[:2])
                continue

            # Fuzzy match against all names
            close = difflib.get_close_matches(candidate, self._all_names, n=2, cutoff=0.75)
            for match in close:
                idx = self._all_names.index(match)
                matched_fqns.append(self._all_fqns[idx])

        # Deduplicate while preserving order
        seen: set[str] = set()
        result: list[str] = []
        for fqn in matched_fqns:
            if fqn not in seen:
                seen.add(fqn)
                result.append(fqn)

        return result[:top_n]

"""Intent classifier: map a natural-language question to a QueryIntent.

Uses a lightweight rule-based classifier first (fast, no API call).
Falls back to LLM zero-shot classification for ambiguous cases when
an LLM is configured.

Intent hierarchy:
    PATH        — "how does X reach Y", "flow from A to B"
    IMPACT      — "what breaks if", "what depends on", "callers of"
    STRUCTURAL  — "what calls", "which files import", DSL-compatible phrasing
    SEMANTIC    — everything else (broad conceptual questions)
"""
from __future__ import annotations

import re

from knowstack.retrieval.query_engine import QueryIntent

_PATH_PATTERNS = [
    re.compile(p, re.I) for p in [
        r"how does .+ (reach|get to|flow (through|to|into))",
        r"path (from|between) .+ (to|and)",
        r"flow (from|through)",
        r"trace .+ to",
    ]
]

_IMPACT_PATTERNS = [
    re.compile(p, re.I) for p in [
        r"what (breaks|fails|changes) if",
        r"what depends on",
        r"(callers?|dependents?) of",
        r"who (uses|calls|imports)",
        r"impact of (changing|removing|modifying)",
    ]
]

_STRUCTURAL_PATTERNS = [
    re.compile(p, re.I) for p in [
        r"what (calls|imports|inherits|implements|extends)",
        r"which (files?|classes?|functions?|methods?) (call|import|use|define)",
        r"where is .+ (defined|implemented|declared)",
        r"list (all )?(functions?|classes?|endpoints?|models?)",
        r"show me (all )?(functions?|classes?|files?)",
        r"find (all )?(functions?|classes?|files?) (that|where|with)",
    ]
]


class IntentClassifier:
    def classify(self, question: str) -> QueryIntent:
        """Return the most likely QueryIntent for a natural-language question."""
        if any(p.search(question) for p in _PATH_PATTERNS):
            return QueryIntent.PATH
        if any(p.search(question) for p in _IMPACT_PATTERNS):
            return QueryIntent.IMPACT
        if any(p.search(question) for p in _STRUCTURAL_PATTERNS):
            return QueryIntent.STRUCTURAL
        return QueryIntent.SEMANTIC

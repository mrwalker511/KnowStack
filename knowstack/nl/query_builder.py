"""NL → DSL query builder.

Combines intent classification + entity extraction to produce a
KnowStack DSL query string from a natural-language question.

When an LLM is configured, it is used for DSL generation directly.
Otherwise the rule-based builder constructs a best-effort DSL query.
"""
from __future__ import annotations

import logging

from knowstack.config.schema import KnowStackConfig
from knowstack.graph.store import GraphStore
from knowstack.nl.entity_extractor import EntityExtractor
from knowstack.nl.intent_classifier import IntentClassifier
from knowstack.retrieval.query_engine import QueryIntent

log = logging.getLogger(__name__)

_LLM_SYSTEM_PROMPT = """\
You are a code knowledge graph query translator.
Convert the user's natural-language question into a KnowStack DSL query.

DSL grammar:
  FIND [node_type] [WHERE field op value [AND field op value ...]] [LIMIT n]
  DEPENDENTS "symbol_name"
  IMPACT "symbol_name" [DEPTH n]
  PATH FROM "src_symbol" TO "dst_symbol"

Node types: function, method, class, file, interface, type, endpoint, model, test, config, *
Fields: name, fqn, file, tag, language
Operators: =, ~, contains

Return ONLY the DSL query. No explanation. No markdown.

Examples:
  Q: What calls the authenticate function?
  A: DEPENDENTS "authenticate"

  Q: How does auth flow to the database?
  A: PATH FROM "auth" TO "database"

  Q: Which classes implement Repository?
  A: FIND class WHERE name contains "Repository"

  Q: Find all API endpoints
  A: FIND endpoint LIMIT 50

  Q: What breaks if I change UserService?
  A: IMPACT "UserService" DEPTH 4
"""


class NLQueryBuilder:
    def __init__(self, config: KnowStackConfig, store: GraphStore) -> None:
        self._config = config
        self._store = store
        self._classifier = IntentClassifier()
        self._extractor = EntityExtractor(store)

    def build(self, question: str) -> tuple[QueryIntent, str]:
        """Return (intent, dsl_query). dsl may be empty for pure semantic queries."""
        intent = self._classifier.classify(question)

        llm_ready = self._config.llm_provider and (
            self._config.llm_provider == "ollama" or self._config.llm_api_key
        )
        if llm_ready:
            dsl = self._llm_build(question)
            if dsl:
                return intent, dsl

        return intent, self._rule_build(question, intent)

    def _rule_build(self, question: str, intent: QueryIntent) -> str:
        entities = self._extractor.extract(question)
        primary = f'"{entities[0]}"' if entities else '"unknown"'

        if intent == QueryIntent.PATH:
            if len(entities) < 2:
                # Can't build a valid PATH without two endpoints; fall back to DEPENDENTS
                return f"DEPENDENTS {primary}" if entities else "FIND * LIMIT 20"
            secondary = f'"{entities[1]}"'
            return f"PATH FROM {primary} TO {secondary}"
        elif intent == QueryIntent.IMPACT:
            return f"IMPACT {primary} DEPTH 3"
        elif intent == QueryIntent.STRUCTURAL:
            if entities:
                return f"DEPENDENTS {primary}"
            return "FIND * LIMIT 20"
        else:
            return ""  # Let caller fall back to semantic search

    def _llm_build(self, question: str) -> str:
        """Call the configured LLM to generate a DSL query."""
        try:
            if self._config.llm_provider == "anthropic":
                return self._anthropic_build(question)
            elif self._config.llm_provider == "openai":
                return self._openai_build(question)
            elif self._config.llm_provider == "ollama":
                return self._ollama_build(question)
        except Exception as exc:
            log.warning("LLM DSL generation failed: %s", exc)
        return ""

    def _anthropic_build(self, question: str) -> str:
        import anthropic
        client = anthropic.Anthropic(api_key=self._config.llm_api_key)
        msg = client.messages.create(
            model=self._config.llm_model or "claude-haiku-4-5-20251001",
            max_tokens=128,
            system=_LLM_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": question}],
        )
        content = msg.content[0].text if msg.content else ""
        return content.strip()

    def _openai_build(self, question: str) -> str:
        import httpx
        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {self._config.llm_api_key}"},
            json={
                "model": self._config.llm_model or "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": _LLM_SYSTEM_PROMPT},
                    {"role": "user", "content": question},
                ],
                "max_tokens": 128,
                "temperature": 0,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return content.strip()

    def _ollama_build(self, question: str) -> str:
        import httpx
        base_url = self._config.llm_ollama_base_url.rstrip("/")
        resp = httpx.post(
            f"{base_url}/v1/chat/completions",
            json={
                "model": self._config.llm_model or "qwen2.5-coder:7b",
                "messages": [
                    {"role": "system", "content": _LLM_SYSTEM_PROMPT},
                    {"role": "user", "content": question},
                ],
                "max_tokens": 128,
                "temperature": 0,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return content.strip()

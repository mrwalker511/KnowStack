"""Unit tests for NLQueryBuilder provider routing."""
from unittest.mock import MagicMock, patch

import pytest

from knowstack.config.schema import KnowStackConfig
from knowstack.nl.query_builder import NLQueryBuilder


@pytest.fixture
def mock_store():
    return MagicMock()


def _builder(mock_store, **config_kwargs) -> NLQueryBuilder:
    config = KnowStackConfig(**config_kwargs)
    return NLQueryBuilder(config, mock_store)


def _fake_response(dsl: str) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = {"choices": [{"message": {"content": dsl}}]}
    return resp


# ── Ollama routing ──────────────────────────────────────────────────────────

def test_ollama_build_calls_correct_url(mock_store):
    builder = _builder(mock_store, llm_provider="ollama", llm_model="qwen2.5-coder:7b")
    with patch("httpx.post", return_value=_fake_response('FIND function WHERE name = "auth"')) as mock_post:
        result = builder._ollama_build("Find the auth function")
    assert mock_post.call_args[0][0] == "http://localhost:11434/v1/chat/completions"
    assert result == 'FIND function WHERE name = "auth"'


def test_ollama_build_custom_base_url(mock_store):
    builder = _builder(mock_store, llm_provider="ollama", llm_ollama_base_url="http://192.168.1.10:11434")
    with patch("httpx.post", return_value=_fake_response("FIND * LIMIT 20")) as mock_post:
        builder._ollama_build("list everything")
    assert mock_post.call_args[0][0] == "http://192.168.1.10:11434/v1/chat/completions"


def test_ollama_build_no_authorization_header(mock_store):
    builder = _builder(mock_store, llm_provider="ollama")
    with patch("httpx.post", return_value=_fake_response("FIND * LIMIT 20")) as mock_post:
        builder._ollama_build("list everything")
    call_kwargs = mock_post.call_args[1]
    assert "headers" not in call_kwargs


def test_ollama_default_model(mock_store):
    builder = _builder(mock_store, llm_provider="ollama")  # no llm_model set
    with patch("httpx.post", return_value=_fake_response("FIND * LIMIT 20")) as mock_post:
        builder._ollama_build("list everything")
    assert mock_post.call_args[1]["json"]["model"] == "qwen2.5-coder:7b"


# ── build() guard ───────────────────────────────────────────────────────────

def test_build_routes_ollama_without_api_key(mock_store):
    builder = _builder(mock_store, llm_provider="ollama")
    with patch("httpx.post", return_value=_fake_response('DEPENDENTS "authenticate"')):
        _intent, dsl = builder.build("What calls authenticate?")
    assert dsl == 'DEPENDENTS "authenticate"'


def test_build_openai_still_requires_api_key(mock_store):
    builder = _builder(mock_store, llm_provider="openai")  # no llm_api_key
    with patch("httpx.post") as mock_post:
        builder.build("What calls authenticate?")
    mock_post.assert_not_called()


# ── Error fallback ──────────────────────────────────────────────────────────

def test_ollama_failure_falls_back_to_rule_based(mock_store):
    builder = _builder(mock_store, llm_provider="ollama")
    with patch("httpx.post", side_effect=Exception("connection refused")):
        _intent, dsl = builder.build("path from login to database")
    assert dsl != ""

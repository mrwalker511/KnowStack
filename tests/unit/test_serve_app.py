"""Unit tests for the FastAPI serve application."""
from unittest.mock import MagicMock, patch
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from knowstack.config.schema import KnowStackConfig
from knowstack.retrieval.query_engine import QueryIntent, QueryResult


@pytest.fixture
def mock_result():
    return QueryResult(
        query="test",
        intent=QueryIntent.STRUCTURAL,
        nodes=[],
        context="mock context",
    )


@pytest.fixture
def client(mock_result):
    from knowstack.serve.app import create_app

    config = KnowStackConfig(repo_path=Path("."))

    mock_engine = MagicMock()
    mock_engine.query_dsl.return_value = mock_result
    mock_engine.query_semantic.return_value = mock_result
    mock_engine.query_hybrid.return_value = mock_result
    mock_engine.query_nl.return_value = mock_result
    mock_engine.query_impact.return_value = mock_result
    mock_engine.query_path.return_value = mock_result
    mock_engine._store.node_count.return_value = 42
    mock_engine._store.edge_count.return_value = 99

    app = create_app(config)

    # Bypass lifespan by injecting mock engine directly into the closure dict
    with patch("knowstack.serve.app.QueryEngine", return_value=mock_engine):
        with TestClient(app) as c:
            yield c


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_info(client):
    resp = client.get("/v1/info")
    assert resp.status_code == 200
    data = resp.json()
    assert data["node_count"] == 42
    assert data["edge_count"] == 99


def test_query_dsl(client):
    resp = client.post("/v1/query/dsl", json={"query": "FIND function WHERE tag = auth"})
    assert resp.status_code == 200
    data = resp.json()
    assert "nodes" in data
    assert data["context"] == "mock context"


def test_query_semantic(client):
    resp = client.post("/v1/query/semantic", json={"query": "authentication logic"})
    assert resp.status_code == 200
    assert "nodes" in resp.json()


def test_query_hybrid(client):
    resp = client.post("/v1/query/hybrid", json={"query": "checkout pipeline"})
    assert resp.status_code == 200


def test_query_nl(client):
    resp = client.post("/v1/query/nl", json={"question": "what calls authenticate?"})
    assert resp.status_code == 200


def test_query_impact(client):
    resp = client.post("/v1/query/impact", json={"target": "UserService", "depth": 3})
    assert resp.status_code == 200


def test_query_path(client):
    resp = client.post("/v1/query/path", json={"src": "login", "dst": "database"})
    assert resp.status_code == 200


def test_context_excluded_when_false(client):
    resp = client.post("/v1/query/dsl", json={"query": "FIND *", "context": False})
    assert resp.status_code == 200
    assert "context" not in resp.json()


def test_error_result_returns_200_when_no_error(client):
    # mock_result has error="" so _result does not raise — verifies the happy path
    resp = client.post("/v1/query/dsl", json={"query": "FIND *"})
    assert resp.status_code == 200
    assert resp.json()["error"] == ""

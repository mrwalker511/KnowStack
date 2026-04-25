"""FastAPI application for KnowStack.

All query endpoints are thin wrappers around QueryEngine. The engine is
opened once at startup and closed on shutdown via the lifespan context.

Install: pip install knowstack[serve]
Run:     knowstack serve [REPO_PATH]
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from knowstack import __version__
from knowstack.config.schema import KnowStackConfig
from knowstack.retrieval.query_engine import QueryEngine

# ── Request / Response models ─────────────────────────────────────────────────

class DslRequest(BaseModel):
    query: str
    context: bool = True


class SemanticRequest(BaseModel):
    query: str
    top_k: int | None = None
    context: bool = True


class HybridRequest(BaseModel):
    query: str
    top_k: int | None = None
    context: bool = True


class NLRequest(BaseModel):
    question: str
    context: bool = True


class ImpactRequest(BaseModel):
    target: str
    depth: int = 3
    context: bool = True


class PathRequest(BaseModel):
    src: str
    dst: str
    max_depth: int = 6
    context: bool = True


# ── App factory ───────────────────────────────────────────────────────────────

def create_app(config: KnowStackConfig) -> FastAPI:
    """Return a configured FastAPI application bound to config."""

    engine: dict[str, QueryEngine] = {}  # mutable container for lifespan access

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine["q"] = QueryEngine(config)
        try:
            yield
        finally:
            engine["q"].close()

    app = FastAPI(
        title="KnowStack API",
        version=__version__,
        description="Query your codebase knowledge graph over HTTP.",
        lifespan=lifespan,
    )

    def _q() -> QueryEngine:
        return engine["q"]

    def _result(raw: Any, include_context: bool) -> dict[str, Any]:
        data: dict[str, Any] = raw.as_dict()
        if include_context:
            data["context"] = raw.context
        if raw.error:
            raise HTTPException(status_code=422, detail=raw.error)
        return data

    # ── Endpoints ─────────────────────────────────────────────────────────────

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/v1/info", tags=["meta"])
    def info() -> dict[str, Any]:
        store = _q()._store
        return {
            "version": __version__,
            "repo_path": str(config.repo_path),
            "node_count": store.node_count(),
            "edge_count": store.edge_count(),
        }

    @app.post("/v1/query/dsl", tags=["query"])
    def query_dsl(req: DslRequest) -> dict[str, Any]:
        """Execute a KnowStack DSL query (FIND / DEPENDENTS / IMPACT / PATH)."""
        return _result(_q().query_dsl(req.query), req.context)

    @app.post("/v1/query/semantic", tags=["query"])
    def query_semantic(req: SemanticRequest) -> dict[str, Any]:
        """Semantic similarity search over embedded nodes."""
        return _result(_q().query_semantic(req.query, top_k=req.top_k), req.context)

    @app.post("/v1/query/hybrid", tags=["query"])
    def query_hybrid(req: HybridRequest) -> dict[str, Any]:
        """Graph structural + semantic vector fusion."""
        return _result(_q().query_hybrid(req.query, top_k=req.top_k), req.context)

    @app.post("/v1/query/nl", tags=["query"])
    def query_nl(req: NLRequest) -> dict[str, Any]:
        """Natural language question → auto-routed query."""
        return _result(_q().query_nl(req.question), req.context)

    @app.post("/v1/query/impact", tags=["query"])
    def query_impact(req: ImpactRequest) -> dict[str, Any]:
        """Impact analysis: what depends on the target symbol."""
        return _result(_q().query_impact(req.target, depth=req.depth), req.context)

    @app.post("/v1/query/path", tags=["query"])
    def query_path(req: PathRequest) -> dict[str, Any]:
        """Find paths between two symbols."""
        return _result(_q().query_path(req.src, req.dst, max_depth=req.max_depth), req.context)

    return app

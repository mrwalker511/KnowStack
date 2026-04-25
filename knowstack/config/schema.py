"""KnowStack configuration schema.

Loaded from knowstack.toml (or .knowstack.toml) in the project root,
with CLI flags able to override any field.
"""
from pathlib import Path

from pydantic import BaseModel, Field

from knowstack.models.enums import Language


class KnowStackConfig(BaseModel):
    # ── Core paths ──────────────────────────────────────────────────────────
    repo_path: Path = Path(".")
    db_path: Path = Path(".knowstack/graph.kuzu")
    vector_db_path: Path = Path(".knowstack/vectors")

    # ── Embedding ───────────────────────────────────────────────────────────
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_device: str = "cpu"  # "cuda" if GPU available
    embedding_batch_size: int = 64
    embed_limit: int = 0  # Max nodes to embed per table; 0 = unlimited

    # ── Ingestion filters ───────────────────────────────────────────────────
    max_file_size_bytes: int = 512 * 1024  # 512 KB
    include_extensions: list[str] = Field(
        default_factory=lambda: [".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".yaml", ".yml", ".toml"]
    )
    exclude_patterns: list[str] = Field(
        default_factory=lambda: [
            "**/node_modules/**",
            "**/.git/**",
            "**/__pycache__/**",
            "**/dist/**",
            "**/build/**",
            "**/.venv/**",
            "**/venv/**",
            "**/*.min.js",
            "**/*.min.css",
            "**/coverage/**",
            "**/.pytest_cache/**",
        ]
    )
    languages: list[Language] = Field(
        default_factory=lambda: [Language.PYTHON, Language.TYPESCRIPT, Language.JAVASCRIPT]
    )

    # ── Parser options ───────────────────────────────────────────────────────
    max_call_depth: int = 10  # Max hops for PATH queries
    parse_workers: int = 4  # Parallel parser processes

    # ── Git enrichment ───────────────────────────────────────────────────────
    enable_git_enrichment: bool = True
    git_history_limit: int = 500  # Max commits to analyse

    # ── Retrieval ────────────────────────────────────────────────────────────
    context_max_tokens: int = 6000
    default_top_k: int = 20

    # ── Multi-repo (Phase 6) ─────────────────────────────────────────────────
    repo_id: str = ""  # Identifier for this repo in multi-repo workspaces

    # ── LLM (Phase 3) ────────────────────────────────────────────────────────
    llm_provider: str | None = None  # "anthropic" | "openai" | "ollama" | None
    llm_model: str | None = None
    llm_api_key: str | None = None  # Prefer env var ANTHROPIC_API_KEY / OPENAI_API_KEY
    llm_ollama_base_url: str = "http://localhost:11434"

    # ── Logging ──────────────────────────────────────────────────────────────
    log_level: str = "INFO"

    def resolve_paths(self, base: Path) -> "KnowStackConfig":
        """Return a copy with all relative paths resolved against base."""
        return self.model_copy(
            update={
                "repo_path": (base / self.repo_path).resolve(),
                "db_path": (base / self.db_path).resolve(),
                "vector_db_path": (base / self.vector_db_path).resolve(),
            }
        )

"""Shared pytest fixtures for KnowStack tests."""
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from knowstack.config.schema import KnowStackConfig
from knowstack.ingestion.scanner import FileRecord
from knowstack.models.enums import Language

FIXTURES_DIR = Path(__file__).parent / "fixtures"
PYTHON_SAMPLE = FIXTURES_DIR / "python_sample"
TS_SAMPLE = FIXTURES_DIR / "typescript_sample"


@pytest.fixture
def python_sample_dir() -> Path:
    return PYTHON_SAMPLE


@pytest.fixture
def ts_sample_dir() -> Path:
    return TS_SAMPLE


@pytest.fixture
def tmp_config(tmp_path: Path) -> KnowStackConfig:
    """A minimal config pointing at tmp_path."""
    return KnowStackConfig(
        repo_path=PYTHON_SAMPLE,
        db_path=tmp_path / "graph.kuzu",
        vector_db_path=str(tmp_path / "vectors"),
        enable_git_enrichment=False,
        embedding_model="BAAI/bge-small-en-v1.5",
    )


@pytest.fixture
def auth_file_record() -> FileRecord:
    """FileRecord for the Python sample auth.py."""
    path = PYTHON_SAMPLE / "auth.py"
    content = path.read_bytes()
    from knowstack.utils.hashing import content_hash
    return FileRecord(
        abs_path=path,
        rel_path="auth.py",
        language=Language.PYTHON,
        size_bytes=len(content),
        content=content,
        content_hash=content_hash(content),
    )


@pytest.fixture
def models_file_record() -> FileRecord:
    """FileRecord for the Python sample models.py."""
    path = PYTHON_SAMPLE / "models.py"
    content = path.read_bytes()
    from knowstack.utils.hashing import content_hash
    return FileRecord(
        abs_path=path,
        rel_path="models.py",
        language=Language.PYTHON,
        size_bytes=len(content),
        content=content,
        content_hash=content_hash(content),
    )

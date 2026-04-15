import hashlib
from pathlib import Path


def content_hash(data: bytes) -> str:
    """SHA-256 of raw bytes — used for file change detection."""
    return hashlib.sha256(data).hexdigest()


def file_hash(path: Path) -> str:
    """SHA-256 of a file on disk."""
    return content_hash(path.read_bytes())

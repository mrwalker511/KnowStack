"""Base parser contract.

Every language parser implements BaseParser.parse() and returns a ParseResult.
ParseResult carries all nodes and intra-file edges extracted from one file.
Cross-file edge resolution happens later in the Normalizer.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel

from knowstack.ingestion.scanner import FileRecord
from knowstack.models.edges import BaseEdge
from knowstack.models.nodes import BaseNode


class ParseResult(BaseModel):
    """Output of a single file parse."""

    file_record: FileRecord
    nodes: list[BaseNode] = []
    edges: list[BaseEdge] = []
    errors: list[str] = []  # Non-fatal parse errors (malformed code, etc.)

    model_config = {"arbitrary_types_allowed": True}


class BaseParser(ABC):
    """Abstract base for all language parsers."""

    @abstractmethod
    def can_parse(self, record: FileRecord) -> bool:
        """Return True if this parser handles the given FileRecord."""

    @abstractmethod
    def parse(self, record: FileRecord) -> ParseResult:
        """Extract nodes and edges from a FileRecord."""

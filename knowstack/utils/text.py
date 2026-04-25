"""Text utilities for embedding document construction and docstring handling."""
import re
import textwrap

from knowstack.models.nodes import BaseNode


def truncate(text: str, max_chars: int = 512, suffix: str = "…") -> str:
    """Truncate text to max_chars, appending suffix if truncated."""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - len(suffix)] + suffix


def clean_docstring(raw: str | None) -> str | None:
    """Dedent, strip, and normalize a raw docstring."""
    if not raw:
        return None
    cleaned = textwrap.dedent(raw).strip()
    # Collapse multiple blank lines
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return truncate(cleaned, max_chars=512) or None


def make_embedding_doc(node: BaseNode) -> str:
    """Build the text string embedded in the vector store for a node.

    Ordered by information density per token so the most useful content
    appears first (important if truncated by the embedding model).
    """
    parts: list[str] = [f"{node.node_type}: {node.fqn}"]

    # Signature (for functions/methods)
    sig = getattr(node, "signature", None)
    if sig:
        parts.append(f"Signature: {sig}")

    # Docstring
    if node.docstring:
        parts.append(f"Doc: {truncate(node.docstring, 300)}")

    # Location
    if node.source_span:
        parts.append(f"File: {node.source_span.file_path}:{node.source_span.start_line}")

    # Tags
    if node.tags:
        parts.append(f"Tags: {', '.join(node.tags)}")

    return "\n".join(parts)


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~3.5 chars per token (GPT/Claude average)."""
    return max(1, int(len(text) / 3.5))

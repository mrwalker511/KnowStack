"""Context packing: convert ranked nodes into a token-efficient LLM prompt block.

The packer works within a token budget and formats each node as a compact
structured block ordered by information density per token. The most relevant
nodes appear first so truncation (if it occurs) cuts the least valuable content.
"""
from __future__ import annotations

from knowstack.retrieval.ranker import RankedNode
from knowstack.utils.text import estimate_tokens, truncate

_AVG_CHARS_PER_TOKEN = 3.5


class ContextPacker:
    def __init__(self, max_tokens: int = 6000) -> None:
        self._max_tokens = max_tokens

    def pack(self, nodes: list[RankedNode], query: str = "") -> str:
        """Pack ranked nodes into a context string within the token budget."""
        budget_chars = int(self._max_tokens * _AVG_CHARS_PER_TOKEN)
        header = f"# Code Context\n**Query:** {query}\n\n" if query else "# Code Context\n\n"
        used = len(header)
        sections: list[str] = []

        for node in nodes:
            block = self._format_node(node)
            sep = "\n\n---\n\n"
            block_len = len(block) + len(sep)

            if used + block_len > budget_chars:
                remaining = budget_chars - used - len(sep)
                if remaining > 200:
                    block = block[:remaining] + "\n… [truncated]"
                    sections.append(block)
                break

            sections.append(block)
            used += block_len

        return header + (sep if sections else "").join(sections)

    def _format_node(self, node: RankedNode) -> str:
        parts: list[str] = []

        # Header line (most compact identifier)
        parts.append(f"## {node.node_type}: `{node.fqn}`")

        # Signature (functions/methods only)
        if node.signature:
            parts.append(f"**Signature:** `{truncate(node.signature, 150)}`")

        # Docstring
        if node.docstring:
            parts.append(f"**Doc:** {truncate(node.docstring, 300)}")

        # Location
        loc = node.file_path
        if node.start_line:
            loc += f":{node.start_line}"
            if node.end_line and node.end_line != node.start_line:
                loc += f"-{node.end_line}"
        parts.append(f"**File:** `{loc}`")

        # Direct relationships (max 5 — more is noise)
        if node.related_edges:
            rel_lines = [f"  - {e.get('edge_type', '')} → `{e.get('dst_name', '')}`"
                         for e in node.related_edges[:5]]
            parts.append("**Relationships:**\n" + "\n".join(rel_lines))

        return "\n".join(parts)

    def estimate_tokens(self, nodes: list[RankedNode], query: str = "") -> int:
        return estimate_tokens(self.pack(nodes, query))

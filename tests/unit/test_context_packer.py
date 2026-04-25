"""Unit tests for the ContextPacker."""

from knowstack.retrieval.context_packer import ContextPacker
from knowstack.retrieval.ranker import RankedNode
from knowstack.utils.text import estimate_tokens


def _make_node(fqn: str, sig: str = "", doc: str = "") -> RankedNode:
    return RankedNode(
        node_id=fqn[:8],
        fqn=fqn,
        name=fqn.split(".")[-1],
        node_type="Function",
        file_path="src/auth.py",
        language="python",
        signature=sig,
        docstring=doc,
        start_line=10,
        end_line=20,
    )


def test_packer_respects_token_budget():
    packer = ContextPacker(max_tokens=500)
    nodes = [_make_node(f"src.module.func_{i}", doc="A" * 200) for i in range(20)]
    result = packer.pack(nodes, query="test")
    assert estimate_tokens(result) <= 600  # allow small overshoot from headers


def test_packer_includes_query_header():
    packer = ContextPacker(max_tokens=2000)
    nodes = [_make_node("src.auth.login", sig="def login(email: str) -> Token")]
    result = packer.pack(nodes, query="authentication flow")
    assert "authentication flow" in result


def test_packer_includes_fqn():
    packer = ContextPacker(max_tokens=2000)
    nodes = [_make_node("src.auth.login", sig="def login(email: str) -> Token")]
    result = packer.pack(nodes)
    assert "src.auth.login" in result


def test_packer_empty_nodes():
    packer = ContextPacker(max_tokens=2000)
    result = packer.pack([])
    assert result  # header at minimum


def test_packer_truncates_long_docstring():
    packer = ContextPacker(max_tokens=300)
    long_doc = "This is a very long docstring. " * 50
    nodes = [_make_node("src.auth.f", doc=long_doc)]
    result = packer.pack(nodes)
    assert len(result) < 2000  # should be truncated

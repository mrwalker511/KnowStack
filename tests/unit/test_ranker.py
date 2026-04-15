"""Unit tests for the Ranker."""
from knowstack.retrieval.ranker import RankedNode, Ranker


def _node(fqn: str, centrality: float = 0.0, semantic: float = 0.0) -> RankedNode:
    return RankedNode(
        node_id=fqn[:8],
        fqn=fqn,
        name=fqn.split(".")[-1],
        node_type="Function",
        file_path="src/x.py",
        language="python",
        centrality_score=centrality,
        semantic_score=semantic,
    )


def test_ranker_sorts_by_final_score():
    ranker = Ranker()
    nodes = [
        _node("src.low", centrality=0.1, semantic=0.1),
        _node("src.high", centrality=0.9, semantic=0.9),
        _node("src.mid", centrality=0.5, semantic=0.5),
    ]
    ranked = ranker.rank(nodes)
    assert ranked[0].fqn == "src.high"
    assert ranked[-1].fqn == "src.low"


def test_ranker_name_match():
    ranker = Ranker()
    nodes = [
        _node("src.authenticate"),
        _node("src.logout"),
    ]
    ranked = ranker.rank(nodes, query_terms=["authenticate"])
    assert ranked[0].name == "authenticate"


def test_ranker_empty():
    ranker = Ranker()
    assert ranker.rank([]) == []


def test_ranker_final_score_range():
    ranker = Ranker()
    nodes = [_node(f"src.fn_{i}", centrality=float(i) / 10) for i in range(5)]
    ranked = ranker.rank(nodes)
    for node in ranked:
        assert 0.0 <= node.final_score <= 1.5  # weights sum to 1.0 but inputs may exceed 1

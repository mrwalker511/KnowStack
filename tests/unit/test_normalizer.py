"""Unit tests for the Normalizer."""
import pytest

from knowstack.ingestion.normalizer import Normalizer
from knowstack.ingestion.parsers.python_parser import PythonParser


def test_normalizer_deduplicates_edges(auth_file_record, models_file_record):
    parser = PythonParser()
    r1 = parser.parse(auth_file_record)
    r2 = parser.parse(models_file_record)

    normalizer = Normalizer()
    graph = normalizer.normalize([r1, r2])

    # Check no duplicate edge IDs
    edge_ids = [e.edge_id for e in graph.edges]
    assert len(edge_ids) == len(set(edge_ids))


def test_normalizer_resolves_imports(auth_file_record, models_file_record):
    parser = PythonParser()
    r1 = parser.parse(auth_file_record)
    r2 = parser.parse(models_file_record)

    normalizer = Normalizer()
    graph = normalizer.normalize([r1, r2])

    # All remaining edge src_ids should be in graph.nodes
    node_ids = set(graph.nodes.keys())
    for edge in graph.edges:
        assert edge.src_id in node_ids, f"Edge src {edge.src_id} not in graph"


def test_normalizer_node_count(auth_file_record, models_file_record):
    parser = PythonParser()
    results = [parser.parse(auth_file_record), parser.parse(models_file_record)]

    normalizer = Normalizer()
    graph = normalizer.normalize(results)

    assert graph.node_count > 0
    assert graph.edge_count >= 0


def test_normalizer_empty_input():
    normalizer = Normalizer()
    graph = normalizer.normalize([])
    assert graph.node_count == 0
    assert graph.edge_count == 0

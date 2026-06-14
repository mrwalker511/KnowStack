"""Unit tests for graph_retriever's depth-handling.

Kuzu's parser rejects parameterized variable-length traversal bounds
(``[*1..$depth]``). We inline the bound as a literal and validate it
first; these tests pin that behavior.
"""
from __future__ import annotations

import pytest

from knowstack.retrieval.graph_retriever import _safe_depth


def test_safe_depth_accepts_in_range():
    assert _safe_depth(1) == 1
    assert _safe_depth(10) == 10


def test_safe_depth_rejects_zero_and_negative():
    with pytest.raises(ValueError):
        _safe_depth(0)
    with pytest.raises(ValueError):
        _safe_depth(-1)


def test_safe_depth_rejects_above_default_hi():
    with pytest.raises(ValueError):
        _safe_depth(11)


def test_safe_depth_custom_hi():
    assert _safe_depth(15, hi=20) == 15
    with pytest.raises(ValueError):
        _safe_depth(21, hi=20)


def test_safe_depth_rejects_bool():
    # bool subclasses int; we don't want True/False slipping in.
    with pytest.raises(TypeError):
        _safe_depth(True)


def test_safe_depth_rejects_non_int():
    with pytest.raises(TypeError):
        _safe_depth("2")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        _safe_depth(2.5)  # type: ignore[arg-type]

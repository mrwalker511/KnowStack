"""Tests for the PR-comment formatter (.github/actions/pr-context/format_comment.py).

The formatter lives outside the package so the action can run it as a plain
script. We import it via a small spec-based loader to keep the tests in
the standard pytest tree.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_FORMATTER_PATH = (
    Path(__file__).resolve().parents[2]
    / ".github" / "actions" / "pr-context" / "format_comment.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("format_comment", _FORMATTER_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _bundle(**overrides) -> dict:
    base = {
        "context_text": "# Code Context\n## Function: a.b.c\n",
        "estimated_tokens": 500,
        "budget_tokens": 4000,
        "baseline_tokens": 5000,
        "tokens_saved": 4500,
        "seeds": [
            {"fqn": "pkg.mod.func", "node_type": "Function"},
            {"fqn": "pkg.mod.MyClass.method", "node_type": "Method"},
        ],
        "dropped_count": 0,
        "notes": [],
        "nodes": [
            {
                "node_id": "n1",
                "fqn": "pkg.mod.func",
                "node_type": "Function",
                "file_path": "pkg/mod.py",
                "start_line": 10,
                "end_line": 20,
                "score": 1.2,
                "reason": "touched",
                "distance": 0,
            }
        ],
    }
    base.update(overrides)
    return base


def test_render_includes_savings_headline():
    fmt = _load()
    out = fmt._render(_bundle())
    assert "Saved ~4,500 tokens (90%)" in out
    assert "files in full: 5,000" in out


def test_render_omits_savings_when_baseline_zero():
    fmt = _load()
    out = fmt._render(_bundle(baseline_tokens=0, tokens_saved=0))
    assert "Saved ~" not in out


def test_render_splits_file_seeds_from_symbol_seeds():
    fmt = _load()
    bundle = _bundle(seeds=[
        {"fqn": "pkg.mod.func", "node_type": "Function"},
        {"fqn": ".github/workflows/ci.yml", "node_type": "ConfigFile"},
        {"fqn": "src/static.txt", "node_type": "File"},
    ])
    out = fmt._render(bundle)
    assert "**Touched symbols**" in out
    assert "**Changed files**" in out
    # ConfigFile shouldn't be in the "Touched symbols" group.
    touched_block = out.split("**Touched symbols**", 1)[1].split("\n\n", 1)[0]
    assert ".github/workflows/ci.yml" not in touched_block
    assert "src/static.txt" not in touched_block
    # And conversely, the symbol shouldn't sneak into "Changed files".
    changed_block = out.split("**Changed files**", 1)[1].split("\n\n", 1)[0]
    assert "pkg.mod.func" not in changed_block


def test_render_accepts_legacy_string_seeds():
    # The M2 bundle shape: seeds is a list of bare FQN strings.
    fmt = _load()
    bundle = _bundle(seeds=["pkg.mod.func", "pkg.mod.other"])
    out = fmt._render(bundle)
    assert "pkg.mod.func" in out
    assert "pkg.mod.other" in out
    # Unknown node_type → treated as a symbol seed, not filtered out.
    assert "**Touched symbols**" in out


def test_render_marker_present_and_is_first_line():
    fmt = _load()
    out = fmt._render(_bundle())
    assert out.splitlines()[0] == fmt.MARKER

"""Unit tests for ChangeDetector and ChangeSet."""
from pathlib import Path
from unittest.mock import patch

import pytest

from knowstack.incremental.change_detector import ChangeDetector, ChangeSet


REPO_ROOT = Path("/fake/repo")


def _make_detector() -> ChangeDetector:
    """Return a ChangeDetector with a dummy store (not used in these tests)."""
    with patch.object(ChangeDetector, "__init__", lambda self, repo_path, store: None):
        cd = ChangeDetector.__new__(ChangeDetector)
        cd._root = REPO_ROOT
        cd._store = None
    return cd


def _detect(indexed: dict, current: dict) -> ChangeSet:
    cd = _make_detector()
    with (
        patch.object(cd, "_load_indexed_hashes", return_value=indexed),
        patch.object(cd, "_scan_current_hashes", return_value=current),
    ):
        return cd.detect()


# ---------------------------------------------------------------------------
# ChangeSet helpers
# ---------------------------------------------------------------------------

class TestChangeSet:
    def test_is_empty_when_all_empty(self):
        assert ChangeSet().is_empty()

    def test_is_empty_false_when_added(self):
        assert not ChangeSet(added=[Path("a.py")]).is_empty()

    def test_is_empty_false_when_modified(self):
        assert not ChangeSet(modified=[Path("b.py")]).is_empty()

    def test_is_empty_false_when_deleted(self):
        assert not ChangeSet(deleted=["c.py"]).is_empty()

    def test_all_changed_is_added_plus_modified(self):
        a, m = Path("a.py"), Path("m.py")
        cs = ChangeSet(added=[a], modified=[m])
        assert cs.all_changed() == [a, m]

    def test_all_changed_empty_when_only_deleted(self):
        cs = ChangeSet(deleted=["d.py"])
        assert cs.all_changed() == []


# ---------------------------------------------------------------------------
# detect()
# ---------------------------------------------------------------------------

class TestChangeDetectorDetect:
    def test_all_added_when_indexed_empty(self):
        cs = _detect(indexed={}, current={"auth.py": "abc", "models.py": "def"})
        assert len(cs.added) == 2
        assert all(isinstance(p, Path) for p in cs.added)
        assert cs.modified == []
        assert cs.deleted == []

    def test_no_changes_when_hashes_match(self):
        same = {"auth.py": "abc123", "models.py": "def456"}
        cs = _detect(indexed=same, current=same)
        assert cs.is_empty()

    def test_modified_when_hash_differs(self):
        cs = _detect(
            indexed={"auth.py": "old_hash"},
            current={"auth.py": "new_hash"},
        )
        assert cs.modified == [REPO_ROOT / "auth.py"]
        assert cs.added == []
        assert cs.deleted == []

    def test_deleted_when_file_absent_from_current(self):
        cs = _detect(
            indexed={"auth.py": "abc", "gone.py": "xyz"},
            current={"auth.py": "abc"},
        )
        assert cs.deleted == ["gone.py"]
        assert cs.added == []
        assert cs.modified == []

    def test_combined_changeset(self):
        cs = _detect(
            indexed={"existing.py": "old", "removed.py": "zzz"},
            current={"existing.py": "new", "brand_new.py": "qqq"},
        )
        assert REPO_ROOT / "brand_new.py" in cs.added
        assert REPO_ROOT / "existing.py" in cs.modified
        assert "removed.py" in cs.deleted
        assert cs.all_changed() == cs.added + cs.modified

    def test_added_paths_are_absolute_under_root(self):
        cs = _detect(indexed={}, current={"sub/new.py": "hash1"})
        assert cs.added == [REPO_ROOT / "sub/new.py"]

    def test_unchanged_files_not_in_any_category(self):
        cs = _detect(
            indexed={"unchanged.py": "same", "changed.py": "old"},
            current={"unchanged.py": "same", "changed.py": "NEW"},
        )
        unchanged_paths = [p.name for p in cs.added + cs.modified]
        assert "unchanged.py" not in unchanged_paths

    def test_load_indexed_hashes_returns_empty_on_store_error(self):
        from unittest.mock import MagicMock
        cd = _make_detector()
        cd._store = MagicMock()
        cd._store.cypher.side_effect = Exception("db down")
        assert cd._load_indexed_hashes() == {}

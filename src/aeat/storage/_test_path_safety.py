"""Tests for the typed path-containment helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from . import PathContainmentError
from ._path_safety import safe_record_path, safe_subpath

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


class TestSafeSubpath:
    """``safe_subpath`` resolves nested relative paths and rejects escapes."""

    def test_legitimate_nested_path(self, tmp_path: Path) -> None:
        resolved = safe_subpath(tmp_path, "alpha/beta/gamma.json", context="test")
        assert resolved == (tmp_path / "alpha" / "beta" / "gamma.json").resolve()

    def test_traversal_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(PathContainmentError):
            safe_subpath(tmp_path, "../escape.json", context="test")

    def test_absolute_path_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(PathContainmentError):
            safe_subpath(tmp_path, "/etc/passwd", context="test")

    def test_backslash_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(PathContainmentError):
            safe_subpath(tmp_path, "alpha\\beta.json", context="test")

    def test_double_dot_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(PathContainmentError):
            safe_subpath(tmp_path, "alpha/../beta.json", context="test")

    def test_inherits_value_error(self, tmp_path: Path) -> None:
        """Legacy ``except ValueError`` callers must still catch the typed error."""
        with pytest.raises(ValueError):
            safe_subpath(tmp_path, "../escape", context="test")


class TestSafeRecordPath:
    """``safe_record_path`` enforces the simple-token allow-list."""

    def test_valid_token_resolves(self, tmp_path: Path) -> None:
        resolved = safe_record_path(tmp_path, "abc123", context="test")
        assert resolved == (tmp_path / "abc123.json").resolve()

    def test_traversal_token_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(PathContainmentError):
            safe_record_path(tmp_path, "../escape", context="test")

    def test_slash_in_token_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(PathContainmentError):
            safe_record_path(tmp_path, "alpha/beta", context="test")

    def test_empty_token_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(PathContainmentError):
            safe_record_path(tmp_path, "", context="test")

    def test_overly_long_token_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(PathContainmentError):
            safe_record_path(tmp_path, "a" * 200, context="test")


class TestErrorCodeBinding:
    """``PathContainmentError`` binds to the registered INTEGRITY code."""

    def test_class_binds_to_registered_code(self) -> None:
        from ..errors._registry import bind_error_code

        bound = bind_error_code(PathContainmentError)
        assert bound.code == "INTEGRITY_STORAGE_PATH_CONTAINMENT"
        assert bound.category.value == "INTEGRITY"

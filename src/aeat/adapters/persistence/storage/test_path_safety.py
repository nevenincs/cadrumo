"""Tests for the typed path-containment helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from . import PathContainmentError
from ._path_safety import safe_record_path, safe_repository_id, safe_subpath

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


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


class TestSafeRepositoryId:
    """``safe_repository_id`` rejects tokens that would compose into an unsafe filename."""

    def test_clean_token_returned_unchanged(self) -> None:
        assert safe_repository_id("abc123-de", context="test_id") == "abc123-de"

    def test_uuid_shape_accepted(self) -> None:
        token = "550e8400-e29b-41d4-a716-446655440000"
        assert safe_repository_id(token, context="submission_id") == token

    def test_empty_rejected(self) -> None:
        with pytest.raises(PathContainmentError, match="must be non-empty"):
            safe_repository_id("", context="draft_id")

    def test_forward_slash_rejected(self) -> None:
        with pytest.raises(PathContainmentError, match="path separator"):
            safe_repository_id("foo/bar", context="draft_id")

    def test_backslash_rejected(self) -> None:
        with pytest.raises(PathContainmentError, match="path separator"):
            safe_repository_id("foo\\bar", context="draft_id")

    def test_single_dot_rejected(self) -> None:
        with pytest.raises(PathContainmentError, match="relative-path token"):
            safe_repository_id(".", context="modelo")

    def test_double_dot_rejected(self) -> None:
        with pytest.raises(PathContainmentError, match="relative-path token"):
            safe_repository_id("..", context="modelo")

    def test_dot_prefix_rejected(self) -> None:
        with pytest.raises(PathContainmentError, match="relative-path token"):
            safe_repository_id(".hidden", context="csv")

    def test_context_label_appears_in_error(self) -> None:
        with pytest.raises(PathContainmentError, match=r"^submission_id must"):
            safe_repository_id("foo/bar", context="submission_id")

    def test_failure_inherits_value_error(self) -> None:
        """Legacy ``except ValueError`` callers in test surface keep working."""
        with pytest.raises(ValueError):
            safe_repository_id("foo/bar", context="x")


class TestErrorCodeBinding:
    """``PathContainmentError`` binds to the registered INTEGRITY code."""

    def test_class_binds_to_registered_code(self) -> None:
        from ....core.errors._registry import bind_error_code

        bound = bind_error_code(PathContainmentError)
        assert bound.code == "INTEGRITY_STORAGE_PATH_CONTAINMENT"
        assert bound.category.value == "INTEGRITY"

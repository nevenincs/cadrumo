"""Tests for the typed path-containment helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core.config import override_settings
from .....core.errors.error_codes import build_error_envelope, resolve_error_message
from ..errors import PathContainmentError
from ..path_safety import safe_repository_id

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def _raise_unsafe_repository_id(_root: Path) -> None:
    safe_repository_id("foo/bar", context="x")


def test_path_containment_errors_inherit_value_error(tmp_path: Path) -> None:
    """Legacy ``except ValueError`` callers must still catch typed errors."""
    with pytest.raises(ValueError):
        _raise_unsafe_repository_id(tmp_path)


class TestSafeRepositoryId:
    """``safe_repository_id`` rejects tokens that would compose into an unsafe filename."""

    def test_safe_repository_id_returns_clean_token_unchanged(self) -> None:
        for token, context in (
            ("abc123-de", "test_id"),
            ("550e8400-e29b-41d4-a716-446655440000", "submission_id"),
        ):
            assert safe_repository_id(token, context=context) == token, token

    def test_unsafe_repository_ids_rejected(self) -> None:
        for unsafe_id, context, message in (
            ("", "draft_id", "must be non-empty"),
            ("foo/bar", "draft_id", "path separator"),
            ("foo\\bar", "draft_id", "path separator"),
            (".", "modelo", "relative-path token"),
            ("..", "modelo", "relative-path token"),
            (".hidden", "csv", "relative-path token"),
        ):
            with pytest.raises(PathContainmentError, match=message):
                safe_repository_id(unsafe_id, context=context)

    def test_context_label_appears_in_error(self) -> None:
        with pytest.raises(PathContainmentError, match=r"^submission_id must"):
            safe_repository_id("foo/bar", context="submission_id")

    def test_rejection_message_and_context_do_not_expose_token(self) -> None:
        token = "tax-id/12345678Z"

        with pytest.raises(PathContainmentError) as excinfo:
            safe_repository_id(token, context="taxpayer_nif")
        envelope = build_error_envelope(excinfo.value)

        assert token not in str(excinfo.value)
        assert token not in envelope.message
        assert token not in str(envelope.context)
        assert envelope.context == {
            "path_context": "taxpayer_nif",
            "violation": "repository_id_separator",
        }


class TestErrorCodeBinding:
    """``PathContainmentError`` binds to the registered INTEGRITY code."""

    def test_class_binds_to_registered_code(self) -> None:
        from .....core.errors.error_codes import bind_error_code

        bound = bind_error_code(PathContainmentError)
        assert bound is not None
        assert bound.code == "INTEGRITY_STORAGE_PATH_CONTAINMENT"
        assert bound.category.value == "INTEGRITY"

    def test_path_containment_error_uses_localized_operator_message(self) -> None:
        with pytest.raises(PathContainmentError) as excinfo:
            safe_repository_id("../escape", context="path")

        with override_settings(cadrumo_output_language="en"):
            message = resolve_error_message(excinfo.value)

        assert excinfo.value.translated_message == "errors.integrity.integrity_storage_path_containment"
        assert message == "A computed path escapes the configured root directory."
        assert excinfo.value.context == {
            "path_context": "path",
            "violation": "repository_id_separator",
        }

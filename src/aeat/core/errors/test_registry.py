"""Unit tests for the error-code registry."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ...entrypoints.cli._i18n import tr
from ..access_gate import LiveSubmitForbiddenError
from ..observability._errors import RunContextMissingError
from . import (
    ERROR_REGISTRY,
    ErrorCategory,
    ErrorCode,
    register,
    render_error_json,
    render_error_text,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]


def _sample_code(code: str) -> ErrorCode:
    return ErrorCode(
        code=code,
        category=ErrorCategory.ERROR,
        message_key="errors.error.sample_error",
        default_suggestion="aeat modelos list",
        retryable=False,
        runbook_id=None,
    )


def test_error_code_model_is_frozen() -> None:
    code = _sample_code("ERROR_TEST_SAMPLE")
    with pytest.raises((ValidationError, TypeError), match=r"frozen|Instance is frozen|attribute"):
        code.code = "ERROR_TEST_MUTATED"


def test_duplicate_registration_raises_clear_error() -> None:
    existing = next(iter(ERROR_REGISTRY.values()))
    duplicate = ErrorCode(
        code=existing.code,
        category=ErrorCategory.FAIL,
        message_key="errors.fail.duplicate_error",
        default_suggestion=None,
        retryable=False,
        runbook_id=None,
    )
    with pytest.raises(ValueError, match="duplicate ErrorCode registration"):
        register(duplicate)


def test_messages_do_not_leak_sphinx_role_markup() -> None:
    """Verify that resolved messages do not contain Sphinx markup roles."""
    for code in ERROR_REGISTRY.values():
        for locale in ("es", "en", "ca", "hu"):
            message = tr(code.message_key, locale=locale)
            assert ":mod:" not in message
            assert ":meth:" not in message
            assert ":func:" not in message
            assert ":class:" not in message
            assert ":data:" not in message


def test_messages_do_not_contain_known_broken_fragments() -> None:
    """Verify that resolved messages do not contain known broken fragments."""
    disallowed_fragments = (
        "Error de no configured proveedor.",
        "No configured szolgaltato hiba.",
        "Error de no soportado financiero origen.",
        "Error de aeat en vivo read no enabled.",
        "Aeat elo read nem enabled hiba.",
        "Error de aeat inicio de sesion assertion.",
        "Aeat bejelentkezes assertion hiba.",
        "Error de artefacto no recognised.",
        "Artefaktum nem recognised hiba.",
        "Error de proveedor no implemented.",
        "Szolgaltato nem implemented hiba.",
        "Error de no extractor registered.",
        "No kinyero registered hiba.",
        "Error de sitio health.",
        "Oldal health hiba.",
        "Error de presentacion draft.",
        "Beadas draft hiba.",
        "Error de l l m",
        "Raised when a ``manifest.",
        "Raised when persisted JSONL or trace.",
        "Raised when a repository operation fails (not-found, integrity, etc.",
        "Error de flujo de trabajo aborted.",
        "Munkafolyamat aborted hiba.",
    )
    for code in ERROR_REGISTRY.values():
        for locale in ("es", "en", "ca", "hu"):
            message = tr(code.message_key, locale=locale)
            for fragment in disallowed_fragments:
                assert fragment not in message


def test_core_error_prefixes_are_grep_stable() -> None:
    """Stable upper-case category identifiers survive in JSON; rendered text uses sentence case."""

    for error_factory, expected_category, expected_text_prefix in (
        (LiveSubmitForbiddenError, "LOCKED", "Locked."),
        (RunContextMissingError, "INTERNAL", "Internal."),
    ):
        error = error_factory()
        assert error.code.category.value == expected_category
        rendered_json = render_error_json(error)
        assert f'"category":"{expected_category}"' in rendered_json
        rendered_text = render_error_text(error)
        assert rendered_text.startswith(f"{expected_text_prefix} ")

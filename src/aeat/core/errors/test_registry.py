"""Unit tests for the error-code registry."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ..access_gate import LiveSubmitForbiddenError
from ..observability._errors import RunContextMissingError
from . import (
    ERROR_REGISTRY,
    ErrorCategory,
    ErrorCode,
    register,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]


def _sample_code(code: str) -> ErrorCode:
    return ErrorCode(
        code=code,
        category=ErrorCategory.ERROR,
        default_message_es="Error de ejemplo.",
        default_message_en="Sample error.",
        default_message_hu="Minta hiba.",
        default_suggestion="aeat modelos list",
        retryable=False,
        runbook_id=None,
    )


def test_error_code_model_is_frozen() -> None:
    code = _sample_code("ERROR_TEST_SAMPLE")
    with pytest.raises((ValidationError, TypeError)):
        code.code = "ERROR_TEST_MUTATED"  # type: ignore[misc]


def test_duplicate_registration_raises_clear_error() -> None:
    existing = next(iter(ERROR_REGISTRY.values()))
    duplicate = ErrorCode(
        code=existing.code,
        category=ErrorCategory.FAIL,
        default_message_es="Error duplicado.",
        default_message_en="Duplicate error.",
        default_message_hu="Duplikalt hiba.",
        default_suggestion=None,
        retryable=False,
        runbook_id=None,
    )
    with pytest.raises(ValueError, match="duplicate ErrorCode registration"):
        register(duplicate)


def test_default_messages_do_not_leak_sphinx_role_markup() -> None:
    for code in ERROR_REGISTRY.values():
        assert ":mod:" not in code.default_message_en
        assert ":meth:" not in code.default_message_en
        assert ":func:" not in code.default_message_en
        assert ":class:" not in code.default_message_en
        assert ":data:" not in code.default_message_en


def test_default_messages_do_not_contain_known_broken_fragments() -> None:
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
        messages = (code.default_message_es, code.default_message_en, code.default_message_hu)
        for message in messages:
            for fragment in disallowed_fragments:
                assert fragment not in message


def test_core_error_prefixes_are_grep_stable() -> None:
    for error_factory, expected_prefix in (
        (LiveSubmitForbiddenError, "LOCKED"),
        (RunContextMissingError, "INTERNAL"),
    ):
        first_line = error_factory().code.category.value
        assert first_line == expected_prefix

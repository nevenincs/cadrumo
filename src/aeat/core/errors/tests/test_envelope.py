"""Unit tests for the JSON error envelope."""

from __future__ import annotations

import json

import pytest

from ...config import override_settings
from ...locks_errors import LockAcquisitionError
from .. import build_error_envelope, render_error_json, render_error_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _output_language(language: str):
    """Pin ``aeat_output_language`` via the canonical Settings override."""
    return override_settings(aeat_output_language=language)


def test_error_envelope_serializes_deterministically() -> None:
    error = LockAcquisitionError(context={"z_key": "last", "a_key": "first"})
    first = render_error_json(error)
    second = render_error_json(error)

    assert first == second
    assert first.index('"category"') < first.index('"code"') < first.index('"context"')


def test_secret_scrubbing_redacts_sensitive_fields_in_json_and_text() -> None:
    jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.aaaaaaaaaaaa.bbbbbbbbbbbb"
    error = LockAcquisitionError(
        context={
            "api_token": "top-secret",
            "cookie": "session-cookie",
            "cert_password": "hunter2",
            "profile_tax_id": "X1234567L",
            "callback": "https://example.test/private/path?token=secret",
            "session_detail": f"bearer {jwt}",
        },
    )

    rendered_json = render_error_json(error)
    rendered_text = render_error_text(error)

    assert "<redacted>" in rendered_json
    assert "<redacted>" in rendered_text
    assert "top-secret" not in rendered_json
    assert "session-cookie" not in rendered_json
    assert "hunter2" not in rendered_json
    assert "top-secret" not in rendered_text
    assert "session-cookie" not in rendered_text
    assert "hunter2" not in rendered_text
    assert "X1234567L" not in rendered_json
    assert "X1234567L" not in rendered_text
    assert "sha256:2a000539" in rendered_json
    assert "https://example.test/private/path?token=secret" not in rendered_json
    assert "https://example.test" in rendered_json
    assert "private/path" not in rendered_json
    assert jwt not in rendered_json
    assert "token:sha256:0a2c77ea" in rendered_json


def test_error_document_carries_shared_spine() -> None:
    from ...json_contract import ENVELOPE_SCHEMA_VERSION, EnvelopeStatus

    payload = json.loads(render_error_json(LockAcquisitionError()))
    # The error document shares the success-envelope outer spine.
    assert payload["schema_version"] == ENVELOPE_SCHEMA_VERSION
    assert payload["status"] == EnvelopeStatus.ERROR.value
    assert payload["command"] is None
    assert payload["notices"] == []
    # The error detail is nested under ``error``; the spine owns the version.
    assert "schema_version" not in payload["error"]
    assert payload["error"]["code"]


def test_envelope_message_renders_under_every_supported_language() -> None:
    """Every supported locale must produce a non-empty rendered message.

    A locale that produced ``None`` or an empty string would mean the
    i18n routing collapsed for that language.
    """
    languages = ("es", "en", "hu", "ca")
    rendered_per_language: dict[str, str] = {}
    for language in languages:
        with _output_language(language):
            envelope = build_error_envelope(LockAcquisitionError())
            assert envelope.message, f"empty envelope.message for locale {language!r}"
            rendered_per_language[language] = envelope.message
    # Pin that EVERY supported locale rendered SOMETHING — the original
    # `assert envelope.message` inside the loop catches per-locale empty,
    # this catches a silent loop-skip where the iterator yielded zero
    # languages.
    assert set(rendered_per_language) == set(languages), (
        f"expected every locale to render, got {sorted(rendered_per_language)}"
    )


# --- Fix 5: internal context keys are stripped from operator-facing output ---


def test_scrub_error_context_strips_internal_keys_from_rendered_output() -> None:
    """``prompt_key`` and ``question_id`` are internal implementation
    details of the wizard widget layer.  They must not appear in either
    the text or JSON error output the operator sees.

    The keys must remain accessible on the exception's ``.context``
    attribute so internal diagnostics and existing tests can still
    inspect them.
    """

    from .._registry import _INTERNAL_CONTEXT_KEYS

    error = LockAcquisitionError(
        context={
            "prompt_key": "wizard.setup.profile.tax-id.prompt",
            "question_id": "tax-id",
            "raw": "INVALID_NIF",
            "detail": "not a valid NIF shape",
        },
    )

    rendered_json = render_error_json(error)
    rendered_text = render_error_text(error)

    # Internal keys must NOT appear in rendered output.
    assert "prompt_key" not in rendered_json
    assert "question_id" not in rendered_json
    assert "prompt_key" not in rendered_text
    assert "question_id" not in rendered_text

    # User-facing context keys must still appear.
    assert "detail" in rendered_json
    assert "raw" in rendered_json

    # The keys must remain accessible on the original exception context
    # (they are stripped only from the RENDERED output, not from the object).
    assert error.context is not None
    assert "prompt_key" in error.context
    assert "question_id" in error.context

    # The internal key set is a frozenset containing exactly these two names.
    assert "prompt_key" in _INTERNAL_CONTEXT_KEYS
    assert "question_id" in _INTERNAL_CONTEXT_KEYS

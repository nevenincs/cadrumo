"""Unit tests for the JSON error envelope."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from . import WorkspaceLockedError, build_error_envelope, render_error_json, render_error_text

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]


@contextmanager
def _output_language(language: str) -> Iterator[None]:
    previous = os.environ.get("AEAT_OUTPUT_LANGUAGE")
    os.environ["AEAT_OUTPUT_LANGUAGE"] = language
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("AEAT_OUTPUT_LANGUAGE", None)
        else:
            os.environ["AEAT_OUTPUT_LANGUAGE"] = previous


def test_error_envelope_serializes_deterministically() -> None:
    error = WorkspaceLockedError(context={"z_key": "last", "a_key": "first"})
    first = render_error_json(error)
    second = render_error_json(error)

    assert first == second
    assert first.index('"category"') < first.index('"code"') < first.index('"context"')


def test_secret_scrubbing_redacts_sensitive_fields_in_json_and_text() -> None:
    error = WorkspaceLockedError(
        context={
            "api_token": "top-secret",
            "cookie": "session-cookie",
            "cert_password": "hunter2",
            "profile_tax_id": "X1234567L",
        }
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
    assert "X1234567L" in rendered_json


def test_schema_version_is_present() -> None:
    envelope = build_error_envelope(WorkspaceLockedError())
    assert envelope.schema_version == "1"

    payload = json.loads(render_error_json(WorkspaceLockedError()))
    assert payload["error"]["schema_version"] == "1"


@pytest.mark.parametrize(
    ("language", "expected_attribute"),
    [
        ("es", "default_message_es"),
        ("en", "default_message_en"),
        ("hu", "default_message_hu"),
    ],
)
def test_default_messages_follow_requested_language(language: str, expected_attribute: str) -> None:
    error = WorkspaceLockedError()
    code = type(error).code

    with _output_language(language):
        envelope = build_error_envelope(error)

    assert envelope.message == getattr(code, expected_attribute)

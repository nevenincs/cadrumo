"""Recorded codes retain canonical presentation without retaining exception payloads."""

from __future__ import annotations

import json

import pytest

from ...config import override_settings
from ..error_codes import build_error_envelope, get_registered_error_code_by_code, render_error_json, render_error_text
from ..hierarchy import InternalInvariantError, RecordedRegisteredError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize(
    "code", ["REFUSED_EVIDENCE_BUNDLE_NOT_FOUND", "FAIL_PROFILE_EXPORT", "ERROR_CALCULATIONS_REGISTRY_VALIDATION"]
)
def test_recorded_failure_keeps_its_declared_code_category_and_retryability(code: str) -> None:
    registered = get_registered_error_code_by_code(code)
    with override_settings(cadrumo_output_language="en"):
        error = RecordedRegisteredError(
            code, context={"operation_id": "a" * 64, "effect": "none", "password": "private"}
        )
        envelope = build_error_envelope(error)
        text = render_error_text(error)
        document = json.loads(render_error_json(error))
    assert envelope.code == registered.code
    assert envelope.category == registered.category.value
    assert envelope.retryable is registered.retryable
    assert envelope.runbook_id == registered.runbook_id
    assert envelope.message and envelope.message != code and envelope.message != registered.message_key
    assert envelope.message in text
    assert document["error"] == envelope.model_dump(mode="json")
    assert envelope.context is not None and envelope.context.get("password") == "<redacted>"
    assert envelope.context["effect"] == "none"
    assert error.args == ()
    assert "private" not in text and "private" not in json.dumps(document)


def test_unregistered_recorded_reference_is_refused_before_presentation() -> None:
    with pytest.raises(InternalInvariantError):
        RecordedRegisteredError("UNREGISTERED_RECORD_WITH_PRIVATE_TEXT")

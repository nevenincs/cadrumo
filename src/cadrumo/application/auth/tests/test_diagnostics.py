"""Application-owned auth-diagnostic payload and refusal contracts."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from ....core.errors.error_codes import build_error_envelope
from ....core.external_constants import UTF_8_ENCODING
from ....tests.aeat_literal_fixtures import aeat_url, configured_path
from ..diagnostics import (
    AUTH_DIAGNOSTIC_PHONE_STATES,
    _DiagnosticPayload,
    _summary_from_payload,
    diagnostic_payload,
    record_auth_diagnostic_phone_state,
)
from ..errors import AuthDiagnosticPayloadError, AuthDiagnosticPhoneStateError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


class _UnusedDiagnosticPersistence:
    """Inward fake proving invalid phone states fail before persistence access."""

    def list_records(self):
        raise AssertionError("invalid phone state must not list diagnostics")

    def load_record(self, diagnostic_id: str):
        del diagnostic_id
        raise AssertionError("invalid phone state must not load diagnostics")

    def save_record(self, diagnostic_id: str, payload: bytes, *, written_at):
        del diagnostic_id, payload, written_at
        raise AssertionError("invalid phone state must not save diagnostics")


def test_auth_diagnostic_phone_state_error_round_trips_through_build_error_envelope() -> None:
    """The envelope carries resolved locale text, not the rejected raw token."""
    err = AuthDiagnosticPhoneStateError(
        translated_message="errors.refused.refused_auth_diagnostic_phone_state",
        context={"phone_state": "not_a_valid_state"},
    )
    envelope = build_error_envelope(err)
    assert envelope.code == "REFUSED_AUTH_DIAGNOSTIC_PHONE_STATE"
    assert envelope.category == "REFUSED"
    assert envelope.message
    assert envelope.message != "not_a_valid_state"
    assert envelope.message != err.translated_message


def test_diagnostic_payload_round_trips_through_json() -> None:
    """The typed diagnostic payload validates and serialises equivalently."""
    raw = {
        "diagnostic_id": "diag-rt-001",
        "reason": "push-wait-state-not-reached",
        "url": aeat_url("www2", configured_path("sede_paths", "clave_movil_login")),
        "captured_at": "2026-05-28T10:00:00+00:00",
        "html": "<html><body>page</body></html>",
        "screenshot_png_base64": "aW1hZ2U=",
        "auth_attempt": {"auth_mode": "non_qr", "headless": True, "timeout_ms": 120000},
        "operator_report": {"phone_state": "app_did_not_prompt", "reported_at": "2026-05-28T11:00:00+00:00"},
        "phone_state": "",
        "future_extension": "value",
    }

    payload_a = _DiagnosticPayload.model_validate(raw)
    serialised = payload_a.model_dump(mode="json")
    payload_b = _DiagnosticPayload.model_validate(serialised)

    assert payload_a == payload_b
    assert payload_a.diagnostic_id == "diag-rt-001"
    assert payload_a.reason == "push-wait-state-not-reached"
    assert payload_a.html == "<html><body>page</body></html>"
    assert payload_a.auth_attempt["auth_mode"] == "non_qr"
    assert payload_a.operator_report["phone_state"] == "app_did_not_prompt"

    serialised["diagnostic_id"] = "diag-rt-MUTATED"
    payload_mutated = _DiagnosticPayload.model_validate(serialised)
    assert payload_mutated != payload_a


def test_diagnostic_payload_rejects_non_object_json() -> None:
    """A non-object JSON root reports its typed validation rule."""
    import json as _json

    from ....core.errors.error_codes import get_registered_error_code, resolve_error_message

    with pytest.raises(AuthDiagnosticPayloadError) as raised:
        diagnostic_payload(_json.dumps([1, 2, 3]).encode(UTF_8_ENCODING))

    error = raised.value
    assert isinstance(error, ValueError)
    assert error.translated_message == "errors.refused.refused_auth_diagnostic_payload"
    assert error.context == {"validation_rule": "json_root_object", "json_root_type": "list"}
    assert get_registered_error_code(error).code == "REFUSED_AUTH_DIAGNOSTIC_PAYLOAD"
    assert str(error) == error.translated_message
    resolved = resolve_error_message(error)
    assert resolved and resolved != error.translated_message


@pytest.mark.parametrize(
    ("build_payload", "expected_context"),
    [
        pytest.param(
            lambda: {"diagnostic_id": "diag-1", "reason": "r"},
            {"validation_rule": "captured_at_present"},
            id="captured_at_missing",
        ),
        pytest.param(
            lambda: {"diagnostic_id": "diag-1", "reason": "r", "captured_at": "not-an-instant"},
            {"validation_rule": "iso_8601_instant", "field": "captured_at"},
            id="captured_at_not_iso",
        ),
        pytest.param(
            lambda: {"diagnostic_id": "diag-1", "reason": "r", "captured_at": "2026-08-13T09:00:00"},
            {"validation_rule": "utc_aware_instant", "field": "captured_at"},
            id="captured_at_naive",
        ),
        pytest.param(
            lambda: {
                "diagnostic_id": "diag-1",
                "reason": "r",
                "captured_at": "2026-08-13T09:00:00+00:00",
                "phone_state": "not_a_known_state",
            },
            {
                "validation_rule": "closed_phone_state_vocabulary",
                "phone_state": "not_a_known_state",
                "accepted_phone_states": ", ".join(AUTH_DIAGNOSTIC_PHONE_STATES),
            },
            id="phone_state_outside_vocabulary",
        ),
        pytest.param(
            lambda: {
                "diagnostic_id": "diag-1",
                "reason": "r",
                "captured_at": "2026-08-13T09:00:00+00:00",
                "phone_state": "app_did_not_prompt",
            },
            {"validation_rule": "browser_proven_state_requires_landing_source", "phone_state_source": ""},
            id="browser_proven_state_without_landing_source",
        ),
        pytest.param(
            lambda: {
                "diagnostic_id": "diag-1",
                "reason": "r",
                "captured_at": "2026-08-13T09:00:00+00:00",
                "phone_state": "app_did_not_prompt",
                "phone_state_source": "aeat_authenticated_landing",
            },
            {"validation_rule": "browser_proven_state_requires_observation_instant"},
            id="browser_proven_state_without_observation_instant",
        ),
    ],
)
def test_diagnostic_payload_refusals_author_no_sentence(
    build_payload: Callable[[], dict[str, object]],
    expected_context: dict[str, object],
) -> None:
    """Structural payload refusals use the registered key and rule facts."""
    from ....core.errors.error_codes import get_registered_error_code, resolve_error_message

    payload = _DiagnosticPayload.model_validate(build_payload())
    with pytest.raises(AuthDiagnosticPayloadError) as raised:
        _summary_from_payload(payload)

    error = raised.value
    assert error.translated_message == "errors.refused.refused_auth_diagnostic_payload"
    assert error.context == expected_context
    assert get_registered_error_code(error).code == "REFUSED_AUTH_DIAGNOSTIC_PAYLOAD"
    assert str(error) == error.translated_message
    resolved = resolve_error_message(error)
    assert resolved and resolved != error.translated_message


def test_record_phone_state_refusal_authors_no_sentence() -> None:
    """An unknown phone state carries the token as a fact, not authored prose."""
    from ....core.errors.error_codes import get_registered_error_code, resolve_error_message

    with pytest.raises(AuthDiagnosticPhoneStateError) as raised:
        record_auth_diagnostic_phone_state(
            "diag-1",
            "not_a_known_state",
            persistence=_UnusedDiagnosticPersistence(),
        )

    error = raised.value
    assert error.translated_message == "errors.refused.refused_auth_diagnostic_phone_state"
    assert error.context == {"phone_state": "not_a_known_state"}
    assert get_registered_error_code(error).code == "REFUSED_AUTH_DIAGNOSTIC_PHONE_STATE"
    assert str(error) == error.translated_message
    resolved = resolve_error_message(error)
    assert resolved and resolved != error.translated_message

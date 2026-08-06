"""Canonical application-result parity for auth CLI JSON payloads."""

from __future__ import annotations

import json

import pytest
from pydantic import BaseModel, ValidationError

from ....application.auth import (
    AuthLoginResult,
    AuthStatusResult,
    AuthTestResult,
    ProviderProbeResult,
)
from .._config_payloads import AuthLoginPayload, AuthStatusPayload, AuthTestPayload

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize(
    ("result", "payload_type"),
    (
        (
            AuthStatusResult(
                provider="certificate",
                configured=True,
                available=True,
                certificate_path="operator.p12",
                health_severity="ok",
            ),
            AuthStatusPayload,
        ),
        (
            AuthTestResult(
                provider="certificate",
                configured=True,
                available=True,
                persisted_session_present=True,
                persisted_session_expired=False,
                persisted_session_state="active",
                probe_result=ProviderProbeResult.OK,
            ),
            AuthTestPayload,
        ),
        (
            AuthLoginResult(
                provider="clave_movil",
                authenticated=True,
                reused_persisted_session=False,
                fresh=True,
                removed_sessions=1,
                acquired_lock=True,
                verification_status="verified",
            ),
            AuthLoginPayload,
        ),
    ),
)
def test_auth_payload_accepts_canonical_operator_result(
    result: BaseModel,
    payload_type: type[AuthStatusPayload | AuthTestPayload | AuthLoginPayload],
) -> None:
    """Each CLI shell accepts and preserves the real application's JSON projection."""
    payload = payload_type.model_validate_json(result.model_dump_json())

    assert payload.model_dump(mode="json") == result.model_dump(mode="json")


@pytest.mark.parametrize(
    ("result", "payload_type", "secret_field"),
    (
        (AuthStatusResult(provider="certificate"), AuthStatusPayload, "certificate_password"),
        (AuthTestResult(provider="certificate"), AuthTestPayload, "session_token"),
        (
            AuthLoginResult(
                provider="clave_movil",
                authenticated=True,
                reused_persisted_session=False,
                fresh=True,
                removed_sessions=0,
                acquired_lock=True,
            ),
            AuthLoginPayload,
            "qr_payload",
        ),
    ),
)
def test_auth_payload_refuses_undeclared_secret_shaped_field(
    result: BaseModel,
    payload_type: type[AuthStatusPayload | AuthTestPayload | AuthLoginPayload],
    secret_field: str,
) -> None:
    """Secret-shaped additions cannot cross a payload boundary undeclared."""
    payload = {**result.model_dump(mode="json"), secret_field: "must-not-leak"}

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        payload_type.model_validate_json(json.dumps(payload))

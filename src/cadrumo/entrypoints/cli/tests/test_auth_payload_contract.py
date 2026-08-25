"""Canonical application-result parity for auth CLI JSON payloads."""

from __future__ import annotations

import json

import pytest
from pydantic import BaseModel, ValidationError

from ....application.auth.operator_results import AuthLoginResult, AuthStatusResult, AuthTestResult
from ....application.auth.probes import ProviderProbeResult
from ....application.operator_actions import (
    ConditionEvidence,
    PreconditionVerdict,
)
from ....core import (
    ActionConditionality,
    ActionEvidenceProvenance,
    NoRecoveryOutcome,
)
from .._common import resolve_cli_precondition_action
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
    """Each CLI shell projects the real application's result without leaking its verdict model."""
    if isinstance(result, AuthTestResult):
        payload = AuthTestPayload.from_test_result(result, active_profile_precondition_action=None)
        expected = {
            **result.model_dump(mode="json", exclude={"active_profile_precondition_verdict"}),
            "active_profile_precondition_action": None,
        }
    elif isinstance(result, AuthStatusResult):
        payload = AuthStatusPayload.from_result(result, active_profile_precondition_action=None)
        expected = {
            **result.model_dump(mode="json", exclude={"active_profile_precondition_verdict"}),
            "active_profile_precondition_action": None,
        }
    else:
        payload = AuthLoginPayload.model_validate_json(result.model_dump_json())
        expected = result.model_dump(mode="json")

    assert payload.model_dump(mode="json") == expected


def test_auth_status_payload_projects_the_application_verdict_to_the_wire_action() -> None:
    """The status schema carries the canonical action DTO, not the application verdict model."""
    verdict = PreconditionVerdict(
        failed_condition_id="profile.active.required",
        evidence=(
            ConditionEvidence(
                condition_id="profile.active.required",
                evidence_id="profile.active.required.missing",
                provenance=ActionEvidenceProvenance.APPLICATION_STATE,
                values={"active_profile_present": False},
            ),
        ),
        conditionality=ActionConditionality.NOT_APPLICABLE,
        no_recovery_outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )
    action = resolve_cli_precondition_action(verdict)
    payload = AuthStatusPayload.from_result(
        AuthStatusResult(active_profile_precondition_verdict=verdict),
        active_profile_precondition_action=action,
    ).model_dump(mode="json")

    assert "active_profile_precondition_verdict" not in payload
    assert payload["active_profile_precondition_action"] == action.model_dump(mode="json")


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
    if isinstance(result, AuthTestResult):
        payload = AuthTestPayload.from_test_result(result, active_profile_precondition_action=None).model_dump(
            mode="json"
        )
    elif isinstance(result, AuthStatusResult):
        payload = AuthStatusPayload.from_result(result, active_profile_precondition_action=None).model_dump(mode="json")
    else:
        payload = AuthLoginPayload.model_validate_json(result.model_dump_json()).model_dump(mode="json")
    payload[secret_field] = "must-not-leak"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        payload_type.model_validate_json(json.dumps(payload))

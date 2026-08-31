"""Identity contract for the auth-configure result payload."""

from __future__ import annotations

import pytest

from ....application.auth.operator_results import AuthConfigureResult
from ....application.operator_actions.models import ConditionEvidence, PreconditionVerdict
from ....core.operator_action_enums import ActionConditionality, ActionEvidenceProvenance, NoRecoveryOutcome
from .._common import resolve_cli_precondition_action
from .._config_payloads import AuthConfigurePayload

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_auth_configure_result_does_not_duplicate_the_envelope_profile_identity() -> None:
    """The result carries readiness booleans, never an internal profile id."""
    verdict = PreconditionVerdict(
        failed_condition_id="auth.clave_movil.identity_aligned",
        evidence=(
            ConditionEvidence(
                condition_id="auth.clave_movil.identity_aligned",
                evidence_id="auth.configure.clave_movil.identity_alignment",
                provenance=ActionEvidenceProvenance.APPLICATION_STATE,
                values={
                    "identity_alignment": "clave_identity_missing",
                    "profile_tax_id_present": True,
                    "provider": "clave_movil",
                    "provider_identity_present": False,
                },
            ),
        ),
        conditionality=ActionConditionality.NOT_APPLICABLE,
        no_recovery_outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )
    result = AuthConfigureResult(
        provider="clave_movil",
        complete=False,
        profile_tax_id_present=True,
        provider_identity_present=False,
        identity_alignment="clave_identity_missing",
        precondition_verdict=verdict,
    )

    payload = AuthConfigurePayload.from_result(
        result,
        precondition_action=resolve_cli_precondition_action(verdict),
    ).model_dump(mode="json")

    assert payload["profile_tax_id_present"] is True
    assert "active_profile" not in payload
    assert "next_action" not in payload
    assert payload["precondition_action"] == {
        "failed_condition_id": "auth.clave_movil.identity_aligned",
        "evidence": [
            {
                "condition_id": "auth.clave_movil.identity_aligned",
                "evidence_id": "auth.configure.clave_movil.identity_alignment",
                "provenance": "application_state",
                "values": {
                    "identity_alignment": "clave_identity_missing",
                    "profile_tax_id_present": True,
                    "provider": "clave_movil",
                    "provider_identity_present": False,
                },
            },
        ],
        "action": None,
        "argument_bindings": [],
        "missing_argument_names": [],
        "conditionality": "not_applicable",
        "no_recovery_outcome": "operator_decision",
    }

"""Original Google human codes and ordered action facts survive closed disclosure."""

from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import ValidationError

from ....core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ...operator_actions.preconditions import no_action_precondition_verdict
from ...operator_actions.projection import PreconditionVerdictSnapshot
from ..google_configuration_operation_contracts import GoogleConfigurationOutcome
from ..google_configuration_operation_refusal import (
    GoogleConfigurationPresentationFacts,
    GoogleConfigurationRefusalProjection,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
_PROFILE = UUID("58585858-5858-4585-8585-585858585858")


def test_closed_tty_refusal_keeps_ordered_canonical_verdict_without_a_second_framework() -> None:
    verdict = no_action_precondition_verdict(
        condition_id="google.auth.interactive_terminal.available",
        facts={"interactive_terminal_available": False},
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )
    refusal = GoogleConfigurationRefusalProjection(
        profile_id=_PROFILE,
        provider_code="REFUSED_GOOGLE_NON_INTERACTIVE",
        message_key="adapters.google.oauth_flow.errors.non_interactive",
        facts=GoogleConfigurationPresentationFacts(profile=_PROFILE, reason="stdin_not_tty"),
        verdict=PreconditionVerdictSnapshot.from_verdict(verdict),
    )
    reopened = GoogleConfigurationRefusalProjection.model_validate_json(refusal.model_dump_json())
    assert reopened.verdict is not None and reopened.verdict.to_verdict() == verdict
    assert reopened.provider_code == "REFUSED_GOOGLE_NON_INTERACTIVE"
    assert reopened.message_key == "adapters.google.oauth_flow.errors.non_interactive"
    assert reopened.facts.presentation_context() == {"profile": str(_PROFILE), "reason": "stdin_not_tty"}


@pytest.mark.parametrize(
    "replacement",
    [
        {"provider_code": "UNDECLARED_GOOGLE_FAILURE"},
        {"message_key": "arbitrary.exception.message"},
        {"message_key": "cli.config.google.detail.no_metadata_for_refresh"},
        {"context": {"secret": "arbitrary-exception-context"}},
        {"facts": {"profile": _PROFILE, "unknown_secret": "unchecked"}},
    ],
)
def test_closed_google_refusal_rejects_unknown_codes_keys_context_and_cross_code_messages(
    replacement: dict[str, object],
) -> None:
    fields: dict[str, object] = {
        "profile_id": _PROFILE,
        "provider_code": "REFUSED_GOOGLE_CLIENT_METADATA_UNAVAILABLE",
        "message_key": "adapters.google.installation_client.errors.client_metadata_invalid",
        "facts": GoogleConfigurationPresentationFacts(profile=_PROFILE),
    }
    with pytest.raises(ValidationError):
        GoogleConfigurationRefusalProjection.model_validate({**fields, **replacement}, strict=True)


def test_outcome_rejects_refusal_details_for_another_profile() -> None:
    refusal = GoogleConfigurationRefusalProjection(
        profile_id=_PROFILE,
        provider_code="AUTH_GOOGLE_EXPIRED",
        message_key="cli.config.google.detail.no_metadata_for_refresh",
        facts=GoogleConfigurationPresentationFacts(profile=_PROFILE),
    )
    with pytest.raises(ValidationError):
        GoogleConfigurationOutcome(
            profile_id=UUID("59595959-5959-4595-8595-595959595959"), outcome="refused", refusal=refusal
        )

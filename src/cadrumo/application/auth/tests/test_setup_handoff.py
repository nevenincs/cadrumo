"""The agent gets saved-state guidance and an exact protected navigation target."""

from uuid import UUID

import pytest
from pydantic import ValidationError

from ..auth_read_contracts import AuthReadProjection, AuthReadRequest, AuthReadResult
from ..setup_handoff import auth_setup_handoff
from ..sync_readiness import AuthSyncReadiness, AuthSyncRequirement

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")


def test_setup_cannot_replace_the_saved_method_with_a_provider_override() -> None:
    with pytest.raises(ValidationError):
        AuthReadRequest(profile_id=_PROFILE, kind="setup", provider="clave_movil")
    request = AuthReadRequest(profile_id=_PROFILE, kind="setup")
    assert request.provider is None


def test_setup_explains_only_missing_requirements_and_preserves_readiness_roundtrip() -> None:
    readiness = AuthSyncReadiness(
        provider="clave_movil",
        route="app_request",
        requirements=(
            AuthSyncRequirement(field="identity.tax_id", satisfied=True, reason="profile_tax_id_required"),
            AuthSyncRequirement(field="auth.numero_soporte", satisfied=False, reason="nie_support_required"),
        ),
    )
    handoff = auth_setup_handoff(_PROFILE, readiness)
    assert handoff.url == f"cadrumo://profiles/{_PROFILE}/aeat-auth"
    assert len(handoff.missing) == 1
    assert handoff.missing[0].field == "auth.numero_soporte"
    assert handoff.missing[0].explanation not in {
        "",
        "nie_support_required",
        "auth.sync.requirement.nie_support_required",
    }
    assert {method.value for method in handoff.supported_methods} == {"clave_movil", "clave_permanente", "certificate"}
    projection = AuthReadProjection(profile_id=_PROFILE, kind="setup", sync_readiness=readiness, setup=handoff)
    result = projection.to_result()
    assert result.kind == "setup"
    assert result.sync_readiness == readiness
    assert AuthReadResult.model_validate_json(result.model_dump_json()) == result
    assert "password" not in handoff.model_dump_json()


def test_ready_setup_does_not_invent_missing_fields() -> None:
    readiness = AuthSyncReadiness(
        ready=True,
        requirements=(AuthSyncRequirement(field="auth.provider", satisfied=True, reason="auth_method_required"),),
    )
    assert auth_setup_handoff(_PROFILE, readiness).missing == ()

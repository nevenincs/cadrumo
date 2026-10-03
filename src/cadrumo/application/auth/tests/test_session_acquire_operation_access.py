"""Provider login admission and projection preserve profile and human authority."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import BaseModel

from cadrumo.application.auth.operation_definitions import (
    AUTH_SESSION_ACQUIRE_OPERATION_DEFINITION_ID,
    AuthOperationPorts,
    AuthSessionAcquireOperationRequest,
    build_auth_operation_definitions,
    build_auth_operation_registrations,
)
from cadrumo.application.auth.operator_results import AuthLoginResult
from cadrumo.application.auth.protocols import BrowserSessionPort
from cadrumo.application.auth.session_acquire_operation_access import (
    AUTH_SESSION_ACQUIRE_RESULT_SCHEMA_ID,
    AuthSessionAcquireOperationProjection,
    project_auth_session_acquire_result,
)
from cadrumo.application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from cadrumo.application.operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationRegistry
from cadrumo.application.user_profile.access_contracts import AccessAction, AccessDenialCode, Availability
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.config import Settings
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject

from ._operator_probe_fakes import fake_operator_probe_ports
from ._operator_scope_fakes import build_inward_operator_scope_ports
from .certificate_secret_fakes import InMemoryCertificateSecretBackendFactory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


async def _no_browser(settings: Settings) -> BrowserSessionPort:
    del settings
    raise AssertionError("admission must not open a browser")


def _registry() -> OperationRegistry:
    definitions = build_auth_operation_definitions(
        ports=AuthOperationPorts(
            certificate_secret_backend_factory=InMemoryCertificateSecretBackendFactory(),
            browser_session_factory=_no_browser,
            operator_probe_ports=fake_operator_probe_ports(),
            operator_scope_ports=build_inward_operator_scope_ports(session=None),
        )
    )
    return OperationRegistry(
        definitions=definitions, public_registrations=build_auth_operation_registrations(definitions)
    )


@pytest.mark.parametrize("action", [AccessAction.START, AccessAction.COMMIT, AccessAction.RESULT])
def test_login_registration_requires_human_authority_and_exact_profile(action: AccessAction) -> None:
    registry = _registry()
    profile_id = uuid4()
    contract = registry.lookup_public_contract(AUTH_SESSION_ACQUIRE_OPERATION_DEFINITION_ID)
    assert contract.result_schema is not None
    assert contract.result_schema.schema_id == AUTH_SESSION_ACQUIRE_RESULT_SCHEMA_ID
    request = OperationRequest[BaseModel](
        definition_id=AUTH_SESSION_ACQUIRE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        payload=AuthSessionAcquireOperationRequest(),
    )
    context = OperationAccessContext(
        profile_id=profile_id,
        destination_id=uuid4(),
        action=action,
        frontend=OperationFrontendProjection.CLI,
        contract=contract,
        published_authority=Availability.AVAILABLE,
    )
    resolved = resolve_operation_access(registry=registry, request=request, context=context)
    assert resolved.policy.requires_human
    assert resolved.request.profile_id == profile_id
    assert resolved.policy.provider is Availability.NOT_REQUIRED
    if action is AccessAction.RESULT:
        assert {item.projection_id for item in resolved.policy.disclosures} == {AUTH_SESSION_ACQUIRE_RESULT_SCHEMA_ID}

    for changed, reason in (
        (replace(context, profile_id=uuid4()), AccessDenialCode.PROFILE_MISMATCH),
        (replace(context, frontend=OperationFrontendProjection.MCP), AccessDenialCode.FRONTEND_DENIED),
    ):
        with pytest.raises(ProfileAccessRefusedError) as refused:
            resolve_operation_access(registry=registry, request=request, context=changed)
        assert refused.value.reason is reason


def _result() -> AuthLoginResult:
    return AuthLoginResult(
        provider="certificate",
        authenticated=True,
        reused_persisted_session=True,
        fresh=False,
        removed_sessions=0,
        acquired_lock=True,
        verification_status="verified",
    )


@pytest.mark.parametrize("effect", [OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN])
def test_login_projection_preserves_result_and_refuses_uncertain_effect(effect: OperationEffect) -> None:
    profile_id = uuid4()
    receipt = OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="a" * 64,
            definition_id=AUTH_SESSION_ACQUIRE_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(profile_id)),
        ),
        revision=1,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=effect,
        settled_at=datetime(2026, 9, 30, tzinfo=UTC),
        result_ref="b" * 64,
    )
    if effect is OperationEffect.UNKNOWN:
        with pytest.raises(ValueError, match="invalid provider login result"):
            project_auth_session_acquire_result(_result(), receipt)
        return
    result = project_auth_session_acquire_result(_result(), receipt)
    assert isinstance(result, AuthSessionAcquireOperationProjection)
    assert result.profile_id == profile_id
    assert result.result == _result()
    assert AuthSessionAcquireOperationProjection.model_validate_json(result.model_dump_json(), strict=True) == result

    class SecretResult(AuthLoginResult):
        credential: str

    secret_result = SecretResult(**_result().model_dump(), credential="synthetic-secret-sentinel")
    with pytest.raises(ValueError, match="invalid provider login result") as refused:
        project_auth_session_acquire_result(secret_result, receipt)
    assert "synthetic-secret-sentinel" not in str(refused.value)

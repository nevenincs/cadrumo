"""Provider configure is exact-profile work with one safe public result."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from cadrumo.application.auth.operation_definitions import (
    AUTH_CONFIGURE_OPERATION_DEFINITION_ID,
    AuthConfigureOperationExecutor,
    AuthConfigureOperationRequest,
    AuthOperationPorts,
    build_auth_operation_definitions,
    build_auth_operation_registrations,
)
from cadrumo.application.auth.operator_results import AuthConfigureResult
from cadrumo.application.auth.protocols import BrowserSessionPort
from cadrumo.application.auth.provider_configure_operation_access import (
    AUTH_CONFIGURE_RESULT_SCHEMA_ID,
    AuthConfigureOperationProjection,
    AuthConfigureResultSnapshot,
    project_auth_configure_result,
)
from cadrumo.application.auth.tests._operator_probe_fakes import fake_operator_probe_ports
from cadrumo.application.auth.tests._operator_scope_fakes import build_inward_operator_scope_ports
from cadrumo.application.auth.tests.certificate_secret_fakes import InMemoryCertificateSecretBackendFactory
from cadrumo.application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from cadrumo.application.operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from cadrumo.application.operations.owner import OperationExecutorContext
from cadrumo.application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationRegistry,
)
from cadrumo.application.operator_actions.models import ConditionEvidence, PreconditionVerdict
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
)
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.auth_provider import AuthProviderKind
from cadrumo.core.config import Settings
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from cadrumo.core.operator_action_enums import ActionConditionality, ActionEvidenceProvenance, NoRecoveryOutcome

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_SETTLED_AT = datetime(2026, 9, 29, 12, tzinfo=UTC)


async def _unopened_browser_session(settings: Settings) -> BrowserSessionPort:
    """The configure tests never open an auth browser session."""
    del settings
    raise AssertionError("configure tests never open an auth browser session")


def _ports() -> AuthOperationPorts:
    return AuthOperationPorts(
        certificate_secret_backend_factory=InMemoryCertificateSecretBackendFactory(),
        browser_session_factory=_unopened_browser_session,
        operator_probe_ports=fake_operator_probe_ports(),
        operator_scope_ports=build_inward_operator_scope_ports(session=None),
    )


def _registered_configure() -> tuple[OperationRegistry, OperationPublicDefinitionRegistrationV1]:
    definition = next(
        item
        for item in build_auth_operation_definitions(ports=_ports())
        if item.definition_id == AUTH_CONFIGURE_OPERATION_DEFINITION_ID
    )
    registration = build_auth_operation_registrations((definition,))[0]
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    return registry, registration


def _request(*, subject_profile_id: UUID = _PROFILE) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=AUTH_CONFIGURE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(subject_profile_id)),
        payload=AuthConfigureOperationRequest(provider=AuthProviderKind.CERTIFICATE, certificate_path=None),
    )


def _access_context(
    registration: OperationPublicDefinitionRegistrationV1,
    *,
    profile_id: UUID = _PROFILE,
    action: AccessAction = AccessAction.SUBMIT,
    frontend: OperationFrontendProjection = OperationFrontendProjection.CLI,
) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=profile_id,
        destination_id=uuid4(),
        action=action,
        frontend=frontend,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
    )


@pytest.mark.parametrize("action", [AccessAction.SUBMIT, AccessAction.COMMIT, AccessAction.RESULT])
def test_registered_configure_requires_exact_profile_and_releases_profile_result_for_humans(
    action: AccessAction,
) -> None:
    registry, registration = _registered_configure()

    resolved = resolve_operation_access(
        registry=registry,
        request=_request(),
        context=_access_context(registration, action=action),
    )

    assert registry.lookup(AUTH_CONFIGURE_OPERATION_DEFINITION_ID).permitted_frontends == frozenset(
        {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}
    )
    assert registration.contract.result_schema is not None
    assert registration.contract.result_schema.schema_id == AUTH_CONFIGURE_RESULT_SCHEMA_ID
    assert action in resolved.policy.actions
    assert resolved.policy.requires_human
    assert resolved.request.profile_id == _PROFILE
    assert resolved.request.action is action
    assert resolved.request.period_independent
    if action is AccessAction.RESULT:
        assert len(resolved.policy.disclosures) == 1
        disclosure = next(iter(resolved.policy.disclosures))
        assert disclosure.projection_id == AUTH_CONFIGURE_RESULT_SCHEMA_ID
        assert disclosure.category is DisclosureCategory.PROFILE_VALUES


def test_configure_access_refuses_a_different_profile_subject() -> None:
    registry, registration = _registered_configure()

    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_operation_access(
            registry=registry,
            request=_request(subject_profile_id=_OTHER_PROFILE),
            context=_access_context(registration, profile_id=_PROFILE),
        )

    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_configure_access_refuses_mcp_frontend() -> None:
    registry, registration = _registered_configure()

    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_operation_access(
            registry=registry,
            request=_request(),
            context=_access_context(registration, frontend=OperationFrontendProjection.MCP),
        )

    assert refused.value.reason is AccessDenialCode.FRONTEND_DENIED


def _receipt(
    *,
    profile_id: UUID = _PROFILE,
    definition_id: str = AUTH_CONFIGURE_OPERATION_DEFINITION_ID,
    subject_ref: str | None = None,
    condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED,
    effect: OperationEffect = OperationEffect.UPDATED,
) -> OperationTerminalReceipt:
    return OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="a" * 64,
            definition_id=definition_id,
            subject_ref=subject_ref or profile_operation_subject(str(profile_id)),
        ),
        revision=1,
        condition=condition,
        effect=effect,
        settled_at=_SETTLED_AT,
        result_ref="b" * 64 if condition is OperationTerminalCondition.SUCCEEDED else None,
        refusal_ref="refused" if condition is OperationTerminalCondition.REFUSED else None,
    )


def test_configure_result_projector_binds_exact_subject_effect_and_exposes_only_safe_result_fields() -> None:
    result = AuthConfigureResult(
        provider="certificate",
        file="C:/synthetic/aeat-certificate.p12",
        complete=True,
        profile_tax_id_present=False,
        provider_identity_present=False,
        identity_alignment="not_applicable",
    )

    projected = project_auth_configure_result(result, _receipt())

    assert projected.profile_id == _PROFILE
    assert projected.result.to_result() == result
    encoded = projected.model_dump_json().casefold()
    assert "password" not in encoded
    assert "cookie" not in encoded
    assert "token" not in encoded
    assert "private_key" not in encoded
    assert set(AuthConfigureOperationProjection.model_fields) == {"profile_id", "result"}
    assert set(AuthConfigureResultSnapshot.model_fields) == {
        "provider",
        "file",
        "complete",
        "incomplete_reason",
        "profile_tax_id_present",
        "provider_identity_present",
        "identity_alignment",
        "identity_alignment_detail",
        "precondition_verdict",
    }

    assert project_auth_configure_result(result, _receipt(profile_id=_OTHER_PROFILE)).profile_id == _OTHER_PROFILE

    mismatches = (
        _receipt(definition_id="auth.session.acquire"),
        _receipt(condition=OperationTerminalCondition.FAILED),
        _receipt(effect=OperationEffect.NONE),
        _receipt(subject_ref="not-a-profile-subject"),
    )
    for receipt in mismatches:
        with pytest.raises(ValueError, match="invalid provider configuration"):
            project_auth_configure_result(result, receipt)


class _SecretBearingConfigureResult(AuthConfigureResult):
    credential: str


def test_configure_result_projector_refuses_secret_bearing_subclasses() -> None:
    marker = "synthetic-certificate-secret"
    result = _SecretBearingConfigureResult(provider="certificate", credential=marker)

    with pytest.raises(ValueError, match="invalid provider configuration") as refused:
        project_auth_configure_result(result, _receipt())

    assert marker not in str(refused.value)


def test_configure_result_projection_preserves_precondition_evidence_through_wire_schema() -> None:
    verdict = PreconditionVerdict(
        failed_condition_id="auth.clave_movil.identity_aligned",
        evidence=(
            ConditionEvidence(
                condition_id="auth.clave_movil.identity_aligned",
                evidence_id="auth.configure.clave_movil.identity_alignment",
                provenance=ActionEvidenceProvenance.APPLICATION_STATE,
                values={"identity_alignment": "clave_identity_missing", "profile_tax_id_present": True},
            ),
        ),
        conditionality=ActionConditionality.NOT_APPLICABLE,
        no_recovery_outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )
    result = AuthConfigureResult(
        provider="clave_movil",
        complete=False,
        identity_alignment="clave_identity_missing",
        precondition_verdict=verdict,
    )

    projected = project_auth_configure_result(result, _receipt())
    restored = AuthConfigureOperationProjection.model_validate_json(projected.model_dump_json(), strict=True)

    assert restored.result.to_result() == result


@pytest.mark.asyncio
async def test_configure_executor_does_not_call_service_when_commit_guard_refuses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[object, dict[str, object]]] = []
    effects: list[OperationEffect] = []
    phases: list[str] = []
    guard_entries: list[bool] = []

    def configure(*args: object, **kwargs: object) -> AuthConfigureResult:
        calls.append((args, kwargs))
        raise AssertionError("configure service must not run without COMMIT")

    class Cancellation:
        @asynccontextmanager
        async def irreversible_section(self):
            guard_entries.append(True)
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            yield

    class Events:
        async def phase(self, phase: str) -> None:
            phases.append(phase)

        async def effect(self, effect: OperationEffect) -> None:
            effects.append(effect)

    class Operands:
        async def put(self, operand: BaseModel, *, written_at: object) -> str:
            raise AssertionError(f"refused configure wrote an operand: {operand!r} at {written_at!r}")

    ports = _ports()
    executor = AuthConfigureOperationExecutor(ports=ports, configure=configure)
    context = SimpleNamespace(
        identity=SimpleNamespace(
            definition_id=AUTH_CONFIGURE_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(_PROFILE)),
        ),
        authority_operation=object(),
        cancellation=Cancellation(),
        events=Events(),
        operands=Operands(),
    )
    request = OperationRequest[AuthConfigureOperationRequest](
        definition_id=AUTH_CONFIGURE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=AuthConfigureOperationRequest(provider=AuthProviderKind.CERTIFICATE, certificate_path=None),
    )
    monkeypatch.setattr(
        "cadrumo.application.auth.operation_definitions.require_active_bucket_id",
        lambda: str(_PROFILE),
    )

    with pytest.raises(ProfileAccessRefusedError) as refused:
        await executor.execute(request, cast(OperationExecutorContext, context))

    assert refused.value.reason is AccessDenialCode.OPERATION_DENIED
    assert guard_entries == [True]
    assert calls == []
    assert phases == ["auth.configure.preflight"]
    assert effects == []

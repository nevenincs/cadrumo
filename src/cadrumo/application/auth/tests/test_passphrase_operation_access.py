"""Registered rotation exposes only exact-profile human result authority."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from cadrumo.application.auth.operation_definitions import (
    PROFILE_ROTATION_OPERATION_DEFINITION_ID,
    AuthOperationPorts,
    ProfilePassphraseRotationOperationRequest,
    build_auth_operation_definitions,
    build_auth_operation_registrations,
)
from cadrumo.application.auth.passphrase_operation_access import (
    PROFILE_ROTATION_RESULT_SCHEMA_ID,
    ProfilePassphraseRotationResultProjection,
    project_profile_rotation_result,
)
from cadrumo.application.auth.protocols import BrowserSessionPort
from cadrumo.application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from cadrumo.application.operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from cadrumo.application.operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationRegistry
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessAllowed,
    AccessDenialCode,
    AccessDenied,
    AccessEvaluationContext,
    AccessScope,
    AccessSession,
    ApiKeyRecord,
    AuthorityState,
    AutomationGrant,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
    LoginEligibility,
    OsLoginContext,
    ProfileAccessBinding,
    ProfileAccessState,
    SessionKind,
    SessionState,
)
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.access_policy import evaluate_operation_access
from cadrumo.application.user_profile.passphrase_rotation import ProfilePassphraseRotationOutcome
from cadrumo.core.config import Settings
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject

from ._operator_probe_fakes import fake_operator_probe_ports
from ._operator_scope_fakes import build_inward_operator_scope_ports
from .certificate_secret_fakes import InMemoryCertificateSecretBackendFactory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


async def _unopened_browser_session(settings: Settings) -> BrowserSessionPort:
    del settings
    raise AssertionError("rotation access does not open an auth provider")


def _registry() -> OperationRegistry:
    definitions = build_auth_operation_definitions(
        ports=AuthOperationPorts(
            certificate_secret_backend_factory=InMemoryCertificateSecretBackendFactory(),
            browser_session_factory=_unopened_browser_session,
            operator_probe_ports=fake_operator_probe_ports(),
            operator_scope_ports=build_inward_operator_scope_ports(session=None),
        )
    )
    return OperationRegistry(
        definitions=tuple(sorted(definitions, key=lambda item: item.definition_id)),
        public_registrations=build_auth_operation_registrations(definitions),
    )


def _request(profile_id: UUID) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=PROFILE_ROTATION_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        payload=ProfilePassphraseRotationOperationRequest(profile_id=profile_id),
    )


def test_rotation_registration_exposes_one_typed_human_result_with_no_secret_schema() -> None:
    registry = _registry()
    contract = registry.lookup_public_contract(PROFILE_ROTATION_OPERATION_DEFINITION_ID)
    assert contract.permitted_frontends == frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI})
    assert contract.result_schema is not None
    assert contract.result_schema.schema_id == PROFILE_ROTATION_RESULT_SCHEMA_ID
    assert registry.lookup_public_registration(PROFILE_ROTATION_OPERATION_DEFINITION_ID).result_projector is not None
    bindings = registry.lookup_public_registration(PROFILE_ROTATION_OPERATION_DEFINITION_ID).schema_bindings
    assert any(
        item.identity == contract.result_schema and item.model_type is ProfilePassphraseRotationResultProjection
        for item in bindings
    )
    assert contract.interaction_response_schema is None
    assert contract.review_projection_schema is None
    assert contract.ephemeral_secret_required


def test_rotation_resolver_enforces_exact_subject_frontend_actions_and_destination() -> None:
    registry = _registry()
    profile_id, destination_id = uuid4(), uuid4()
    request = _request(profile_id)
    contract = registry.lookup_public_contract(PROFILE_ROTATION_OPERATION_DEFINITION_ID)
    allowed = {
        AccessAction.SUBMIT,
        AccessAction.START,
        AccessAction.COMMIT,
        AccessAction.OBSERVE,
        AccessAction.RESULT,
    }
    for frontend in (OperationFrontendProjection.CLI, OperationFrontendProjection.TUI):
        for action in allowed:
            context = OperationAccessContext(
                profile_id=profile_id,
                destination_id=destination_id,
                action=action,
                frontend=frontend,
                contract=contract,
                published_authority=Availability.AVAILABLE,
            )
            resolved = resolve_operation_access(registry=registry, request=request, context=context)
            assert resolved.policy.requires_human
            assert resolved.policy.actions == allowed
            assert resolved.request.profile_id == profile_id
            assert resolved.request.period_independent and not resolved.request.periods
            assert resolved.policy.periods == frozenset()
            disclosures = resolved.policy.disclosures
            if action is AccessAction.RESULT:
                assert disclosures == frozenset(
                    {
                        DisclosurePermission(
                            destination_id=destination_id,
                            projection_id=PROFILE_ROTATION_RESULT_SCHEMA_ID,
                            category=DisclosureCategory.PROFILE_VALUES,
                        )
                    }
                )
            elif action is AccessAction.OBSERVE:
                assert disclosures == frozenset(
                    {
                        DisclosurePermission(
                            destination_id=destination_id,
                            projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                            category=DisclosureCategory.OPERATION_METADATA,
                        )
                    }
                )
            else:
                assert not disclosures
    base = OperationAccessContext(
        profile_id=profile_id,
        destination_id=destination_id,
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.CLI,
        contract=contract,
        published_authority=Availability.AVAILABLE,
    )
    for changed_context, expected in (
        (replace(base, profile_id=uuid4()), AccessDenialCode.PROFILE_MISMATCH),
        (replace(base, frontend=OperationFrontendProjection.MCP), AccessDenialCode.FRONTEND_DENIED),
        (replace(base, action=AccessAction.DETACH), AccessDenialCode.OPERATION_DENIED),
    ):
        with pytest.raises(ProfileAccessRefusedError) as refused:
            resolve_operation_access(registry=registry, request=request, context=changed_context)
        assert refused.value.reason is expected
    with pytest.raises(ProfileAccessRefusedError) as wrong_subject:
        resolve_operation_access(
            registry=registry,
            request=request.model_copy(update={"subject_ref": "profile:" + str(uuid4())}),
            context=base,
        )
    assert wrong_subject.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_live_api_key_still_cannot_use_rotation_human_scope() -> None:
    registry = _registry()
    profile_id, destination_id, boot, connection_id = uuid4(), uuid4(), uuid4(), uuid4()
    request = _request(profile_id)
    contract = registry.lookup_public_contract(PROFILE_ROTATION_OPERATION_DEFINITION_ID)
    resolved = resolve_operation_access(
        registry=registry,
        request=request,
        context=OperationAccessContext(
            profile_id=profile_id,
            destination_id=destination_id,
            action=AccessAction.SUBMIT,
            frontend=OperationFrontendProjection.CLI,
            contract=contract,
            published_authority=Availability.AVAILABLE,
        ),
    )
    instant = datetime(2026, 9, 27, 12, tzinfo=UTC)
    binding = ProfileAccessBinding(
        profile_id=profile_id,
        installation_id=uuid4(),
        os_owner_id="synthetic-owner",
        custody_generation=1,
        dek_epoch=uuid4(),
    )
    scope = AccessScope(
        operations=frozenset({PROFILE_ROTATION_OPERATION_DEFINITION_ID}),
        actions=frozenset(AccessAction),
        disclosures=frozenset(),
        periods=None,
        allow_period_independent=True,
        allow_delegation=False,
    )
    profile = ProfileAccessState(
        binding=binding,
        lock_generation=0,
        globally_locked=False,
        automation_enabled=True,
        scope=scope,
        storage=Availability.AVAILABLE,
        automation_custody=Availability.AVAILABLE,
    )
    grant = AutomationGrant(
        grant_id=uuid4(),
        binding=binding,
        client_id=destination_id,
        generation=1,
        profile_lock_generation=0,
        state=AuthorityState.ACTIVE,
        scope=scope,
        valid_from=instant - timedelta(days=1),
        expires_at=instant + timedelta(days=1),
        unattended=True,
        allow_os_lock=True,
    )
    key = ApiKeyRecord(
        key_id=uuid4(),
        grant_id=grant.grant_id,
        binding=binding,
        generation=1,
        state=AuthorityState.ACTIVE,
        valid_from=grant.valid_from,
        expires_at=grant.expires_at,
    )
    session = AccessSession(
        session_id=uuid4(),
        binding=binding,
        profile_lock_generation=0,
        runtime_boot_id=boot,
        connection_id=connection_id,
        client_id=destination_id,
        kind=SessionKind.API_KEY,
        state=SessionState.ACTIVE,
        scope=scope,
        grant_id=grant.grant_id,
        grant_generation=1,
        key_id=key.key_id,
        key_generation=1,
        issued_at=instant,
        expires_at=instant + timedelta(minutes=5),
        issued_monotonic=100.0,
    )
    observation = AccessEvaluationContext(
        now=instant,
        monotonic_now=100.0,
        clock_rollback_detected=False,
        runtime_boot_id=boot,
        connection_id=connection_id,
        authenticated_client_id=destination_id,
        login_contexts=(
            OsLoginContext(
                login_id="login-a",
                os_owner_id=binding.os_owner_id,
                active=True,
                locked=False,
                unattended=LoginEligibility.ELIGIBLE,
                credential_facilities=Availability.AVAILABLE,
            ),
        ),
        private_work_available=True,
    )
    assert evaluate_operation_access(
        request=resolved.request,
        policy=resolved.policy,
        registry=registry,
        session=session,
        ancestors=(),
        grant=grant,
        key=key,
        profile=profile,
        context=observation,
    ) == AccessDenied(code=AccessDenialCode.HUMAN_AUTHORITY_REQUIRED)
    human = AccessSession(
        session_id=uuid4(),
        binding=binding,
        profile_lock_generation=0,
        runtime_boot_id=boot,
        connection_id=connection_id,
        client_id=destination_id,
        kind=SessionKind.HUMAN,
        originating_login_id="login-a",
        state=SessionState.ACTIVE,
        scope=scope,
        issued_at=instant,
        expires_at=instant + timedelta(minutes=5),
        issued_monotonic=100.0,
    )
    assert isinstance(
        evaluate_operation_access(
            request=resolved.request,
            policy=resolved.policy,
            registry=registry,
            session=human,
            ancestors=(),
            grant=None,
            key=None,
            profile=profile,
            context=observation,
        ),
        AccessAllowed,
    )


def test_rotation_projector_checks_terminal_identity_and_validated_outcome() -> None:
    profile_id = uuid4()
    outcome = ProfilePassphraseRotationOutcome(
        profile_id=str(profile_id),
        password_generation=2,
        dek_epoch_preserved=True,
        recovery_enrollment_retained=False,
    )
    receipt = OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="a" * 64,
            definition_id=PROFILE_ROTATION_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(profile_id)),
        ),
        revision=3,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.UPDATED,
        settled_at=datetime(2026, 9, 27, 12, tzinfo=UTC),
        result_ref="b" * 64,
    )
    projected = project_profile_rotation_result(outcome, receipt)
    assert projected == ProfilePassphraseRotationResultProjection(outcome=outcome)
    for wrong in (
        receipt.model_copy(
            update={"identity": receipt.identity.model_copy(update={"subject_ref": "profile:" + str(uuid4())})}
        ),
        receipt.model_copy(
            update={"identity": receipt.identity.model_copy(update={"definition_id": "auth.profile.login"})}
        ),
        receipt.model_copy(update={"condition": OperationTerminalCondition.FAILED}),
        receipt.model_copy(update={"effect": OperationEffect.NONE}),
    ):
        with pytest.raises(ValueError, match="invalid passphrase rotation result"):
            project_profile_rotation_result(outcome, wrong)
    malformed = ProfilePassphraseRotationOutcome.model_construct(
        profile_id=str(profile_id),
        password_generation=True,
        dek_epoch_preserved="private-untrusted-value",
        recovery_enrollment_retained=False,
    )
    with pytest.raises(ValueError, match="invalid passphrase rotation result") as caught:
        project_profile_rotation_result(malformed, receipt)
    assert "private-untrusted-value" not in str(caught.value)
    assert caught.value.__context__ is None

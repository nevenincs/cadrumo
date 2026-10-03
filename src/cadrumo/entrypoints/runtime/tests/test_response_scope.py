"""Current profile permission for a REVIEW response is distinct from its bearer."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import BaseModel

from cadrumo.adapters.outbound.aeat.browser.factory import default_browser_session_factory
from cadrumo.adapters.outbound.aeat.sede.censal_datos import fetch_censal_datos
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.application.auth.tests.certificate_secret_fakes import InMemoryCertificateSecretBackendFactory
from cadrumo.application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationRegistry
from cadrumo.application.user_profile.access_contracts import (
    ACCESS_LEASE_MAXIMUM,
    AccessAction,
    AccessDenialCode,
    AccessDenied,
    AccessEvaluationContext,
    AccessScope,
    AccessSession,
    ApiKeyRecord,
    AuthorityState,
    AutomationGrant,
    Availability,
    LoginEligibility,
    OperationAccessPolicy,
    OperationAccessRequest,
    OperationResponseScopeAllowed,
    OsLoginContext,
    ProfileAccessBinding,
    ProfileAccessState,
    SessionKind,
    SessionState,
)
from cadrumo.application.user_profile.censal_operation import (
    CENSAL_OPERATION_DEFINITION_ID,
    CensalFieldIntent,
    CensalOperationRequest,
    CensalProfileBaseline,
    CensalReviewedFieldIntent,
    build_censal_operation_definition,
    build_censal_operation_registration,
)
from cadrumo.application.user_profile.censo_sync import CENSAL_ADOPTABLE_PATHS
from cadrumo.application.user_profile.operation_access_policy import evaluate_operation_access, evaluate_response_scope
from cadrumo.application.user_profile.operations import (
    USER_PROFILE_OPERATION_DEFINITIONS,
    build_user_profile_operation_registrations,
)
from cadrumo.application.user_profile.profile_operation_contracts import PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_NOW = datetime(2026, 9, 26, 12, tzinfo=UTC)


def _changed[T: BaseModel](model: T, **updates: object) -> T:
    return model.__class__.model_validate(
        {**{name: getattr(model, name) for name in model.__class__.model_fields}, **updates}
    )


@dataclass(frozen=True)
class ResponseCase:
    registry: OperationRegistry
    request: OperationAccessRequest
    policy: OperationAccessPolicy
    profile: ProfileAccessState
    session: AccessSession
    grant: AutomationGrant
    key: ApiKeyRecord
    context: AccessEvaluationContext

    def evaluate(self) -> OperationResponseScopeAllowed | AccessDenied:
        return evaluate_response_scope(
            request=self.request,
            policy=self.policy,
            registry=self.registry,
            session=self.session,
            ancestors=(),
            grant=self.grant,
            key=self.key,
            profile=self.profile,
            context=self.context,
        )


@pytest.fixture
def response_case() -> ResponseCase:
    censal = build_censal_operation_definition(
        certificate_secret_backend_factory=InMemoryCertificateSecretBackendFactory(),
        browser_session_factory=default_browser_session_factory,
        operator_scope_ports=build_operator_scope_ports(),
        censal_fetch_port=fetch_censal_datos,
        provider_preflight=lambda _profile_id, _operation: None,
    )
    definitions = tuple(sorted((*USER_PROFILE_OPERATION_DEFINITIONS, censal), key=lambda item: item.definition_id))
    registrations = (
        *build_user_profile_operation_registrations(USER_PROFILE_OPERATION_DEFINITIONS),
        build_censal_operation_registration(censal),
    )
    registry = OperationRegistry(
        definitions=definitions,
        public_registrations=tuple(sorted(registrations, key=lambda item: item.contract.definition_id)),
    )
    binding = ProfileAccessBinding(
        profile_id=uuid4(),
        installation_id=uuid4(),
        os_owner_id="response-owner",
        custody_generation=1,
        dek_epoch=uuid4(),
    )
    client_id = uuid4()
    typed_request = OperationRequest[BaseModel](
        definition_id=CENSAL_OPERATION_DEFINITION_ID,
        subject_ref=str(binding.profile_id),
        payload=CensalOperationRequest(
            baseline=CensalProfileBaseline(
                profile_id=str(binding.profile_id), record_revision=3, content_digest="a" * 64
            ),
            field_intents=tuple(
                CensalReviewedFieldIntent(path=path, intent=CensalFieldIntent.PRESERVE)
                for path in CENSAL_ADOPTABLE_PATHS
            ),
        ),
    )
    resolution = resolve_operation_access(
        registry=registry,
        request=typed_request,
        context=OperationAccessContext(
            profile_id=binding.profile_id,
            destination_id=client_id,
            action=AccessAction.RESPOND,
            frontend=OperationFrontendProjection.MCP,
            contract=registry.lookup_public_contract(CENSAL_OPERATION_DEFINITION_ID),
            published_authority=Availability.AVAILABLE,
        ),
    )
    scope = AccessScope(
        operations=frozenset(item.definition_id for item in definitions),
        actions=frozenset(AccessAction),
        disclosures=resolution.policy.disclosures,
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
        client_id=client_id,
        generation=1,
        profile_lock_generation=0,
        state=AuthorityState.ACTIVE,
        scope=scope,
        valid_from=_NOW - timedelta(hours=1),
        expires_at=_NOW + timedelta(days=1),
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
        runtime_boot_id=uuid4(),
        connection_id=uuid4(),
        client_id=client_id,
        kind=SessionKind.API_KEY,
        state=SessionState.ACTIVE,
        scope=scope,
        grant_id=grant.grant_id,
        grant_generation=1,
        key_id=key.key_id,
        key_generation=1,
        issued_at=_NOW,
        expires_at=_NOW + ACCESS_LEASE_MAXIMUM,
        issued_monotonic=100.0,
    )
    context = AccessEvaluationContext(
        now=_NOW,
        monotonic_now=100.0,
        clock_rollback_detected=False,
        runtime_boot_id=session.runtime_boot_id,
        connection_id=session.connection_id,
        authenticated_client_id=client_id,
        login_contexts=(
            OsLoginContext(
                login_id="response-login",
                os_owner_id=binding.os_owner_id,
                active=True,
                locked=False,
                unattended=LoginEligibility.ELIGIBLE,
                credential_facilities=Availability.AVAILABLE,
            ),
        ),
        private_work_available=True,
    )
    return ResponseCase(registry, resolution.request, resolution.policy, profile, session, grant, key, context)


def test_response_scope_is_current_permission_and_never_a_transaction_capability(response_case: ResponseCase) -> None:
    allowed = response_case.evaluate()
    assert isinstance(allowed, OperationResponseScopeAllowed)
    assert (allowed.profile_id, allowed.session_id, allowed.expires_at) == (
        response_case.profile.binding.profile_id,
        response_case.session.session_id,
        response_case.session.expires_at,
    )
    ordinary = evaluate_operation_access(
        request=response_case.request,
        policy=response_case.policy,
        registry=response_case.registry,
        session=response_case.session,
        ancestors=(),
        grant=response_case.grant,
        key=response_case.key,
        profile=response_case.profile,
        context=response_case.context,
    )
    assert ordinary == AccessDenied(code=AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED)


@pytest.mark.parametrize(
    "change,expected",
    [
        ("revoked_grant", AccessDenialCode.GRANT_INACTIVE),
        ("expired_grant", AccessDenialCode.GRANT_EXPIRED),
        ("expired_session", AccessDenialCode.SESSION_EXPIRED),
        ("foreign_profile", AccessDenialCode.PROFILE_MISMATCH),
        ("revoked_key", AccessDenialCode.KEY_INACTIVE),
        ("no_disclosure", AccessDenialCode.DISCLOSURE_DENIED),
        ("provider_unavailable", AccessDenialCode.PROVIDER_REQUIRED),
        ("transaction_authority", AccessDenialCode.TRANSACTION_AUTHORITY_REQUIRED),
    ],
)
def test_response_scope_refuses_stale_or_missing_current_authority(
    response_case: ResponseCase, change: str, expected: AccessDenialCode
) -> None:
    case = response_case
    if change == "revoked_grant":
        case = replace(case, grant=_changed(case.grant, state=AuthorityState.REVOKED))
    elif change == "expired_grant":
        case = replace(case, grant=_changed(case.grant, expires_at=_NOW))
    elif change == "expired_session":
        case = replace(case, context=_changed(case.context, now=case.session.expires_at))
    elif change == "foreign_profile":
        case = replace(case, request=_changed(case.request, profile_id=uuid4()))
    elif change == "revoked_key":
        case = replace(case, key=_changed(case.key, state=AuthorityState.REVOKED))
    elif change == "no_disclosure":
        narrowed = _changed(case.profile.scope, disclosures=frozenset())
        case = replace(case, profile=_changed(case.profile, scope=narrowed))
    elif change == "provider_unavailable":
        case = replace(case, policy=_changed(case.policy, provider=Availability.NEEDS_USER))
    else:
        case = replace(case, policy=_changed(case.policy, transaction_authority_required=True))
    assert case.evaluate() == AccessDenied(code=expected)


def test_only_registered_review_response_can_receive_response_scope(response_case: ResponseCase) -> None:
    non_response = replace(response_case, request=_changed(response_case.request, action=AccessAction.REVIEW))
    assert non_response.evaluate() == AccessDenied(code=AccessDenialCode.OPERATION_DENIED)

    ordinary_definition = PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID
    contract = response_case.registry.lookup_public_contract(ordinary_definition)
    assert contract.review_projection_schema is None and contract.interaction_response_schema is None
    ordinary = replace(
        response_case,
        request=_changed(response_case.request, definition_id=ordinary_definition),
        policy=_changed(
            response_case.policy,
            definition_id=ordinary_definition,
            definition_contract_digest=contract.definition_contract_digest,
            disclosures=frozenset(),
        ),
    )
    assert ordinary.evaluate() == AccessDenied(code=AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED)

"""Authorization invariants against real registered profile operations."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

from cadrumo.application.operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from cadrumo.application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationRegistry,
    OperationSchemaBindingV1,
)
from cadrumo.application.user_profile.access_administration import (
    AccessAdministrationAction,
    AccessAdministrationRequest,
    AdministrationAllowed,
    AdministrationRequirement,
    FreshPasswordAuthorization,
    administration_requirement,
    evaluate_access_administration,
)
from cadrumo.application.user_profile.access_contracts import (
    ACCESS_LEASE_MAXIMUM,
    AccessAction,
    AccessAllowed,
    AccessDecision,
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
    OperationAccessPolicy,
    OperationAccessRequest,
    OsLoginContext,
    ProfileAccessBinding,
    ProfileAccessState,
    SessionKind,
    SessionState,
)
from cadrumo.application.user_profile.access_policy import (
    evaluate_operation_access,
    intersect_scopes,
    scope_is_subset,
)
from cadrumo.application.user_profile.access_projections import (
    project_access_session,
    project_access_status,
    project_api_key,
    project_automation_grant,
)
from cadrumo.application.user_profile.operations import (
    PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID,
    build_user_profile_operation_definitions,
    build_user_profile_operation_registrations,
)
from cadrumo.core.period import Period

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
NOW = datetime(2026, 9, 26, 12, tzinfo=UTC)
PERIOD = Period.from_year_and_code(2026, "3T")
OTHER_PERIOD = Period.from_year_and_code(2025, "3T")


def changed[T: BaseModel](model: T, **updates: object) -> T:
    """Revalidate modified facts instead of bypassing validation with model_copy."""
    model_type = model.__class__
    return model_type.model_validate({**{name: getattr(model, name) for name in model_type.model_fields}, **updates})


@dataclass(frozen=True)
class Scenario:
    registry: OperationRegistry
    profile: ProfileAccessState
    grant: AutomationGrant
    key: ApiKeyRecord
    session: AccessSession
    context: AccessEvaluationContext
    request: OperationAccessRequest
    policy: OperationAccessPolicy
    ancestors: tuple[AccessSession, ...] = ()

    def evaluate(self) -> AccessDecision:
        return evaluate_operation_access(
            registry=self.registry,
            profile=self.profile,
            grant=self.grant,
            key=self.key,
            session=self.session,
            context=self.context,
            request=self.request,
            policy=self.policy,
            ancestors=self.ancestors,
        )


@pytest.fixture
def scenario() -> Scenario:
    definitions = build_user_profile_operation_definitions()
    registry = OperationRegistry(
        definitions=definitions,
        public_registrations=build_user_profile_operation_registrations(definitions),
    )
    binding = ProfileAccessBinding(
        profile_id=uuid4(),
        installation_id=uuid4(),
        os_owner_id="synthetic-owner",
        custody_generation=1,
        dek_epoch=uuid4(),
    )
    scope = AccessScope(
        operations=frozenset(item.definition_id for item in definitions),
        actions=frozenset(AccessAction),
        disclosures=frozenset(),
        periods=None,
        allow_period_independent=True,
        allow_delegation=True,
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
        client_id=uuid4(),
        generation=1,
        profile_lock_generation=0,
        state=AuthorityState.ACTIVE,
        scope=scope,
        valid_from=NOW - timedelta(days=1),
        expires_at=NOW + timedelta(days=364),
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
        client_id=grant.client_id,
        kind=SessionKind.API_KEY,
        state=SessionState.ACTIVE,
        scope=scope,
        grant_id=grant.grant_id,
        grant_generation=1,
        key_id=key.key_id,
        key_generation=1,
        issued_at=NOW,
        expires_at=NOW + ACCESS_LEASE_MAXIMUM,
        issued_monotonic=100.0,
    )
    context = AccessEvaluationContext(
        now=NOW,
        monotonic_now=100.0,
        clock_rollback_detected=False,
        runtime_boot_id=session.runtime_boot_id,
        connection_id=session.connection_id,
        authenticated_client_id=grant.client_id,
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
    request = OperationAccessRequest(
        profile_id=binding.profile_id,
        definition_id=PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID,
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.MCP,
        periods=frozenset({PERIOD}),
        period_independent=False,
        destination_id=uuid4(),
    )
    policy = OperationAccessPolicy(
        definition_id=request.definition_id,
        definition_contract_digest=registry.lookup_public_contract(request.definition_id).definition_contract_digest,
        actions=frozenset(AccessAction),
        disclosures=frozenset(),
        periods=None,
        allow_period_independent=True,
        backend=Availability.AVAILABLE,
        published_authority=Availability.AVAILABLE,
        provider=Availability.NOT_REQUIRED,
        transaction_authority_required=False,
    )
    return Scenario(registry, profile, grant, key, session, context, request, policy)


def assert_denied(scenario: Scenario, code: AccessDenialCode) -> None:
    assert scenario.evaluate() == AccessDenied(code=code)


def test_exact_profile_and_connection_are_required(scenario: Scenario) -> None:
    assert isinstance(scenario.evaluate(), AccessAllowed)
    assert_denied(
        replace(scenario, request=changed(scenario.request, profile_id=uuid4())), AccessDenialCode.PROFILE_MISMATCH
    )
    assert_denied(
        replace(scenario, context=changed(scenario.context, connection_id=uuid4())),
        AccessDenialCode.CONNECTION_MISMATCH,
    )
    assert_denied(
        replace(scenario, context=changed(scenario.context, authenticated_client_id=uuid4())),
        AccessDenialCode.CLIENT_MISMATCH,
    )
    assert_denied(
        replace(scenario, context=changed(scenario.context, runtime_boot_id=uuid4())), AccessDenialCode.RUNTIME_CHANGED
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("installation_id", UUID(int=4)),
        ("os_owner_id", "other-owner"),
        ("custody_generation", 2),
        ("dek_epoch", UUID(int=5)),
    ],
)
def test_custody_binding_changes_refuse(scenario: Scenario, field: str, value: object) -> None:
    profile = changed(scenario.profile, binding=changed(scenario.profile.binding, **{field: value}))
    assert_denied(replace(scenario, profile=profile), AccessDenialCode.CUSTODY_CHANGED)


@pytest.mark.parametrize("state", [AuthorityState.PENDING, AuthorityState.SUSPENDED, AuthorityState.REVOKED])
def test_inactive_grants_and_keys_refuse(scenario: Scenario, state: AuthorityState) -> None:
    assert_denied(replace(scenario, grant=changed(scenario.grant, state=state)), AccessDenialCode.GRANT_INACTIVE)
    assert_denied(replace(scenario, key=changed(scenario.key, state=state)), AccessDenialCode.KEY_INACTIVE)


def test_expiry_utc_monotonic_and_rollback(scenario: Scenario) -> None:
    assert_denied(
        replace(scenario, context=changed(scenario.context, now=scenario.session.expires_at)),
        AccessDenialCode.SESSION_EXPIRED,
    )
    assert_denied(
        replace(scenario, context=changed(scenario.context, monotonic_now=400.0)), AccessDenialCode.SESSION_EXPIRED
    )
    for updates in ({"clock_rollback_detected": True}, {"monotonic_now": 99.0}, {"now": NOW - timedelta(seconds=1)}):
        assert_denied(replace(scenario, context=changed(scenario.context, **updates)), AccessDenialCode.CLOCK_INVALID)
    assert_denied(replace(scenario, grant=changed(scenario.grant, expires_at=NOW)), AccessDenialCode.GRANT_EXPIRED)
    assert_denied(replace(scenario, key=changed(scenario.key, expires_at=NOW)), AccessDenialCode.KEY_EXPIRED)
    assert_denied(
        replace(scenario, grant=changed(scenario.grant, valid_from=NOW + timedelta(seconds=1))),
        AccessDenialCode.GRANT_EXPIRED,
    )


def test_session_lock_does_not_revoke_root_but_global_lock_fences_all(scenario: Scenario) -> None:
    assert_denied(
        replace(scenario, session=changed(scenario.session, state=SessionState.LOCKED)),
        AccessDenialCode.SESSION_INACTIVE,
    )
    fresh = changed(scenario.session, session_id=uuid4(), connection_id=uuid4())
    reconnect = replace(scenario, session=fresh, context=changed(scenario.context, connection_id=fresh.connection_id))
    assert isinstance(reconnect.evaluate(), AccessAllowed)
    assert_denied(
        replace(reconnect, profile=changed(scenario.profile, globally_locked=True)), AccessDenialCode.PROFILE_LOCKED
    )
    assert_denied(
        replace(reconnect, profile=changed(scenario.profile, lock_generation=1)), AccessDenialCode.PROFILE_LOCKED
    )
    assert_denied(
        replace(reconnect, profile=changed(scenario.profile, automation_enabled=False)),
        AccessDenialCode.AUTOMATION_SUSPENDED,
    )


def test_all_scope_dimensions_intersect(scenario: Scenario) -> None:
    for field in ("operations", "actions"):
        narrow = changed(scenario.profile.scope, **{field: frozenset()})
        assert_denied(
            replace(scenario, profile=changed(scenario.profile, scope=narrow)), AccessDenialCode.OPERATION_DENIED
        )
        assert_denied(
            replace(scenario, session=changed(scenario.session, scope=narrow)), AccessDenialCode.OPERATION_DENIED
        )
        # A stale session cannot claim more than its now-narrowed root grant.
        assert_denied(
            replace(scenario, grant=changed(scenario.grant, scope=narrow)), AccessDenialCode.PRIVILEGE_EXPANSION
        )
    assert_denied(
        replace(scenario, policy=changed(scenario.policy, actions=frozenset())), AccessDenialCode.OPERATION_DENIED
    )
    restricted = changed(scenario.profile.scope, periods=frozenset({PERIOD}), allow_period_independent=False)
    subject = replace(scenario, profile=changed(scenario.profile, scope=restricted))
    assert isinstance(subject.evaluate(), AccessAllowed)
    assert_denied(
        replace(subject, request=changed(scenario.request, periods=frozenset({PERIOD, OTHER_PERIOD}))),
        AccessDenialCode.PERIOD_DENIED,
    )
    assert_denied(
        replace(subject, request=changed(scenario.request, periods=frozenset(), period_independent=True)),
        AccessDenialCode.PERIOD_DENIED,
    )
    assert not scope_is_subset(scenario.session.scope, restricted)
    assert intersect_scopes(()).operations == frozenset()


@pytest.mark.parametrize("periods", [frozenset({PERIOD}), frozenset()])
def test_all_periods_policy_refuses_finite_and_empty_scopes_for_independent_request(
    scenario: Scenario, periods: frozenset[Period]
) -> None:
    scope = changed(scenario.profile.scope, periods=periods, allow_period_independent=True)
    subject = replace(
        scenario,
        profile=changed(scenario.profile, scope=scope),
        grant=changed(scenario.grant, scope=scope),
        session=changed(scenario.session, scope=scope),
        request=changed(scenario.request, periods=frozenset(), period_independent=True),
        policy=changed(scenario.policy, allow_period_independent=True, requires_all_periods=True),
    )

    assert_denied(subject, AccessDenialCode.PERIOD_DENIED)


def test_all_periods_policy_accepts_unrestricted_scope(scenario: Scenario) -> None:
    subject = replace(
        scenario,
        request=changed(scenario.request, periods=frozenset(), period_independent=True),
        policy=changed(scenario.policy, allow_period_independent=True, requires_all_periods=True),
    )

    assert isinstance(subject.evaluate(), AccessAllowed)


def test_all_periods_policy_checks_narrower_current_child_scope(scenario: Scenario) -> None:
    parent = scenario.session
    child = changed(
        parent,
        session_id=uuid4(),
        connection_id=uuid4(),
        parent_session_id=parent.session_id,
        scope=changed(parent.scope, periods=frozenset({PERIOD}), allow_period_independent=True),
        expires_at=NOW + timedelta(minutes=2),
    )
    subject = replace(
        scenario,
        session=child,
        ancestors=(parent,),
        context=changed(scenario.context, connection_id=child.connection_id),
        request=changed(scenario.request, periods=frozenset(), period_independent=True),
        policy=changed(scenario.policy, allow_period_independent=True, requires_all_periods=True),
    )

    assert_denied(subject, AccessDenialCode.PERIOD_DENIED)


def test_ordinary_independent_operation_keeps_finite_scope_behavior(scenario: Scenario) -> None:
    scope = changed(scenario.profile.scope, periods=frozenset({PERIOD}), allow_period_independent=True)
    subject = replace(
        scenario,
        profile=changed(scenario.profile, scope=scope),
        grant=changed(scenario.grant, scope=scope),
        session=changed(scenario.session, scope=scope),
        request=changed(scenario.request, periods=frozenset(), period_independent=True),
        policy=changed(scenario.policy, allow_period_independent=True, requires_all_periods=False),
    )

    assert isinstance(subject.evaluate(), AccessAllowed)


def test_disclosure_requires_projection_category_and_destination(scenario: Scenario) -> None:
    permission = DisclosurePermission(
        destination_id=scenario.request.destination_id,
        projection_id="profile.safe.metadata",
        category=DisclosureCategory.OPERATION_METADATA,
    )
    scope = changed(scenario.session.scope, disclosures=frozenset({permission}))
    subject = replace(
        scenario,
        profile=changed(scenario.profile, scope=scope),
        grant=changed(scenario.grant, scope=scope),
        session=changed(scenario.session, scope=scope),
        policy=changed(scenario.policy, disclosures=frozenset({permission})),
    )
    assert isinstance(subject.evaluate(), AccessAllowed)
    assert_denied(
        replace(subject, request=changed(scenario.request, destination_id=uuid4())), AccessDenialCode.DISCLOSURE_DENIED
    )
    for updates in ({"category": DisclosureCategory.TAX_VALUES}, {"projection_id": "profile.private.values"}):
        policy = changed(subject.policy, disclosures=frozenset({changed(permission, **updates)}))
        assert_denied(replace(subject, policy=policy), AccessDenialCode.DISCLOSURE_DENIED)
    assert_denied(
        replace(subject, request=changed(subject.request, action=AccessAction.RESULT)),
        AccessDenialCode.DISCLOSURE_DENIED,
    )


@pytest.mark.parametrize("projection", ["operation.observation", "profile.safe.metadata"])
def test_observation_consent_names_the_common_versioned_projection(scenario: Scenario, projection: str) -> None:
    permission = DisclosurePermission(
        destination_id=scenario.request.destination_id,
        projection_id=projection,
        category=DisclosureCategory.OPERATION_METADATA,
    )
    scope = changed(scenario.session.scope, disclosures=frozenset({permission}))
    subject = replace(
        scenario,
        profile=changed(scenario.profile, scope=scope),
        grant=changed(scenario.grant, scope=scope),
        session=changed(scenario.session, scope=scope),
        request=changed(scenario.request, action=AccessAction.OBSERVE),
        policy=changed(scenario.policy, disclosures=frozenset({permission})),
    )
    if projection == "operation.observation":
        assert isinstance(subject.evaluate(), AccessAllowed)
    else:
        assert_denied(subject, AccessDenialCode.DISCLOSURE_DENIED)


def test_current_registry_and_readiness_are_separate_authorities(scenario: Scenario) -> None:
    assert_denied(
        replace(scenario, request=changed(scenario.request, definition_id="unregistered.operation")),
        AccessDenialCode.OPERATION_UNAVAILABLE,
    )
    assert_denied(
        replace(scenario, policy=changed(scenario.policy, definition_contract_digest="0" * 64)),
        AccessDenialCode.OPERATION_UNAVAILABLE,
    )
    for field, denial in (
        ("backend", AccessDenialCode.BACKEND_UNAVAILABLE),
        ("published_authority", AccessDenialCode.AUTHORITY_UNAVAILABLE),
        ("provider", AccessDenialCode.PROVIDER_REQUIRED),
    ):
        assert_denied(replace(scenario, policy=changed(scenario.policy, **{field: Availability.UNSUPPORTED})), denial)
    assert_denied(
        replace(scenario, request=changed(scenario.request, action=AccessAction.RESPOND)),
        AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED,
    )


def test_child_lineage_cannot_expand_or_survive_parent_lock(scenario: Scenario) -> None:
    child = changed(
        scenario.session,
        session_id=uuid4(),
        connection_id=uuid4(),
        parent_session_id=scenario.session.session_id,
        scope=changed(scenario.session.scope, allow_delegation=False),
        expires_at=NOW + timedelta(minutes=2),
    )
    subject = replace(
        scenario,
        session=child,
        ancestors=(scenario.session,),
        context=changed(scenario.context, connection_id=child.connection_id),
    )
    assert isinstance(subject.evaluate(), AccessAllowed)
    assert_denied(replace(subject, ancestors=()), AccessDenialCode.PARENT_INVALID)
    assert_denied(
        replace(subject, ancestors=(changed(scenario.session, state=SessionState.LOCKED),)),
        AccessDenialCode.SESSION_INACTIVE,
    )
    assert_denied(
        replace(
            subject,
            ancestors=(changed(scenario.session, scope=changed(scenario.session.scope, allow_delegation=False)),),
        ),
        AccessDenialCode.PRIVILEGE_EXPANSION,
    )
    assert_denied(
        replace(subject, ancestors=(changed(scenario.session, expires_at=NOW + timedelta(minutes=1)),)),
        AccessDenialCode.PRIVILEGE_EXPANSION,
    )
    assert_denied(replace(subject, ancestors=(scenario.session, child)), AccessDenialCode.PARENT_INVALID)
    assert_denied(replace(subject, grant=changed(scenario.grant, generation=2)), AccessDenialCode.GRANT_INACTIVE)
    assert_denied(replace(subject, key=changed(scenario.key, generation=2)), AccessDenialCode.KEY_INACTIVE)


def human_session(scenario: Scenario) -> AccessSession:
    return changed(
        scenario.session,
        kind=SessionKind.HUMAN,
        originating_login_id="login-a",
        grant_id=None,
        grant_generation=None,
        key_id=None,
        key_generation=None,
        expires_at=NOW + timedelta(hours=4),
    )


@pytest.mark.parametrize(
    "action",
    [
        AccessAction.SUBMIT,
        AccessAction.START,
        AccessAction.RESUME,
        AccessAction.COMMIT,
        AccessAction.CANCEL,
        AccessAction.DETACH,
        AccessAction.OBSERVE,
        AccessAction.RESULT,
        AccessAction.RESPOND,
    ],
)
def test_human_only_operation_refuses_live_api_and_attended_authority_at_every_action(
    scenario: Scenario, action: AccessAction
) -> None:
    """A valid delegated lease and disclosure scope cannot release human inventory."""
    disclosure = None
    if action in {AccessAction.OBSERVE, AccessAction.CANCEL, AccessAction.DETACH}:
        disclosure = DisclosurePermission(
            destination_id=scenario.request.destination_id,
            projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
            category=DisclosureCategory.OPERATION_METADATA,
        )
    elif action is AccessAction.RESULT:
        result_schema = scenario.registry.lookup_public_contract(scenario.request.definition_id).result_schema
        assert result_schema is not None
        disclosure = DisclosurePermission(
            destination_id=scenario.request.destination_id,
            projection_id=result_schema.schema_id,
            category=DisclosureCategory.PROFILE_VALUES,
        )
    scope = changed(
        scenario.session.scope,
        disclosures=frozenset((disclosure,)) if disclosure is not None else frozenset(),
    )
    base = replace(
        scenario,
        profile=changed(scenario.profile, scope=scope),
        grant=changed(scenario.grant, scope=scope),
        session=changed(scenario.session, scope=scope),
        request=changed(scenario.request, action=action),
        policy=changed(
            scenario.policy,
            requires_human=True,
            disclosures=frozenset((disclosure,)) if disclosure is not None else frozenset(),
        ),
    )
    assert_denied(base, AccessDenialCode.HUMAN_AUTHORITY_REQUIRED)
    human = human_session(base)
    attended = changed(
        base.session,
        session_id=uuid4(),
        kind=SessionKind.ATTENDED,
        originating_login_id="login-a",
        parent_session_id=human.session_id,
        key_id=None,
        key_generation=None,
    )
    assert_denied(
        replace(
            base,
            session=attended,
            ancestors=(human,),
            grant=changed(base.grant, unattended=False, allow_os_lock=False),
        ),
        AccessDenialCode.HUMAN_AUTHORITY_REQUIRED,
    )
    expected = (
        AccessDenied(code=AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED)
        if action is AccessAction.RESPOND
        else AccessAllowed(
            profile_id=human.binding.profile_id, session_id=human.session_id, expires_at=human.expires_at
        )
    )
    assert (
        evaluate_operation_access(
            registry=base.registry,
            profile=base.profile,
            grant=None,
            key=None,
            session=human,
            context=base.context,
            request=base.request,
            policy=base.policy,
            ancestors=(),
        )
        == expected
    )


def test_attended_expiry_and_independent_password_access(scenario: Scenario) -> None:
    human = human_session(scenario)
    subject = replace(
        scenario,
        session=human,
        profile=changed(scenario.profile, automation_custody=Availability.UNAVAILABLE, automation_enabled=False),
    )
    assert isinstance(subject.evaluate(), AccessAllowed)
    attended = changed(
        scenario.session,
        session_id=uuid4(),
        kind=SessionKind.ATTENDED,
        originating_login_id="login-a",
        parent_session_id=human.session_id,
        key_id=None,
        key_generation=None,
    )
    attended_subject = replace(
        scenario,
        session=attended,
        ancestors=(human,),
        grant=changed(scenario.grant, unattended=False, allow_os_lock=False),
    )
    assert isinstance(attended_subject.evaluate(), AccessAllowed)
    assert_denied(
        replace(attended_subject, ancestors=(changed(human, expires_at=NOW + timedelta(minutes=1)),)),
        AccessDenialCode.PRIVILEGE_EXPANSION,
    )
    assert_denied(
        replace(attended_subject, ancestors=(changed(human, state=SessionState.REVOKED),)),
        AccessDenialCode.SESSION_INACTIVE,
    )
    locked = changed(scenario.context, login_contexts=(changed(scenario.context.login_contexts[0], locked=True),))
    assert isinstance(replace(scenario, context=locked).evaluate(), AccessAllowed)
    assert_denied(replace(attended_subject, context=locked), AccessDenialCode.OS_LOCKED)
    assert_denied(
        replace(scenario, context=locked, grant=changed(scenario.grant, allow_os_lock=False)),
        AccessDenialCode.OS_LOCKED,
    )
    assert_denied(
        replace(scenario, context=changed(scenario.context, private_work_available=False)),
        AccessDenialCode.OS_SESSION_UNAVAILABLE,
    )


def test_contracts_are_strict_frozen_and_do_not_accept_agent_identity(scenario: Scenario) -> None:
    for model in (scenario.session, scenario.grant, scenario.key, scenario.profile):
        with pytest.raises(ValidationError):
            changed(model, agent_name="owner", api_secret=uuid4().hex)
        with pytest.raises(ValidationError):
            model.__setattr__(next(iter(type(model).model_fields)), "replacement")
    for invalid in (datetime(2026, 9, 26), NOW.astimezone(timezone(timedelta(hours=2)))):
        with pytest.raises(ValidationError):
            changed(scenario.context, now=invalid)
    with pytest.raises(ValidationError):
        changed(scenario.session, expires_at=NOW + ACCESS_LEASE_MAXIMUM + timedelta(seconds=1))
    with pytest.raises(ValidationError):
        changed(scenario.grant, generation=True)
    with pytest.raises(ValidationError):
        changed(scenario.context, monotonic_now=float("nan"))
    with pytest.raises(ValidationError):
        changed(scenario.request, periods=frozenset())
    assert AccessSession.model_validate_json(scenario.session.model_dump_json()) == scenario.session
    assert TypeAdapter(AccessDecision).validate_json(scenario.evaluate().model_dump_json()) == scenario.evaluate()


def test_public_inventory_omits_custody_and_connection_internals(scenario: Scenario) -> None:
    for projection in (
        project_access_session(scenario.session),
        project_api_key(scenario.key),
        project_automation_grant(scenario.grant),
    ):
        serialized = projection.model_dump_json()
        assert str(scenario.profile.binding.installation_id) not in serialized
        assert scenario.profile.binding.os_owner_id not in serialized
        assert str(scenario.profile.binding.dek_epoch) not in serialized
        assert str(scenario.session.connection_id) not in serialized
        assert type(projection).model_validate_json(serialized) == projection


def admin_request(scenario: Scenario, action: AccessAdministrationAction) -> AccessAdministrationRequest:
    return AccessAdministrationRequest(
        request_id=uuid4(),
        profile_id=scenario.request.profile_id,
        action=action,
        request_digest="a" * 64,
        target_session_id=scenario.session.session_id if action is AccessAdministrationAction.LOCK_SESSION else None,
    )


def admin_evaluate(
    scenario: Scenario, request: AccessAdministrationRequest, proof: FreshPasswordAuthorization | None = None
):
    return evaluate_access_administration(
        request=request,
        session=scenario.session,
        ancestors=scenario.ancestors,
        grant=scenario.grant,
        key=scenario.key,
        profile=scenario.profile,
        context=scenario.context,
        password_proof=proof,
    )


@pytest.mark.parametrize("action", list(AccessAdministrationAction))
def test_key_authenticated_frontends_cannot_administer_root_authority(
    scenario: Scenario, action: AccessAdministrationAction
) -> None:
    result = admin_evaluate(scenario, admin_request(scenario, action))
    if action is AccessAdministrationAction.LOCK_SESSION:
        assert isinstance(result, AdministrationAllowed)
    else:
        assert isinstance(result, AccessDenied)


def test_own_session_lock_differs_from_selected_session_lock(scenario: Scenario) -> None:
    request = changed(admin_request(scenario, AccessAdministrationAction.LOCK_SESSION), target_session_id=uuid4())
    assert admin_evaluate(scenario, request) == AccessDenied(code=AccessDenialCode.HUMAN_AUTHORITY_REQUIRED)
    assert isinstance(
        admin_evaluate(replace(scenario, session=human_session(scenario)), request), AdministrationAllowed
    )


def test_fresh_password_is_exact_bound_expiring_and_separate_from_session(scenario: Scenario) -> None:
    request = admin_request(scenario, AccessAdministrationAction.RESUME_PROFILE)
    proof = FreshPasswordAuthorization(
        originating_login_id="login-a",
        request=request,
        binding=scenario.profile.binding,
        profile_lock_generation=0,
        runtime_boot_id=scenario.context.runtime_boot_id,
        connection_id=scenario.context.connection_id,
        client_id=scenario.context.authenticated_client_id,
        verified_at=NOW,
        expires_at=NOW + ACCESS_LEASE_MAXIMUM,
        verified_monotonic=100.0,
        consumed=False,
    )
    locked = replace(scenario, profile=changed(scenario.profile, globally_locked=True))
    assert isinstance(admin_evaluate(locked, request, proof), AdministrationAllowed)
    assert scenario.session.kind is SessionKind.API_KEY
    for invalid in (
        changed(proof, consumed=True),
        changed(proof, request=changed(request, request_digest="b" * 64)),
        changed(proof, connection_id=uuid4()),
        changed(proof, profile_lock_generation=1),
    ):
        assert admin_evaluate(locked, request, invalid) == AccessDenied(code=AccessDenialCode.FRESH_PASSWORD_REQUIRED)
    assert admin_evaluate(
        replace(locked, context=changed(scenario.context, monotonic_now=400.0)), request, proof
    ) == AccessDenied(code=AccessDenialCode.FRESH_PASSWORD_REQUIRED)
    assert admin_evaluate(
        replace(locked, context=changed(scenario.context, now=proof.expires_at)), request, proof
    ) == AccessDenied(code=AccessDenialCode.FRESH_PASSWORD_REQUIRED)
    assert administration_requirement(AccessAdministrationAction.ROTATE) is AdministrationRequirement.FRESH_PASSWORD


def test_global_unlock_requires_selected_grant_reactivation(scenario: Scenario) -> None:
    resumed = replace(
        scenario,
        profile=changed(scenario.profile, lock_generation=1),
        session=changed(scenario.session, profile_lock_generation=1),
    )
    assert_denied(resumed, AccessDenialCode.AUTOMATION_SUSPENDED)
    selected = replace(resumed, grant=changed(resumed.grant, profile_lock_generation=1))
    assert isinstance(selected.evaluate(), AccessAllowed)
    assert selected.grant.expires_at == scenario.grant.expires_at
    assert selected.grant.scope == scenario.grant.scope


def test_frontend_and_registered_result_projection_are_enforced(scenario: Scenario) -> None:
    original = scenario.registry.lookup(scenario.request.definition_id)
    definition = changed(original, permitted_frontends=frozenset({OperationFrontendProjection.CLI}))
    registry = OperationRegistry(
        definitions=(definition,), public_registrations=build_user_profile_operation_registrations((definition,))
    )
    subject = replace(
        scenario,
        registry=registry,
        policy=changed(
            scenario.policy,
            definition_contract_digest=registry.lookup_public_contract(
                definition.definition_id
            ).definition_contract_digest,
        ),
    )
    assert_denied(subject, AccessDenialCode.FRONTEND_DENIED)
    # Enroll the real executor's existing result model in an isolated registry to
    # exercise the generic result door without claiming this production exposure.
    assert original.result_type is not None
    result_schema = OperationSchemaBindingV1.bind(
        schema_id="profile.mutation.result", schema_version=1, model_type=original.result_type
    )
    registration = OperationPublicDefinitionRegistrationV1.compose(
        definition=original,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id="profile.mutation.request", schema_version=1, model_type=original.request_type
        ),
        result_schema=result_schema,
    )
    result_registry = OperationRegistry(definitions=(original,), public_registrations=(registration,))
    permission = DisclosurePermission(
        destination_id=scenario.request.destination_id,
        projection_id=result_schema.identity.schema_id,
        category=DisclosureCategory.OPERATION_METADATA,
    )
    scope = changed(scenario.session.scope, disclosures=frozenset({permission}))
    subject = replace(
        scenario,
        registry=result_registry,
        request=changed(scenario.request, action=AccessAction.RESULT),
        policy=changed(
            scenario.policy,
            definition_contract_digest=registration.contract.definition_contract_digest,
            disclosures=frozenset({permission}),
        ),
        profile=changed(scenario.profile, scope=scope),
        grant=changed(scenario.grant, scope=scope),
        session=changed(scenario.session, scope=scope),
    )
    assert isinstance(subject.evaluate(), AccessAllowed)
    assert_denied(
        replace(subject, policy=changed(subject.policy, transaction_authority_required=True)),
        AccessDenialCode.TRANSACTION_AUTHORITY_REQUIRED,
    )
    assert_denied(
        replace(subject, request=changed(subject.request, action=AccessAction.RESPOND)),
        AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED,
    )
    assert_denied(replace(subject, profile=scenario.profile), AccessDenialCode.DISCLOSURE_DENIED)


def test_status_does_not_confuse_credential_connection_with_current_authority(scenario: Scenario) -> None:
    context = changed(scenario.context, now=scenario.session.expires_at)
    status = project_access_status(
        session=scenario.session,
        ancestors=(),
        grant=scenario.grant,
        key=scenario.key,
        profile=scenario.profile,
        context=context,
        published_authority=Availability.UNAVAILABLE,
        provider=Availability.NEEDS_USER,
    )
    assert status.connected and status.credential_authenticated and status.profile_bound
    assert status.grant_valid
    assert status.denial is AccessDenialCode.SESSION_EXPIRED
    assert status.effective_scope.operations == frozenset()
    assert status.published_authority is Availability.UNAVAILABLE
    assert status.provider is Availability.NEEDS_USER


@pytest.mark.parametrize(
    "field,value",
    [
        ("operations", frozenset()),
        ("actions", frozenset()),
        ("periods", frozenset()),
        ("allow_period_independent", False),
        ("allow_delegation", False),
    ],
)
def test_child_restrictions_are_checked_in_every_dimension(scenario: Scenario, field: str, value: object) -> None:
    assert not scope_is_subset(scenario.session.scope, changed(scenario.session.scope, **{field: value}))


def test_missing_credential_facts_never_admit(scenario: Scenario) -> None:
    def evaluate(
        session: AccessSession | None,
        grant: AutomationGrant | None,
        key: ApiKeyRecord | None,
    ) -> AccessDecision:
        return evaluate_operation_access(
            request=scenario.request,
            policy=scenario.policy,
            registry=scenario.registry,
            profile=scenario.profile,
            context=scenario.context,
            ancestors=(),
            session=session,
            grant=grant,
            key=key,
        )

    assert evaluate(None, None, None) == AccessDenied(code=AccessDenialCode.AUTHENTICATION_REQUIRED)
    assert evaluate(scenario.session, None, scenario.key) == AccessDenied(code=AccessDenialCode.GRANT_INACTIVE)
    assert evaluate(scenario.session, scenario.grant, None) == AccessDenied(code=AccessDenialCode.KEY_INACTIVE)


def test_operation_period_policy_and_observation_consent_cannot_be_skipped(scenario: Scenario) -> None:
    restricted = replace(scenario, policy=changed(scenario.policy, periods=frozenset({OTHER_PERIOD})))
    assert_denied(restricted, AccessDenialCode.PERIOD_DENIED)
    independent = replace(
        scenario,
        request=changed(scenario.request, periods=frozenset(), period_independent=True),
        policy=changed(scenario.policy, allow_period_independent=False),
    )
    assert_denied(independent, AccessDenialCode.PERIOD_DENIED)
    assert_denied(
        replace(scenario, request=changed(scenario.request, action=AccessAction.OBSERVE)),
        AccessDenialCode.DISCLOSURE_DENIED,
    )


def test_originating_logout_does_not_revoke_independent_automation(scenario: Scenario) -> None:
    other = changed(scenario.context.login_contexts[0], login_id="login-b")
    context = changed(scenario.context, login_contexts=(other,))
    assert isinstance(replace(scenario, context=context).evaluate(), AccessAllowed)
    human = human_session(scenario)
    assert_denied(replace(scenario, session=human, context=context), AccessDenialCode.OS_SESSION_UNAVAILABLE)
    attended = changed(
        scenario.session,
        kind=SessionKind.ATTENDED,
        session_id=uuid4(),
        originating_login_id="login-a",
        parent_session_id=human.session_id,
        key_id=None,
        key_generation=None,
    )
    assert_denied(
        replace(scenario, session=attended, ancestors=(human,), context=context),
        AccessDenialCode.OS_SESSION_UNAVAILABLE,
    )
    assert scenario.grant.state is AuthorityState.ACTIVE
    assert not scenario.profile.globally_locked


@pytest.mark.parametrize(
    "updates",
    [
        {"unattended": LoginEligibility.UNKNOWN},
        {"unattended": LoginEligibility.INELIGIBLE},
        {"credential_facilities": Availability.NEEDS_USER},
        {"active": False},
        {"os_owner_id": "another-owner"},
    ],
)
def test_another_login_must_prove_unattended_dependencies(scenario: Scenario, updates: dict[str, object]) -> None:
    other = changed(scenario.context.login_contexts[0], login_id="login-b", **updates)
    assert_denied(
        replace(scenario, context=changed(scenario.context, login_contexts=(other,))),
        AccessDenialCode.OS_SESSION_UNAVAILABLE,
    )


def test_last_logout_and_suspend_fence_without_suspending_grant(scenario: Scenario) -> None:
    assert_denied(
        replace(scenario, context=changed(scenario.context, login_contexts=())), AccessDenialCode.OS_SESSION_UNAVAILABLE
    )
    assert_denied(
        replace(scenario, context=changed(scenario.context, private_work_available=False)),
        AccessDenialCode.OS_SESSION_UNAVAILABLE,
    )
    assert_denied(
        replace(scenario, context=changed(scenario.context, runtime_boot_id=uuid4())), AccessDenialCode.RUNTIME_CHANGED
    )
    assert isinstance(scenario.evaluate(), AccessAllowed)
    with pytest.raises(ValidationError):
        changed(scenario.context, login_contexts=scenario.context.login_contexts * 2)

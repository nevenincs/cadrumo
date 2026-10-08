"""Exact-profile, lossless profile-history read and whole-period authority."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.operations import OperationEffect, profile_operation_subject
from ....core.period import Period
from ....domain.buckets.event import (
    BucketEvent,
    BucketEventHistoryCatalogue,
    BucketEventObjectType,
    BucketEventType,
)
from ....domain.buckets.event_repository import append_bucket_event, build_bucket_event
from ....domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...bucket_event_projection import BucketEventProjection
from ...operations import profile_guard
from ...operations.access_resolution import OperationAccessContext
from ...operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ...operations.models import OperationIdentity, OperationRequest
from ...operations.owner import OperationExecutorContext
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ..access_contracts import (
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
    OperationAccessRequest,
    OsLockState,
    OsLoginContext,
    ProfileAccessBinding,
    ProfileAccessState,
    SessionKind,
    SessionState,
)
from ..access_errors import ProfileAccessRefusedError
from ..history_contracts import ProfileHistoryExecutionResult, ProfileHistoryProjection, ProfileHistoryRequest
from ..history_operation import (
    PROFILE_HISTORY_OPERATION_DEFINITION_ID,
    ProfileHistoryExecutor,
    ProfileHistoryReadPorts,
    build_profile_history_definition,
    build_profile_history_registration,
    resolve_profile_history_access,
)
from ..operation_access_policy import evaluate_operation_access

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("3a3a3a3a-3a3a-4a3a-8a3a-3a3a3a3a3a3a")
_OTHER = UUID("4b4b4b4b-4b4b-4b4b-8b4b-4b4b4b4b4b4b")
_PIN = cast(PinnedAuthorityOperation, object())


def _event(*, marker: str, minute: int, actor: str = "operator") -> BucketEvent:
    return build_bucket_event(
        bucket_id=str(_PROFILE),
        event_type=BucketEventType.PROFILE_VALUES_UPDATED,
        occurred_at=datetime(2026, 5, 1, 12, minute, tzinfo=UTC),
        actor=actor,
        object_type=BucketEventObjectType.PROFILE,
        object_id=marker,
        payload={"marker": marker},
        payload_version=1,
    )


def _registry() -> OperationRegistry:
    def unopened(*, bucket_id: str, operation: PinnedAuthorityOperation) -> ProfileHistoryReadPorts:
        raise AssertionError("registration must not open history persistence")

    definition = build_profile_history_definition(unopened)
    return OperationRegistry(
        definitions=(definition,), public_registrations=(build_profile_history_registration(definition),)
    )


def _request(**filters: object) -> OperationRequest[ProfileHistoryRequest]:
    return OperationRequest[ProfileHistoryRequest](
        definition_id=PROFILE_HISTORY_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=ProfileHistoryRequest.model_validate({"profile_id": _PROFILE, **filters}),
    )


def _access_request() -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=PROFILE_HISTORY_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=ProfileHistoryRequest(profile_id=_PROFILE),
    )


def test_history_contract_requires_all_periods_and_exact_result_destination() -> None:
    registry = _registry()
    contract = registry.lookup_public_contract(PROFILE_HISTORY_OPERATION_DEFINITION_ID)
    assert contract.permitted_frontends == frozenset({OperationFrontendProjection.CLI})
    assert contract.result_schema is not None
    destination = uuid4()
    base = OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=destination,
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.CLI,
        contract=contract,
        published_authority=Availability.AVAILABLE,
        authority_operation=_PIN,
    )
    admitted = resolve_profile_history_access(_access_request(), base)
    assert admitted.request.periods == frozenset()
    assert admitted.request.period_independent and admitted.policy.requires_all_periods
    assert AccessAction.COMMIT not in admitted.policy.actions
    result = resolve_profile_history_access(
        _access_request(),
        OperationAccessContext(
            profile_id=_PROFILE,
            destination_id=destination,
            action=AccessAction.RESULT,
            frontend=OperationFrontendProjection.CLI,
            contract=contract,
            published_authority=Availability.AVAILABLE,
            authority_operation=_PIN,
            admitted_request=admitted.request,
        ),
    )
    assert {(item.destination_id, item.projection_id, item.category) for item in result.policy.disclosures} == {
        (destination, contract.result_schema.schema_id, DisclosureCategory.PROFILE_VALUES),
        (destination, contract.result_schema.schema_id, DisclosureCategory.TAX_VALUES),
    }
    observation = resolve_profile_history_access(
        _access_request(),
        OperationAccessContext(
            profile_id=_PROFILE,
            destination_id=destination,
            action=AccessAction.OBSERVE,
            frontend=OperationFrontendProjection.CLI,
            contract=contract,
            published_authority=Availability.AVAILABLE,
            admitted_request=admitted.request,
        ),
    )
    assert observation.policy.disclosures == frozenset(
        {
            DisclosurePermission(
                destination_id=destination,
                projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                category=DisclosureCategory.OPERATION_METADATA,
            )
        }
    )
    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_profile_history_access(
            _access_request(),
            OperationAccessContext(
                profile_id=_OTHER,
                destination_id=destination,
                action=AccessAction.SUBMIT,
                frontend=OperationFrontendProjection.CLI,
                contract=contract,
                published_authority=Availability.AVAILABLE,
                authority_operation=_PIN,
            ),
        )
    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH


def _history_context(
    action: AccessAction,
    *,
    destination_id: UUID,
    frontend: OperationFrontendProjection = OperationFrontendProjection.CLI,
    admitted: OperationAccessRequest | None = None,
    authority: PinnedAuthorityOperation | None = None,
) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=destination_id,
        action=action,
        frontend=frontend,
        contract=_registry().lookup_public_contract(PROFILE_HISTORY_OPERATION_DEFINITION_ID),
        published_authority=Availability.AVAILABLE,
        admitted_request=admitted,
        authority_operation=authority,
    )


@pytest.mark.parametrize(
    "action", [AccessAction.OBSERVE, AccessAction.RESULT, AccessAction.CANCEL, AccessAction.DETACH]
)
def test_history_replay_from_a_fresh_process_keeps_the_admitted_scope(action: AccessAction) -> None:
    """A later session has a new destination; replay binds profile, definition and scope, not origin."""
    admitted = resolve_profile_history_access(
        _access_request(), _history_context(AccessAction.SUBMIT, destination_id=uuid4(), authority=_PIN)
    ).request
    fresh_destination = uuid4()

    for frontend in OperationFrontendProjection:
        replayed = resolve_profile_history_access(
            _access_request(),
            _history_context(action, destination_id=fresh_destination, frontend=frontend, admitted=admitted),
        )
        assert replayed.request.destination_id == fresh_destination
        assert replayed.request.period_independent and replayed.request.action is action
        assert all(item.destination_id == fresh_destination for item in replayed.policy.disclosures)

    period_scoped = admitted.model_copy(
        update={"periods": frozenset({Period.from_year_and_code(2026, "1T")}), "period_independent": False}
    )
    for foreign in (
        admitted.model_copy(update={"profile_id": _OTHER}),
        admitted.model_copy(update={"definition_id": "user-profile.other"}),
        admitted.model_copy(update={"action": AccessAction.START}),
        period_scoped,
    ):
        with pytest.raises(ProfileAccessRefusedError) as refused:
            resolve_profile_history_access(
                _access_request(),
                _history_context(action, destination_id=fresh_destination, admitted=foreign, authority=_PIN),
            )
        assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE


@pytest.mark.parametrize("action", [AccessAction.SUBMIT, AccessAction.START, AccessAction.RESUME])
def test_history_entry_actions_resolve_under_held_authority_not_the_admission(action: AccessAction) -> None:
    period_scoped = OperationAccessRequest(
        profile_id=_OTHER,
        definition_id="user-profile.other",
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.MCP,
        periods=frozenset({Period.from_year_and_code(2026, "1T")}),
        period_independent=False,
        destination_id=uuid4(),
    )
    destination = uuid4()

    fresh = resolve_profile_history_access(
        _access_request(),
        _history_context(action, destination_id=destination, admitted=period_scoped, authority=_PIN),
    )
    assert fresh.request.destination_id == destination and fresh.request.action is action
    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_profile_history_access(
            _access_request(), _history_context(action, destination_id=destination, admitted=period_scoped)
        )
    assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE


@pytest.mark.parametrize("missing", [DisclosureCategory.PROFILE_VALUES, DisclosureCategory.TAX_VALUES, None])
def test_history_result_requires_complete_profile_and_tax_disclosure_consent(
    missing: DisclosureCategory | None,
) -> None:
    registry = _registry()
    contract = registry.lookup_public_contract(PROFILE_HISTORY_OPERATION_DEFINITION_ID)
    schema = contract.result_schema
    assert schema is not None
    destination = uuid4()
    resolved = resolve_profile_history_access(
        _access_request(),
        OperationAccessContext(
            profile_id=_PROFILE,
            destination_id=destination,
            action=AccessAction.RESULT,
            frontend=OperationFrontendProjection.CLI,
            contract=contract,
            published_authority=Availability.AVAILABLE,
            authority_operation=_PIN,
        ),
    )
    permissions = frozenset(
        DisclosurePermission(
            destination_id=destination,
            projection_id=schema.schema_id,
            category=category,
        )
        for category in (DisclosureCategory.PROFILE_VALUES, DisclosureCategory.TAX_VALUES)
    )
    complete = AccessScope(
        operations=frozenset({PROFILE_HISTORY_OPERATION_DEFINITION_ID}),
        actions=frozenset({AccessAction.RESULT}),
        disclosures=permissions,
        periods=None,
        allow_period_independent=True,
        allow_delegation=False,
    )
    granted = AccessScope(
        operations=complete.operations,
        actions=complete.actions,
        disclosures=frozenset(permission for permission in permissions if permission.category is not missing),
        periods=None,
        allow_period_independent=True,
        allow_delegation=False,
    )
    instant = datetime(2026, 10, 1, 12, tzinfo=UTC)
    binding = ProfileAccessBinding(
        profile_id=_PROFILE,
        installation_id=uuid4(),
        os_owner_id="synthetic-owner",
        custody_generation=1,
        dek_epoch=uuid4(),
    )
    grant = AutomationGrant(
        grant_id=uuid4(),
        binding=binding,
        client_id=uuid4(),
        generation=1,
        profile_lock_generation=0,
        state=AuthorityState.ACTIVE,
        scope=granted,
        valid_from=instant - timedelta(days=1),
        expires_at=instant + timedelta(days=1),
        unattended=True,
        allow_os_lock=False,
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
        scope=granted,
        grant_id=grant.grant_id,
        grant_generation=grant.generation,
        key_id=key.key_id,
        key_generation=key.generation,
        issued_at=instant,
        expires_at=instant + timedelta(minutes=2),
        issued_monotonic=100.0,
    )
    decision = evaluate_operation_access(
        request=resolved.request,
        policy=resolved.policy,
        registry=registry,
        session=session,
        ancestors=(),
        grant=grant,
        key=key,
        profile=ProfileAccessState(
            binding=binding,
            lock_generation=0,
            globally_locked=False,
            automation_enabled=True,
            scope=complete,
            storage=Availability.AVAILABLE,
            automation_custody=Availability.AVAILABLE,
        ),
        context=AccessEvaluationContext(
            now=instant,
            monotonic_now=100.0,
            clock_rollback_detected=False,
            runtime_boot_id=session.runtime_boot_id,
            connection_id=session.connection_id,
            authenticated_client_id=grant.client_id,
            login_contexts=(
                OsLoginContext(
                    login_id="synthetic-login",
                    os_owner_id=binding.os_owner_id,
                    active=True,
                    lock_state=OsLockState.UNLOCKED,
                    unattended=LoginEligibility.ELIGIBLE,
                    credential_facilities=Availability.AVAILABLE,
                ),
            ),
            private_work_available=True,
        ),
    )
    if missing is None:
        assert isinstance(decision, AccessAllowed)
    else:
        assert isinstance(decision, AccessDenied) and decision.code is AccessDenialCode.DISCLOSURE_DENIED


@pytest.mark.asyncio
async def test_executor_retains_full_ordered_filtered_events_without_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(_PROFILE))
    first = _event(marker="first", minute=1)
    chosen = _event(marker="chosen", minute=2)
    wrong_actor = _event(marker="chosen", minute=3, actor="other")
    catalogue = BucketEventHistoryCatalogue()
    for event in (wrong_actor, chosen, first):
        catalogue = append_bucket_event(catalogue, event)
    reads: list[str] = []

    class HistoryRepository:
        def load(self) -> BucketEventHistoryCatalogue:
            reads.append("load")
            return catalogue

    def factory(*, bucket_id: str, operation: PinnedAuthorityOperation) -> ProfileHistoryReadPorts:
        assert bucket_id == str(_PROFILE) and operation is _PIN
        return ProfileHistoryReadPorts(
            bucket_id=bucket_id,
            operation=operation,
            event_repository=cast(BucketEventHistoryRepositoryProtocol, HistoryRepository()),
        )

    values: list[BaseModel] = []
    effects: list[OperationEffect] = []

    class Operands:
        async def put(self, value: BaseModel, *, written_at: datetime) -> str:
            assert written_at.tzinfo is not None
            values.append(value)
            return "f" * 64

    class Events:
        async def phase(self, _code: str) -> None:
            return None

        async def effect(self, effect: OperationEffect) -> None:
            effects.append(effect)

    request = _request(
        event_types=(BucketEventType.PROFILE_VALUES_UPDATED, BucketEventType.PROFILE_VALUES_UPDATED),
        since=datetime(2026, 5, 1, 12, 2, tzinfo=UTC),
        until=datetime(2026, 5, 1, 12, 3, tzinfo=UTC),
        object_id="chosen",
        actor="operator",
    )
    context = cast(
        OperationExecutorContext,
        SimpleNamespace(
            identity=OperationIdentity(
                operation_id="e" * 64,
                definition_id=PROFILE_HISTORY_OPERATION_DEFINITION_ID,
                subject_ref=profile_operation_subject(str(_PROFILE)),
            ),
            authority_operation=_PIN,
            events=Events(),
            operands=Operands(),
        ),
    )
    assert await ProfileHistoryExecutor(factory).execute(request, context) == "f" * 64
    assert reads == ["load"] and effects == [OperationEffect.NONE]
    assert len(values) == 1 and isinstance(values[0], ProfileHistoryExecutionResult)
    projected = values[0].projection
    assert projected.event_count == 1
    assert projected.events[0].to_event() == chosen
    assert projected.event_types == request.payload.event_types
    assert projected.since == request.payload.since and projected.until == request.payload.until
    assert projected.object_id == "chosen" and projected.actor == "operator"


def test_history_projection_rejects_other_profile_and_filter_mismatch() -> None:
    event = _event(marker="chosen", minute=2)
    projection = ProfileHistoryProjection(
        profile_id=_PROFILE,
        event_count=1,
        events=(BucketEventProjection.from_event(event),),
    )
    assert ProfileHistoryProjection.model_validate_json(projection.model_dump_json()) == projection
    with pytest.raises(ValidationError):
        ProfileHistoryProjection.model_validate(projection.model_copy(update={"profile_id": _OTHER}).model_dump())
    with pytest.raises(ValidationError):
        ProfileHistoryProjection.model_validate(projection.model_copy(update={"actor": "someone-else"}).model_dump())

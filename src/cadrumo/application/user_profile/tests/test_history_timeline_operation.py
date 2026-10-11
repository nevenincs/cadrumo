"""The profile timeline: the history's events without their payload, admitted on every frontend as the history is."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....domain.buckets.event import (
    BucketEvent,
    BucketEventHistoryCatalogue,
    BucketEventObjectType,
    BucketEventType,
)
from ....domain.buckets.event_repository import append_bucket_event, build_bucket_event
from ....domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...operations import profile_guard
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.owner import OperationExecutorContext
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ..access_contracts import AccessAction, AccessDenialCode, Availability, OperationAccessRequest
from ..access_errors import ProfileAccessRefusedError
from ..history_contracts import (
    ProfileHistoryExecutionResult,
    ProfileHistoryRequest,
    ProfileHistoryTimelineExecutionResult,
    ProfileHistoryTimelineProjection,
    ProfileTimelineEvent,
)
from ..history_operation import (
    PROFILE_HISTORY_OPERATION_DEFINITION_ID,
    PROFILE_HISTORY_TIMELINE_OPERATION_DEFINITION_ID,
    ProfileHistoryExecutor,
    ProfileHistoryReadPorts,
    ProfileHistoryTimelineExecutor,
    build_profile_history_definition,
    build_profile_history_registration,
    build_profile_history_timeline_definition,
    build_profile_history_timeline_registration,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("3a3a3a3a-3a3a-4a3a-8a3a-3a3a3a3a3a3a")
_OTHER = UUID("4b4b4b4b-4b4b-4b4b-8b4b-4b4b4b4b4b4b")
_PIN = cast(PinnedAuthorityOperation, object())
_HOST_PATH = r"C:\Users\synthetic-operator\Documents\facturas-privadas\factura-417.pdf"
_PAYLOAD_NOTE = "synthetic-payload-note-7f3a"
_PAYLOAD_FRAGMENTS = ("synthetic-operator", "facturas-privadas", "source_path", "note_text", _PAYLOAD_NOTE)


def _event(*, marker: str, minute: int, payload: dict[str, str], actor: str = "operator") -> BucketEvent:
    return build_bucket_event(
        bucket_id=str(_PROFILE),
        event_type=BucketEventType.PROFILE_VALUES_UPDATED,
        occurred_at=datetime(2026, 5, 1, 12, minute, tzinfo=UTC),
        actor=actor,
        object_type=BucketEventObjectType.PROFILE,
        object_id=marker,
        payload=payload,
        payload_version=1,
    )


_FIRST = _event(marker="first", minute=1, payload={})
_CHOSEN = _event(marker="chosen", minute=2, payload={"source_path": _HOST_PATH, "note_text": _PAYLOAD_NOTE})
_OTHER_ACTOR = _event(marker="chosen", minute=3, payload={"note_text": _PAYLOAD_NOTE}, actor="other")


def _catalogue() -> BucketEventHistoryCatalogue:
    catalogue = BucketEventHistoryCatalogue()
    for event in (_OTHER_ACTOR, _CHOSEN, _FIRST):
        catalogue = append_bucket_event(catalogue, event)
    return catalogue


class _StoredHistory:
    """An event history held in memory, which the reads under test only load."""

    def load(self) -> BucketEventHistoryCatalogue:
        return _catalogue()


def _factory(*, bucket_id: str, operation: PinnedAuthorityOperation) -> ProfileHistoryReadPorts:
    assert bucket_id == str(_PROFILE) and operation is _PIN
    return ProfileHistoryReadPorts(
        bucket_id=bucket_id,
        operation=operation,
        event_repository=cast(BucketEventHistoryRepositoryProtocol, _StoredHistory()),
    )


def _unopened(*, bucket_id: str, operation: PinnedAuthorityOperation) -> ProfileHistoryReadPorts:
    raise AssertionError(f"registration opened history persistence for {bucket_id} under {operation!r}")


def _registry() -> OperationRegistry:
    history = build_profile_history_definition(_unopened)
    timeline = build_profile_history_timeline_definition(_unopened)
    return OperationRegistry(
        definitions=(history, timeline),
        public_registrations=(
            build_profile_history_registration(history),
            build_profile_history_timeline_registration(timeline),
        ),
    )


def _request(definition_id: str, **filters: object) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=ProfileHistoryRequest.model_validate({"profile_id": _PROFILE, **filters}),
    )


def _worker_request(definition_id: str, **filters: object) -> OperationRequest[ProfileHistoryRequest]:
    return OperationRequest[ProfileHistoryRequest](
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=ProfileHistoryRequest.model_validate({"profile_id": _PROFILE, **filters}),
    )


def _context(
    registry: OperationRegistry,
    definition_id: str,
    *,
    frontend: OperationFrontendProjection,
    action: AccessAction = AccessAction.SUBMIT,
    profile_id: UUID = _PROFILE,
    admitted: OperationAccessRequest | None = None,
) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=profile_id,
        destination_id=uuid4(),
        action=action,
        frontend=frontend,
        contract=registry.lookup_public_contract(definition_id),
        published_authority=Availability.AVAILABLE,
        authority_operation=_PIN,
        admitted_request=admitted,
    )


@pytest.mark.parametrize(
    "definition_id", [PROFILE_HISTORY_OPERATION_DEFINITION_ID, PROFILE_HISTORY_TIMELINE_OPERATION_DEFINITION_ID]
)
def test_every_frontend_is_admitted_to_either_read_alike_for_either_kind_of_session_without_a_commit_door(
    definition_id: str,
) -> None:
    registry = _registry()
    contract = registry.lookup_public_contract(definition_id)

    admitted = {
        frontend: resolve_operation_access(
            registry=registry,
            request=_request(definition_id),
            context=_context(registry, definition_id, frontend=frontend),
        )
        for frontend in OperationFrontendProjection
    }

    assert contract.result_schema is not None
    for frontend, access in admitted.items():
        assert access.request.frontend is frontend
        assert access.request.period_independent and access.policy.requires_all_periods
        # A session under the person's sign-in and one under an enrolled key differ
        # in kind alone, and only a human-only policy tells the two apart.
        assert access.policy.requires_human is False
        assert AccessAction.COMMIT not in access.policy.actions
        assert access.policy.actions == admitted[OperationFrontendProjection.CLI].policy.actions
        released = resolve_operation_access(
            registry=registry,
            request=_request(definition_id),
            context=_context(
                registry, definition_id, frontend=frontend, action=AccessAction.RESULT, admitted=access.request
            ),
        )
        assert {item.projection_id for item in released.policy.disclosures} == {contract.result_schema.schema_id}
        with pytest.raises(ProfileAccessRefusedError) as foreign:
            resolve_operation_access(
                registry=registry,
                request=_request(definition_id),
                context=_context(registry, definition_id, frontend=frontend, profile_id=_OTHER),
            )
        assert foreign.value.reason is AccessDenialCode.PROFILE_MISMATCH


class _Operands:
    def __init__(self) -> None:
        self.values: list[BaseModel] = []

    async def put(self, value: BaseModel, *, written_at: datetime) -> str:
        assert written_at.tzinfo is not None
        self.values.append(value)
        return "f" * 64


class _Events:
    def __init__(self) -> None:
        self.effects: list[OperationEffect] = []

    async def phase(self, _code: str) -> None:
        return None

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)


def _executor_context(definition_id: str) -> tuple[OperationExecutorContext, _Operands, _Events, OperationIdentity]:
    operands, events = _Operands(), _Events()
    identity = OperationIdentity(
        operation_id="e" * 64, definition_id=definition_id, subject_ref=profile_operation_subject(str(_PROFILE))
    )
    context = SimpleNamespace(identity=identity, authority_operation=_PIN, events=events, operands=operands)
    return cast(OperationExecutorContext, cast(object, context)), operands, events, identity


def _receipt(identity: OperationIdentity) -> OperationTerminalReceipt:
    return OperationTerminalReceipt(
        identity=identity,
        revision=1,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE,
        settled_at=datetime(2026, 5, 2, 9, tzinfo=UTC),
        result_ref="f" * 64,
    )


@pytest.mark.asyncio
async def test_the_timeline_releases_each_event_fact_and_nothing_of_its_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(_PROFILE))
    timeline = PROFILE_HISTORY_TIMELINE_OPERATION_DEFINITION_ID
    request = _worker_request(timeline, actor="operator")
    context, operands, events, identity = _executor_context(timeline)

    assert await ProfileHistoryTimelineExecutor(_factory).execute(request, context) == "f" * 64

    assert events.effects == [OperationEffect.NONE]
    (private,) = operands.values
    assert isinstance(private, ProfileHistoryTimelineExecutionResult)
    projector = _registry().lookup_public_registration(timeline).result_projector
    assert projector is not None
    released = projector(private, _receipt(identity))
    assert isinstance(released, ProfileHistoryTimelineProjection)
    assert released.profile_id == _PROFILE and released.actor == "operator"
    assert released.event_count == 2
    assert released.events == (
        ProfileTimelineEvent(
            event_id=_FIRST.event_id,
            event_type=BucketEventType.PROFILE_VALUES_UPDATED,
            occurred_at=_FIRST.occurred_at,
            actor="operator",
            object_type=BucketEventObjectType.PROFILE,
            object_id="first",
            withheld_detail_count=0,
        ),
        ProfileTimelineEvent(
            event_id=_CHOSEN.event_id,
            event_type=BucketEventType.PROFILE_VALUES_UPDATED,
            occurred_at=_CHOSEN.occurred_at,
            actor="operator",
            object_type=BucketEventObjectType.PROFILE,
            object_id="chosen",
            withheld_detail_count=2,
        ),
    )
    document = released.model_dump_json()
    assert [fragment for fragment in _PAYLOAD_FRAGMENTS if fragment in document] == []
    person_identity = identity.model_copy(update={"definition_id": PROFILE_HISTORY_OPERATION_DEFINITION_ID})
    with pytest.raises(ValueError):
        projector(private, _receipt(person_identity))


@pytest.mark.asyncio
async def test_the_history_still_releases_the_complete_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(_PROFILE))
    history = PROFILE_HISTORY_OPERATION_DEFINITION_ID
    request = _worker_request(history, actor="operator", object_id="chosen")
    context, operands, _events, identity = _executor_context(history)

    await ProfileHistoryExecutor(_factory).execute(request, context)

    (private,) = operands.values
    assert isinstance(private, ProfileHistoryExecutionResult)
    projector = _registry().lookup_public_registration(history).result_projector
    assert projector is not None
    released = projector(private, _receipt(identity))
    assert [event.to_event() for event in private.projection.events] == [_CHOSEN]
    assert _HOST_PATH.replace("\\", "\\\\") in released.model_dump_json()
    timeline_projector = (
        _registry().lookup_public_registration(PROFILE_HISTORY_TIMELINE_OPERATION_DEFINITION_ID).result_projector
    )
    assert timeline_projector is not None
    with pytest.raises(ValueError):
        timeline_projector(private, _receipt(identity))


def test_the_timeline_event_declares_no_payload_field_and_the_projection_rejects_a_foreign_filter() -> None:
    assert set(ProfileTimelineEvent.model_fields) == {
        "event_id",
        "event_type",
        "occurred_at",
        "actor",
        "object_type",
        "object_id",
        "withheld_detail_count",
    }
    projection = ProfileHistoryTimelineProjection(
        profile_id=_PROFILE, event_count=1, events=(ProfileTimelineEvent.from_event(_CHOSEN),)
    )
    assert ProfileHistoryTimelineProjection.model_validate_json(projection.model_dump_json()) == projection
    with pytest.raises(ValidationError):
        ProfileHistoryTimelineProjection.model_validate(
            projection.model_copy(update={"actor": "someone-else"}).model_dump()
        )
    with pytest.raises(ValidationError):
        ProfileHistoryTimelineProjection.model_validate(projection.model_copy(update={"event_count": 2}).model_dump())

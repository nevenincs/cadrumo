"""Registered-executor conformance scenarios for the profile history read and its agent timeline."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from ...adapters.persistence.profile.buckets import build_bucket_event_history_repository
from ...application.bucket_event_projection import BucketEventDetail, BucketEventProjection
from ...application.user_profile.history_contracts import (
    ProfileHistoryProjection,
    ProfileHistoryRequest,
    ProfileHistoryTimelineProjection,
    ProfileTimelineEvent,
)
from ...application.user_profile.history_operation import (
    PROFILE_HISTORY_OPERATION_DEFINITION_ID,
    PROFILE_HISTORY_TIMELINE_OPERATION_DEFINITION_ID,
)
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.buckets.event import (
    BucketEvent,
    BucketEventHistoryCatalogue,
    BucketEventObjectType,
    BucketEventType,
    derive_bucket_event_id,
)
from ...domain.buckets.event_repository import append_bucket_event
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)

_ACTOR = "conformance-operator"
_OBJECT = "conformance-history-subject"
_OTHER_OBJECT = "conformance-history-other-subject"
_SINCE = datetime(2026, 4, 1, tzinfo=UTC)
_UNTIL = datetime(2026, 4, 30, 23, 59, tzinfo=UTC)
_TYPES = (BucketEventType.PROFILE_VALUES_UPDATED, BucketEventType.PROFILE_VALUES_CLEARED)
_PAYLOAD_PATH_NAME = "source_path"
_PAYLOAD_PATH_VALUE = "/home/conformance-operator/documents/synthetic-statement.pdf"


def _event(
    profile_id: UUID,
    event_type: BucketEventType,
    occurred_at: datetime,
    object_id: str,
    payload: dict[str, str],
) -> BucketEvent:
    bucket_id = str(profile_id)
    return BucketEvent(
        event_id=derive_bucket_event_id(
            bucket_id=bucket_id,
            event_type=event_type,
            occurred_at=occurred_at,
            actor=_ACTOR,
            object_type=BucketEventObjectType.PROFILE,
            object_id=object_id,
            payload=payload,
        ),
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor=_ACTOR,
        object_type=BucketEventObjectType.PROFILE,
        object_id=object_id,
        payload_version=1,
        payload=payload,
    )


def _expected_event(event: BucketEvent) -> BucketEventProjection:
    return BucketEventProjection(
        event_id=event.event_id,
        bucket_id=UUID(event.bucket_id),
        event_type=event.event_type,
        occurred_at=event.occurred_at,
        actor=event.actor,
        object_type=event.object_type,
        object_id=event.object_id,
        payload_version=event.payload_version,
        details=tuple(BucketEventDetail(name=name, value=value) for name, value in sorted(event.payload.items())),
    )


def _prepare_history(context: ConformanceFamilyContext) -> ConformancePreparation:
    profile_id = context.profile_id
    updated = _event(
        profile_id, BucketEventType.PROFILE_VALUES_UPDATED, datetime(2026, 4, 2, 9, tzinfo=UTC), _OBJECT, {"path": "a"}
    )
    cleared = _event(
        profile_id, BucketEventType.PROFILE_VALUES_CLEARED, datetime(2026, 4, 1, 9, tzinfo=UTC), _OBJECT, {"path": "b"}
    )
    # Each of these fails exactly one filter: before the window, another
    # object, and an event type outside the requested set.
    excluded = (
        _event(profile_id, BucketEventType.PROFILE_VALUES_UPDATED, datetime(2026, 3, 31, 23, tzinfo=UTC), _OBJECT, {}),
        _event(profile_id, BucketEventType.PROFILE_VALUES_UPDATED, datetime(2026, 4, 3, tzinfo=UTC), _OTHER_OBJECT, {}),
        _event(profile_id, BucketEventType.PROFILE_RENAMED, datetime(2026, 4, 4, tzinfo=UTC), _OBJECT, {}),
    )

    def seed(catalogue: BucketEventHistoryCatalogue) -> BucketEventHistoryCatalogue:
        for event in (updated, cleared, *excluded):
            catalogue = append_bucket_event(catalogue, event)
        return catalogue

    build_bucket_event_history_repository(bucket_id=str(profile_id)).append_guarded(seed)
    request = ProfileHistoryRequest(
        profile_id=profile_id, event_types=_TYPES, since=_SINCE, until=_UNTIL, object_id=_OBJECT
    )
    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(profile_id)),
        request=request,
        expected_result=ProfileHistoryProjection(
            profile_id=profile_id,
            event_types=_TYPES,
            since=_SINCE,
            until=_UNTIL,
            object_id=_OBJECT,
            event_count=2,
            # Chronological order (domain/buckets/event.py bucket_event_order_key).
            events=(_expected_event(cleared), _expected_event(updated)),
        ),
    )


def _expected_timeline_event(event: BucketEvent) -> ProfileTimelineEvent:
    return ProfileTimelineEvent(
        event_id=event.event_id,
        event_type=event.event_type,
        occurred_at=event.occurred_at,
        actor=event.actor,
        object_type=event.object_type,
        object_id=event.object_id,
        withheld_detail_count=len(event.payload),
    )


def _prepare_timeline(context: ConformanceFamilyContext) -> ConformancePreparation:
    profile_id = context.profile_id
    first = _event(
        profile_id,
        BucketEventType.PROFILE_VALUES_UPDATED,
        datetime(2026, 4, 5, 9, tzinfo=UTC),
        _OBJECT,
        {_PAYLOAD_PATH_NAME: _PAYLOAD_PATH_VALUE, "path": "a"},
    )
    second = _event(
        profile_id, BucketEventType.PROFILE_VALUES_CLEARED, datetime(2026, 4, 6, 9, tzinfo=UTC), _OBJECT, {}
    )
    other_object = _event(
        profile_id, BucketEventType.PROFILE_VALUES_UPDATED, datetime(2026, 4, 7, tzinfo=UTC), _OTHER_OBJECT, {}
    )

    def seed(catalogue: BucketEventHistoryCatalogue) -> BucketEventHistoryCatalogue:
        for event in (second, other_object, first):
            catalogue = append_bucket_event(catalogue, event)
        return catalogue

    build_bucket_event_history_repository(bucket_id=str(profile_id)).append_guarded(seed)

    def verify(outcome: ConformanceOutcome) -> None:
        released = outcome.resolve_result(ProfileHistoryTimelineProjection).model_dump_json()
        assert _PAYLOAD_PATH_VALUE not in released
        assert _PAYLOAD_PATH_NAME not in released

    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(profile_id)),
        request=ProfileHistoryRequest(
            profile_id=profile_id, event_types=_TYPES, since=_SINCE, until=_UNTIL, object_id=_OBJECT
        ),
        expected_result=ProfileHistoryTimelineProjection(
            profile_id=profile_id,
            event_types=_TYPES,
            since=_SINCE,
            until=_UNTIL,
            object_id=_OBJECT,
            event_count=2,
            events=(_expected_timeline_event(first), _expected_timeline_event(second)),
        ),
        verify=verify,
    )


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    if context.definition.definition_id == PROFILE_HISTORY_OPERATION_DEFINITION_ID:
        return _prepare_history(context)
    if context.definition.definition_id == PROFILE_HISTORY_TIMELINE_OPERATION_DEFINITION_ID:
        return _prepare_timeline(context)
    raise AssertionError(f"no profile history conformance scenario for {context.definition.definition_id}")


PROFILE_HISTORY_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=(
        # A single-phase definition publishes its own id and settles NONE
        # (application/user_profile/history_operation.py:123,131).
        RegisteredExecutorConformanceCase(
            PROFILE_HISTORY_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            (PROFILE_HISTORY_OPERATION_DEFINITION_ID,),
        ),
        # The timeline is the same single-phase read with a reduced result
        # (application/user_profile/history_operation.py ProfileHistoryTimelineExecutor).
        RegisteredExecutorConformanceCase(
            PROFILE_HISTORY_TIMELINE_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            (PROFILE_HISTORY_TIMELINE_OPERATION_DEFINITION_ID,),
        ),
    ),
    prepare=_prepare,
)

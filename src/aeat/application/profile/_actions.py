"""Application services for autónomo profile management."""

from __future__ import annotations

import hashlib

from ...core.errors import CoreValidationError
from ...domain.buckets import (
    BucketEvent,
    BucketEventHistoryRepository,
    BucketEventObjectType,
    BucketEventType,
    append_bucket_event,
    derive_bucket_event_id,
)
from ..workflow._models import ProfileBucketPointer, WorkflowEvent, WorkflowState
from ..workflow._utils import _normalise_key, utc_now
from ._models import ProfileRecord
from ._repository import profile_bucket_id, profile_bucket_repository


def _append_bucket_event(
    state: WorkflowState,
    *,
    action: str,
    bucket_id: str,
    object_id: str,
) -> WorkflowState:
    event = WorkflowEvent(action=action, bucket_id=bucket_id, object_id=object_id)
    return state.model_copy(update={"bucket_events": (*state.bucket_events, event), "updated_at": utc_now()})


def _emit_profile_bucket_event(
    *,
    action: BucketEventType,
    bucket_id: str,
    object_id: str,
    payload: dict[str, str] | None = None,
) -> None:
    occurred_at = utc_now()
    event = BucketEvent(
        event_id=derive_bucket_event_id(
            bucket_id=bucket_id,
            event_type=action,
            occurred_at=occurred_at,
            actor="aeat.application.profile",
            object_type=BucketEventObjectType.PROFILE,
            object_id=object_id,
            payload=payload or {},
        ),
        bucket_id=bucket_id,
        event_type=action,
        occurred_at=occurred_at,
        actor="aeat.application.profile",
        object_type=BucketEventObjectType.PROFILE,
        object_id=object_id,
        payload_version=1,
        payload=payload or {},
    )
    repository = BucketEventHistoryRepository()
    repository.save(append_bucket_event(repository.load(), event))


def _event_object_id(keys: tuple[str, ...]) -> str:
    joined = ",".join(sorted(keys))
    if len(joined) <= 500:
        return joined
    digest = hashlib.sha256(joined.encode("utf-8")).hexdigest()
    return f"keys:{len(keys)}:{digest}"


def set_active_profile(state: WorkflowState, name: str) -> WorkflowState:
    """Select or create an active profile."""

    try:
        profile_name = profile_bucket_id(name)
    except ValueError as exc:
        raise CoreValidationError("profile name must not be blank") from exc
    repository = profile_bucket_repository()
    profiles = dict(state.profiles)
    created = repository.load(profile_name) is None
    if created:
        repository.save(ProfileRecord(name=profile_name))
    profiles[profile_name] = ProfileBucketPointer(bucket_id=profile_name)
    updated = state.model_copy(update={"active_profile": profile_name, "profiles": profiles, "updated_at": utc_now()})
    if created:
        _emit_profile_bucket_event(
            action=BucketEventType.PROFILE_BUCKET_CREATED,
            bucket_id=profile_name,
            object_id=profile_name,
        )
        updated = _append_bucket_event(
            updated,
            action="profile.created",
            bucket_id=profile_name,
            object_id=profile_name,
        )
    _emit_profile_bucket_event(
        action=BucketEventType.PROFILE_SELECTED,
        bucket_id=profile_name,
        object_id=profile_name,
    )
    return _append_bucket_event(
        updated,
        action="profile.selected",
        bucket_id=profile_name,
        object_id=profile_name,
    )


def set_profile_values(state: WorkflowState, profile_name: str, values: dict[str, str]) -> WorkflowState:
    """Merge values into one profile and select it."""

    bucket_id = profile_bucket_id(profile_name)
    repository = profile_bucket_repository()
    profiles = dict(state.profiles)
    current = repository.load(bucket_id)
    created = current is None
    if current is None:
        current = ProfileRecord(name=bucket_id)

    normalised = {_normalise_key(key): raw.strip() for key, raw in values.items()}
    merged = {**current.values, **normalised}
    saved = repository.save(current.model_copy(update={"values": merged, "updated_at": utc_now()}))
    profiles[bucket_id] = ProfileBucketPointer(bucket_id=bucket_id)
    updated = state.model_copy(update={"active_profile": bucket_id, "profiles": profiles, "updated_at": utc_now()})
    if created:
        _emit_profile_bucket_event(
            action=BucketEventType.PROFILE_BUCKET_CREATED,
            bucket_id=bucket_id,
            object_id=bucket_id,
        )
        updated = _append_bucket_event(
            updated,
            action="profile.created",
            bucket_id=bucket_id,
            object_id=bucket_id,
        )
    if normalised:
        _emit_profile_bucket_event(
            action=BucketEventType.PROFILE_VALUES_UPDATED,
            bucket_id=bucket_id,
            object_id=saved.name,
            payload={"keys": _event_object_id(tuple(normalised))},
        )
        updated = _append_bucket_event(
            updated,
            action="profile.values.updated",
            bucket_id=bucket_id,
            object_id=_event_object_id(tuple(normalised)),
        )
    return updated


def clear_profile_values(state: WorkflowState, profile_name: str, keys: tuple[str, ...]) -> WorkflowState:
    """Clear values from one profile and select it."""

    bucket_id = profile_bucket_id(profile_name)
    repository = profile_bucket_repository()
    profiles = dict(state.profiles)
    current = repository.load(bucket_id)
    created = current is None
    if current is None:
        current = ProfileRecord(name=bucket_id)

    values = dict(current.values)
    normalised = tuple(_normalise_key(key) for key in keys)
    for key in normalised:
        values.pop(key, None)
    repository.save(current.model_copy(update={"values": values, "updated_at": utc_now()}))
    profiles[bucket_id] = ProfileBucketPointer(bucket_id=bucket_id)
    updated = state.model_copy(update={"active_profile": bucket_id, "profiles": profiles, "updated_at": utc_now()})
    if created:
        _emit_profile_bucket_event(
            action=BucketEventType.PROFILE_BUCKET_CREATED,
            bucket_id=bucket_id,
            object_id=bucket_id,
        )
        updated = _append_bucket_event(
            updated,
            action="profile.created",
            bucket_id=bucket_id,
            object_id=bucket_id,
        )
    if normalised:
        _emit_profile_bucket_event(
            action=BucketEventType.PROFILE_VALUES_CLEARED,
            bucket_id=bucket_id,
            object_id=bucket_id,
            payload={"keys": _event_object_id(normalised)},
        )
        updated = _append_bucket_event(
            updated,
            action="profile.values.cleared",
            bucket_id=bucket_id,
            object_id=_event_object_id(normalised),
        )
    return updated

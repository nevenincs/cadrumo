"""WorkflowState-aware orchestration over :class:`ProfileLifecycleService`.

The lifecycle service handles secure-DB persistence and BucketEvent
emission per profile. This module threads :class:`WorkflowState`
pointers (``profiles``, ``active_profile``) and the workflow-level
:class:`WorkflowEvent` audit stream around those calls so CLI surfaces
do not duplicate that wiring.

Bucket identity convention: ``bucket_id == profile_id``. The
orchestration helpers below are the single place that conflation
lives.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...domain.user_profile import (
    ProfileNotFoundError,
    ProfileSchemaDefinition,
    UserProfileFact,
    UserProfileRecord,
    load_user_profile_schema,
)
from ..workflow._bucket_pointer import BucketPointer
from ..workflow._bucket_pointer_io import write_pointer
from ..workflow._models import ProfileBucketPointer, WorkflowEvent, WorkflowState
from ..workflow._utils import utc_now
from . import (
    EditProfileFieldCommand,
    ProfileValidationService,
    RegisterProfileCommand,
    RemoveProfileCommand,
    UserProfileLifecycleRepository,
)
from ._lifecycle import ProfileLifecycleService

_SHARED_SCHEMA: ProfileSchemaDefinition | None = None
_SENTINEL_DATE = date.min


def _shared_schema() -> ProfileSchemaDefinition:
    """Return the canonical schema, loaded once per process."""

    global _SHARED_SCHEMA
    if _SHARED_SCHEMA is None:
        _SHARED_SCHEMA = load_user_profile_schema()
    return _SHARED_SCHEMA


def build_lifecycle_service(
    *,
    bucket_id: str,
    secure_objects: SecureObjectRepository | None = None,
    schema: ProfileSchemaDefinition | None = None,
) -> ProfileLifecycleService:
    """Construct a :class:`ProfileLifecycleService` for one bucket."""

    schema = schema or _shared_schema()
    return ProfileLifecycleService(
        repository=UserProfileLifecycleRepository(bucket_id=bucket_id, objects=secure_objects),
        validator=ProfileValidationService(schema=schema),
    )


def _append_workflow_event(state: WorkflowState, *, action: str, bucket_id: str, object_id: str) -> WorkflowState:
    event = WorkflowEvent(action=action, bucket_id=bucket_id, object_id=object_id)
    return state.model_copy(update={"bucket_events": (*state.bucket_events, event), "updated_at": utc_now()})


def _write_active_profile_pointer(bucket_id: str) -> None:
    """Atomically materialise the active-profile pointer file on disk.

    The pointer file is the canonical default for the active-profile
    precedence chain. Writing happens here so a successful register /
    select call leaves the on-disk state self-consistent: the next
    process invocation resolves the active profile from the pointer
    before any encrypted state row needs to load.
    """

    from ...core.config import load_settings

    settings = load_settings()
    write_pointer(
        settings.aeat_local_storage_root,
        BucketPointer(bucket_id=bucket_id, schema_version=1),
    )


def _clear_active_profile_pointer() -> None:
    """Remove the active-profile pointer file if present.

    Tombstoning a profile clears the precedence-chain rung-2 entry so
    the next CLI invocation reports no active profile rather than
    pointing at a tombstoned record.
    """

    from ...core.config import load_settings
    from ..workflow._bucket_pointer_io import pointer_path

    settings = load_settings()
    target = pointer_path(settings.aeat_local_storage_root)
    if target.is_file():
        target.unlink()


def register_active_profile(
    state: WorkflowState,
    *,
    profile_id: str,
    display_name: str,
    facts: tuple[UserProfileFact, ...] = (),
    secure_objects: SecureObjectRepository | None = None,
    schema: ProfileSchemaDefinition | None = None,
) -> WorkflowState:
    """Register a new profile and make it the active one.

    Atomically:
    - Persists the new :class:`UserProfileRecord` via the lifecycle
      service (which emits ``PROFILE_BUCKET_CREATED`` and, if facts
      were supplied, ``PROFILE_VALUES_UPDATED``).
    - Records the active profile pointer in
      :attr:`WorkflowState.profiles` and selects it.
    - Appends ``profile.created`` and ``profile.selected``
      WorkflowEvents.
    """

    service = build_lifecycle_service(bucket_id=profile_id, secure_objects=secure_objects, schema=schema)
    service.register(RegisterProfileCommand(profile_id=profile_id, display_name=display_name, facts=facts))
    # WorkflowState.profiles is now computed at access time from a
    # filesystem manifest scan; provisioning the bucket directory +
    # writing its manifest is what makes the profile appear in the
    # scan. No state mutation needed beyond the event log and the
    # active-profile pointer file.
    updated = state.model_copy(update={"updated_at": utc_now()})
    updated = _append_workflow_event(updated, action="profile.created", bucket_id=profile_id, object_id=profile_id)
    updated = _append_workflow_event(updated, action="profile.selected", bucket_id=profile_id, object_id=profile_id)
    if facts:
        keys_id = "keys:" + ",".join(sorted(f.path for f in facts if f.value is not None))
        if keys_id != "keys:":
            updated = _append_workflow_event(
                updated, action="profile.values.updated", bucket_id=profile_id, object_id=keys_id
            )
    _write_active_profile_pointer(profile_id)
    return updated


def select_profile(
    state: WorkflowState,
    *,
    profile_id: str,
    secure_objects: SecureObjectRepository | None = None,
    schema: ProfileSchemaDefinition | None = None,
) -> WorkflowState:
    """Select an existing profile as active.

    Raises :class:`ProfileNotFoundError` if the profile does not
    already exist; registration is the explicit path
    (:func:`register_active_profile`).
    """

    service = build_lifecycle_service(bucket_id=profile_id, secure_objects=secure_objects, schema=schema)
    service.read(profile_id)  # raises ProfileNotFoundError if missing
    # WorkflowState.profiles is now computed at access time from a
    # filesystem manifest scan; the bucket manifest already exists
    # for any profile the service can read.
    updated = state.model_copy(update={"updated_at": utc_now()})
    _write_active_profile_pointer(profile_id)
    return _append_workflow_event(updated, action="profile.selected", bucket_id=profile_id, object_id=profile_id)


def set_active_field(
    state: WorkflowState,
    fact: UserProfileFact,
    *,
    secure_objects: SecureObjectRepository | None = None,
    schema: ProfileSchemaDefinition | None = None,
) -> WorkflowState:
    """Upsert one fact on the active profile and append a WorkflowEvent."""

    profile_id = _require_active(state)
    service = build_lifecycle_service(bucket_id=profile_id, secure_objects=secure_objects, schema=schema)
    service.edit_field(
        EditProfileFieldCommand(
            profile_id=profile_id,
            path=fact.path,
            value=fact.value,
            valid_from=fact.valid_from,
            valid_to=fact.valid_to,
            source=fact.source,
        )
    )
    action = "profile.values.cleared" if fact.value is None else "profile.values.updated"
    return _append_workflow_event(state, action=action, bucket_id=profile_id, object_id=fact.path)


def set_active_fields(
    state: WorkflowState,
    facts: Iterable[UserProfileFact],
    *,
    secure_objects: SecureObjectRepository | None = None,
    schema: ProfileSchemaDefinition | None = None,
) -> WorkflowState:
    """Upsert several facts on the active profile in sequence."""

    updated = state
    for fact in facts:
        updated = set_active_field(updated, fact, secure_objects=secure_objects, schema=schema)
    return updated


def remove_active_profile(
    state: WorkflowState,
    *,
    secure_objects: SecureObjectRepository | None = None,
    schema: ProfileSchemaDefinition | None = None,
) -> WorkflowState:
    """Tombstone the active profile and clear the active pointer.

    The bucket pointer in :attr:`WorkflowState.profiles` is retained so
    audit and history reads can still resolve the bucket; selecting
    the tombstoned profile via :func:`select_profile` will raise
    because the record is no longer live.
    """

    profile_id = _require_active(state)
    service = build_lifecycle_service(bucket_id=profile_id, secure_objects=secure_objects, schema=schema)
    service.remove(RemoveProfileCommand(profile_id=profile_id))
    _clear_active_profile_pointer()
    updated = state.model_copy(update={"updated_at": utc_now()})
    return _append_workflow_event(updated, action="profile.tombstoned", bucket_id=profile_id, object_id=profile_id)


def read_active_profile(
    state: WorkflowState,
    *,
    secure_objects: SecureObjectRepository | None = None,
    schema: ProfileSchemaDefinition | None = None,
) -> UserProfileRecord | None:
    """Return the active :class:`UserProfileRecord`, or ``None`` when none is selected."""

    from ..workflow._models import resolve_active_bucket_id

    bucket_id = resolve_active_bucket_id()
    if bucket_id is None:
        return None
    service = build_lifecycle_service(bucket_id=bucket_id, secure_objects=secure_objects, schema=schema)
    try:
        return service.read(bucket_id)
    except ProfileNotFoundError:
        return None


def fact_value(record: UserProfileRecord | None, path: str) -> str | None:
    """Return the live string-rendered value of one fact path on ``record``.

    Returns ``None`` when ``record`` is ``None``, when the path has no
    fact, or when the recorded value is ``None``. Repeated facts at
    the same path (effective-dated windows) resolve to the
    chronologically last :attr:`UserProfileFact.valid_from`.
    """

    if record is None:
        return None
    matches = [fact for fact in record.facts if fact.path == path and fact.value is not None]
    if not matches:
        return None
    matches.sort(key=lambda fact: fact.valid_from or _SENTINEL_DATE)
    return str(matches[-1].value)


def _require_active(state: WorkflowState) -> str:
    """Return the active bucket id or raise.

    Reads through the precedence chain (Settings > pointer file >
    `state.active_profile` while the field migration is in flight).
    """

    from ..workflow._models import resolve_active_bucket_id

    bucket_id = resolve_active_bucket_id()
    if bucket_id is None:
        raise ProfileNotFoundError("no active profile selected")
    return bucket_id


__all__ = [
    "build_lifecycle_service",
    "fact_value",
    "read_active_profile",
    "register_active_profile",
    "remove_active_profile",
    "select_profile",
    "set_active_field",
    "set_active_fields",
]

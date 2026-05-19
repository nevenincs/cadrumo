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

import secrets
from collections.abc import Iterable
from datetime import UTC, date, datetime

from ...adapters.persistence.storage.bucket._layout import bucket_paths, provision_bucket_directory
from ...adapters.persistence.storage.bucket._manifest import BucketManifest, ManifestKdfParams
from ...adapters.persistence.storage.bucket._manifest_io import manifest_path, write_manifest
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...core.config import load_settings
from ...core.i18n import tr
from ...domain.user_profile import (
    ProfileNotFoundError,
    ProfileSchemaDefinition,
    UserProfileFact,
    UserProfileRecord,
    load_user_profile_schema,
)
from ..workflow._bucket_pointer import BucketPointer
from ..workflow._bucket_pointer_io import write_pointer
from ..workflow._models import WorkflowEvent, WorkflowState
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


class ProfileAlreadyRegisteredError(ProfileNotFoundError):
    """Raised when ``profile create`` targets a name that already has a manifest.

    Inherits from ``ProfileNotFoundError`` so existing exception
    handlers that catch the broader family also catch this case;
    the CLI decorator translates it to a typed refusal that names
    ``profile switch`` as the next action.
    """


def register_active_profile(
    state: WorkflowState,
    *,
    profile_id: str,
    display_name: str,
    facts: tuple[UserProfileFact, ...] = (),
    secure_objects: SecureObjectRepository | None = None,
    schema: ProfileSchemaDefinition | None = None,
) -> WorkflowState:
    """Atomically register a new profile and make it the active one.

    Five writes in sequence; failure at any step reverts the
    bucket directory and manifest so the operator never sees a
    half-created profile in ``profile list``:

    1. Refuse-if-exists: the bucket manifest must NOT exist on
       disk. Duplicate-name protection per the disaster ADR
       Ruling 3.
    2. Provision ``<root>/buckets/<id>/`` + manifest.
    3. ``service.register`` writes the encrypted
       :class:`UserProfileRecord` via the lifecycle service.
    4. Append the workflow events.
    5. Write the active-profile pointer file.

    On failure at step 3-5 the bucket directory + manifest are
    removed via the trash-rename pattern so a crashed create
    never leaves a phantom profile in the manifest scan.
    """

    _refuse_duplicate_profile(profile_id)
    service = build_lifecycle_service(bucket_id=profile_id, secure_objects=secure_objects, schema=schema)
    _ensure_profile_bucket_manifest(profile_id)
    try:
        service.register(RegisterProfileCommand(profile_id=profile_id, display_name=display_name, facts=facts))
    except Exception:
        _rollback_profile_bucket(profile_id)
        raise
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


def _refuse_duplicate_profile(profile_id: str) -> None:
    """Refuse a ``profile create`` when the manifest already exists.

    The manifest-scan helper is the canonical "is this profile
    registered?" oracle (disaster ADR Ruling 2). If the manifest is
    already on disk the operator already has a profile with this
    name; ``profile create`` must refuse rather than overwrite.
    """

    from ..workflow._profile_bucket_scan import read_profile_bucket

    if read_profile_bucket(profile_id) is not None:
        raise ProfileAlreadyRegisteredError(
            f"profile {profile_id!r} already exists; "
            "run `aeat config profile switch NAME` to activate it or "
            "`aeat config profile delete NAME` first.",
        )


def _rollback_profile_bucket(profile_id: str) -> None:
    """Trash-rename a half-created bucket directory after a failed register.

    Atomic-create rollback (disaster ADR Ruling 3 step 4 / 5
    rollback contract). The directory is renamed to a trash-prefix
    sibling rather than recursively unlinked so a crashed rollback
    leaves a recoverable on-disk trace. The follow-on cleanup is a
    best-effort recursive delete.
    """

    import shutil

    root = load_settings().aeat_local_storage_root
    target = bucket_paths(root, profile_id).bucket_dir
    if not target.exists():
        return
    trash = target.with_name(f".trash-{profile_id}-{secrets.token_hex(4)}")
    try:
        target.rename(trash)
    except OSError:
        return
    try:
        shutil.rmtree(trash, ignore_errors=True)
    except Exception:  # noqa: BLE001 - rollback is best-effort
        return


def _ensure_profile_bucket_manifest(profile_id: str) -> None:
    """Ensure manifest-scan profile discovery can see the profile bucket."""

    root = load_settings().aeat_local_storage_root
    try:
        paths = provision_bucket_directory(root, profile_id)
    except FileExistsError:
        paths = bucket_paths(root, profile_id)
    if manifest_path(paths).is_file():
        return
    write_manifest(
        paths,
        BucketManifest(
            bucket_id=profile_id,
            label=profile_id,
            created_at=datetime.now(UTC),
            last_unlocked_at=None,
            kdf_params=ManifestKdfParams(
                algorithm="argon2id",
                version=0x13,
                memory_cost=19_456,
                time_cost=2,
                parallelism=1,
                salt=secrets.token_bytes(16),
                output_length=32,
            ),
            recovery_enrolled=False,
            schema_version=1,
        ),
    )


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
        raise ProfileNotFoundError(tr("application.user_profile.errors.no_active_profile_selected"))
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

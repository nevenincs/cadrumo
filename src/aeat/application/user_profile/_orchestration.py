"""WorkflowState-aware orchestration over :class:`ProfileLifecycleService`.

The lifecycle service handles secure-DB persistence and BucketEvent
emission per profile. This module threads :class:`WorkflowState`
pointers (``active_profile``) and the workflow-level
:class:`WorkflowEvent` audit stream around those calls so CLI surfaces
do not duplicate that wiring.

Profile identity is an immutable UUIDv4 minted at creation. The bucket
directory, keystore directory, secure-object key, and active-profile
pointer all key on that UUID; the operator-chosen display name is a
fully decoupled mutable label carried in the bucket manifest.
"""

from __future__ import annotations

import secrets
from collections.abc import Iterable
from datetime import date

from ...adapters.persistence.storage.bucket._layout import bucket_paths
from ...adapters.persistence.storage.bucket._manifest_io import read_manifest, write_manifest
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...core._bucket_pointer import BucketPointer
from ...core._bucket_pointer_io import write_pointer
from ...core.config import load_settings
from ...core.i18n import tr
from ...domain.user_profile import (
    ProfileNotFoundError,
    ProfileSchemaDefinition,
    UserProfileFact,
    UserProfileRecord,
    load_user_profile_schema,
)
from ...domain.user_profile._errors import UserProfileValidationError
from ..workflow._models import WorkflowEvent, WorkflowState
from ..workflow._utils import utc_now
from . import (
    EditProfileFieldCommand,
    ProfileValidationService,
    RenameProfileCommand,
    UserProfileLifecycleRepository,
)
from ._lifecycle import ProfileLifecycleService
from ._profile_repository import _CAPTURE_POINTER, ProfileRepository, _CapturePointerSentinel

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
    """Construct a :class:`ProfileLifecycleService` for one bucket.

    The profile aggregate AND the bucket-event-history catalogue both
    belong to the named bucket's own database. When no repository is
    injected, a single per-bucket secure-object store is resolved and
    handed to both the lifecycle repository and the event-history
    repository, so the audit trail can never split from the records
    it describes. The prior wiring left the event-history repository
    on the process-global engine, which had no URL until an active
    profile existed — every ``register`` then crashed before its
    first event landed.
    """

    from ...domain.buckets import BucketEventHistoryRepository
    from ._repository import _secure_objects_for_bucket

    schema = schema or _shared_schema()
    objects = secure_objects or _secure_objects_for_bucket(bucket_id)
    return ProfileLifecycleService(
        repository=UserProfileLifecycleRepository(bucket_id=bucket_id, objects=objects),
        validator=ProfileValidationService(schema=schema),
        events=BucketEventHistoryRepository(objects=objects),
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

    from ...core._bucket_pointer_io import pointer_path
    from ...core.config import load_settings

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


def capture_active_profile_pointer() -> str | None:
    """Return the raw active-profile pointer text, or ``None`` if absent.

    A caller that writes the active-profile pointer EARLY for the
    cold-start load-order (so the per-bucket SQLAlchemy engine resolves
    before :func:`register_active_profile` runs inside
    ``workflow_state_repository().update``) captures the genuine prior
    pointer with this helper first, then hands it to
    :func:`register_active_profile` as ``prior_pointer_text`` so a
    failed create rolls the pointer back to exactly its pre-create
    state. The repository owns the rollback; this helper is the only
    extra coordination a cold-start caller needs.
    """

    from ...core._bucket_pointer_io import pointer_path

    target = pointer_path(load_settings().aeat_local_storage_root)
    if not target.is_file():
        return None
    return target.read_text(encoding="utf-8")


def register_active_profile(
    state: WorkflowState,
    *,
    profile_id: str,
    display_name: str,
    facts: tuple[UserProfileFact, ...] = (),
    secure_objects: SecureObjectRepository | None = None,
    schema: ProfileSchemaDefinition | None = None,
    prior_pointer_text: str | None | _CapturePointerSentinel = _CAPTURE_POINTER,
) -> WorkflowState:
    """Atomically register a new profile and make it the active one.

    ``profile_id`` is the immutable UUIDv4 profile identity, minted by
    the caller (see :func:`aeat.domain.user_profile.new_profile_id`).
    ``display_name`` is the operator-chosen label; it is carried in the
    bucket manifest and the encrypted record and plays no role in any
    key or path.

    This function is a thin :class:`WorkflowState` coordinator: the
    cross-store write (bucket directory + manifest + encrypted record +
    active-profile pointer), the duplicate-label refusal, and the
    rollback on any failure all live solely in
    :class:`ProfileRepository`. This function delegates the create and
    threads the workflow-level event audit stream around it.

    ``prior_pointer_text`` is forwarded to the repository as the
    rollback anchor; a cold-start caller captures it with
    :func:`capture_active_profile_pointer` before writing the early
    load-order pointer.
    """

    repository = ProfileRepository(secure_objects=secure_objects, schema=schema)
    repository.create(
        label=display_name,
        facts=facts,
        profile_id=profile_id,
        prior_pointer_text=prior_pointer_text,
    )
    updated = state.model_copy(update={"updated_at": utc_now()})
    updated = _append_workflow_event(updated, action="profile.created", bucket_id=profile_id, object_id=profile_id)
    updated = _append_workflow_event(updated, action="profile.selected", bucket_id=profile_id, object_id=profile_id)
    if facts:
        keys_id = "keys:" + ",".join(sorted(f.path for f in facts if f.value is not None))
        if keys_id != "keys:":
            updated = _append_workflow_event(
                updated, action="profile.values.updated", bucket_id=profile_id, object_id=keys_id
            )
    return updated


def _refuse_duplicate_label(
    display_name: str,
) -> None:
    """Refuse a ``profile create`` when a live profile carries the label.

    Display names (labels) are unique among live profiles, compared
    case-insensitively. A bucket manifest already carrying ``display_name``
    is an existence claim; recreating in place would silently mix new
    profile data into the existing bucket, so the create is refused and
    the operator is routed to ``switch`` or ``delete``.
    """

    from ..workflow._profile_bucket_scan import read_profile_bucket

    if read_profile_bucket(display_name) is None:
        return
    raise ProfileAlreadyRegisteredError(
        tr(
            "application.user_profile.errors.profile_already_exists",
            default=(
                "Profile '%{profile}' already exists; run `aeat config profile switch NAME` "
                "to activate it or `aeat config profile delete NAME` first."
            ),
            profile=display_name,
        ),
    )


def _require_registered_label(display_name: str) -> None:
    """Refuse a ``profile edit`` when no live profile carries the label.

    Symmetric to :func:`_refuse_duplicate_label`: ``profile edit``
    re-runs the wizard against an *existing* profile, so an unknown
    label is an operator error, not an implicit create.
    """

    from ..workflow._profile_bucket_scan import read_profile_bucket

    if read_profile_bucket(display_name) is None:
        raise ProfileNotFoundError(
            tr(
                "application.user_profile.errors.profile_not_registered",
                default="Profile '%{profile}' does not exist; run `aeat config profile create NAME` to create it.",
                profile=display_name,
            ),
        )


def remove_profile_bucket_directory(profile_id: str) -> None:
    """Trash-rename and remove a profile's on-disk bucket directory.

    Used both by atomic-create rollback (disaster ADR Ruling 3 step
    4 / 5 rollback contract) and by scoped config reset. The
    directory is first renamed to a trash-prefix sibling so a crashed
    removal leaves a recoverable on-disk trace, then recursively
    deleted. When the rename is refused — Windows denies renaming a
    directory whose SQLite file was only just closed — the directory
    is removed in place so the bucket does not survive the reset.

    Raises :class:`OSError` if the in-place removal also fails and the
    bucket directory genuinely survives on disk, so a caller (config
    reset in particular) never reports a removed profile while the
    bucket is still present. The atomic-create rollback caller wraps
    this call best-effort, since a residual directory there must not
    mask the original registration failure.
    """

    import gc
    import shutil

    root = load_settings().aeat_local_storage_root
    target = bucket_paths(root, profile_id).bucket_dir
    if not target.exists():
        return
    trash = target.with_name(f".trash-{profile_id}-{secrets.token_hex(4)}")
    try:
        target.rename(trash)
    except OSError:
        # The crash-safe rename was refused (file handle still held);
        # release lingering handles and remove the directory in place.
        gc.collect()
        shutil.rmtree(target, ignore_errors=True)
        if target.exists():
            raise OSError(
                f"profile bucket directory {target} could not be removed "
                "(a file handle is still held); the bucket survives on disk"
            )
        return
    shutil.rmtree(trash, ignore_errors=True)


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

    This function is a thin :class:`WorkflowState` coordinator: the
    profile load + integrity check + active-profile pointer write live
    solely in :meth:`ProfileRepository.select`.
    """

    repository = ProfileRepository(secure_objects=secure_objects, schema=schema)
    repository.select(profile_id)  # raises ProfileNotFoundError if missing
    updated = state.model_copy(update={"updated_at": utc_now()})
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

    This function is a thin :class:`WorkflowState` coordinator: the
    cross-store tombstone (encrypted-record tombstone + active-profile
    pointer clear) lives solely in :meth:`ProfileRepository.delete`.
    """

    profile_id = _require_active(state)
    repository = ProfileRepository(secure_objects=secure_objects, schema=schema)
    repository.delete(profile_id)
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


def rename_profile(
    *,
    profile_id: str,
    new_label: str,
    secure_objects: SecureObjectRepository | None = None,
    schema: ProfileSchemaDefinition | None = None,
) -> UserProfileRecord:
    """Rename a profile by updating its display label only.

    The profile identity (``profile_id``), bucket directory, keystore
    directory, and secure-object key are immutable and never move. This
    helper updates the operator-visible label in two places that hold a
    copy of it: the encrypted :class:`UserProfileRecord.display_name`
    and the plaintext bucket manifest ``label``. No directory move, no
    re-key, no rollback machinery — a label is a pure metadata edit.

    Refuses if ``new_label`` is already carried by another live profile
    (case-insensitive uniqueness).
    """

    from ..workflow._profile_bucket_scan import read_profile_bucket, read_profile_bucket_by_id

    pointer = read_profile_bucket_by_id(profile_id)
    if pointer is None:
        raise ProfileNotFoundError(f"profile {profile_id!r} has no registered bucket")

    trimmed = new_label.strip()
    if not trimmed:
        raise UserProfileValidationError("profile label must not be blank")

    if trimmed.casefold() != pointer.label.casefold():
        clash = read_profile_bucket(trimmed)
        if clash is not None and clash.bucket_id != profile_id:
            raise ProfileAlreadyRegisteredError(
                tr(
                    "application.user_profile.errors.profile_already_exists",
                    default=(
                        "Profile '%{profile}' already exists; run `aeat config profile switch NAME` "
                        "to activate it or `aeat config profile delete NAME` first."
                    ),
                    profile=trimmed,
                ),
            )

    service = build_lifecycle_service(bucket_id=profile_id, secure_objects=secure_objects, schema=schema)
    result = service.rename(RenameProfileCommand(profile_id=profile_id, target_display_name=trimmed))

    root = load_settings().aeat_local_storage_root
    paths = bucket_paths(root, profile_id)
    manifest = read_manifest(paths)
    write_manifest(paths, manifest.model_copy(update={"label": trimmed}))
    return result.profile


__all__ = [
    "build_lifecycle_service",
    "fact_value",
    "read_active_profile",
    "register_active_profile",
    "remove_active_profile",
    "rename_profile",
    "select_profile",
    "set_active_field",
    "set_active_fields",
]

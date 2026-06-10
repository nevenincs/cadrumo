"""WorkflowState-aware orchestration over :class:`ProfileLifecycleService`.

The lifecycle service handles secure-DB persistence via a
:class:`SecureObjectRepository` and emits bucket events to
:class:`BucketEventHistoryRepository` per profile. This module threads
:class:`WorkflowState` pointers (``active_profile``) and the
workflow-level :class:`WorkflowEvent` audit stream around those calls
so CLI surfaces do not duplicate that wiring.

Profile identity is an immutable UUIDv4 minted at creation. The bucket
directory, keystore directory, secure-object key, and active-profile
pointer all key on that UUID; the operator-chosen display name is a
fully decoupled mutable label carried in the bucket manifest.
"""

from __future__ import annotations

import secrets
from collections.abc import Iterable
from contextlib import contextmanager
from datetime import date

from ...adapters.persistence.storage.bucket import bucket_paths
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...core._bucket_pointer import BucketPointer
from ...core._bucket_pointer_io import write_pointer
from ...core.config import load_settings
from ...core.errors import AeatError
from ...core.external_constants import UTF_8_ENCODING as _UTF_8_ENCODING
from ...core.logging import get_logger
from ...core.time import now
from ...domain.user_profile import (
    ProfileNotFoundError,
    ProfileSchemaDefinition,
    UserProfileFact,
    UserProfileRecord,
    load_user_profile_schema,
)
from ...domain.user_profile._errors import UserProfileError
from ..workflow._models import WorkflowEvent, WorkflowState
from ..workflow._utils import utc_now
from . import (
    EditProfileFieldCommand,
    ProfileValidationService,
    UserProfileLifecycleRepository,
)
from ._lifecycle import ProfileLifecycleService
from ._profile_repository import ProfileRepository

_log = get_logger(__name__)
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

    ``secure_objects`` is an optional :class:`SecureObjectRepository` override; a
    per-bucket store is resolved when ``None``.

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


@contextmanager
def profile_create_storage_span(profile_id: str):
    """Open the first-profile storage span for a bucket being created."""
    from ...adapters.persistence.storage import activate_master_key_provider, get_master_key_provider
    from ...adapters.persistence.storage.errors import MasterKeyMaterialMissingError, SecretAlreadyExistsError
    from ...core.config import override_settings

    prior_pointer = capture_active_profile_pointer()
    _write_active_profile_pointer(profile_id)
    provider = get_master_key_provider()
    try:
        try:
            provider.get_master_key()
        except MasterKeyMaterialMissingError:
            try:
                provider.provision_master_key()
            except SecretAlreadyExistsError:
                _log.debug("master key already provisioned while opening create span for profile %s", profile_id)
        with (
            override_settings(aeat_active_profile=profile_id),
            activate_master_key_provider(
                provider,
                fallback_bucket_id=profile_id,
                allow_bucket_dek_enrollment=True,
            ),
        ):
            yield profile_id
    except (AeatError, OSError):
        # AeatError: encrypted-storage or workflow domain failures during profile create.
        # OSError: filesystem write of the active-profile pointer or bucket directory.
        restore_active_profile_pointer(prior_pointer)
        raise


@contextmanager
def profile_storage_session(profile_id: str):
    """Open a storage session scoped to ``profile_id`` for application-owned writes."""
    from ...adapters.persistence.storage import activate_master_key_provider, get_master_key_provider
    from ...core.config import override_settings

    with (
        override_settings(aeat_active_profile=profile_id),
        activate_master_key_provider(get_master_key_provider(), fallback_bucket_id=profile_id),
    ):
        yield profile_id


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
    ``config switch`` as the next action.
    """


def register_active_profile(
    state: WorkflowState,
    *,
    profile_id: str,
    display_name: str,
    facts: tuple[UserProfileFact, ...] = (),
    secure_objects: SecureObjectRepository | None = None,
    schema: ProfileSchemaDefinition | None = None,
    enforce_unique_tax_id: bool = True,
    routing_profile_id: str | None = None,
) -> WorkflowState:
    """Atomically register a new profile and make it the active one.

    Args:
        state: The current :class:`WorkflowState`; the returned state carries
            the registration event appended to the audit stream.
        profile_id: Immutable UUIDv4 profile identity, minted by the caller
            (see :func:`aeat.domain.user_profile.new_profile_id`).
        display_name: Operator-chosen label carried in the bucket manifest and
            the encrypted record; plays no role in any key or path.
        facts: Initial profile facts to persist alongside the registration.
        secure_objects: Optional :class:`SecureObjectRepository` override for
            the encrypted profile store.
        schema: Optional profile schema definition override.
        enforce_unique_tax_id: When ``True``, refuses if another live profile
            already carries the same tax id.
        routing_profile_id: When set, wires a cross-bucket routing entry so
            the new profile can inherit data from an existing bucket.

    This function is a thin :class:`WorkflowState` coordinator: the
    entire cross-store write — bucket directory, manifest, encrypted
    record, AND the active-profile pointer — plus the duplicate-label
    refusal and the all-or-nothing rollback are a single unit of work
    owned by :meth:`ProfileRepository.create`. This function delegates
    that create and threads the workflow-level event audit stream onto
    the supplied :class:`WorkflowState`.

    The repository owns every store write, the pointer included. A
    caller that performs the cold-start pointer write early (so the
    workflow-state engine can resolve before this function runs inside
    ``workflow_state_repository().update``) is responsible for
    restoring that early pointer if the surrounding span fails before
    or after ``create`` - :func:`capture_active_profile_pointer` and a
    ``try``/``except`` around the span cover the steps the repository's
    own rollback cannot see (engine open, master-key activation).
    """
    repository = ProfileRepository(secure_objects=secure_objects, schema=schema)
    repository.create(
        label=display_name,
        facts=facts,
        profile_id=profile_id,
        enforce_unique_tax_id=enforce_unique_tax_id,
        routing_profile_id=routing_profile_id,
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


def _append_profile_activated_event(*, profile_id: str, active_profile: str | None) -> None:
    """Append a PROFILE_ACTIVATED event to the active bucket-event catalogue."""
    from ...domain.buckets import (
        BucketEvent,
        BucketEventHistoryRepository,
        BucketEventObjectType,
        BucketEventType,
        append_bucket_event,
        derive_bucket_event_id,
    )

    if active_profile is None:
        return

    occurred_at = now()
    payload = {"profile_id": profile_id, "active_profile": active_profile}
    actor = "operator"
    bucket_id = active_profile
    event_id = derive_bucket_event_id(
        bucket_id=bucket_id,
        event_type=BucketEventType.PROFILE_ACTIVATED,
        occurred_at=occurred_at,
        actor=actor,
        object_type=BucketEventObjectType.PROFILE,
        object_id=profile_id,
        payload=payload,
    )
    repo = BucketEventHistoryRepository()
    repo.save(
        append_bucket_event(
            repo.load(),
            BucketEvent(
                event_id=event_id,
                bucket_id=bucket_id,
                event_type=BucketEventType.PROFILE_ACTIVATED,
                occurred_at=occurred_at,
                actor=actor,
                object_type=BucketEventObjectType.PROFILE,
                object_id=profile_id,
                payload_version=1,
                payload=payload,
            ),
        )
    )


def select_profile_with_lifecycle_span(profile_id: str) -> None:
    """Select ``profile_id`` inside an application-owned bucket session."""
    from ...core import resolve_active_bucket_id
    from ..workflow._persistence import workflow_state_repository

    with profile_storage_session(profile_id):
        workflow_state_repository().update(lambda current: select_profile(current, profile_id=profile_id))
        _append_profile_activated_event(profile_id=profile_id, active_profile=resolve_active_bucket_id())


def delete_profile_with_lifecycle_span(profile_id: str) -> UserProfileRecord:
    """Tombstone ``profile_id`` inside an application-owned bucket session.

    Returns the deleted :class:`UserProfileRecord`.
    """
    with profile_storage_session(profile_id):
        aggregate = ProfileRepository().delete(profile_id)
    return aggregate.record


def logout_active_profile() -> str | None:
    """Clear the active profile pointer and return the profile that was logged out."""
    from ...core import resolve_active_bucket_id

    before = resolve_active_bucket_id()
    _clear_active_profile_pointer()
    return before


def capture_active_profile_pointer() -> str | None:
    """Return the raw active-profile pointer text, or ``None`` if absent.

    A cold-start caller — one that must write the active-profile pointer
    early so ``workflow_state_repository()`` can resolve its per-bucket
    engine before :func:`register_active_profile` runs — captures the
    genuine pre-write pointer with this helper, then restores it in a
    ``try``/``except`` if the create span fails. This closes the window
    the repository's own rollback cannot reach: a failure between the
    early pointer write and ``ProfileRepository.create`` (engine open,
    master-key activation) would otherwise strand the pointer at a
    profile whose record was never persisted.
    """
    from ...core._bucket_pointer_io import pointer_path

    target = pointer_path(load_settings().aeat_local_storage_root)
    if not target.is_file():
        return None
    return target.read_text(encoding=_UTF_8_ENCODING)


def restore_active_profile_pointer(prior_text: str | None) -> None:
    """Restore the active-profile pointer to a previously captured state.

    Counterpart to :func:`capture_active_profile_pointer`. A cold-start
    caller calls this from the ``except`` arm of the span it wraps: if
    there was no prior pointer the early write is removed, otherwise the
    captured bytes are written back, so a failed create leaves the
    pointer exactly as it was found.
    """
    from ...core._bucket_pointer_io import pointer_path

    target = pointer_path(load_settings().aeat_local_storage_root)
    if prior_text is None:
        if target.is_file():
            target.unlink()
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(prior_text, encoding=_UTF_8_ENCODING)


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
        translated_message="application.user_profile.errors.profile_already_exists",
        context={"profile": display_name},
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
            translated_message="application.user_profile.errors.profile_not_registered",
            context={"profile": display_name},
        )


def remove_profile_bucket_directory(profile_id: str) -> None:
    """Trash-rename and remove a profile's on-disk bucket directory.

    Used both by atomic-create rollback and by scoped config reset. The
    directory is first renamed to a trash-prefix sibling so a crashed
    removal leaves a recoverable on-disk trace, then recursively
    deleted. When the rename is refused — Windows denies renaming a
    directory whose SQLite file was only just closed — the directory is
    removed in place so the bucket does not survive the reset.

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
            raise UserProfileError(
                translated_message="application.user_profile.errors.profile_bucket_directory_removal_failed",
                context={"profile_id": profile_id, "operation": "remove_profile_bucket_directory"},
            ) from None
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

    ``secure_objects`` is an optional :class:`SecureObjectRepository` override.

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
    """Upsert one fact on the active profile, append a WorkflowEvent, and return the updated :class:`WorkflowState`.

    Args:
        state: The current workflow state.
        fact: The profile fact to upsert.
        secure_objects: Optional :class:`SecureObjectRepository` override for
            the encrypted profile store.
        schema: Optional profile schema definition override.
    """
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
    """Upsert several facts on the active profile in sequence.

    ``secure_objects`` is an optional :class:`SecureObjectRepository` override.

    Returns a :class:`WorkflowState`.
    """
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

    ``secure_objects`` is an optional :class:`SecureObjectRepository` override.

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
    """Return the active :class:`UserProfileRecord`, or ``None`` when none is selected.

    ``secure_objects`` is an optional :class:`SecureObjectRepository` override.
    """
    from ...core import resolve_active_bucket_id

    bucket_id = resolve_active_bucket_id()
    if bucket_id is None:
        return None
    service = build_lifecycle_service(bucket_id=bucket_id, secure_objects=secure_objects, schema=schema)
    try:
        return service.read(bucket_id)
    except ProfileNotFoundError:
        _log.debug("active profile selection resolved to a missing profile record; returning no active profile")
        return None


def fact_value(record: UserProfileRecord | None, path: str) -> str | None:
    """Return the live string-rendered value of one fact path on ``record``.

    Args:
        record: The :class:`UserProfileRecord` to inspect, or ``None``.
        path: Schema fact path (e.g. ``"identity.tax_id"``).

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
    from ...core import resolve_active_bucket_id

    bucket_id = resolve_active_bucket_id()
    if bucket_id is None:
        raise ProfileNotFoundError(
            translated_message="application.user_profile.errors.no_active_profile_selected",
        )
    return bucket_id


def rename_profile(
    *,
    profile_id: str,
    new_label: str,
    secure_objects: SecureObjectRepository | None = None,
    schema: ProfileSchemaDefinition | None = None,
) -> UserProfileRecord:
    """Rename a profile by updating its display label only.

    Args:
        profile_id: The immutable UUIDv4 identity of the profile to rename.
        new_label: The new display label.
        secure_objects: Optional :class:`SecureObjectRepository` override for
            the encrypted profile store.
        schema: Optional profile schema definition override.

    The profile identity (``profile_id``), bucket directory, keystore
    directory, and secure-object key are immutable and never move. A
    rename is a pure label edit across the two stores that hold a copy
    of the label - the encrypted :class:`UserProfileRecord.display_name`
    and the plaintext manifest ``label``.

    This function is a thin coordinator: the cross-store label write -
    record AND manifest - lives solely in :meth:`ProfileRepository.rename`.
    Refuses if ``new_label`` is already carried by another live profile.

    Returns the updated :class:`UserProfileRecord` after the label change
    is persisted.
    """
    repository = ProfileRepository(secure_objects=secure_objects, schema=schema)
    aggregate = repository.rename(profile_id, new_label=new_label)
    return aggregate.record


__all__ = [
    "build_lifecycle_service",
    "delete_profile_with_lifecycle_span",
    "fact_value",
    "logout_active_profile",
    "profile_create_storage_span",
    "profile_storage_session",
    "read_active_profile",
    "register_active_profile",
    "remove_active_profile",
    "rename_profile",
    "select_profile",
    "select_profile_with_lifecycle_span",
    "set_active_field",
    "set_active_fields",
]

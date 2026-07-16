"""WorkflowState-aware orchestration for profile lifecycle services.

The lifecycle service handles secure-DB persistence via a
:class:`~cadrumo.application.user_profile.ProfileLifecycleService`, which wraps a
:class:`~cadrumo.adapters.persistence.storage.SecureObjectRepository`
and emits bucket events to
:class:`~cadrumo.domain.buckets.BucketEventHistoryRepository` per profile.
This module threads active-profile selection through
:class:`~cadrumo.application.workflow.WorkflowState`, the plaintext
:class:`~cadrumo.core.BucketPointer`, and the workflow-level
:class:`~cadrumo.application.workflow.WorkflowEvent` audit stream around
those calls so CLI surfaces do not duplicate that wiring.

Profile identity is an immutable UUIDv4 minted at creation. The bucket
directory, keystore directory, secure-object key, and active-profile
pointer all key on that UUID; the operator-chosen display name is a
fully decoupled mutable label carried in the
:class:`~cadrumo.adapters.persistence.storage.bucket.BucketManifest`.

See Also:
    :class:`~cadrumo.application.user_profile.ProfileRepository`
        Sole writer for the cross-store profile aggregate.
    :func:`~cadrumo.application.user_profile.profile_create_storage_span`
        Create-time bucket session used before the encrypted record exists.
    :func:`~cadrumo.application.user_profile.profile_storage_session`
        Existing-profile bucket session used for application-owned writes.
"""

from __future__ import annotations

import secrets
from collections.abc import Iterable
from contextlib import contextmanager
from datetime import date
from typing import TYPE_CHECKING

from ...adapters.persistence.storage import BUCKET_DEK_FILENAME
from ...adapters.persistence.storage.bucket import bucket_paths, keystore_path
from ...adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ...core import BucketPointer
from ...core.config import load_settings
from ...core.errors import AeatError
from ...core.logging import get_logger
from ...core.time import now
from ...domain.user_profile import (
    ProfileNotFoundError,
    ProfileSchemaDefinition,
    UserProfileError,
    UserProfileFact,
    UserProfileRecord,
    load_user_profile_schema,
)
from . import (
    EditProfileFieldCommand,
    ProfileValidationService,
    UserProfileLifecycleRepository,
)
from ._lifecycle import ProfileLifecycleService
from ._profile_pointer_transaction import active_profile_pointer_transaction
from ._profile_repository import ProfileRepository

if TYPE_CHECKING:
    from ..workflow import WorkflowState

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
    """Construct a lifecycle service for one bucket.

    Returns a
    :class:`~cadrumo.application.user_profile.ProfileLifecycleService`.

    ``secure_objects`` is an optional
    :class:`~cadrumo.adapters.persistence.storage.SecureObjectRepository`
    override; a per-bucket store is resolved when ``None``.

    The profile aggregate AND the bucket-event-history catalogue both
    belong to the named bucket's own database. When no repository is
    injected, a single per-bucket secure-object store is resolved and
    handed to both the
    :class:`~cadrumo.application.user_profile.UserProfileLifecycleRepository`
    and the
    :class:`~cadrumo.domain.buckets.BucketEventHistoryRepository`, so the
    audit trail can never split from the records it describes. The
    prior wiring left the event-history repository on the process-global
    engine, which had no URL until an active profile existed - every
    ``register`` then crashed before its first event landed.
    """
    from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ._repository import _secure_objects_for_bucket

    schema = schema or _shared_schema()
    objects = secure_objects or _secure_objects_for_bucket(bucket_id)
    return ProfileLifecycleService(
        repository=UserProfileLifecycleRepository(bucket_id=bucket_id, objects=objects),
        validator=ProfileValidationService(schema=schema),
        events=BucketEventHistoryRepository(objects=objects),
    )


def _append_workflow_event(state: WorkflowState, *, action: str, bucket_id: str, object_id: str) -> WorkflowState:
    from ..workflow import WorkflowEvent, utc_now

    event = WorkflowEvent(action=action, bucket_id=bucket_id, object_id=object_id)
    return state.model_copy(update={"bucket_events": (*state.bucket_events, event), "updated_at": utc_now()})


@contextmanager
def profile_create_storage_span(profile_id: str):
    """Open the first-profile storage span for a bucket being created.

    The span writes the provisional :class:`~cadrumo.core.BucketPointer`
    needed to resolve the create-time bucket route, then enters
    :func:`~cadrumo.adapters.persistence.storage.activate_master_key_provider`
    with DEK enrollment enabled. If bucket setup fails before repository
    creation, or later outside the repository's own rollback boundary, the
    prior pointer bytes are restored and provisional bucket/DEK artifacts
    minted by this span are removed.
    """
    from ...adapters.persistence.storage.errors import (
        MasterKeyMaterialMissingError,
        SecretAlreadyExistsError,
    )
    from ...adapters.persistence.storage.master_key import (
        activate_master_key_provider,
        get_master_key_provider,
    )
    from ...core.config import override_settings

    root = load_settings().cadrumo_local_storage_root
    with active_profile_pointer_transaction(root) as pointer_transaction:
        paths = bucket_paths(root, profile_id)
        dek_path = keystore_path(root, profile_id) / BUCKET_DEK_FILENAME
        bucket_dir_existed = paths.bucket_dir.exists()
        keystore_dir_existed = dek_path.parent.exists()
        dek_existed = dek_path.exists()
        prior_pointer = pointer_transaction.capture()
        try:
            pointer_transaction.write(BucketPointer(bucket_id=profile_id, schema_version=1))
            provider = get_master_key_provider()
            try:
                provider.get_master_key()
            except MasterKeyMaterialMissingError:
                try:
                    provider.provision_master_key()
                except SecretAlreadyExistsError:
                    _log.debug("master key already provisioned while opening create span for profile %s", profile_id)
            with (
                override_settings(cadrumo_active_profile=profile_id),
                activate_master_key_provider(
                    provider,
                    fallback_bucket_id=profile_id,
                    allow_bucket_dek_enrollment=True,
                ),
            ):
                yield profile_id
        except BaseException as create_error:
            try:
                pointer_transaction.restore(prior_pointer)
            except BaseException as rollback_error:
                _remove_create_span_artifacts(
                    profile_id,
                    bucket_dir_existed=bucket_dir_existed,
                    keystore_dir_existed=keystore_dir_existed,
                    dek_existed=dek_existed,
                )
                raise BaseExceptionGroup(
                    "profile creation and active-pointer rollback both failed",
                    [create_error, rollback_error],
                ) from None
            _remove_create_span_artifacts(
                profile_id,
                bucket_dir_existed=bucket_dir_existed,
                keystore_dir_existed=keystore_dir_existed,
                dek_existed=dek_existed,
            )
            raise


def _remove_create_span_artifacts(
    profile_id: str,
    *,
    bucket_dir_existed: bool,
    keystore_dir_existed: bool,
    dek_existed: bool,
) -> None:
    """Best-effort cleanup of artifacts minted by a failed create span."""
    import shutil

    root = load_settings().cadrumo_local_storage_root
    if not bucket_dir_existed:
        try:
            remove_profile_bucket_directory(profile_id)
        except (AeatError, OSError):
            _log.debug("failed create-span bucket cleanup for profile %s", profile_id, exc_info=True)

    dek_path = keystore_path(root, profile_id) / BUCKET_DEK_FILENAME
    if not dek_existed and dek_path.is_file():
        try:
            dek_path.unlink()
        except OSError:
            _log.debug("failed create-span wrapped-DEK cleanup for profile %s", profile_id, exc_info=True)

    keystore_dir = dek_path.parent
    if not keystore_dir_existed and keystore_dir.exists():
        try:
            shutil.rmtree(keystore_dir)
        except OSError:
            _log.debug("failed create-span keystore cleanup for profile %s", profile_id, exc_info=True)


@contextmanager
def profile_storage_session(profile_id: str):
    """Open a storage session scoped to ``profile_id`` for application-owned writes.

    Existing-profile operations use this span to bind the active
    :class:`~cadrumo.core.BucketPointer` route and master-key session before
    repositories open encrypted bucket-local storage.
    """
    from ...adapters.persistence.storage.master_key import (
        activate_master_key_provider,
        get_master_key_provider,
    )
    from ...core.config import override_settings

    with (
        override_settings(cadrumo_active_profile=profile_id),
        activate_master_key_provider(get_master_key_provider(), fallback_bucket_id=profile_id),
    ):
        yield profile_id


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
        state: The current :class:`~cadrumo.application.workflow.WorkflowState`;
            the returned state carries the registration event appended to the
            audit stream.
        profile_id: Immutable UUIDv4 profile identity, minted by the caller
            (see :func:`~cadrumo.domain.user_profile.new_profile_id`).
        display_name: Operator-chosen label carried in the bucket manifest and
            the encrypted record; plays no role in any key or path.
        facts: Initial profile facts to persist alongside the registration.
        secure_objects: Optional
            :class:`~cadrumo.adapters.persistence.storage.SecureObjectRepository`
            override for the encrypted profile store.
        schema: Optional profile schema definition override.
        enforce_unique_tax_id: When ``True``, refuses if another live profile
            already carries the same tax id.
        routing_profile_id: When set, wires a cross-bucket routing entry so
            the new profile can inherit data from an existing bucket.

    This function is a thin
    :class:`~cadrumo.application.workflow.WorkflowState` coordinator: the
    entire cross-store write — bucket directory, manifest, encrypted
    record, AND the active-profile pointer — plus the duplicate-label
    refusal and the all-or-nothing rollback are a single unit of work
    owned by
    :meth:`~cadrumo.application.user_profile.ProfileRepository.create`.
    This function delegates that create and threads the workflow-level
    event audit stream onto the supplied
    :class:`~cadrumo.application.workflow.WorkflowState`.

    The repository owns every aggregate store write, the pointer included.
    This coordinator enters the shared pointer transaction before repository
    creation. A surrounding :func:`profile_create_storage_span` retains the
    same reentrant transaction across cold-start routing, engine activation,
    repository creation, and byte-exact failed-create rollback.
    """
    with active_profile_pointer_transaction():
        repository = ProfileRepository(secure_objects=secure_objects, schema=schema)
        repository.create(
            label=display_name,
            facts=facts,
            profile_id=profile_id,
            enforce_unique_tax_id=enforce_unique_tax_id,
            routing_profile_id=routing_profile_id,
        )
        from ..workflow import utc_now

        updated = state.model_copy(update={"updated_at": utc_now()})
        updated = _append_workflow_event(updated, action="profile.created", bucket_id=profile_id, object_id=profile_id)
        updated = _append_workflow_event(updated, action="profile.selected", bucket_id=profile_id, object_id=profile_id)
        if facts:
            keys_id = "keys:" + ",".join(sorted(f.path for f in facts if f.value is not None))
            if keys_id != "keys:":
                updated = _append_workflow_event(
                    updated,
                    action="profile.values.updated",
                    bucket_id=profile_id,
                    object_id=keys_id,
                )
        return updated


def _append_profile_activated_event(*, profile_id: str, active_profile: str | None) -> None:
    """Append a PROFILE_ACTIVATED event to the active bucket-event catalogue."""
    from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ...domain.buckets import (
        BucketEvent,
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
        ),
    )


def select_profile_with_lifecycle_span(profile_id: str) -> None:
    """Select ``profile_id`` inside an application-owned bucket session.

    Opens :func:`profile_storage_session`, delegates the pointer write to
    :func:`select_profile`, then appends the bucket-level activation event.
    """
    from ...core import resolve_active_bucket_id
    from ..workflow import workflow_state_repository

    with active_profile_pointer_transaction(), profile_storage_session(profile_id):
        workflow_state_repository().update(lambda current: select_profile(current, profile_id=profile_id))
        _append_profile_activated_event(profile_id=profile_id, active_profile=resolve_active_bucket_id())


def delete_profile_with_lifecycle_span(profile_id: str) -> UserProfileRecord:
    """Tombstone ``profile_id`` inside an application-owned bucket session.

    Returns the deleted :class:`~cadrumo.domain.user_profile.UserProfileRecord`
    from :meth:`~cadrumo.application.user_profile.ProfileRepository.delete`.
    """
    with active_profile_pointer_transaction(), profile_storage_session(profile_id):
        aggregate = ProfileRepository().delete(profile_id)
    return aggregate.record


def reactivate_profile_with_lifecycle_span(profile_id: str) -> UserProfileRecord:
    """Restore a tombstoned ``profile_id`` inside an application-owned bucket session.

    Symmetric inverse of :func:`delete_profile_with_lifecycle_span`.
    Returns the reactivated :class:`~cadrumo.domain.user_profile.UserProfileRecord`
    from :meth:`~cadrumo.application.user_profile.ProfileRepository.reactivate`.
    """
    with profile_storage_session(profile_id):
        aggregate = ProfileRepository().reactivate(profile_id)
    return aggregate.record


def logout_active_profile() -> str | None:
    """Close the active storage session, clear its pointer, and return its profile.

    The pointer transaction is acquired before session teardown to preserve the
    project-wide lock order. Session close and ContextVar eviction complete
    before pointer mutation, so an unexpected teardown failure cannot report a
    successful pointer-only logout. Provider bookkeeping remains owned by the
    provider context and unwinds idempotently when that context exits.
    """
    from ...adapters.persistence.storage import close_active_bucket_session
    from ...core import resolve_active_bucket_id

    with active_profile_pointer_transaction() as pointer_transaction:
        before = resolve_active_bucket_id()
        close_active_bucket_session()
        pointer_transaction.clear()
        return before


def refuse_duplicate_label(
    display_name: str,
) -> None:
    """Refuse a ``profile create`` when a live profile carries the label.

    Display names (labels) are unique among live profiles, compared
    case-insensitively. A bucket manifest already carrying ``display_name``
    is an existence claim; recreating in place would silently mix new
    profile data into the existing bucket, so the create is refused and
    the operator is routed to ``switch`` or ``delete``. The live-label
    lookup is :func:`~cadrumo.application.workflow.read_profile_bucket`.
    """
    from ..workflow import read_profile_bucket

    if read_profile_bucket(display_name) is None:
        return
    raise ProfileAlreadyRegisteredError(
        translated_message="application.user_profile.errors.profile_already_exists",
        context={"profile": display_name},
    )


def require_registered_label(display_name: str) -> None:
    """Refuse a ``profile edit`` when no live profile carries the label.

    Symmetric to :func:`refuse_duplicate_label`: ``profile edit``
    re-runs the wizard against an *existing* profile, so an unknown
    label is an operator error, not an implicit create. The registered
    label authority is
    :func:`~cadrumo.application.workflow.read_profile_bucket`.
    """
    from ..workflow import read_profile_bucket

    if read_profile_bucket(display_name) is None:
        raise ProfileNotFoundError(
            translated_message="application.user_profile.errors.profile_not_registered",
            context={"profile": display_name},
        )


def remove_profile_bucket_directory(profile_id: str) -> None:
    """Trash-rename and remove a profile's on-disk bucket directory.

    Used both by atomic-create rollback and by
    :func:`~cadrumo.application.config_reset.reset_config`. The
    directory is first renamed to a trash-prefix sibling so a crashed
    removal leaves a recoverable on-disk trace, then recursively
    deleted. When the rename is refused - Windows denies renaming a
    directory whose SQLite file was only just closed - the directory is
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

    from ...adapters.persistence.storage.master_key import current_active_bucket_session
    from ...adapters.persistence.storage.sql.engine import dispose_engines_for_bucket

    root = load_settings().cadrumo_local_storage_root
    target = bucket_paths(root, profile_id).bucket_dir
    if not target.exists():
        return
    # Dispose this bucket's cached SQLAlchemy engine before removing the
    # directory. The engine pool holds open SQLite file handles; on Windows an
    # undisposed handle makes the crash-safe rename below fail (forcing the
    # in-place rmtree fallback), and a cached engine bound to this bucket would
    # otherwise serve stale connections to a deleted-then-recreated file. The
    # engine re-creates lazily on next use, so the bucket-scoped dispose is safe
    # and leaves other buckets' engines untouched.
    dispose_engines_for_bucket(profile_id)
    # The process-wide dispose above does not reach a still-open
    # BucketSession's own cached engine handle (acquire_engine caches per
    # session, not only in the process-wide pool). A caller that removes this
    # bucket's directory while its session is the currently active one — the
    # config-reset PROFILE/ALL path unlocks and resets within the same
    # session — must invalidate that session-level handle too, or the next
    # storage access through the session reuses a handle bound to a directory
    # that no longer exists.
    active_session = current_active_bucket_session()
    if active_session is not None and active_session.bucket_id == profile_id:
        active_session.invalidate_engine()
    gc.collect()
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

    ``secure_objects`` is an optional
    :class:`~cadrumo.adapters.persistence.storage.SecureObjectRepository`
    override.

    Raises :class:`ProfileNotFoundError` if the profile does not
    already exist; registration is the explicit path
    (:func:`register_active_profile`).

    This function is a thin
    :class:`~cadrumo.application.workflow.WorkflowState` coordinator: the
    profile load + integrity check + active-profile pointer write live
    solely in
    :meth:`~cadrumo.application.user_profile.ProfileRepository.select`.
    """
    with active_profile_pointer_transaction():
        repository = ProfileRepository(secure_objects=secure_objects, schema=schema)
        repository.select(profile_id)  # raises ProfileNotFoundError if missing
        from ..workflow import utc_now

        updated = state.model_copy(update={"updated_at": utc_now()})
        return _append_workflow_event(updated, action="profile.selected", bucket_id=profile_id, object_id=profile_id)


def set_active_field(
    state: WorkflowState,
    fact: UserProfileFact,
    *,
    secure_objects: SecureObjectRepository | None = None,
    schema: ProfileSchemaDefinition | None = None,
) -> WorkflowState:
    """Upsert one fact on the active profile and append a workflow event.

    Args:
        state: The current workflow state.
        fact: The profile fact to upsert.
        secure_objects: Optional
            :class:`~cadrumo.adapters.persistence.storage.SecureObjectRepository`
            override for the encrypted profile store.
        schema: Optional profile schema definition override.

    Returns:
        The updated :class:`~cadrumo.application.workflow.WorkflowState`.
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
        ),
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

    ``secure_objects`` is an optional
    :class:`~cadrumo.adapters.persistence.storage.SecureObjectRepository`
    override.

    Returns a :class:`~cadrumo.application.workflow.WorkflowState`.
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

    ``secure_objects`` is an optional
    :class:`~cadrumo.adapters.persistence.storage.SecureObjectRepository`
    override.

    The bucket directory and
    :class:`~cadrumo.adapters.persistence.storage.bucket.BucketManifest`
    stay on disk so audit and history reads can still resolve the
    tombstoned bucket; selecting the tombstoned profile via
    :func:`select_profile` will raise because the record is no longer
    live.

    This function is a thin
    :class:`~cadrumo.application.workflow.WorkflowState` coordinator: the
    cross-store tombstone (encrypted-record tombstone + active-profile
    pointer clear) lives solely in
    :meth:`~cadrumo.application.user_profile.ProfileRepository.delete`.
    """
    with active_profile_pointer_transaction():
        profile_id = _require_active(state)
        repository = ProfileRepository(secure_objects=secure_objects, schema=schema)
        repository.delete(profile_id)
        from ..workflow import utc_now

        updated = state.model_copy(update={"updated_at": utc_now()})
        return _append_workflow_event(updated, action="profile.tombstoned", bucket_id=profile_id, object_id=profile_id)


def fact_value(record: UserProfileRecord | None, path: str) -> str | None:
    """Return the live string-rendered value of one fact path on ``record``.

    Args:
        record: The :class:`~cadrumo.domain.user_profile.UserProfileRecord`
            to inspect, or ``None``.
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

    Reads through :func:`~cadrumo.core.resolve_active_bucket_id`, whose
    current precedence chain is settings override, then plaintext
    :class:`~cadrumo.core.BucketPointer`. The ``state`` argument keeps the
    workflow-coordinator call shape; it is not a fallback source.
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
        secure_objects: Optional
            :class:`~cadrumo.adapters.persistence.storage.SecureObjectRepository`
            override for the encrypted profile store.
        schema: Optional profile schema definition override.

    The profile identity (``profile_id``), bucket directory, keystore
    directory, and secure-object key are immutable and never move. A
    rename is a pure label edit across the two stores that hold a copy
    of the label - the encrypted
    :class:`~cadrumo.domain.user_profile.UserProfileRecord`
    ``display_name`` and the plaintext
    :class:`~cadrumo.adapters.persistence.storage.bucket.BucketManifest`
    ``label``.

    This function is a thin coordinator: the cross-store label write -
    record AND manifest - lives solely in
    :meth:`~cadrumo.application.user_profile.ProfileRepository.rename`.
    Refuses if ``new_label`` is already carried by another live profile.

    Returns the updated
    :class:`~cadrumo.domain.user_profile.UserProfileRecord` after the label
    change is persisted.
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
    "reactivate_profile_with_lifecycle_span",
    "register_active_profile",
    "remove_active_profile",
    "rename_profile",
    "select_profile",
    "select_profile_with_lifecycle_span",
    "set_active_field",
    "set_active_fields",
]

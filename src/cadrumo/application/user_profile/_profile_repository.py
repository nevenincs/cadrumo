"""Sequence a logical profile's changes across its durable stores.

A logical profile fragments across a bucket directory, a plaintext
:class:`~cadrumo.adapters.persistence.storage.bucket.BucketManifest`, an
encrypted :class:`~cadrumo.domain.user_profile.UserProfileRecord` row in a
per-bucket SQLite database, and an append-only
:class:`~cadrumo.domain.buckets.BucketEventHistoryRepository`.
The :class:`ProfileRepository` owns cross-store aggregate ordering. The shared
reentrant active-profile pointer transaction coordinates same-root pointer
access, while the core pointer API owns byte-level persistence. Creation writes
the manifest, pointer, then encrypted record and events. Deletion conditionally
clears an active pointer before writing the manifest and encrypted-record
tombstones. :meth:`ProfileRepository.load` runs
:func:`~cadrumo.application.user_profile._integrity.verify_profile_integrity`
so a profile whose stores have drifted surfaces the drift instead of
being served silently.

Application orchestration
(:func:`~cadrumo.application.user_profile.register_active_profile`,
:func:`~cadrumo.application.user_profile.remove_active_profile`,
:func:`~cadrumo.application.user_profile.select_profile`) and the CLI
``config profile`` verbs delegate aggregate sequencing here. Profile-health
inspection and repair remain separate responsibilities.

See Also:
    :class:`~cadrumo.application.user_profile.ProfileLifecycleService`
        Bucket-local record and lifecycle-event service composed by this
        repository.
    :func:`~cadrumo.application.workflow.read_profile_bucket`
        Manifest scan used by label lookup and live-profile surfaces.
    :class:`~cadrumo.application.user_profile._aggregate.ProfileAggregate`
        In-memory cross-store profile aggregate returned by this repository.
"""

from __future__ import annotations

import secrets
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, ValidationError

from ...adapters.persistence.storage import (
    BUCKET_DEK_FILENAME,
    BUCKETS_DIRNAME,
    SecureObjectRepository,
    StorageValidationError,
    dispose_engines_for_bucket,
)
from ...adapters.persistence.storage.bucket import (
    BucketKeySchedule,
    BucketManifest,
    ManifestKdfParams,
    bucket_paths,
    keystore_path,
    manifest_path,
    provision_bucket_directory,
    read_manifest,
    write_manifest,
)
from ...adapters.persistence.storage.master_key import KdfParams
from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import BucketPointer
from ...core.config import load_settings
from ...core.errors import CadrumoError
from ...core.identity import ProfileId
from ...core.logging import get_logger
from ...core.redaction import redact_for_cli_output
from ...core.time import now
from ...domain.user_profile import (
    ProfileNotFoundError,
    ProfileSchemaDefinition,
    UserProfileFact,
    UserProfileStatus,
    UserProfileValidationError,
    new_profile_id,
)
from . import (
    CompleteSetupCommand,
    ReactivateProfileCommand,
    RegisterProfileCommand,
    RemoveProfileCommand,
    RenameProfileCommand,
)
from ._aggregate import ProfileAggregate
from ._integrity import verify_profile_integrity
from ._profile_pointer_transaction import ActiveProfilePointerTransaction, active_profile_pointer_transaction
from ._repository import UserProfileLifecycleRepository, _refresh_output_language_hint

if TYPE_CHECKING:
    from ._lifecycle import ProfileLifecycleService

_log = get_logger(__name__)

TAX_ID_FACT_PATH = "identity.tax_id"
"""Profile-fact path carrying the taxpayer's Spanish NIF / NIE / CIF."""


def _canonical_tax_id(facts: Sequence[UserProfileFact]) -> str | None:
    """Return the canonical (upper-cased, trimmed) tax id from ``facts``.

    Returns :data:`None` when no ``identity.tax_id`` fact is present or
    it carries no value, so a profile without a tax id never collides.
    """
    for fact in facts:
        if fact.path == TAX_ID_FACT_PATH and fact.value is not None:
            text = str(fact.value).strip().upper()
            if text:
                return text
    return None


def _default_kdf_params() -> ManifestKdfParams:
    """Return the OWASP-baseline Argon2id parameters for a fresh bucket.

    A profile created through this repository is not yet passphrase-
    enrolled; the manifest still records the KDF parameter window the
    bucket will be enrolled under so a future cost-bump is
    non-breaking. The salt is freshly minted per bucket.
    """
    return KdfParams.default().to_manifest_params()


class ProfileSummary(BaseModel):
    """A typed one-row summary of a registered profile.

    Returned by :meth:`ProfileRepository.list`; carries only the
    plaintext-manifest projection (UUID, label, lifecycle status) so a
    listing never needs to unlock an encrypted bucket.
    """

    model_config = _STRICT_FROZEN

    profile_id: ProfileId
    label: str = Field(min_length=1, max_length=160)
    status: UserProfileStatus


class ProfileRepository:
    """Sequence profile aggregate mutations across their durable stores.

    The repository composes the existing lower-level pieces — the
    secure-record
    :class:`~cadrumo.application.user_profile.UserProfileLifecycleRepository`,
    :func:`~cadrumo.adapters.persistence.storage.bucket.provision_bucket_directory`,
    the :class:`~cadrumo.adapters.persistence.storage.bucket.BucketManifest`
    IO helpers, and the shared reentrant active-profile pointer transaction.
    The transaction coordinates same-root access and delegates pointer byte IO
    to the core API.
    """

    def __init__(
        self,
        *,
        root: Path | None = None,
        secure_objects: SecureObjectRepository | None = None,
        schema: ProfileSchemaDefinition | None = None,
    ) -> None:
        """Construct the repository.

        Args:
            root: Cadrumo local storage root (the parent of ``buckets/``).
                When ``None`` the value is resolved from the
                pydantic-settings :class:`~cadrumo.core.config.Settings`
                object.
            secure_objects: Optional injected secure-object repository.
                When supplied, every encrypted-store read and write is
                routed through it instead of a per-bucket engine
                resolved from settings. This is the dependency-injection
                seam real-adapter tests use to bind a single SQLite
                engine; production code leaves it ``None``.
            schema: Optional profile schema definition handed to the
                lifecycle service. ``None`` resolves the canonical
                process-shared schema.
        """
        self._root = root if root is not None else load_settings().cadrumo_local_storage_root
        self._secure_objects = secure_objects
        self._schema = schema

    @property
    def root(self) -> Path:
        return self._root

    def _rollback_failed_create(
        self,
        *,
        profile_id: str,
        pointer_transaction: ActiveProfilePointerTransaction,
        rollback_pointer: bytes | None,
    ) -> tuple[BaseException, ...]:
        """Attempt every create rollback action and return all failures."""
        rollback_errors: list[BaseException] = []
        try:
            dispose_engines_for_bucket(profile_id)
        except BaseException as dispose_error:
            rollback_errors.append(dispose_error)
        try:
            self._remove_bucket_directory(profile_id)
        except BaseException as cleanup_error:
            rollback_errors.append(cleanup_error)
        try:
            pointer_transaction.restore(rollback_pointer)
        except BaseException as restore_error:
            rollback_errors.append(restore_error)
        return tuple(rollback_errors)

    # ── create ─────────────────────────────────────────────────────

    def create(
        self,
        *,
        label: str,
        facts: Sequence[UserProfileFact] = (),
        profile_id: str | None = None,
        enforce_unique_tax_id: bool = True,
        routing_profile_id: str | None = None,
        status: UserProfileStatus = UserProfileStatus.ACTIVE,
    ) -> ProfileAggregate:
        """Create a new profile as a cross-store unit of work.

        ``status`` selects the birth lifecycle state: ``ACTIVE`` (the
        default) for a fully-registered profile, ``SETUP_INCOMPLETE`` for
        the interactive setup flow's early mint (the record is live and
        its tax id reserved, but modelo work is refused until
        :meth:`complete_setup` lands). The plaintext manifest mirror and
        the encrypted record are minted at the same status so the two
        stores agree from birth; a tombstoned birth is refused by
        :class:`RegisterProfileCommand`.

        ``enforce_unique_tax_id`` (default :data:`True`) refuses a create
        whose tax id is already carried by a live profile — a fresh
        ``config profile create`` must not split one taxpayer's filing
        history across two profiles. ``config profile duplicate`` and
        ``config profile import`` legitimately reproduce an existing
        profile's tax id and pass :data:`False`.

        Mints a fresh UUID identity (unless ``profile_id`` is supplied
        for a caller that already minted one), then enters the repository
        root's shared active-profile pointer transaction before doing work:

        1. Stage the bucket directory + plaintext manifest. A directory
           with no manifest is detectable, reclaimable garbage — a
           rolled-back create; the manifest write is the point a profile
           becomes registered.
        2. Write the active-profile pointer. The per-bucket SQLAlchemy
           engine resolves its URL from the pointer chain, so the
           pointer must precede the encrypted-record write.
        3. Commit the encrypted
           :class:`~cadrumo.domain.user_profile.UserProfileRecord` (the
           SQLite transaction).

        The exact repository-entry pointer bytes are captured before the first
        repository write. A canonical cold-create caller normally already holds
        the same-root transaction and has written a provisional pointer, so the
        repository acquisition is a nested rollback layer. If a
        :class:`BaseException` occurs after staging begins, the repository
        independently attempts engine disposal, bucket cleanup, and exact
        pointer restoration while ownership remains held. It re-raises the
        original failure when rollback succeeds; otherwise a
        :class:`BaseExceptionGroup` retains the original followed by every
        rollback failure. A process interruption can still leave a complete
        provisional pointer for health inspection and repair.

        Args:
            label: Operator-visible display name for the new profile.
            facts: Initial profile fact sequence. Defaults to empty.
            profile_id: Optional explicit UUID. When ``None``, a fresh
                UUID is minted.
            enforce_unique_tax_id: When ``True`` (default), refuses a
                create whose tax id is already carried by a live profile.
            routing_profile_id: Optional routing assertion; must match
                ``profile_id`` when supplied.
            status: Birth lifecycle state — ``ACTIVE`` (default) for a
                complete registration, ``SETUP_INCOMPLETE`` for the setup
                flow's early mint. Written to both the manifest mirror and
                the encrypted record so the two stores agree from birth.

        Returns:
            The assembled
            :class:`~cadrumo.application.user_profile._aggregate.ProfileAggregate`.

        Raises:
            ProfileNotFoundError: If the profile already carries a
                manifest (it is already a registered profile).
            CadrumoError: If an error occurs during the all-or-nothing write.
            OSError: If a filesystem error occurs during directory staging.
            UserProfileValidationError: If the routing profile id does not
                match the resolved profile id.
            ValidationError: If the encrypted record fails schema validation.
            BaseExceptionGroup: If creation fails and one or more rollback
                actions also fail.
        """
        with active_profile_pointer_transaction(self._root) as pointer_transaction:
            resolved_id = profile_id if profile_id is not None else new_profile_id()
            if routing_profile_id is not None and routing_profile_id.strip() != resolved_id:
                raise UserProfileValidationError(
                    translated_message="application.user_profile.errors.profile_create_route_mismatch",
                    context={"route": routing_profile_id, "profile": resolved_id},
                )
            paths = bucket_paths(self._root, resolved_id)
            rollback_pointer = pointer_transaction.capture()

            # Refuse before any store write: a label already carried by a
            # live profile, or a UUID that already carries a registered
            # manifest, is a refusal. No store was written, so there is
            # nothing to roll back.
            if manifest_path(paths).is_file():
                raise ProfileNotFoundError(
                    translated_message="application.user_profile.errors.profile_manifest_already_registered",
                    context={"profile": resolved_id, "bucket_dir": paths.bucket_dir},
                )
            self._refuse_duplicate_label(label)
            if enforce_unique_tax_id:
                self._refuse_duplicate_tax_id(facts)

            kdf_params = _default_kdf_params()
            created_at = now()
            bucket_dek_path = keystore_path(self._root, resolved_id) / BUCKET_DEK_FILENAME
            if not bucket_dek_path.is_file():
                # The create span mints the per-bucket wrapped DEK before this
                # repository writes the manifest. A missing DEK here is a torn
                # create, not a valid schedule — fail closed rather than register
                # a bucket whose only key schedule is BUCKET_DEK_V1 with no DEK.
                raise StorageValidationError(
                    f"bucket {resolved_id!r} has no wrapped DEK at {bucket_dek_path}; "
                    "the create span must mint the per-bucket DEK before manifest registration.",
                )
            key_schedule = BucketKeySchedule.BUCKET_DEK_V1
            manifest_schema_version = 2

            try:
                # Step 1: stage the bucket directory tree + the plaintext
                # manifest — the point at which the bucket becomes a registered
                # profile. A bare directory may already exist: a cold-start
                # caller's workflow-state engine creates ``<bucket>/db/`` when
                # it opens before this create runs. A directory with no manifest
                # is not yet a registered profile, so it is reclaimed as
                # staging rather than refused.
                self._ensure_bucket_directory(resolved_id)
                write_manifest(
                    bucket_paths(self._root, resolved_id),
                    BucketManifest(
                        bucket_id=resolved_id,
                        label=label,
                        created_at=created_at,
                        last_unlocked_at=None,
                        kdf_params=kdf_params,
                        recovery_enrolled=False,
                        key_schedule=key_schedule,
                        schema_version=manifest_schema_version,
                        status=status,
                    ),
                )

                # Step 2: write the active-profile pointer. The per-bucket
                # engine resolves its URL from the pointer chain.
                pointer_transaction.write(BucketPointer(bucket_id=resolved_id, schema_version=1))

                # Step 3: commit the encrypted record and its bucket events
                # via the lifecycle service — schema validation and the
                # PROFILE_BUCKET_CREATED / PROFILE_VALUES_UPDATED audit
                # events are the service's single-store concern; this
                # repository owns the cross-store sequencing and the
                # rollback around it.
                result = self._lifecycle_service(resolved_id).register(
                    RegisterProfileCommand(
                        profile_id=resolved_id,
                        display_name=label,
                        facts=tuple(facts),
                        status=status,
                    ),
                )
                record = result.profile
            except BaseException as create_error:
                rollback_errors = self._rollback_failed_create(
                    profile_id=resolved_id,
                    pointer_transaction=pointer_transaction,
                    rollback_pointer=rollback_pointer,
                )
                if rollback_errors:
                    raise BaseExceptionGroup(
                        "profile creation and repository rollback failed",
                        [create_error, *rollback_errors],
                    ) from None
                raise

            return ProfileAggregate(
                profile_id=resolved_id,
                label=label,
                created_at=created_at,
                kdf_params=kdf_params,
                recovery_enrolled=False,
                manifest_schema_version=manifest_schema_version,
                record=record,
                status=record.status,
            )

    # ── load ───────────────────────────────────────────────────────

    def load(self, profile_id: str) -> ProfileAggregate:
        """Assemble the aggregate from every store; verify integrity.

        Reads the plaintext manifest and the encrypted record, runs
        :func:`~cadrumo.application.user_profile._integrity.verify_profile_integrity`
        to confirm the directory, the manifest, and the record all
        agree on the UUID, the lifecycle status, and the display label,
        then builds the
        :class:`~cadrumo.application.user_profile._aggregate.ProfileAggregate`.

        Args:
            profile_id: The UUID of the profile to load.

        Returns:
            The assembled
            :class:`~cadrumo.application.user_profile._aggregate.ProfileAggregate`
            for the profile.

        Raises:
            ProfileNotFoundError: If the bucket directory or manifest
                is absent.
        """
        paths = bucket_paths(self._root, profile_id)
        if not manifest_path(paths).is_file():
            raise ProfileNotFoundError(
                translated_message="application.user_profile.errors.profile_manifest_missing",
                context={"profile": profile_id, "bucket_dir": paths.bucket_dir},
            )
        manifest = read_manifest(paths)
        record = self._lifecycle_repository(profile_id).load(profile_id)

        verify_profile_integrity(
            profile_id=profile_id,
            directory_name=paths.bucket_dir.name,
            manifest_bucket_id=manifest.bucket_id,
            record_profile_id=record.profile_id,
            manifest_status=manifest.status.value,
            record_status=record.status.value,
            manifest_label=manifest.label,
            record_display_name=record.display_name,
        )

        return ProfileAggregate(
            profile_id=profile_id,
            label=manifest.label,
            created_at=manifest.created_at,
            kdf_params=manifest.kdf_params,
            recovery_enrolled=manifest.recovery_enrolled,
            manifest_schema_version=manifest.schema_version,
            record=record,
            status=record.status,
        )

    # ── save ───────────────────────────────────────────────────────

    def save(self, aggregate: ProfileAggregate) -> None:
        """Persist changes to the aggregate across its physical stores.

        The manifest projection (``label``, ``kdf_params``,
        ``recovery_enrolled``) and the encrypted record are both
        re-written so the two label copies never drift. The
        active-profile pointer is not touched — selecting a profile is
        a distinct operation.
        """
        paths = bucket_paths(self._root, aggregate.profile_id)
        current_manifest = read_manifest(paths)
        write_manifest(
            paths,
            BucketManifest(
                bucket_id=aggregate.profile_id,
                label=aggregate.label,
                created_at=aggregate.created_at,
                last_unlocked_at=current_manifest.last_unlocked_at,
                kdf_params=aggregate.kdf_params,
                recovery_enrolled=aggregate.recovery_enrolled,
                idle_lock_minutes=current_manifest.idle_lock_minutes,
                key_schedule=current_manifest.key_schedule,
                schema_version=aggregate.manifest_schema_version,
                status=aggregate.status,
            ),
        )
        self._lifecycle_repository(aggregate.profile_id).save(aggregate.record)

    # ── rename ─────────────────────────────────────────────────────

    def rename(self, profile_id: str, *, new_label: str) -> ProfileAggregate:
        """Change a profile's operator-visible label across its stores.

        Profile identity is an immutable UUID, so a rename is a pure
        metadata edit: only the label moves, in the two stores that
        hold a copy of it - the encrypted
        :class:`~cadrumo.domain.user_profile.UserProfileRecord`
        ``display_name`` and the plaintext manifest ``label``. There
        is no directory move and no re-key.

        Both writes happen here, inside the sole writer: the lifecycle
        service updates the record and emits ``PROFILE_RENAMED``, then
        the manifest label projection is rewritten. ``load`` runs the
        cross-store integrity check first, so a drifted profile raises
        :class:`~cadrumo.application.user_profile._integrity.ProfileIntegrityError`
        rather than being relabelled in a torn state.

        Args:
            profile_id: The UUID of the profile to rename.
            new_label: The new operator-visible display name.

        Returns:
            The updated
            :class:`~cadrumo.application.user_profile._aggregate.ProfileAggregate`
            with the new label.

        Raises:
            ProfileAlreadyRegisteredError: If ``new_label`` is already
                carried by another live profile.
            UserProfileValidationError: If ``new_label`` is blank after
                stripping.
        """
        from ..workflow import read_profile_bucket
        from ._orchestration import ProfileAlreadyRegisteredError

        aggregate = self.load(profile_id)
        trimmed = new_label.strip()
        if not trimmed:
            from ...domain.user_profile import UserProfileValidationError

            raise UserProfileValidationError(
                translated_message="application.user_profile.errors.profile_label_blank",
            )

        if trimmed.casefold() != aggregate.label.casefold():
            clash = read_profile_bucket(trimmed, root=self._root)
            if clash is not None and clash.bucket_id != profile_id:
                raise ProfileAlreadyRegisteredError(
                    translated_message="application.user_profile.errors.profile_already_exists",
                    context={"profile": trimmed},
                )

        result = self._lifecycle_service(profile_id).rename(
            RenameProfileCommand(profile_id=profile_id, target_display_name=trimmed),
        )
        renamed_record = result.profile
        # The repository is the sole writer of the manifest: rewrite the
        # label projection so the manifest and the record never drift.
        paths = bucket_paths(self._root, profile_id)
        manifest = read_manifest(paths)
        write_manifest(paths, manifest.model_copy(update={"label": trimmed}))
        return aggregate.model_copy(update={"label": trimmed, "record": renamed_record})

    # ── delete ─────────────────────────────────────────────────────

    def delete(self, profile_id: str) -> ProfileAggregate:
        """Tombstone a profile via its lifecycle status.

        ``delete`` is a soft removal: the encrypted record is
        tombstoned and re-saved; the bucket directory and manifest are
        left intact so audit and history reads still resolve.

        The repository enters its root's active-profile pointer transaction
        before loading the aggregate. Two or three stores then mutate, in an
        order chosen so every torn intermediate fails closed:

        1. The pointer is read and cleared only when it targets this profile.
           The read and conditional clear share one transaction, so another
           cooperating writer cannot select a different profile between them.
           A crash here leaves a still-live record with no active pointer —
           benign, the operator simply re-selects.
        2. The plaintext manifest ``status`` is mirrored to
           ``tombstoned`` BEFORE the record tombstone. A crash between
           this write and the record tombstone leaves a manifest saying
           ``tombstoned`` over a still-live record. That is the safe
           direction: the profile immediately drops off every live
           surface (``list`` / ``switch`` / name-uniqueness all read
           the manifest), and the encrypted record remains available to repair
           machinery.
           The reverse order — record first — would leave a manifest
           saying ``active`` over a tombstoned record, re-opening the
           leak.
        3. The encrypted record is tombstoned last.

        ``load`` runs the cross-store integrity check, which compares
        the manifest status against the record status, so a profile
        left in the step-2/step-3 drift state by a crash raises
        :class:`~cadrumo.application.user_profile._integrity.ProfileIntegrityError`
        on the next load - reclaiming a drifted profile is the ``repair``
        surface's domain.

        Args:
            profile_id: The UUID of the profile to tombstone.

        Returns:
            The updated :class:`ProfileAggregate` with tombstoned status.
        """
        with active_profile_pointer_transaction(self._root) as pointer_transaction:
            aggregate = self.load(profile_id)
            pointer = pointer_transaction.read()
            if pointer is not None and pointer.bucket_id == profile_id:
                pointer_transaction.clear()
            # Step 2: mirror the tombstone onto the plaintext manifest
            # before the record tombstone. The manifest scan excludes this
            # profile from every live operator surface without unlocking
            # the encrypted bucket; doing this first means a crash before
            # the record write fails closed (manifest tombstoned, record
            # still loadable for repair) instead of re-opening the leak.
            paths = bucket_paths(self._root, profile_id)
            manifest = read_manifest(paths)
            write_manifest(
                paths,
                manifest.model_copy(update={"status": UserProfileStatus.TOMBSTONED}),
            )
            # Step 3: tombstone the encrypted record.
            result = self._lifecycle_service(profile_id).remove(RemoveProfileCommand(profile_id=profile_id))
            tombstoned_record = result.profile
            return aggregate.model_copy(update={"record": tombstoned_record, "status": tombstoned_record.status})

    # ── reactivate ─────────────────────────────────────────────────

    def reactivate(self, profile_id: str) -> ProfileAggregate:
        """Restore a tombstoned profile to active status; symmetric inverse of :meth:`delete`.

        ``reactivate`` never opened by ``delete``'s counterpart before:
        it is a pure lifecycle-status flip back to active. The bucket
        directory, manifest, and encrypted record were all left intact
        by the soft tombstone, so no directory or key-schedule
        provisioning happens here.

        The write order is the mirror image of :meth:`delete`'s own
        crash-safety reasoning: the encrypted record is reactivated
        FIRST, the plaintext manifest mirror SECOND. A crash between
        the two leaves the manifest saying ``tombstoned`` over a
        now-active record — the safe direction, because the manifest
        scan (``list`` / ``switch`` / name-uniqueness) still excludes
        the profile from every live surface until the manifest write
        lands. The reverse order would leave the manifest claiming
        ``active`` over a record the encrypted-store lifecycle service
        still refuses to reactivate-confirm, re-opening the same
        exposure window :meth:`delete` avoids.

        Args:
            profile_id: The UUID of the profile to reactivate.

        Returns:
            The updated :class:`ProfileAggregate` with active status.

        Raises:
            ProfileNotFoundError: If the profile is not currently tombstoned,
                or if the bucket directory or manifest is absent.
        """
        aggregate = self.load(profile_id)
        # Step 1: reactivate the encrypted record first (mirrors delete's
        # step ordering in reverse).
        result = self._lifecycle_service(profile_id).reactivate(
            ReactivateProfileCommand(profile_id=profile_id),
        )
        reactivated_record = result.profile
        # Step 2: mirror the reactivation onto the plaintext manifest.
        paths = bucket_paths(self._root, profile_id)
        manifest = read_manifest(paths)
        write_manifest(
            paths,
            manifest.model_copy(update={"status": UserProfileStatus.ACTIVE}),
        )
        return aggregate.model_copy(update={"record": reactivated_record, "status": reactivated_record.status})

    # ── complete_setup ─────────────────────────────────────────────

    def complete_setup(self, profile_id: str) -> ProfileAggregate:
        """Transition a ``SETUP_INCOMPLETE`` profile to ``ACTIVE`` across both stores.

        The one-way exit from the interactive setup flow's early mint,
        run at the flow's final commit strictly after flow-scope
        validation and fact persistence. The write order mirrors
        :meth:`reactivate`: the encrypted record is completed FIRST
        (emitting ``PROFILE_SETUP_COMPLETED``), the plaintext manifest
        mirror SECOND. A crash between the two leaves the manifest saying
        ``setup_incomplete`` over a now-active record — the safe
        direction, because the readiness gate and every live-surface scan
        still treat the profile as not-yet-workable until the manifest
        write lands, exactly the exposure window :meth:`delete` avoids in
        reverse. The record's own
        :meth:`~cadrumo.domain.user_profile.UserProfileRecord.complete_setup`
        refuses any non-incomplete source, so an active or tombstoned
        profile cannot be laundered through this arm.

        Args:
            profile_id: The UUID of the setup-incomplete profile.

        Returns:
            The updated :class:`ProfileAggregate` with active status.

        Raises:
            UserProfileValidationError: If the record is not currently
                setup-incomplete.
            ProfileNotFoundError: If the bucket directory or manifest is
                absent.
        """
        aggregate = self.load(profile_id)
        # Step 1: complete the encrypted record first (mirrors reactivate).
        result = self._lifecycle_service(profile_id).complete_setup(
            CompleteSetupCommand(profile_id=profile_id),
        )
        completed_record = result.profile
        # Step 2: mirror the completion onto the plaintext manifest.
        paths = bucket_paths(self._root, profile_id)
        manifest = read_manifest(paths)
        write_manifest(
            paths,
            manifest.model_copy(update={"status": UserProfileStatus.ACTIVE}),
        )
        return aggregate.model_copy(update={"record": completed_record, "status": completed_record.status})

    # ── select ─────────────────────────────────────────────────────

    def select(self, profile_id: str) -> ProfileAggregate:
        """Make a registered profile the active one.

        Enters the repository root's active-profile pointer transaction before
        loading the aggregate, then holds it through integrity and tombstone
        validation, output-language-hint refresh, and the final pointer write.
        A profile whose stores have drifted is never selected.

        A tombstoned profile is not a selectable profile: ``delete`` is
        a soft removal that retains the bucket for audit, but the
        profile has left the live surface. Selecting it is refused with
        the same :class:`ProfileNotFoundError` class as an unknown
        profile so the operator cannot unknowingly work inside a
        deleted profile.

        Args:
            profile_id: The UUID of the profile to activate.

        Returns:
            The :class:`ProfileAggregate` for the newly active profile.

        Raises:
            ProfileNotFoundError: If the profile is not registered, or
                is registered but tombstoned.
        """
        with active_profile_pointer_transaction(self._root) as pointer_transaction:
            aggregate = self.load(profile_id)
            if aggregate.status is UserProfileStatus.TOMBSTONED:
                raise ProfileNotFoundError(
                    translated_message="application.user_profile.errors.profile_tombstoned_not_selectable",
                    context={"profile": profile_id},
                )
            _refresh_output_language_hint(bucket_id=profile_id, record=aggregate.record)
            pointer_transaction.write(BucketPointer(bucket_id=profile_id, schema_version=1))
            return aggregate

    # ── list ───────────────────────────────────────────────────────

    def list(self) -> Sequence[ProfileSummary]:
        """Return a typed summary for every registered profile.

        Scans ``<root>/buckets/*/manifest.toml`` — never unlocks an
        encrypted bucket. The lifecycle status reported is the manifest
        ``status`` mirror, kept in lockstep with the encrypted record
        by every :class:`ProfileRepository` write. Tombstoned profiles
        are included so callers that need the full inventory (repair,
        audit) see them; live-surface callers filter on ``status``.

        Each element is a :class:`ProfileSummary`; live label lookups
        use :func:`~cadrumo.application.workflow.read_profile_bucket`.
        """
        buckets_root = self._root / BUCKETS_DIRNAME
        if not buckets_root.is_dir():
            return ()
        summaries: list[ProfileSummary] = []
        for entry in buckets_root.iterdir():
            if not entry.is_dir():
                continue
            try:
                paths = bucket_paths(self._root, entry.name)
            except ValueError:
                _log.debug(
                    "profile inventory skipped invalid bucket directory name bucket_id=%s",
                    redact_for_cli_output(entry.name),
                    exc_info=True,
                )
                continue
            if not manifest_path(paths).is_file():
                continue
            try:
                manifest = read_manifest(paths)
            except (StorageValidationError, ValidationError, OSError) as exc:
                # A torn or obsolete manifest (e.g. missing the lifecycle
                # `status` field added by a later schema version) must not
                # prevent the inventory scan that uniqueness guards and
                # operator-facing list rely on. Skip it with a warning so
                # the operator can repair the bucket separately; a fresh
                # profile create against a different taxpayer remains
                # reachable. The narrow scan in `list_profile_bucket_scan_issues`
                # surfaces the torn bucket on diagnostic surfaces.
                _log.warning(
                    "profile inventory: skipping unreadable bucket manifest bucket_id=%s error_type=%s",
                    redact_for_cli_output(entry.name),
                    type(exc).__name__,
                )
                _log.debug("profile inventory skipped unreadable bucket manifest", exc_info=True)
                continue
            summaries.append(
                ProfileSummary(
                    profile_id=manifest.bucket_id,
                    label=manifest.label,
                    status=manifest.status,
                ),
            )
        summaries.sort(key=lambda row: row.profile_id)
        return tuple(summaries)

    # ── helpers ────────────────────────────────────────────────────

    def _refuse_duplicate_label(self, label: str) -> None:
        """Refuse a create whose label is already carried by a live profile.

        Labels are unique among live profiles, compared
        case-insensitively. The refusal fires before any store write,
        so there is no staged state to roll back.
        """
        from ..workflow import read_profile_bucket
        from ._orchestration import ProfileAlreadyRegisteredError

        if read_profile_bucket(label, root=self._root) is None:
            return
        raise ProfileAlreadyRegisteredError(
            translated_message="application.user_profile.errors.profile_already_exists",
            context={"profile": label},
        )

    def _refuse_duplicate_tax_id(self, facts: Sequence[UserProfileFact]) -> None:
        """Refuse a create whose tax id is already carried by a live profile.

        The Spanish tax id (NIF / NIE / CIF) identifies the taxpayer; two
        profiles carrying the same id are an operator mistake — a second
        profile for the same person silently splits that taxpayer's
        filing history. The refusal scans every registered profile's
        encrypted record, compares the canonical (upper-cased, trimmed)
        tax id, and fires before any store write so there is nothing to
        roll back. An unreadable profile is skipped with an operator-visible
        warning so one torn bucket does not prevent a different taxpayer from
        registering. Duplicate detection still fires against all readable
        profiles in the scan.
        """
        new_tax_id = _canonical_tax_id(facts)
        if new_tax_id is None:
            return
        from ._orchestration import ProfileAlreadyRegisteredError

        for summary in self.list():
            # A tombstoned profile has left the live surface; its tax id
            # is free to reuse, exactly as its display name is.
            if summary.status is UserProfileStatus.TOMBSTONED:
                continue
            try:
                from ._orchestration import profile_storage_session

                with profile_storage_session(summary.profile_id):
                    aggregate = self.load(summary.profile_id)
            except (CadrumoError, OSError, ValidationError) as exc:
                # One torn / unreadable bucket must not prevent an operator
                # from registering a completely different taxpayer. Emit an
                # operator-visible warning and continue scanning the remaining
                # readable profiles so duplicate detection still fires for them.
                _log.warning(
                    "tax-id uniqueness scan: skipping unreadable profile profile_id=%s error_type=%s; "
                    "proceeding with scan against readable profiles",
                    redact_for_cli_output(summary.profile_id),
                    type(exc).__name__,
                )
                _log.debug("tax-id uniqueness scan skipped unreadable profile", exc_info=True)
                continue
            existing_tax_id = _canonical_tax_id(aggregate.record.facts)
            if existing_tax_id is not None and existing_tax_id == new_tax_id:
                raise ProfileAlreadyRegisteredError(
                    translated_message="application.user_profile.errors.duplicate_tax_id",
                    context={"tax_id": new_tax_id, "profile": summary.label},
                )

    def _lifecycle_repository(self, profile_id: str) -> UserProfileLifecycleRepository:
        """Return a secure-record repository bound to ``profile_id``'s db.

        When an injected
        :class:`~cadrumo.adapters.persistence.storage.SecureObjectRepository`
        was supplied at construction it is reused; otherwise the repository
        resolves the per-bucket engine from settings.
        """
        return UserProfileLifecycleRepository(bucket_id=profile_id, objects=self._secure_objects)

    def _lifecycle_service(self, profile_id: str) -> ProfileLifecycleService:
        """Return a lifecycle service bound to ``profile_id``'s stores.

        The lifecycle service owns the single-store concern of the
        encrypted-record write plus its schema validation and the
        PROFILE_BUCKET_CREATED / PROFILE_TOMBSTONED audit events; this
        repository composes it inside the cross-store unit of work.
        It is created by
        :func:`~cadrumo.application.user_profile._orchestration.build_lifecycle_service`.
        """
        from ._orchestration import build_lifecycle_service

        return build_lifecycle_service(
            bucket_id=profile_id,
            secure_objects=self._secure_objects,
            schema=self._schema,
        )

    def _ensure_bucket_directory(self, profile_id: str) -> None:
        """Materialise the bucket directory tree, tolerating a bare pre-existing one.

        ``provision_bucket_directory`` is fail-closed — it raises if the
        bucket directory already exists. A cold-start caller's
        workflow-state engine, however, creates ``<bucket>/db/`` when it
        opens before this create runs. The "already a registered
        profile" guard upstream has already confirmed there is no
        manifest, so a directory present here is bare staging: this
        helper provisions afresh when nothing exists, and otherwise
        idempotently completes the ``db/ blobs/ audit/`` subtree.
        """
        paths = bucket_paths(self._root, profile_id)
        if not paths.bucket_dir.exists():
            provision_bucket_directory(self._root, profile_id)
            return
        for subdir in (paths.db_dir, paths.blobs_dir, paths.audit_dir):
            subdir.mkdir(parents=True, exist_ok=True)

    def _remove_bucket_directory(self, profile_id: str) -> None:
        """Trash-rename and remove a profile's on-disk bucket directory.

        Used by the ``create`` unit-of-work rollback. The directory is
        first renamed to a trash-prefixed sibling so a crashed removal
        leaves a recoverable trace, then recursively deleted. When the
        rename is refused — Windows denies renaming a directory whose
        SQLite file was only just closed — the directory is removed in
        place. A removal failure propagates so the create rollback can preserve
        it alongside the original create failure.
        """
        import gc

        target = bucket_paths(self._root, profile_id).bucket_dir
        if not target.exists():
            return
        trash = target.with_name(f".trash-{profile_id}-{secrets.token_hex(4)}")
        try:
            target.rename(trash)
        except OSError:
            gc.collect()
            self._remove_tree_best_effort(target, reason="create_rollback_in_place")
            return
        self._remove_tree_best_effort(trash, reason="create_rollback_trash")

    def _remove_tree_best_effort(self, target: Path, *, reason: str) -> None:
        """Remove a directory, logging and re-raising ``OSError``.

        The historical name is retained; the create rollback aggregates a
        cleanup failure with the original create failure.
        """
        import shutil

        try:
            shutil.rmtree(target)
        except OSError as exc:
            _log.debug(
                "profile bucket cleanup failed reason=%s target=%s error_type=%s",
                reason,
                redact_for_cli_output(str(target)),
                type(exc).__name__,
                exc_info=True,
            )
            raise


__all__ = ["ProfileRepository", "ProfileSummary"]

"""The single, sole writer of a logical profile's physical stores.

A logical profile fragments across a bucket directory, a plaintext
``manifest.toml``, an encrypted :class:`UserProfileRecord` row in a
per-bucket SQLite database, and an append-only bucket-event history.
Before this repository, every CLI handler and application service
wrote whichever stores it remembered; consistency was by convention
and a failure mid-sequence left a half-live profile.

:class:`ProfileRepository` makes "touch every store" structural.
``create`` and ``delete`` are cross-store units of work: the
filesystem directory + manifest are staged first (a directory with no
secure-object row is detectable, reclaimable garbage), the encrypted
record commits next inside the SQLite transaction, the active-profile
pointer moves last. On any failure the staged filesystem state is
rolled back. ``load`` runs :func:`verify_profile_integrity` so a
profile whose stores have drifted surfaces the drift instead of being
served silently.

Application orchestration (``register_active_profile``,
``remove_active_profile``, ``select_profile``) and the CLI ``config
profile`` verbs delegate their store writes here; there is exactly one
implementation of the cross-store profile write.
"""

from __future__ import annotations

import secrets
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, ValidationError

from ...adapters.persistence.storage import BUCKET_DEK_FILENAME, BUCKETS_DIRNAME
from ...adapters.persistence.storage.bucket import (
    BucketKeySchedule,
    BucketLifecycleStatus,
    BucketManifest,
    ManifestKdfParams,
    bucket_paths,
    keystore_path,
    manifest_path,
    provision_bucket_directory,
    read_manifest,
    write_manifest,
)
from ...adapters.persistence.storage.errors import StorageValidationError
from ...adapters.persistence.storage.master_key import KdfParams
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import BucketPointer, pointer_path, write_pointer
from ...core.config import load_settings
from ...core.errors import AeatError
from ...core.external_constants import UTF_8_ENCODING as _UTF_8_ENCODING
from ...core.identity import ProfileId
from ...core.logging import get_logger
from ...core.redaction import redact_for_cli_output
from ...core.time import now
from ...domain.user_profile import (
    ProfileNotFoundError,
    ProfileSchemaDefinition,
    UserProfileFact,
    UserProfileStatus,
    new_profile_id,
)
from ...domain.user_profile._errors import UserProfileValidationError
from . import RegisterProfileCommand, RemoveProfileCommand, RenameProfileCommand
from ._aggregate import ProfileAggregate
from ._integrity import verify_profile_integrity
from ._repository import UserProfileLifecycleRepository

if TYPE_CHECKING:
    from ._lifecycle import ProfileLifecycleService

_log = get_logger(__name__)

_TAX_ID_FACT_PATH = "identity.tax_id"
"""Profile-fact path carrying the taxpayer's Spanish NIF / NIE / CIF."""


def _canonical_tax_id(facts: Sequence[UserProfileFact]) -> str | None:
    """Return the canonical (upper-cased, trimmed) tax id from ``facts``.

    Returns :data:`None` when no ``identity.tax_id`` fact is present or
    it carries no value, so a profile without a tax id never collides.
    """
    for fact in facts:
        if fact.path == _TAX_ID_FACT_PATH and fact.value is not None:
            text = str(fact.value).strip().upper()
            if text:
                return text
    return None


def _manifest_status_for(status: UserProfileStatus) -> BucketLifecycleStatus:
    """Map the encrypted-record lifecycle status to its manifest mirror.

    The two enums carry identical string values; the mapping is by
    value so a new lifecycle state added to one enum but not the other
    surfaces here as a :class:`ValueError` (the enum lookup rejects an
    unknown value) rather than silently mismatching.
    """
    return BucketLifecycleStatus(status.value)


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
    """The sole writer of a logical profile's cross-store physical state.

    The repository composes the existing lower-level pieces — the
    secure-record :class:`UserProfileLifecycleRepository`, the bucket
    directory provisioner, the manifest IO, and the active-profile
    pointer IO. It is the single place those writes happen.
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
            root: AEAT local storage root (the parent of ``buckets/``).
                When ``None`` the value is resolved from the
                pydantic-settings :class:`Settings` object.
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
        self._root = root if root is not None else load_settings().aeat_local_storage_root
        self._secure_objects = secure_objects
        self._schema = schema

    @property
    def root(self) -> Path:
        return self._root

    # ── create ─────────────────────────────────────────────────────

    def create(
        self,
        *,
        label: str,
        facts: Sequence[UserProfileFact] = (),
        profile_id: str | None = None,
        enforce_unique_tax_id: bool = True,
        routing_profile_id: str | None = None,
    ) -> ProfileAggregate:
        """Create a new profile as a cross-store unit of work.

        ``enforce_unique_tax_id`` (default :data:`True`) refuses a create
        whose tax id is already carried by a live profile — a fresh
        ``config profile create`` must not split one taxpayer's filing
        history across two profiles. ``config profile duplicate`` and
        ``config profile import`` legitimately reproduce an existing
        profile's tax id and pass :data:`False`.

        Mints a fresh UUID identity (unless ``profile_id`` is supplied
        for a caller that already minted one), then performs the
        all-or-nothing write — every store write, the active-profile
        pointer included, is inside this single unit of work:

        1. Stage the bucket directory + plaintext manifest. A directory
           with no manifest is detectable, reclaimable garbage — a
           rolled-back create; the manifest write is the point a profile
           becomes registered.
        2. Write the active-profile pointer. The per-bucket SQLAlchemy
           engine resolves its URL from the pointer chain, so the
           pointer must precede the encrypted-record write.
        3. Commit the encrypted :class:`UserProfileRecord` (the SQLite
           transaction).

        The pre-create active-profile pointer is captured here, before
        the first store write, so a failure at any step rolls back the
        staged directory + manifest AND restores the pointer to exactly
        its pre-create state. No caller writes the pointer; the
        ``missing_profile_record`` torn state (pointer aimed at a
        profile with no record) is unreachable because the pointer
        write and the record write are one unit of work.

        Args:
            label: Operator-visible display name for the new profile.
            facts: Initial profile fact sequence. Defaults to empty.
            profile_id: Optional explicit UUID. When ``None``, a fresh
                UUID is minted.
            enforce_unique_tax_id: When ``True`` (default), refuses a
                create whose tax id is already carried by a live profile.
            routing_profile_id: Optional routing assertion; must match
                ``profile_id`` when supplied.

        Returns:
            The assembled :class:`ProfileAggregate`.

        Raises:
            ProfileNotFoundError: If the profile already carries a
                manifest (it is already a registered profile).
            AeatError: If an error occurs during the all-or-nothing write.
            OSError: If a filesystem error occurs during directory staging.
            UserProfileValidationError: If the routing profile id does not
                match the resolved profile id.
            ValidationError: If the encrypted record fails schema validation.
        """
        resolved_id = profile_id if profile_id is not None else new_profile_id()
        if routing_profile_id is not None and routing_profile_id.strip() != resolved_id:
            raise UserProfileValidationError(
                translated_message="application.user_profile.errors.profile_create_route_mismatch",
                context={"route": routing_profile_id, "profile": resolved_id},
            )
        paths = bucket_paths(self._root, resolved_id)
        # Capture the genuine pre-create pointer before any store write
        # so the rollback restores it exactly.
        rollback_pointer_text = self._read_pointer_text()

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

        # Step 1: stage the bucket directory tree + the plaintext
        # manifest — the point at which the bucket becomes a registered
        # profile. A bare directory may already exist: a cold-start
        # caller's workflow-state engine creates ``<bucket>/db/`` when
        # it opens before this create runs. A directory with no manifest
        # is not yet a registered profile, so it is reclaimed as
        # staging rather than refused.
        self._ensure_bucket_directory(resolved_id)
        try:
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
                    status=BucketLifecycleStatus.ACTIVE,
                ),
            )

            # Step 2: write the active-profile pointer. The per-bucket
            # engine resolves its URL from the pointer chain.
            write_pointer(self._root, BucketPointer(bucket_id=resolved_id, schema_version=1))

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
                ),
            )
            record = result.profile
        except (AeatError, OSError, ValidationError):
            # Roll back every store this create touched: the staged
            # directory + manifest are removed and the pointer is
            # restored to its pre-create state. The per-bucket
            # SQLAlchemy engine opened by the record write is disposed
            # first: on Windows an open SQLite handle refuses the
            # directory removal.
            from ...adapters.persistence.storage.sql.engine import dispose_engine

            dispose_engine()
            self._remove_bucket_directory(resolved_id)
            self._restore_pointer_text(rollback_pointer_text)
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
        :func:`verify_profile_integrity` to confirm the directory, the
        manifest, and the record all agree on the UUID, the lifecycle
        status, and the display label, then builds the
        :class:`ProfileAggregate`.

        Args:
            profile_id: The UUID of the profile to load.

        Returns:
            The assembled :class:`ProfileAggregate` for the profile.

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
                status=_manifest_status_for(aggregate.status),
            ),
        )
        self._lifecycle_repository(aggregate.profile_id).save(aggregate.record)

    # ── rename ─────────────────────────────────────────────────────

    def rename(self, profile_id: str, *, new_label: str) -> ProfileAggregate:
        """Change a profile's operator-visible label across its stores.

        Profile identity is an immutable UUID, so a rename is a pure
        metadata edit: only the label moves, in the two stores that
        hold a copy of it — the encrypted :class:`UserProfileRecord`
        ``display_name`` and the plaintext manifest ``label``. There is
        no directory move and no re-key.

        Both writes happen here, inside the sole writer: the lifecycle
        service updates the record and emits ``PROFILE_RENAMED``, then
        the manifest label projection is rewritten. ``load`` runs the
        cross-store integrity check first, so a drifted profile raises
        :class:`ProfileIntegrityError` rather than being relabelled in
        a torn state.

        Args:
            profile_id: The UUID of the profile to rename.
            new_label: The new operator-visible display name.

        Returns:
            The updated :class:`ProfileAggregate` with the new label.

        Raises:
            ProfileAlreadyRegisteredError: If ``new_label`` is already
                carried by another live profile.
            UserProfileValidationError: If ``new_label`` is blank after
                stripping.
        """
        from ..workflow._profile_bucket_scan import read_profile_bucket
        from ._orchestration import ProfileAlreadyRegisteredError

        aggregate = self.load(profile_id)
        trimmed = new_label.strip()
        if not trimmed:
            from ...domain.user_profile._errors import UserProfileValidationError

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

        Three stores mutate, in an order chosen so every torn
        intermediate fails closed:

        1. The active-profile pointer is cleared first. A crash here
           leaves a still-live record with no active pointer — benign,
           the operator simply re-selects.
        2. The plaintext manifest ``status`` is mirrored to
           ``tombstoned`` BEFORE the record tombstone. A crash between
           this write and the record tombstone leaves a manifest saying
           ``tombstoned`` over a still-live record. That is the safe
           direction: the profile immediately drops off every live
           surface (``list`` / ``switch`` / name-uniqueness all read
           the manifest), and the record is still loadable for repair.
           The reverse order — record first — would leave a manifest
           saying ``active`` over a tombstoned record, re-opening the
           leak.
        3. The encrypted record is tombstoned last.

        ``load`` runs the cross-store integrity check, which compares
        the manifest status against the record status, so a profile
        left in the step-2/step-3 drift state by a crash raises
        :class:`ProfileIntegrityError` on the next load — reclaiming a
        drifted profile is the ``repair`` surface's domain.

        Args:
            profile_id: The UUID of the profile to tombstone.

        Returns:
            The updated :class:`ProfileAggregate` with tombstoned status.
        """
        aggregate = self.load(profile_id)
        if self._active_pointer_targets(profile_id):
            self._clear_pointer()
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
            manifest.model_copy(update={"status": BucketLifecycleStatus.TOMBSTONED}),
        )
        # Step 3: tombstone the encrypted record.
        result = self._lifecycle_service(profile_id).remove(RemoveProfileCommand(profile_id=profile_id))
        tombstoned_record = result.profile
        return aggregate.model_copy(update={"record": tombstoned_record, "status": tombstoned_record.status})

    # ── select ─────────────────────────────────────────────────────

    def select(self, profile_id: str) -> ProfileAggregate:
        """Make a registered profile the active one.

        Loads and integrity-checks the aggregate — a profile whose
        stores have drifted is never selected — then writes the
        active-profile pointer. The pointer is the only store this
        mutates; identity and lifecycle metadata are untouched.

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
        aggregate = self.load(profile_id)
        if aggregate.status is UserProfileStatus.TOMBSTONED:
            raise ProfileNotFoundError(
                translated_message="application.user_profile.errors.profile_tombstoned_not_selectable",
                context={"profile": profile_id},
            )
        write_pointer(self._root, BucketPointer(bucket_id=profile_id, schema_version=1))
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

        Each element is a :class:`ProfileSummary`.
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
                # A torn or legacy manifest (e.g. missing the lifecycle
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
                    status=UserProfileStatus(manifest.status.value),
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
        from ..workflow._profile_bucket_scan import read_profile_bucket
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
            except (AeatError, OSError, ValidationError) as exc:
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

        When an injected :class:`SecureObjectRepository` was supplied at
        construction it is reused; otherwise the repository resolves the
        per-bucket engine from settings.
        """
        return UserProfileLifecycleRepository(bucket_id=profile_id, objects=self._secure_objects)

    def _lifecycle_service(self, profile_id: str) -> ProfileLifecycleService:
        """Return a lifecycle service bound to ``profile_id``'s stores.

        The lifecycle service owns the single-store concern of the
        encrypted-record write plus its schema validation and the
        PROFILE_BUCKET_CREATED / PROFILE_TOMBSTONED audit events; this
        repository composes it inside the cross-store unit of work.
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
        place. Removal is best-effort: a residual directory must not
        mask the original failure being re-raised, and a directory
        with no secure-object row is detectable, reclaimable garbage.
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
        """Remove a directory without masking the caller's original failure."""
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

    def _read_pointer_text(self) -> str | None:
        """Return the raw active-profile pointer text, or ``None`` if absent."""
        target = pointer_path(self._root)
        if not target.is_file():
            return None
        return target.read_text(encoding=_UTF_8_ENCODING)

    def _restore_pointer_text(self, prior_text: str | None) -> None:
        """Restore the active-profile pointer to a previously captured state.

        A rolled-back ``create`` must leave the pointer exactly as it
        was found: if there was no pointer it is removed, otherwise its
        prior bytes are written back.
        """
        target = pointer_path(self._root)
        if prior_text is None:
            if target.is_file():
                target.unlink()
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(prior_text, encoding=_UTF_8_ENCODING)

    def _active_pointer_targets(self, profile_id: str) -> bool:
        """Return whether the active-profile pointer aims at ``profile_id``."""
        from ...core import read_pointer

        pointer = read_pointer(self._root)
        return pointer is not None and pointer.bucket_id == profile_id

    def _clear_pointer(self) -> None:
        """Remove the active-profile pointer file if present."""
        target = pointer_path(self._root)
        if target.is_file():
            target.unlink()


__all__ = ["ProfileRepository", "ProfileSummary"]

"""Canonical lifecycle service for the schema-driven user-profile backend.

This service is the single sanctioned write path for live user-profile
values. It routes every register / edit / remove / duplicate / list /
read operation through the secure-DB repository and the schema-aware
validation service. CLI thin adapters and downstream consumers call
this surface; no caller should construct :class:`UserProfileRecord`
aggregates or touch the secure repository directly. Every mutating
operation emits a typed bucket event to :class:`BucketEventHistoryRepository`.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from datetime import date, datetime
from typing import Literal

from ...core.errors import BaseSeverity
from ...domain.buckets import (
    BucketEvent,
    BucketEventHistoryRepository,
    BucketEventObjectType,
    BucketEventType,
    append_bucket_event,
    derive_bucket_event_id,
)
from ...domain.buckets._protocols import BucketEventHistoryRepositoryProtocol
from ...domain.user_profile import (
    ProfileAlreadyExistsError,
    ProfileNotFoundError,
    ProfileSchemaValidationError,
    UserProfileFact,
    UserProfileRecord,
    UserProfileStatus,
)
from ...domain.user_profile._values import utc_now
from . import (
    DuplicateProfileCommand,
    EditProfileFieldCommand,
    EditProfileSectionCommand,
    ProfileLifecycleResult,
    ProfileListing,
    ProfileListResult,
    RegisterProfileCommand,
    RemoveProfileCommand,
    RenameProfileCommand,
)
from ._repository import UserProfileLifecycleRepository
from ._validation import ProfileValidationService

_PROFILE_LIFECYCLE_ACTOR = "aeat.application.user_profile"
_PROFILE_ALREADY_EXISTS_MESSAGE = "profile already exists in the active bucket"
_PROFILE_TOMBSTONED_RENAME_MESSAGE = "tombstoned profile cannot be renamed"
_PROFILE_TOMBSTONED_DUPLICATE_MESSAGE = "tombstoned profile cannot be duplicated"
_PROFILE_SCHEMA_VALIDATION_MESSAGE = "profile facts failed schema validation"


def _paths_payload(facts: tuple[UserProfileFact, ...]) -> dict[str, str]:
    """Return bounded path summary payload for a bucket event."""
    paths = sorted({fact.path for fact in facts})
    encoded = "\n".join(paths).encode("utf-8")
    return {"path_count": str(len(paths)), "paths_sha256": hashlib.sha256(encoded).hexdigest()}


class ProfileLifecycleService:
    """Schema-validated, secure-DB-backed user-profile lifecycle service."""

    def __init__(
        self,
        *,
        repository: UserProfileLifecycleRepository,
        validator: ProfileValidationService,
        events: BucketEventHistoryRepositoryProtocol | None = None,
    ) -> None:
        self._repository = repository
        self._validator = validator
        self._events = events or BucketEventHistoryRepository()

    # ── register / list / read ─────────────────────────────────────

    def register(self, command: RegisterProfileCommand) -> ProfileLifecycleResult:
        """Register a new active profile aggregate.

        Returns a :class:`ProfileLifecycleResult`.
        """
        if self._repository.exists(command.profile_id):
            raise _profile_already_exists_error(
                profile_id=command.profile_id,
                bucket_id=self._repository.bucket_id,
            )
        self._reject_invalid(command.profile_id, command.facts)
        now = utc_now()
        record = UserProfileRecord(
            schema_id=self._validator.schema.id,
            schema_version=self._validator.schema.version,
            profile_id=command.profile_id,
            display_name=command.display_name,
            facts=command.facts,
            created_at=now,
            updated_at=now,
        )
        self._repository.save(record)
        self._emit_event(
            event_type=BucketEventType.PROFILE_BUCKET_CREATED,
            object_id=record.profile_id,
            occurred_at=now,
            payload={"display_name": record.display_name},
        )
        if record.facts:
            self._emit_event(
                event_type=BucketEventType.PROFILE_VALUES_UPDATED,
                object_id=record.profile_id,
                occurred_at=now,
                payload=_paths_payload(record.facts),
            )
        return ProfileLifecycleResult(profile=record, applied_at=now)

    def read(self, profile_id: str) -> UserProfileRecord:
        """Return the live :class:`UserProfileRecord` aggregate or raise :class:`ProfileNotFoundError`."""
        return self._repository.load(profile_id)

    def list_profiles(self) -> ProfileListResult:
        """List every profile currently visible in the active bucket.

        Returns a :class:`ProfileListResult` with all non-tombstoned profiles.
        """
        listings: list[ProfileListing] = []
        for record in self._iter_profiles():
            listings.append(
                ProfileListing(
                    profile_id=record.profile_id,
                    display_name=record.display_name,
                    status=record.status,
                    created_at=record.created_at,
                    updated_at=record.updated_at,
                ),
            )
        listings.sort(key=lambda row: row.profile_id)
        return ProfileListResult(profiles=tuple(listings))

    # ── edit / remove / duplicate ──────────────────────────────────

    def edit_field(self, command: EditProfileFieldCommand) -> ProfileLifecycleResult:
        """Upsert one effective-dated fact into a profile aggregate and return a :class:`ProfileLifecycleResult`."""
        record = self._repository.load(command.profile_id)
        new_fact = UserProfileFact(
            path=command.path,
            value=command.value,
            valid_from=command.valid_from,
            valid_to=command.valid_to,
            source=command.source,
        )
        next_facts = self._merge_facts(record.facts, (new_fact,))
        self._reject_invalid(command.profile_id, next_facts)
        result = self._save_updated(record, next_facts)
        event_type = (
            BucketEventType.PROFILE_VALUES_CLEARED if new_fact.value is None else BucketEventType.PROFILE_VALUES_UPDATED
        )
        self._emit_event(
            event_type=event_type,
            object_id=record.profile_id,
            occurred_at=result.applied_at,
            payload={"path": new_fact.path},
        )
        return result

    def edit_section(self, command: EditProfileSectionCommand) -> ProfileLifecycleResult:
        """Replace every fact in one schema section with the supplied facts.

        Returns a :class:`ProfileLifecycleResult`.
        """
        record = self._repository.load(command.profile_id)
        retained = tuple(fact for fact in record.facts if not fact.path.startswith(f"{command.section_key}."))
        merged = self._merge_facts(retained, command.facts)
        self._reject_invalid(command.profile_id, merged)
        result = self._save_updated(record, merged)
        self._emit_event(
            event_type=BucketEventType.PROFILE_VALUES_UPDATED,
            object_id=record.profile_id,
            occurred_at=result.applied_at,
            payload={"section": command.section_key, **_paths_payload(command.facts)},
        )
        return result

    def remove(self, command: RemoveProfileCommand) -> ProfileLifecycleResult:
        """Tombstone the live root. Immutable filing snapshots are retained.

        Returns a :class:`ProfileLifecycleResult` with the tombstoned profile.
        """
        record = self._repository.load(command.profile_id)
        tombstoned = record.tombstone()
        self._repository.save(tombstoned)
        self._emit_event(
            event_type=BucketEventType.PROFILE_TOMBSTONED,
            object_id=tombstoned.profile_id,
            occurred_at=tombstoned.updated_at,
        )
        return ProfileLifecycleResult(profile=tombstoned, applied_at=tombstoned.updated_at)

    def rename(self, command: RenameProfileCommand) -> ProfileLifecycleResult:
        """Update a live profile's display label and return a :class:`ProfileLifecycleResult`.

        Profile identity is an immutable UUID, so a rename touches only
        the operator-visible ``display_name``: the record is loaded,
        its label updated, and re-saved under the same secure-object
        key. There is no re-key, no directory move, and no rollback
        machinery. Refuses if the profile is tombstoned. Emits
        ``PROFILE_RENAMED`` carrying the prior label so the audit trail
        records the relabel.

        The orchestration layer updates the parallel copy of the label
        held in the plaintext bucket manifest; the service contract is
        record-only.
        """
        source = self._repository.load(command.profile_id)
        if source.status is not UserProfileStatus.ACTIVE:
            raise _profile_tombstoned_error(command.profile_id, action="rename")
        if command.target_display_name == source.display_name:
            return ProfileLifecycleResult(profile=source, applied_at=utc_now())
        now = utc_now()
        target = source.model_copy(
            update={
                "display_name": command.target_display_name,
                "updated_at": now,
            },
        )
        self._repository.save(target)
        self._emit_event(
            event_type=BucketEventType.PROFILE_RENAMED,
            object_id=target.profile_id,
            occurred_at=now,
            payload={"previous_display_name": source.display_name},
        )
        return ProfileLifecycleResult(profile=target, applied_at=now)

    def duplicate(self, command: DuplicateProfileCommand) -> ProfileLifecycleResult:
        """Copy an existing live profile under a new id and display name.

        Returns a :class:`ProfileLifecycleResult` with the newly created
        duplicate profile.
        """
        if self._repository.exists(command.target_profile_id):
            raise _profile_already_exists_error(
                profile_id=command.target_profile_id,
                bucket_id=self._repository.bucket_id,
            )
        source = self._repository.load(command.source_profile_id)
        if source.status is not UserProfileStatus.ACTIVE:
            raise _profile_tombstoned_error(command.source_profile_id, action="duplicate")
        now = utc_now()
        target = source.model_copy(
            update={
                "profile_id": command.target_profile_id,
                "display_name": command.target_display_name,
                "created_at": now,
                "updated_at": now,
                "removed_at": None,
                "status": UserProfileStatus.ACTIVE,
            },
        )
        self._repository.save(target)
        self._emit_event(
            event_type=BucketEventType.PROFILE_DUPLICATED,
            object_id=target.profile_id,
            occurred_at=now,
            payload={"source_profile_id": source.profile_id},
        )
        return ProfileLifecycleResult(profile=target, applied_at=now)

    # ── helpers ────────────────────────────────────────────────────

    def _reject_invalid(self, profile_id: str, facts: Iterable[UserProfileFact]) -> None:
        report = self._validator.validate_facts(profile_id, facts)
        blocking = [issue for issue in report.issues if issue.severity is BaseSeverity.ERROR]
        if blocking:
            raise ProfileSchemaValidationError(
                _PROFILE_SCHEMA_VALIDATION_MESSAGE,
                context={
                    "profile_id": profile_id,
                    "issue_count": len(blocking),
                    "issue_codes": tuple(issue.code for issue in blocking),
                    "issue_paths": tuple(issue.path for issue in blocking if issue.path is not None),
                    "schema_version": report.schema_version,
                },
                translated_message="application.user_profile.errors.lifecycle_schema_validation_failed",
            )

    def _save_updated(
        self,
        record: UserProfileRecord,
        facts: tuple[UserProfileFact, ...],
    ) -> ProfileLifecycleResult:
        now = utc_now()
        updated = record.model_copy(update={"facts": facts, "updated_at": now})
        self._repository.save(updated)
        return ProfileLifecycleResult(profile=updated, applied_at=now)

    @staticmethod
    def _merge_facts(
        base: tuple[UserProfileFact, ...],
        incoming: tuple[UserProfileFact, ...],
    ) -> tuple[UserProfileFact, ...]:
        merged: dict[tuple[str, date | None, date | None], UserProfileFact] = {
            (fact.path, fact.valid_from, fact.valid_to): fact for fact in base
        }
        for fact in incoming:
            merged[(fact.path, fact.valid_from, fact.valid_to)] = fact
        return tuple(merged.values())

    def _emit_event(
        self,
        *,
        event_type: BucketEventType,
        object_id: str,
        occurred_at: datetime,
        payload: dict[str, str] | None = None,
    ) -> None:
        payload_body = dict(payload or {})
        event = BucketEvent(
            event_id=derive_bucket_event_id(
                bucket_id=self._repository.bucket_id,
                event_type=event_type,
                occurred_at=occurred_at,
                actor=_PROFILE_LIFECYCLE_ACTOR,
                object_type=BucketEventObjectType.PROFILE,
                object_id=object_id,
                payload=payload_body,
            ),
            bucket_id=self._repository.bucket_id,
            event_type=event_type,
            occurred_at=occurred_at,
            actor=_PROFILE_LIFECYCLE_ACTOR,
            object_type=BucketEventObjectType.PROFILE,
            object_id=object_id,
            payload_version=1,
            payload=payload_body,
        )
        self._events.save(append_bucket_event(self._events.load(), event))

    def _iter_profiles(self) -> Iterable[UserProfileRecord]:
        """Yield every live profile record by delegating to the repository.

        Walking the secure-object index lives on
        :class:`UserProfileLifecycleRepository.iter_records` so the
        service consumes a public surface instead of reaching for the
        repository's private secure-object reference.
        """
        return self._repository.iter_records()


def _profile_already_exists_error(*, profile_id: str, bucket_id: str) -> ProfileAlreadyExistsError:
    return ProfileAlreadyExistsError(
        _PROFILE_ALREADY_EXISTS_MESSAGE,
        context={"profile_id": profile_id, "bucket_id": bucket_id},
        translated_message="application.user_profile.errors.lifecycle_profile_already_exists",
    )


def _profile_tombstoned_error(profile_id: str, *, action: Literal["rename", "duplicate"]) -> ProfileNotFoundError:
    if action == "rename":
        return ProfileNotFoundError(
            _PROFILE_TOMBSTONED_RENAME_MESSAGE,
            context={"profile_id": profile_id, "action": action},
            translated_message="application.user_profile.errors.lifecycle_profile_tombstoned_rename",
        )
    if action == "duplicate":
        return ProfileNotFoundError(
            _PROFILE_TOMBSTONED_DUPLICATE_MESSAGE,
            context={"profile_id": profile_id, "action": action},
            translated_message="application.user_profile.errors.lifecycle_profile_tombstoned_duplicate",
        )


__all__ = ["ProfileLifecycleService"]

"""Canonical lifecycle service for the schema-driven user-profile backend.

This service is the single sanctioned write path for live user-profile
values. It routes every register / edit / remove / rename / reactivate /
read operation through the secure-DB repository and the schema-aware
validation service. CLI thin adapters and downstream consumers call
this surface; no caller should construct :class:`UserProfileRecord`
aggregates or touch the secure repository directly. Every mutating
operation emits a typed bucket event to :class:`BucketEventHistoryRepository`.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date, datetime
from typing import Literal

from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...core.errors import BaseSeverity
from ...core.hashing import sha256_hex
from ...domain.buckets import (
    BucketEvent,
    BucketEventHistoryRepositoryProtocol,
    BucketEventObjectType,
    BucketEventType,
    build_bucket_event,
    emit_bucket_event,
    emit_bucket_events,
)
from ...domain.user_profile import (
    ProfileAlreadyExistsError,
    ProfileNotFoundError,
    ProfileSchemaValidationError,
    UserProfileFact,
    UserProfileRecord,
    UserProfileStatus,
    utc_now,
)
from . import (
    CompleteSetupCommand,
    EditProfileFieldCommand,
    ProfileLifecycleResult,
    ReactivateProfileCommand,
    RegisterProfileCommand,
    RemoveProfileCommand,
    RenameProfileCommand,
)
from ._repository import UserProfileLifecycleRepository
from ._validation import COMPLETENESS_ISSUE_CODES, ProfileValidationService

_PROFILE_LIFECYCLE_ACTOR = "cadrumo.application.user_profile"
_PROFILE_EVENT_PAYLOAD_VERSION = 1
"""Schema version for the payload dict on this service's profile-lifecycle events."""
_PROFILE_ALREADY_EXISTS_MESSAGE = "profile already exists in the active bucket"
_PROFILE_TOMBSTONED_RENAME_MESSAGE = "tombstoned profile cannot be renamed"
_PROFILE_NOT_TOMBSTONED_MESSAGE = "profile is not tombstoned; reactivate refuses a live profile"
_PROFILE_SCHEMA_VALIDATION_MESSAGE = "profile facts failed schema validation"
_EMPTY_FIELD_BATCH_MESSAGE = "edit_fields requires at least one field command"
_MIXED_PROFILE_FIELD_BATCH_MESSAGE = "edit_fields refuses commands naming more than one profile"


def _last_fact_per_merge_key(facts: tuple[UserProfileFact, ...]) -> tuple[UserProfileFact, ...]:
    """Return the facts that actually land, in first-seen order.

    :meth:`ProfileLifecycleService._merge_facts` keys on
    ``(path, valid_from, valid_to)``, so a batch naming the same key twice
    stores only the last value. Emitting an event per SUBMITTED command
    would then claim more transitions than the aggregate records; emitting
    one per landed fact keeps the audit trail one-to-one with the change.
    """
    landed: dict[tuple[str, date | None, date | None], UserProfileFact] = {}
    for fact in facts:
        landed[(fact.path, fact.valid_from, fact.valid_to)] = fact
    return tuple(landed.values())


def _paths_payload(facts: tuple[UserProfileFact, ...]) -> dict[str, str]:
    """Return bounded path summary payload for a bucket event."""
    paths = sorted({fact.path for fact in facts})
    encoded = "\n".join(paths).encode("utf-8")
    return {"path_count": str(len(paths)), "paths_sha256": sha256_hex(encoded)}


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

    # ── register / read ────────────────────────────────────────────

    def register(self, command: RegisterProfileCommand) -> ProfileLifecycleResult:
        """Register a new active profile aggregate.

        Returns a :class:`ProfileLifecycleResult`.
        """
        if self._repository.exists(command.profile_id):
            raise _profile_already_exists_error(
                profile_id=command.profile_id,
                bucket_id=self._repository.bucket_id,
            )
        self._reject_invalid(
            command.profile_id,
            command.facts,
            require_complete=command.status is not UserProfileStatus.SETUP_INCOMPLETE,
        )
        now = utc_now()
        record = UserProfileRecord(
            schema_id=self._validator.schema.id,
            schema_version=self._validator.schema.version,
            profile_id=command.profile_id,
            display_name=command.display_name,
            status=command.status,
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

    # ── edit / remove / reactivate / rename ────────────────────────

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
        # Editing one field must not be gated on OTHER fields being filled in.
        # A SETUP_INCOMPLETE profile is filled in a field at a time, so
        # demanding global completeness here would refuse every edit until the
        # profile was already complete — an unreachable state, since the only
        # way to reach it is through this door. The edited value is still
        # validated for shape; completeness binds at the ACTIVE promotion.
        self._reject_invalid(
            command.profile_id,
            next_facts,
            require_complete=record.status is not UserProfileStatus.SETUP_INCOMPLETE,
        )
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

    def edit_fields(self, commands: Sequence[EditProfileFieldCommand]) -> ProfileLifecycleResult:
        """Upsert several effective-dated facts into one aggregate in ONE write.

        The batched counterpart of :meth:`edit_field`, for a caller applying a
        patch of several fields as one change -- the setup wizard's page
        commit, the cotejo apply, the descendant-count reconciliation. Driving
        those through :meth:`edit_field` in a loop ran the ENTIRE cascade once
        per field: N aggregate decrypts, N schema validations, N re-encrypts,
        and N event-catalogue round-trips, for a patch the caller already
        considered atomic. Only the last of those N writes could be observed
        by anything else, so the intermediate N-1 were pure cost.

        The audit trail is unchanged: one event is emitted per fact that
        lands, carrying the same type and payload :meth:`edit_field` would
        have produced. They share the batch's single ``applied_at`` because
        they were, in fact, applied by one write; :func:`emit_bucket_events`
        appends each one individually, so N facts remain N catalogue entries.

        Completeness is judged once, from the status the aggregate held when
        the batch opened -- the same rule :meth:`edit_field` applies, and the
        reason a partially-filled SETUP_INCOMPLETE profile can be patched at
        all.

        Args:
            commands: The per-field upserts to apply. Every command must name
                the same ``profile_id``. An empty sequence is refused rather
                than silently writing nothing, since a caller reaching this
                door believes it has a change to make.

        Returns:
            A :class:`ProfileLifecycleResult` carrying the aggregate as it
            stands after the whole batch.

        Raises:
            ProfileSchemaValidationError: When the POST-BATCH fact set fails
                validation. The batch is judged as a whole, so a patch is
                never left half-applied by a later field's refusal.
        """
        if not commands:
            raise ProfileSchemaValidationError(
                _EMPTY_FIELD_BATCH_MESSAGE,
                context={"issue_count": 0, "issue_codes": (), "issue_paths": ()},
                translated_message="application.user_profile.errors.lifecycle_schema_validation_failed",
            )
        profile_ids = {command.profile_id for command in commands}
        if len(profile_ids) != 1:
            raise ProfileSchemaValidationError(
                _MIXED_PROFILE_FIELD_BATCH_MESSAGE,
                context={
                    "issue_count": len(profile_ids),
                    "issue_codes": (),
                    "issue_paths": tuple(sorted(profile_ids)),
                },
                translated_message="application.user_profile.errors.lifecycle_schema_validation_failed",
            )
        profile_id = profile_ids.pop()

        record = self._repository.load(profile_id)
        incoming = tuple(
            UserProfileFact(
                path=command.path,
                value=command.value,
                valid_from=command.valid_from,
                valid_to=command.valid_to,
                source=command.source,
            )
            for command in commands
        )
        next_facts = self._merge_facts(record.facts, incoming)
        self._reject_invalid(
            profile_id,
            next_facts,
            require_complete=record.status is not UserProfileStatus.SETUP_INCOMPLETE,
        )
        result = self._save_updated(record, next_facts)
        emit_bucket_events(
            repository=self._events,
            events=tuple(
                self._build_event(
                    event_type=(
                        BucketEventType.PROFILE_VALUES_CLEARED
                        if fact.value is None
                        else BucketEventType.PROFILE_VALUES_UPDATED
                    ),
                    object_id=record.profile_id,
                    occurred_at=result.applied_at,
                    payload={"path": fact.path},
                )
                for fact in _last_fact_per_merge_key(incoming)
            ),
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

    def reactivate(self, command: ReactivateProfileCommand) -> ProfileLifecycleResult:
        """Restore a tombstoned root to active status; symmetric inverse of :meth:`remove`.

        Refuses if the target is not currently tombstoned, so a
        reactivate can never silently no-op against an already-active
        profile.

        Returns a :class:`ProfileLifecycleResult` with the reactivated profile.
        """
        record = self._repository.load(command.profile_id)
        if record.status is not UserProfileStatus.TOMBSTONED:
            raise _profile_not_tombstoned_error(command.profile_id)
        reactivated = record.reactivate()
        self._repository.save(reactivated)
        self._emit_event(
            event_type=BucketEventType.PROFILE_REACTIVATED,
            object_id=reactivated.profile_id,
            occurred_at=reactivated.updated_at,
        )
        return ProfileLifecycleResult(profile=reactivated, applied_at=reactivated.updated_at)

    def complete_setup(self, command: CompleteSetupCommand) -> ProfileLifecycleResult:
        """Transition a ``SETUP_INCOMPLETE`` profile to ``ACTIVE`` at setup commit.

        The one-way exit from the interactive setup flow: fires only after
        flow-scope validation has passed at the flow's final commit. The
        record's own :meth:`~cadrumo.domain.user_profile.UserProfileRecord.complete_setup`
        refuses any other source status, so an active or tombstoned profile
        cannot be laundered through this arm. Emits
        ``PROFILE_SETUP_COMPLETED`` so the audit trail records when the
        profile became workable.

        Returns a :class:`ProfileLifecycleResult` with the activated profile.
        """
        record = self._repository.load(command.profile_id)
        # Completeness binds HERE, at the one-way promotion to ACTIVE, rather
        # than at birth. Previously nothing in this arm checked it: the gate
        # was the setup flow's own final-commit validation, which held only
        # for callers that went through the flow. Re-running the full check
        # against the record's accumulated facts makes the guarantee
        # structural — no surface can promote an under-populated profile.
        self._reject_invalid(record.profile_id, record.facts, require_complete=True)
        completed = record.complete_setup()
        self._repository.save(completed)
        self._emit_event(
            event_type=BucketEventType.PROFILE_SETUP_COMPLETED,
            object_id=completed.profile_id,
            occurred_at=completed.updated_at,
        )
        return ProfileLifecycleResult(profile=completed, applied_at=completed.updated_at)

    def record_censo_applied(self, profile_id: str, *, adopted_count: int, divergence_count: int) -> None:
        """Emit the single ``CENSO_APPLIED`` event at a cotejo artefact-apply commit.

        The dormant ``CENSO_APPLIED`` member's live emission site: the setup
        flow's cotejo phase (or the ``config profile censo file --apply`` door)
        reconciles a Certificado de Situación Censal against the profile and
        commits the adopted values plus any deferred divergence rows. Exactly
        ONE event marks that apply-commit — never one per adopted fact — so the
        audit trail records that a censal artefact was reconciled onto the
        profile, at the non-official evidence tier. The per-fact value writes
        keep emitting their own ``PROFILE_VALUES_UPDATED`` / ``..._CLEARED``
        events through :meth:`edit_field`; this event is the apply-commit
        marker layered on top.
        """
        self._emit_event(
            event_type=BucketEventType.CENSO_APPLIED,
            object_id=profile_id,
            occurred_at=utc_now(),
            payload={"adopted_count": str(adopted_count), "divergence_count": str(divergence_count)},
        )

    def rename(
        self,
        command: RenameProfileCommand,
        *,
        extra_events: tuple[BucketEvent, ...] = (),
    ) -> ProfileLifecycleResult:
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

        The record write, ``PROFILE_RENAMED``, and any ``extra_events`` a
        composing surface hands down commit in ONE unit of work. Saving the
        record and emitting afterwards let the rename come to rest
        durable-but-unrecorded: the label moved and the audit trail did not,
        with no marker naming the gap. ``extra_events`` exists so a surface
        layer can record its own verb invocation without opening a second
        write it would have to reconcile -- the bucket-maintenance rename is
        the caller this was built for.

        The manifest write still sits outside this transaction, by design:
        it is a plaintext file, not a secure-object row, so no SQL unit of
        work can span both. That ordering is documented on the repository
        and fails closed through the cross-store integrity check on load.
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
        renamed_event = self._build_event(
            event_type=BucketEventType.PROFILE_RENAMED,
            object_id=target.profile_id,
            occurred_at=now,
            payload={"previous_display_name": source.display_name},
        )
        self._repository.commit_with_events(
            target,
            events=(renamed_event, *extra_events),
            event_repository=self._events,
        )
        return ProfileLifecycleResult(profile=target, applied_at=now)

    # ── helpers ────────────────────────────────────────────────────

    def _reject_invalid(
        self,
        profile_id: str,
        facts: Iterable[UserProfileFact],
        *,
        require_complete: bool = True,
    ) -> None:
        """Refuse the fact set on blocking schema issues.

        ``require_complete`` selects which issues block. A profile being born
        ``SETUP_INCOMPLETE`` is, by definition, allowed to be missing the
        fields filing depends on — demanding them to create an *incomplete*
        profile is a contradiction, and it is what forced a tax id to be known
        before a profile could exist at all. Whatever facts ARE supplied are
        still validated for shape and value in both modes; only the
        missing-required-field issues are deferred.

        They are not dropped: :meth:`complete_setup` re-runs this check with
        ``require_complete=True`` against the record's accumulated facts, so
        completeness is enforced at the ACTIVE promotion instead. That is the
        moment it actually matters, and it now binds regardless of which
        surface drives the promotion.
        """
        report = self._validator.validate_facts(profile_id, facts)
        blocking = [
            issue
            for issue in report.issues
            if issue.severity is BaseSeverity.ERROR and (require_complete or issue.code not in COMPLETENESS_ISSUE_CODES)
        ]
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
        # Inside a CAS update the enclosing operation's instant stands in for a
        # fresh clock read. The bucket event this result stamps derives its id
        # from ``applied_at``, so a retry that re-read the clock would mint a
        # second id for one logical edit and land a duplicate audit row rather
        # than collapsing onto the entry the first attempt prepared.
        from ..workflow import current_operation_instant

        now = current_operation_instant() or utc_now()
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

    def _build_event(
        self,
        *,
        event_type: BucketEventType,
        object_id: str,
        occurred_at: datetime,
        payload: dict[str, str] | None = None,
    ) -> BucketEvent:
        """Derive the lifecycle event without persisting it.

        The derive half of :meth:`_emit_event`, for the transitions that
        commit their event alongside the record write rather than after it.
        """
        return build_bucket_event(
            bucket_id=self._repository.bucket_id,
            event_type=event_type,
            occurred_at=occurred_at,
            actor=_PROFILE_LIFECYCLE_ACTOR,
            object_type=BucketEventObjectType.PROFILE,
            object_id=object_id,
            payload=dict(payload or {}),
            payload_version=_PROFILE_EVENT_PAYLOAD_VERSION,
        )

    def _emit_event(
        self,
        *,
        event_type: BucketEventType,
        object_id: str,
        occurred_at: datetime,
        payload: dict[str, str] | None = None,
    ) -> None:
        emit_bucket_event(
            repository=self._events,
            bucket_id=self._repository.bucket_id,
            event_type=event_type,
            occurred_at=occurred_at,
            actor=_PROFILE_LIFECYCLE_ACTOR,
            object_type=BucketEventObjectType.PROFILE,
            object_id=object_id,
            payload=dict(payload or {}),
            payload_version=_PROFILE_EVENT_PAYLOAD_VERSION,
        )


def _profile_already_exists_error(*, profile_id: str, bucket_id: str) -> ProfileAlreadyExistsError:
    return ProfileAlreadyExistsError(
        _PROFILE_ALREADY_EXISTS_MESSAGE,
        context={"profile_id": profile_id, "bucket_id": bucket_id},
        translated_message="application.user_profile.errors.lifecycle_profile_already_exists",
    )


def _profile_tombstoned_error(profile_id: str, *, action: Literal["rename"]) -> ProfileNotFoundError:
    return ProfileNotFoundError(
        _PROFILE_TOMBSTONED_RENAME_MESSAGE,
        context={"profile_id": profile_id, "action": action},
        translated_message="application.user_profile.errors.lifecycle_profile_tombstoned_rename",
    )


def _profile_not_tombstoned_error(profile_id: str) -> ProfileNotFoundError:
    return ProfileNotFoundError(
        _PROFILE_NOT_TOMBSTONED_MESSAGE,
        context={"profile_id": profile_id, "action": "reactivate"},
        translated_message="application.user_profile.errors.lifecycle_profile_not_tombstoned",
    )


__all__ = ["ProfileLifecycleService"]

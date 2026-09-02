"""Durable roll-forward authority for all-profile configuration reset."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple
from uuid import UUID

from ..core.bucket_pointer import BucketPointer
from ..core.config import load_settings
from ..core.errors.hierarchy import CadrumoError
from ..core.time.clock import now
from ..domain.retention.errors import RetentionFloorError
from ..domain.retention.floor import RetentionFloorAssessment, erase_is_blocked
from ._config_reset_repository import (
    ConfigResetJournalCorruptError,
    ConfigResetJournalIncompleteError,
    ConfigResetJournalNotFoundError,
    ConfigResetJournalRepository,
)
from .auth.operator import reset_operator_auth
from .auth.operator_cleanup import clear_operator_auth_acquisition_locks
from .auth.operator_scope import operator_auth_revocation_is_reachable
from .bucket_maintenance.contracts import AssessBucketDeletionCommand, BucketDeletionAssessment
from .bucket_maintenance.service import BucketMaintenanceService
from .config_reset_models import (
    ConfigResetAuthClearance,
    ConfigResetAuthClearanceMode,
    ConfigResetDeletionMarker,
    ConfigResetOperation,
    ConfigResetOperationStatus,
    ConfigResetPauseReason,
    ConfigResetPointerSnapshot,
    ConfigResetRetentionDecision,
    ConfigResetSummary,
    ConfigResetTarget,
    ConfigResetTargetPhase,
    new_config_reset_operation_id,
)
from .user_profile.custody_hold_models import ProfileCustodyRetentionOverride
from .user_profile.lifecycle import ProfileCapsuleLifecycle
from .user_profile.profile_pointer import active_profile_pointer_transaction
from .workflow.profile_bucket_scan import list_profile_buckets


class ConfigResetError(CadrumoError):
    """Base application failure for durable configuration reset."""


class ConfigResetConfirmationRequiredError(ConfigResetError):
    """Raised when a destructive start or resume lacks confirmation."""


class ConfigResetAlreadyRunningError(ConfigResetError):
    """Raised when a new start overlaps an incomplete reset operation."""


class ConfigResetOperationNotFoundError(ConfigResetError):
    """Raised when status or resume cannot resolve an operation."""


_PHASE_ORDER = {
    ConfigResetTargetPhase.SNAPSHOTTED: 0,
    ConfigResetTargetPhase.RETENTION_APPROVED: 1,
    ConfigResetTargetPhase.AUTH_CLEARING: 2,
    ConfigResetTargetPhase.AUTH_CLEARED: 3,
    ConfigResetTargetPhase.POINTER_RECONCILING: 4,
    ConfigResetTargetPhase.POINTER_RECONCILED: 5,
    ConfigResetTargetPhase.DELETING: 6,
    ConfigResetTargetPhase.DELETED: 7,
}


@dataclass(frozen=True, slots=True)
class _Preflight:
    operation: ConfigResetOperation
    pause_reason: ConfigResetPauseReason | None = None
    paused_target_ids: tuple[str, ...] = ()


def start_config_reset(
    *,
    confirmed: bool,
    acknowledge_retention_override: bool = False,
    retention_override_reason: str | None = None,
) -> ConfigResetOperation:
    """Start and execute one durable all-profile reset operation."""
    _require_confirmation(confirmed)
    settings = load_settings()
    repository = ConfigResetJournalRepository(settings=settings)
    operation_id = new_config_reset_operation_id()
    with (
        repository.operation_lock(operation_id),
        active_profile_pointer_transaction(settings.cadrumo_local_storage_root) as pointer_transaction,
    ):
        pointer_snapshot = _capture_pointer_snapshot(pointer_transaction.read())
        target_ids = set(
            list_profile_buckets(
                root=settings.cadrumo_local_storage_root,
            ),
        )
        if pointer_snapshot.record.bucket_id is not None:
            target_ids.add(pointer_snapshot.record.bucket_id)
        try:
            repository.refuse_if_incomplete()
        except ConfigResetJournalIncompleteError as exc:
            raise _already_running_error(exc) from exc
        with BucketMaintenanceService().deletion_target_locks(
            root=settings.cadrumo_local_storage_root,
            bucket_ids=target_ids,
            wait_seconds=settings.cadrumo_file_lock_timeout_s,
        ):
            preflight = _initial_preflight(
                operation_id=operation_id,
                pointer_snapshot=pointer_snapshot,
                target_ids=tuple(sorted(target_ids)),
                acknowledge_retention_override=acknowledge_retention_override,
                retention_override_reason=retention_override_reason,
            )
            operation = _update_operation(
                preflight.operation,
                status=(
                    ConfigResetOperationStatus.PAUSED
                    if preflight.pause_reason is not None
                    else ConfigResetOperationStatus.INCOMPLETE
                ),
                pause_reason=preflight.pause_reason,
                paused_target_ids=preflight.paused_target_ids,
            )
            try:
                repository.create_exclusive(operation)
            except ConfigResetJournalIncompleteError as exc:
                raise _already_running_error(exc) from exc
            if operation.status is ConfigResetOperationStatus.PAUSED:
                return operation
            return _roll_forward(
                repository=repository,
                operation=operation,
            )


def config_reset_status(operation_id: str | None = None) -> ConfigResetOperation | None:
    """Return one reset journal without changing its status or phase."""
    repository = ConfigResetJournalRepository()
    if operation_id is not None:
        try:
            return repository.load(operation_id)
        except ConfigResetJournalNotFoundError as exc:
            raise ConfigResetOperationNotFoundError(
                translated_message="errors.error.error_cadrumo_core_not_found",
                context={"operation_id": operation_id},
            ) from exc
    return repository.latest()


def resume_config_reset(
    operation_id: str,
    *,
    confirmed: bool,
    acknowledge_retention_override: bool = False,
    retention_override_reason: str | None = None,
) -> ConfigResetOperation:
    """Resume one incomplete operation from its durable recorded phases."""
    _require_confirmation(confirmed)
    settings = load_settings()
    repository = ConfigResetJournalRepository(settings=settings)
    with repository.operation_lock(operation_id):
        try:
            operation = repository.load(operation_id)
        except ConfigResetJournalNotFoundError as exc:
            raise ConfigResetOperationNotFoundError(
                translated_message="errors.error.error_cadrumo_core_not_found",
                context={"operation_id": operation_id},
            ) from exc
        except ConfigResetJournalCorruptError as exc:
            raise ConfigResetError(
                translated_message="errors.error.error_config_boundary",
                context={"operation_id": operation_id, "journal_corrupt": True},
            ) from exc
        if operation.status is ConfigResetOperationStatus.COMPLETE:
            return operation
        with active_profile_pointer_transaction(
            settings.cadrumo_local_storage_root,
        ) as pointer_transaction:
            current_pointer = _capture_pointer_snapshot(pointer_transaction.read())
            lock_ids = tuple(
                sorted(
                    {
                        target.bucket_id
                        for target in operation.targets
                        if target.phase is not ConfigResetTargetPhase.DELETED
                    }
                    | ({current_pointer.record.bucket_id} if current_pointer.record.bucket_id is not None else set()),
                ),
            )
            with BucketMaintenanceService().deletion_target_locks(
                root=settings.cadrumo_local_storage_root,
                bucket_ids=lock_ids,
                wait_seconds=settings.cadrumo_file_lock_timeout_s,
            ):
                pointer_preflight = _reconcile_pointer_snapshot_for_resume(
                    operation,
                    current_pointer=current_pointer,
                )
                operation = pointer_preflight.operation
                if pointer_preflight.pause_reason is not None:
                    operation = _pause_operation(
                        operation,
                        reason=pointer_preflight.pause_reason,
                        target_ids=pointer_preflight.paused_target_ids,
                    )
                    repository.save(operation)
                    return operation
                preflight = _resume_preflight(
                    operation,
                    acknowledge_retention_override=acknowledge_retention_override,
                    retention_override_reason=retention_override_reason,
                )
                if preflight.pause_reason is not None:
                    operation = _pause_operation(
                        preflight.operation,
                        reason=preflight.pause_reason,
                        target_ids=preflight.paused_target_ids,
                    )
                    repository.save(operation)
                    return operation
                operation = _update_operation(
                    preflight.operation,
                    status=ConfigResetOperationStatus.INCOMPLETE,
                    pause_reason=None,
                    paused_target_ids=(),
                    updated_at=now(),
                )
                repository.save(operation)
                return _roll_forward(
                    repository=repository,
                    operation=operation,
                )


def _require_confirmation(confirmed: bool) -> None:
    if not confirmed:
        raise ConfigResetConfirmationRequiredError(
            translated_message="errors.refused.refused_config_reset_unconfirmed",
            context={"confirmed": False},
        )


def _already_running_error(
    error: ConfigResetJournalIncompleteError,
) -> ConfigResetAlreadyRunningError:
    return ConfigResetAlreadyRunningError(
        translated_message="errors.locked.locked_storage_lock_acquisition",
        context={"operation_id": (error.context or {}).get("operation_id", "")},
    )


def _capture_pointer_snapshot(pointer: BucketPointer) -> ConfigResetPointerSnapshot:
    """Record the one transaction-held pointer observation in the reset journal."""
    return ConfigResetPointerSnapshot(record=pointer)


def _initial_preflight(
    *,
    operation_id: str,
    pointer_snapshot: ConfigResetPointerSnapshot,
    target_ids: tuple[str, ...],
    acknowledge_retention_override: bool,
    retention_override_reason: str | None,
) -> _Preflight:
    service = BucketMaintenanceService()
    targets: list[ConfigResetTarget] = []
    blocked: list[str] = []
    for bucket_id in target_ids:
        assessment = service.assess_deletion(
            AssessBucketDeletionCommand(bucket_id=bucket_id),
        )
        target, resolved = _target_from_assessment(
            assessment,
            acknowledge_retention_override=acknowledge_retention_override,
            retention_override_reason=retention_override_reason,
        )
        targets.append(target)
        if not resolved:
            blocked.append(bucket_id)
    recorded_at = now()
    operation = ConfigResetOperation(
        operation_id=operation_id,
        started_at=recorded_at,
        updated_at=recorded_at,
        pointer_snapshot=pointer_snapshot,
        targets=tuple(targets),
    )
    if blocked:
        return _Preflight(
            operation=operation,
            pause_reason=ConfigResetPauseReason.RETENTION_UNRESOLVED,
            paused_target_ids=tuple(blocked),
        )
    return _Preflight(operation=operation)


def _target_from_assessment(
    assessment: BucketDeletionAssessment,
    *,
    acknowledge_retention_override: bool,
    retention_override_reason: str | None,
) -> tuple[ConfigResetTarget, bool]:
    retention = _retention_decision(
        assessment.retention,
        acknowledge_retention_override=acknowledge_retention_override,
        retention_override_reason=retention_override_reason,
    )
    resolved = not erase_is_blocked(
        blocks_erase=retention.blocks_erase,
        override_approved=retention.override_approved,
    )
    return (
        ConfigResetTarget(
            bucket_id=assessment.bucket_id,
            label=assessment.label,
            setup_state_at_snapshot=assessment.setup_state,
            exists_at_snapshot=assessment.exists,
            fingerprint=assessment.fingerprint,
            phase=(ConfigResetTargetPhase.RETENTION_APPROVED if resolved else ConfigResetTargetPhase.SNAPSHOTTED),
            retention=retention,
        ),
        resolved,
    )


def _retention_decision(
    assessment: RetentionFloorAssessment | None,
    *,
    acknowledge_retention_override: bool,
    retention_override_reason: str | None,
) -> ConfigResetRetentionDecision:
    if assessment is None:
        # NOT a fail-open default, though it reads like one. An assessment can
        # only omit retention when its target does not exist:
        # BucketDeletionAssessment's own validator refuses `exists=True` unless
        # label, fingerprint AND retention are all present, and the sole
        # producer builds the absent form only. So reaching here means nothing
        # is on disk, and "nothing is retained" is a true statement about that
        # target rather than a decision taken without evidence.
        #
        # Recorded because this branch has now been read twice as a missing
        # guard on a destructive path. The invariant is enforced by the type,
        # which is stronger than a check here would be; a runtime guard would
        # be unreachable and would imply the rule lives here instead.
        return ConfigResetRetentionDecision(
            assessed_at=now(),
            blocks_erase=False,
            retained_record_count=0,
        )
    reason = (retention_override_reason or "").strip()
    approved = assessment.blocks_erase and acknowledge_retention_override and bool(reason)
    return ConfigResetRetentionDecision(
        assessed_at=assessment.as_of,
        blocks_erase=assessment.blocks_erase,
        retained_record_count=len(assessment.retained),
        latest_safe_erase_date=assessment.latest_safe_erase_date,
        override_approved=approved,
        override_reason=reason if approved else None,
    )


def _reconcile_pointer_snapshot_for_resume(
    operation: ConfigResetOperation,
    *,
    current_pointer: ConfigResetPointerSnapshot,
) -> _Preflight:
    if current_pointer == operation.pointer_snapshot:
        return _Preflight(operation=operation)
    pointer_transition_started = any(
        _phase_at_least(target.phase, ConfigResetTargetPhase.POINTER_RECONCILING) for target in operation.targets
    )
    if pointer_transition_started:
        before = operation.pointer_snapshot.record
        expected_successor = (
            before
            if before.bucket_id is None
            else BucketPointer.absent(transition_revision=before.transition_revision + 1)
        )
        if current_pointer.record == expected_successor:
            return _Preflight(operation=operation)
    target_ids = {target.bucket_id for target in operation.targets}
    targets = list(operation.targets)
    paused_ids: tuple[str, ...] = ()
    if current_pointer.record.bucket_id is not None:
        paused_ids = (current_pointer.record.bucket_id,)
        if current_pointer.record.bucket_id not in target_ids:
            assessment = BucketMaintenanceService().assess_deletion(
                AssessBucketDeletionCommand(bucket_id=current_pointer.record.bucket_id),
            )
            target, _ = _target_from_assessment(
                assessment,
                acknowledge_retention_override=False,
                retention_override_reason=None,
            )
            targets.append(target)
            targets.sort(key=lambda item: item.bucket_id)
    elif operation.pointer_snapshot.record.bucket_id is not None:
        paused_ids = (operation.pointer_snapshot.record.bucket_id,)
    updated = _update_operation(
        operation,
        pointer_snapshot=current_pointer,
        targets=tuple(targets),
        updated_at=now(),
    )
    return _Preflight(
        operation=updated,
        pause_reason=ConfigResetPauseReason.POINTER_CHANGED,
        paused_target_ids=paused_ids,
    )


class _ResumeTargetOutcome(NamedTuple):
    target: ConfigResetTarget
    changed: bool
    blocked: bool


def _vanished_target_outcome(target: ConfigResetTarget) -> _ResumeTargetOutcome:
    """Reconcile a target the assessment no longer finds on disk.

    A target already snapshotted absent, or one already in the deleting
    phase, is where it should be and needs no change. Anything else was
    removed out of band below the deleting phase: re-snapshot it as absent
    so this resume pauses once on the state change and the next one
    converges. Leaving it existing would pause every resume forever.
    """
    if not target.exists_at_snapshot or target.phase is ConfigResetTargetPhase.DELETING:
        return _ResumeTargetOutcome(target=target, changed=False, blocked=False)
    vanished = _update_target(
        target,
        exists_at_snapshot=False,
        fingerprint=None,
        label=None,
        setup_state_at_snapshot=None,
    )
    return _ResumeTargetOutcome(target=vanished, changed=True, blocked=False)


def _resume_target_outcome(
    target: ConfigResetTarget,
    assessment: BucketDeletionAssessment,
    *,
    acknowledge_retention_override: bool,
    retention_override_reason: str | None,
) -> _ResumeTargetOutcome:
    if not assessment.exists:
        return _vanished_target_outcome(target)
    current_fingerprint = assessment.fingerprint
    if current_fingerprint is None:
        raise ConfigResetError(
            f"reset target {target.bucket_id!r} exists on disk but yielded no fingerprint to compare",
        )
    fingerprint_changed = (
        not target.exists_at_snapshot
        or target.fingerprint is None
        or target.fingerprint.digest != current_fingerprint.digest
    )
    if fingerprint_changed:
        refreshed, _ = _target_from_assessment(
            assessment,
            acknowledge_retention_override=False,
            retention_override_reason=None,
        )
        return _ResumeTargetOutcome(target=refreshed, changed=True, blocked=False)
    retention = _retention_decision(
        assessment.retention,
        acknowledge_retention_override=acknowledge_retention_override,
        retention_override_reason=retention_override_reason,
    )
    resolved = not erase_is_blocked(
        blocks_erase=retention.blocks_erase,
        override_approved=retention.override_approved,
    )
    phase = target.phase
    if _phase_before(phase, ConfigResetTargetPhase.AUTH_CLEARING):
        phase = ConfigResetTargetPhase.RETENTION_APPROVED if resolved else ConfigResetTargetPhase.SNAPSHOTTED
    updated_target = _update_target(
        target,
        label=assessment.label,
        setup_state_at_snapshot=assessment.setup_state,
        exists_at_snapshot=True,
        fingerprint=current_fingerprint,
        retention=retention,
        phase=phase,
    )
    return _ResumeTargetOutcome(target=updated_target, changed=False, blocked=not resolved)


def _resume_preflight(
    operation: ConfigResetOperation,
    *,
    acknowledge_retention_override: bool,
    retention_override_reason: str | None,
) -> _Preflight:
    service = BucketMaintenanceService()
    updated_targets: list[ConfigResetTarget] = []
    changed: list[str] = []
    blocked: list[str] = []
    for target in operation.targets:
        if target.phase is ConfigResetTargetPhase.DELETED:
            updated_targets.append(target)
            continue
        assessment = service.assess_deletion(
            AssessBucketDeletionCommand(bucket_id=target.bucket_id),
        )
        outcome = _resume_target_outcome(
            target,
            assessment,
            acknowledge_retention_override=acknowledge_retention_override,
            retention_override_reason=retention_override_reason,
        )
        updated_targets.append(outcome.target)
        if outcome.changed:
            changed.append(target.bucket_id)
        if outcome.blocked:
            blocked.append(target.bucket_id)
    updated = _update_operation(
        operation,
        targets=tuple(updated_targets),
        updated_at=now(),
    )
    if changed:
        return _Preflight(
            operation=updated,
            pause_reason=ConfigResetPauseReason.TARGET_STATE_CHANGED,
            paused_target_ids=tuple(sorted(changed)),
        )
    if blocked:
        return _Preflight(
            operation=updated,
            pause_reason=ConfigResetPauseReason.RETENTION_UNRESOLVED,
            paused_target_ids=tuple(sorted(blocked)),
        )
    return _Preflight(operation=updated)


def _pause_operation(
    operation: ConfigResetOperation,
    *,
    reason: ConfigResetPauseReason,
    target_ids: tuple[str, ...],
) -> ConfigResetOperation:
    return _update_operation(
        operation,
        status=ConfigResetOperationStatus.PAUSED,
        pause_reason=reason,
        paused_target_ids=tuple(sorted(set(target_ids))),
        updated_at=now(),
    )


def _roll_forward(
    *,
    repository: ConfigResetJournalRepository,
    operation: ConfigResetOperation,
) -> ConfigResetOperation:
    operation = _clear_auth_for_targets(repository, operation)
    operation = _reconcile_pointer(repository, operation)
    operation = _delete_targets(repository, operation)
    completed_at = now()
    summary = ConfigResetSummary(
        target_count=len(operation.targets),
        deleted_count=sum(target.exists_at_snapshot for target in operation.targets),
        already_absent_count=sum(not target.exists_at_snapshot for target in operation.targets),
        retention_override_count=sum(
            target.retention is not None and target.retention.override_approved for target in operation.targets
        ),
        completed_at=completed_at,
    )
    operation = _update_operation(
        operation,
        status=ConfigResetOperationStatus.COMPLETE,
        summary=summary,
        pause_reason=None,
        paused_target_ids=(),
        updated_at=completed_at,
    )
    repository.save(operation)
    return operation


def _clear_auth_for_target(bucket_id: str) -> ConfigResetAuthClearance:
    """End one target's auth custody by whichever means its key state allows.

    A reset holds locks on profiles it has NOT unlocked, and the two halves of
    auth custody answer to different keys. The acquisition locks are plaintext
    files outside the capsule: key-free to clear, and NOT reaped by the capsule's
    deletion, so they are cleared here or they outlive the erase. Everything the
    revocation reaches beyond them -- the AEAT browser session and the auth
    workflow state -- are encrypted rows INSIDE the capsule, which the deletion
    destroys wholesale; the revocation cannot open them without the key and does
    not need to.

    So a locked target gets the key-free half only. Driving the full revocation
    at it was the defect: it refused, correctly, and stalled every reset. The
    tempting repair -- catching that refusal and carrying on -- would report a
    revocation that never happened, which is the failure an earlier ruling in
    this campaign closed.

    An open custody session is a different case and keeps the full revocation,
    because it can reach one thing capsule destruction cannot: the
    certificate-source secrets, which live outside the capsule under a
    key-derived lookup digest. Those are the residue a locked target leaves
    behind, and the returned clearance records that it did rather than implying
    a clean sweep.
    """
    settings = load_settings()
    # The erase is the one caller entitled to take a HELD lock: this profile is
    # being destroyed wholesale, the lock is going with it, and refusing would
    # strand the reset. Every other caller leaves the profile alive and must
    # not abort somebody's live acquisition.
    cleared_lock_provider_ids = tuple(
        sorted(clear_operator_auth_acquisition_locks(settings, bucket_id=bucket_id, allow_held=True)),
    )
    # Asked on the ambient route, with no injected Settings, because that is
    # exactly the route the revocation below would take: a probe on a different
    # route would answer about a profile the operation is not about to touch.
    if not operator_auth_revocation_is_reachable(bucket_id=bucket_id):
        return ConfigResetAuthClearance(
            mode=ConfigResetAuthClearanceMode.CAPSULE_DESTRUCTION,
            cleared_at=now(),
            cleared_lock_provider_ids=cleared_lock_provider_ids,
        )
    result = reset_operator_auth(all_providers=True, target_bucket_id=bucket_id)
    return ConfigResetAuthClearance(
        mode=ConfigResetAuthClearanceMode.UNLOCKED_REVOCATION,
        cleared_at=now(),
        cleared_lock_provider_ids=cleared_lock_provider_ids,
        removed_out_of_bucket_secret_records=result.removed_certificate_secrets,
    )


def _clear_auth_for_targets(
    repository: ConfigResetJournalRepository,
    operation: ConfigResetOperation,
) -> ConfigResetOperation:
    for index, target in enumerate(operation.targets):
        if _phase_at_least(target.phase, ConfigResetTargetPhase.AUTH_CLEARED):
            continue
        if not target.exists_at_snapshot:
            # An absent capsule still leaves the key-free locks behind, because
            # they were never inside it. Skipping auth entirely here left one
            # per provider for every dangling target.
            operation = _replace_target(
                operation,
                index,
                _update_target(
                    target,
                    phase=ConfigResetTargetPhase.AUTH_CLEARED,
                    auth_clearance=_clear_auth_for_target(target.bucket_id),
                ),
            )
            repository.save(operation)
            continue
        target = _update_target(target, phase=ConfigResetTargetPhase.AUTH_CLEARING)
        operation = _replace_target(operation, index, target)
        repository.save(operation)
        clearance = _clear_auth_for_target(target.bucket_id)
        assessment = BucketMaintenanceService().assess_deletion(
            AssessBucketDeletionCommand(bucket_id=target.bucket_id),
        )
        if not assessment.exists or assessment.fingerprint is None:
            raise ConfigResetError(
                translated_message="errors.error.error_config_boundary",
                context={"bucket_id": target.bucket_id, "target_present_during_auth_cleanup": False},
            )
        target = _update_target(
            target,
            fingerprint=assessment.fingerprint,
            retention=_retention_decision_from_record(
                assessment.retention,
                target.retention,
            ),
            auth_clearance=clearance,
            phase=ConfigResetTargetPhase.AUTH_CLEARED,
        )
        operation = _replace_target(operation, index, target)
        repository.save(operation)
    return operation


def _retention_decision_from_record(
    assessment: RetentionFloorAssessment | None,
    recorded: ConfigResetRetentionDecision | None,
) -> ConfigResetRetentionDecision:
    if assessment is None:
        return _retention_decision(
            None,
            acknowledge_retention_override=False,
            retention_override_reason=None,
        )
    if recorded is not None and recorded.override_approved:
        # The operator approved erasing a SET, not a predicate. Re-stamping the
        # approval onto a refreshed assessment that now retains more records
        # than they were shown would extend their consent to filings they never
        # saw, so a grown set drops the override and forces it to be given
        # again against the count that actually blocks.
        if len(assessment.retained) > recorded.retained_record_count:
            return _retention_decision(
                assessment,
                acknowledge_retention_override=False,
                retention_override_reason=None,
            )
        return _retention_decision(
            assessment,
            acknowledge_retention_override=True,
            retention_override_reason=recorded.override_reason,
        )
    return _retention_decision(
        assessment,
        acknowledge_retention_override=False,
        retention_override_reason=None,
    )


def _reconcile_pointer(
    repository: ConfigResetJournalRepository,
    operation: ConfigResetOperation,
) -> ConfigResetOperation:
    indexes = [
        index
        for index, target in enumerate(operation.targets)
        if _phase_before(target.phase, ConfigResetTargetPhase.POINTER_RECONCILED)
    ]
    for index in indexes:
        target = operation.targets[index]
        operation = _replace_target(
            operation,
            index,
            _update_target(target, phase=ConfigResetTargetPhase.POINTER_RECONCILING),
        )
    if indexes:
        repository.save(operation)
    active_bucket_id = operation.pointer_snapshot.record.bucket_id
    if active_bucket_id is not None and any(target.bucket_id == active_bucket_id for target in operation.targets):
        with active_profile_pointer_transaction(load_settings().cadrumo_local_storage_root) as pointer_transaction:
            pointer_transaction.clear()
    for index in indexes:
        target = operation.targets[index]
        operation = _replace_target(
            operation,
            index,
            _update_target(target, phase=ConfigResetTargetPhase.POINTER_RECONCILED),
        )
    if indexes:
        repository.save(operation)
    return operation


def _refuse_erase_inside_the_retention_floor(target: ConfigResetTarget) -> None:
    """Refuse to erase a target whose filed records are still legally retained.

    The Administration's right to review a filed self-assessment prescribes four
    years (Ley 58/2003 LGT art. 66/67) and the supporting documentation must be
    conserved for the same window (art. 70.2), so erasing inside it destroys
    evidence the law requires kept. The operator may proceed only by recording
    an explicit override.

    Deliberately checked HERE, at the point bytes are destroyed, rather than
    trusted from the pause that normally stops such a target reaching this
    function. A guard that lives only in an earlier phase is one refactor away
    from being skipped, and the failure it would permit is unrecoverable. No
    supported flow reaches this refusal today; that is the point of a backstop,
    and it is proven by forging the state the earlier phase prevents.

    The count and the date come from the recorded decision, which
    :meth:`~application.filing.FilingRetentionAuthority.assess` computed from
    the filing snapshot -- so the message and the computation cannot drift.
    ``latest_safe_erase_date`` is the instant the WHOLE set clears, which is
    exactly the EARLIEST date erasing all of it is safe; the two names describe
    one instant from opposite ends.
    """
    retention = target.retention
    if retention is None or not retention.blocks_erase or retention.override_approved:
        return
    safe_from = retention.latest_safe_erase_date
    raise RetentionFloorError(
        translated_message="errors.refused.refused_retention_floor",
        context={
            "retained_record_count": retention.retained_record_count,
            "earliest_safe_erase_date": (safe_from.date().isoformat() if safe_from is not None else "unknown"),
            "bucket_id": target.bucket_id,
        },
    )


def _custody_retention_override(
    target: ConfigResetTarget,
) -> ProfileCustodyRetentionOverride | None:
    """Project this target's journaled retention decision into a custody token.

    Built from the operation's own durable record rather than from the live
    call arguments, so the authorisation the custody gates weigh is the one the
    operator gave and this operation persisted -- not a value a later caller
    could supply. Absent an approved override the answer is ``None``, which is
    what keeps a target with no operator decision blocked at the custody gate.
    """
    retention = target.retention
    if retention is None or not retention.override_approved:
        return None
    reason = retention.override_reason
    if reason is None:
        raise ConfigResetError("an approved retention override carries no recorded reason")
    return ProfileCustodyRetentionOverride(
        reason=reason,
        approved_at=retention.assessed_at,
        retained_record_count=retention.retained_record_count,
        latest_safe_erase_date=retention.latest_safe_erase_date,
    )


def _recognize_completed_erase(
    repository: ConfigResetJournalRepository,
    operation: ConfigResetOperation,
    index: int,
    target: ConfigResetTarget,
) -> ConfigResetOperation:
    """Advance a target whose erase already landed, instead of re-driving it.

    The delete loop destroys the capsule and only then advances the phase and
    saves. A crash in that window leaves a durable record saying DELETING while
    the capsule is already gone, and the loop's only skip was for a target
    already DELETED -- so a resume re-entered preparation, tried to load a
    profile that no longer exists, and aborted. The reset was then unresumable
    for good: the data erased, the operation unable to reach completion.

    Absence alone does not authorise this. It is weighed against the deletion
    marker, which this operation wrote immediately before the erase and which
    names the operation and the bucket. Advancing on absence by itself would
    silently absorb a capsule destroyed by something else, which is the one
    thing the reset must never report as its own work -- and is what the
    target-tampering case exists to catch. So a marker that does not attest
    THIS operation erasing THIS bucket refuses instead.

    The completion time is this resume's clock, not the erase's. The instant the
    erase actually happened is recorded in the custody delete receipt, which
    this operation cannot address because it does not record the transaction id
    it started. Reporting the resume's clock is a known and bounded
    imprecision; inventing an earlier one would be worse.
    """
    marker = target.deletion_marker
    if marker is None or marker.operation_id != operation.operation_id or marker.bucket_id != target.bucket_id:
        raise ConfigResetError(
            translated_message="errors.error.error_config_boundary",
            context={
                "bucket_id": target.bucket_id,
                "target_absent_without_attesting_marker": True,
            },
        )
    operation = _replace_target(
        operation,
        index,
        _update_target(target, phase=ConfigResetTargetPhase.DELETED, completed_at=now()),
    )
    repository.save(operation)
    return operation


def _delete_targets(
    repository: ConfigResetJournalRepository,
    operation: ConfigResetOperation,
) -> ConfigResetOperation:
    lifecycle = ProfileCapsuleLifecycle()
    for index, target in enumerate(operation.targets):
        if target.phase is ConfigResetTargetPhase.DELETED:
            continue
        if not target.exists_at_snapshot:
            completed_at = now()
            operation = _replace_target(
                operation,
                index,
                _update_target(
                    target,
                    phase=ConfigResetTargetPhase.DELETED,
                    completed_at=completed_at,
                ),
            )
            repository.save(operation)
            continue
        fingerprint = target.fingerprint
        if fingerprint is None:
            raise ConfigResetError(
                f"reset target {target.bucket_id!r} reached the deleting phase with no recorded fingerprint",
            )
        # Re-derive retention against the LIVE assessment before anything reads
        # it. A target reaching DELETING is skipped by the auth-clearing sweep
        # (it is already past AUTH_CLEARED), so without this its recorded
        # decision -- and the override built from it below -- is whatever the
        # snapshot said, however long ago. `_retention_decision_from_record`
        # carries the growth guard, so an approved override drops when the
        # retained set has grown beyond what the operator was shown.
        assessment = BucketMaintenanceService().assess_deletion(
            AssessBucketDeletionCommand(bucket_id=target.bucket_id),
        )
        target = _update_target(
            target,
            retention=_retention_decision_from_record(assessment.retention, target.retention),
        )
        operation = _replace_target(operation, index, target)
        repository.save(operation)
        if target.phase is ConfigResetTargetPhase.DELETING and not assessment.exists:
            operation = _recognize_completed_erase(repository, operation, index, target)
            continue
        _refuse_erase_inside_the_retention_floor(target)
        if target.phase is not ConfigResetTargetPhase.DELETING:
            target = _update_target(
                target,
                phase=ConfigResetTargetPhase.DELETING,
                deletion_marker=ConfigResetDeletionMarker(
                    operation_id=operation.operation_id,
                    bucket_id=target.bucket_id,
                    fingerprint=fingerprint.digest,
                    marked_at=now(),
                ),
            )
            operation = _replace_target(operation, index, target)
            repository.save(operation)
        journal = lifecycle.prepare_delete(
            profile_id=UUID(target.bucket_id),
            retention_override=_custody_retention_override(target),
            requires_inactive_target=False,
        )
        confirmation = lifecycle.confirm_delete(journal)
        result = lifecycle.delete(confirmation)
        target = _update_target(
            target,
            phase=ConfigResetTargetPhase.DELETED,
            completed_at=result.completed_at,
        )
        operation = _replace_target(operation, index, target)
        repository.save(operation)
    return operation


def _replace_target(
    operation: ConfigResetOperation,
    index: int,
    target: ConfigResetTarget,
) -> ConfigResetOperation:
    targets = list(operation.targets)
    targets[index] = target
    return _update_operation(
        operation,
        targets=tuple(targets),
        updated_at=now(),
    )


def _update_target(
    target: ConfigResetTarget,
    **updates: object,
) -> ConfigResetTarget:
    payload = target.model_dump()
    payload.update(updates)
    return ConfigResetTarget.model_validate(payload)


def _update_operation(
    operation: ConfigResetOperation,
    **updates: object,
) -> ConfigResetOperation:
    payload = operation.model_dump()
    payload.update(updates)
    return ConfigResetOperation.model_validate(payload)


def _phase_before(
    current: ConfigResetTargetPhase,
    expected: ConfigResetTargetPhase,
) -> bool:
    return _PHASE_ORDER[current] < _PHASE_ORDER[expected]


def _phase_at_least(
    current: ConfigResetTargetPhase,
    expected: ConfigResetTargetPhase,
) -> bool:
    return _PHASE_ORDER[current] >= _PHASE_ORDER[expected]


__all__ = [
    "ConfigResetAlreadyRunningError",
    "ConfigResetConfirmationRequiredError",
    "ConfigResetError",
    "ConfigResetOperation",
    "ConfigResetOperationNotFoundError",
    "ConfigResetOperationStatus",
    "ConfigResetPauseReason",
    "ConfigResetTargetPhase",
    "config_reset_status",
    "resume_config_reset",
    "start_config_reset",
]

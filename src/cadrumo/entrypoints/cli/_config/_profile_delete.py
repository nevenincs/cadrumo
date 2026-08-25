"""Single-target profile deletion.

This is the only verb that irreversibly destroys ONE named taxpayer's encrypted
financial history. Its safety argument is its own and is deliberately not
inherited from the all-profile reset, which reaches the same custody primitives
behind a durable journal, a typed confirmation and an explicit acknowledgement:

- **The subject is named and positional.** A verb that destroys a profile must
  say which one on the command line; there is no active-profile default, so a
  bare invocation cannot destroy whatever happened to be selected.
- **The default posture is a preflight that destroys nothing.** Without
  ``--yes`` the verb reports the label, the observed content fingerprint and
  the legal retention position, exits successfully, and writes no bytes. The
  operator sees exactly what would be destroyed before authorising it.
- **The active profile is refused outright.** Deleting the capsule a live
  session is bound to would leave the pointer aimed at nothing and the session
  material orphaned. The refusal names the session verbs rather than reaching a
  path that cannot complete.
- **The legal retention floor is enforced here, at the point bytes are
  destroyed.** The assessment comes from the one sessionless authority that
  computes it (:meth:`BucketMaintenanceService.assess_deletion`), and the
  refusal is the same registered :class:`RetentionFloorError` with the same
  legal grounding the all-profile flow raises, so the two cannot state
  different law about the same records.

There is deliberately **no single-target retention override.** The all-profile
reset offers one because it records the operator's stated reason on a durable
journal that survives the operation; nothing in this verb's path records such a
reason, and an override that leaves no account of itself is worse than no
override. An operator inside the retention window is told the retained count and
the date the window clears, and is NOT routed to the all-profile reset, which
would destroy every other profile to reach this one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from ....core.i18n import OutputLanguage, tr
from ....core.json_contract import Notice, NoticeSeverity
from .._common import activate_subcommand_output_language as _activate_subcommand_output_language
from .._common import emit_envelope
from .._errors import CliRefusedBoundaryError

if TYPE_CHECKING:
    from ....application.bucket_maintenance import BucketDeletionAssessment
    from .._config_payloads import ConfigProfileDeleteResult


def _refuse_deleting_the_active_profile(*, bucket_id: str, label: str) -> None:
    """Refuse a target the current session is bound to.

    The pointer and the session artefacts are written by the login authority
    and cleared by the logout authority; destroying the capsule underneath them
    would leave both aimed at a bucket that no longer exists. Refusing is not a
    limitation of this verb so much as a statement that closing a session is a
    separate, already-owned operation the operator must perform first.
    """
    from ....core.bucket_pointer import resolve_active_bucket_id

    if resolve_active_bucket_id() != bucket_id:
        return
    raise CliRefusedBoundaryError(
        translated_message="cli.config.profile.delete.refusal.active_profile",
        context={"name": label, "profile_id": bucket_id},
    )


def _assess(bucket_id: str) -> BucketDeletionAssessment:
    """Observe the target without unlocking it, or refuse when it is gone."""
    from ....application.bucket_maintenance import AssessBucketDeletionCommand, BucketMaintenanceService

    assessment = BucketMaintenanceService().assess_deletion(AssessBucketDeletionCommand(bucket_id=bucket_id))
    if not assessment.exists:
        raise CliRefusedBoundaryError(
            translated_message="cli.config.profile.unknown_profile",
            context={"name": bucket_id},
        )
    return assessment


def _refuse_erase_inside_the_retention_floor(assessment: BucketDeletionAssessment) -> None:
    """Refuse to destroy a target whose filed records are still legally retained.

    The Administration's right to review a filed self-assessment prescribes four
    years (Ley 58/2003 LGT art. 66/67) and the supporting documentation must be
    conserved for the same window (art. 70.2). The count and the date are read
    from the assessment the maintenance authority computed from the filing
    snapshot and are never recomputed here, so the two refusals cannot report
    different NUMBERS for the same records.

    What is duplicated, and stated plainly rather than claimed away, is the
    DECISION: the all-profile flow tests the blocking flag together with a
    recorded override, and this verb tests the flag alone because it offers no
    override. A third condition added to the retention contract would reach one
    site and not the other. Making that impossible means promoting the decision
    to a shared application function, which lives in a module this surface does
    not own; until that happens the duplication is a known cost, not an
    invariant.
    """
    from ....domain.retention import RetentionFloorError

    retention = assessment.retention
    if retention is None or not retention.blocks_erase:
        return
    safe_from = retention.latest_safe_erase_date
    raise RetentionFloorError(
        translated_message="errors.refused.refused_retention_floor",
        context={
            "retained_record_count": len(retention.retained),
            "earliest_safe_erase_date": (safe_from.date().isoformat() if safe_from is not None else "unknown"),
            "bucket_id": assessment.bucket_id,
        },
    )


def _destroy(bucket_id: str, *, label: str) -> str:
    """Destroy one capsule through the journalled custody owner.

    Delegates to the journalled, crash-resumable custody primitives rather than
    re-implementing a write path: ``prepare_delete`` opens the transaction,
    ``confirm_delete`` produces the confirmation it will only accept, and
    ``delete`` executes it. Each custody transition holds the canonical external
    transaction lock and revalidates the immutable inventory witness. Do not
    hold the bucket's own ``.lock`` across execution: on Windows that live file
    handle makes the authenticated capsule directory impossible to rename to
    its transaction-owned deletion tombstone.
    """
    from uuid import UUID

    from ....application.user_profile.lifecycle import ProfileCapsuleLifecycle
    from ....application.user_profile.profile_pointer import active_profile_pointer_transaction

    with active_profile_pointer_transaction():
        # Revalidate under the canonical root/pointer lock and retain it until
        # every journalled owner effect completes. A concurrent login cannot
        # activate the target between this decision and tombstone removal.
        _refuse_deleting_the_active_profile(bucket_id=bucket_id, label=label)
        lifecycle = ProfileCapsuleLifecycle()
        journal = lifecycle.prepare_delete(
            profile_id=UUID(bucket_id),
            requires_inactive_target=True,
        )
        confirmation = lifecycle.confirm_delete(journal)
        receipt = lifecycle.delete(confirmation)
    return receipt.completed_at.isoformat()


def _result_and_lines(
    assessment: BucketDeletionAssessment,
    *,
    label: str,
    completed_at: str | None,
) -> tuple[ConfigProfileDeleteResult, tuple[str, ...], tuple[Notice, ...]]:
    """Project one outcome onto the registered envelope and its text lines."""
    from .._config_payloads import ConfigProfileDeleteResult

    fingerprint = assessment.fingerprint
    retention = assessment.retention
    safe_from = retention.latest_safe_erase_date if retention is not None else None
    deleted = completed_at is not None
    result = ConfigProfileDeleteResult(
        profile_id=assessment.bucket_id,
        display_name=label,
        deleted=deleted,
        fingerprint=fingerprint,
        retained_record_count=len(retention.retained) if retention is not None else 0,
        earliest_safe_erase_date=(safe_from.date().isoformat() if safe_from is not None else None),
        completed_at=completed_at,
    )
    notice = Notice(
        severity=NoticeSeverity.INFO,
        code=("config.profile.delete.deleted" if deleted else "config.profile.delete.preflight"),
        message=tr(
            "cli.config.profile.delete.notices.deleted" if deleted else "cli.config.profile.delete.notices.preflight",
        ),
        context={"profile_id": assessment.bucket_id},
    )
    lines = (
        f"profile\t{label}",
        f"profile_id\t{assessment.bucket_id}",
        f"deleted\t{str(deleted).lower()}",
        f"content_digest\t{fingerprint.digest if fingerprint is not None else ''}",
        f"file_count\t{fingerprint.file_count if fingerprint is not None else 0}",
        f"total_bytes\t{fingerprint.total_bytes if fingerprint is not None else 0}",
        f"retained_record_count\t{len(retention.retained) if retention is not None else 0}",
        notice.message,
    )
    return result, lines, (notice,)


def config_profile_delete(
    ctx: typer.Context,
    name: str,
    yes: bool = False,
    output_language: OutputLanguage | None = None,
) -> None:
    from ._profile_support import resolve_profile_by_label

    """Destroy one named profile capsule, after a preflight the operator confirms."""
    _activate_subcommand_output_language(ctx, output_language)
    pointer = resolve_profile_by_label(name)
    _refuse_deleting_the_active_profile(bucket_id=pointer.bucket_id, label=pointer.label)
    assessment = _assess(pointer.bucket_id)
    _refuse_erase_inside_the_retention_floor(assessment)
    completed_at = _destroy(pointer.bucket_id, label=pointer.label) if yes else None
    result, lines, notices = _result_and_lines(
        assessment,
        label=pointer.label,
        completed_at=completed_at,
    )
    emit_envelope(
        ctx,
        command="config.profile.delete",
        result=result,
        lines=lines,
        notices=notices,
    )


__all__ = ["config_profile_delete"]

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
- **The selected profile is refused outright.** Human sign-out preserves the
  selected login target. The operator must select another profile through
  its supported login before deleting the original capsule.
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

from cadrumo_client.commands.errors import CliRefusedBoundaryError

from ....core.external_constants import OutputLanguage
from ....core.i18n.render import tr
from ....core.json_contract import Notice, NoticeSeverity
from ..common import activate_subcommand_output_language as _activate_subcommand_output_language
from ..common import emit_envelope

if TYPE_CHECKING:
    from cadrumo_client.commands.payloads import ConfigProfileDeleteResult

    from ....application.bucket_maintenance.contracts import BucketDeletionAssessment
    from ....application.bucket_maintenance.deletion_preflight import ProfileDeletionPreflight


def _refused(preflight: ProfileDeletionPreflight) -> Exception | None:
    """Build this command's refusal for a preflight that offers nothing to delete.

    The decision is the application's; only its rendering is decided here, so
    the command reports the codes, messages and recovery verdicts it always has.
    """
    from ....application.bucket_maintenance.deletion_preflight import ProfileDeletionRefusal
    from ._profile_support import unknown_profile_refusal

    refusal = preflight.refusal
    if refusal is None:
        return None
    if refusal is ProfileDeletionRefusal.PROFILE_LABEL_AMBIGUOUS:
        return CliRefusedBoundaryError(translated_message="errors.refused.refused_profile_label_ambiguous")
    if refusal is ProfileDeletionRefusal.UNKNOWN_PROFILE:
        # A name that resolved to a capsule no longer on disk is reported by
        # the identifier that was observed, since the name did resolve.
        return unknown_profile_refusal(preflight.profile_id or preflight.requested_name)
    if refusal is ProfileDeletionRefusal.PROFILE_SELECTED:
        return _selected_profile_refusal(preflight)
    return _retention_floor_refusal(preflight)


def _selected_profile_refusal(preflight: ProfileDeletionPreflight) -> Exception:
    """Refuse the selected profile: sign-out keeps the selection, so another must be selected first."""
    from ....application.profile_preconditions import profile_deletion_requires_other_selection_verdict
    from ..common import attach_cli_policy_verdict

    label = preflight.label or preflight.requested_name
    return attach_cli_policy_verdict(
        CliRefusedBoundaryError(
            translated_message="cli.config.profile.delete.refusal.active_profile",
            context={"name": label, "profile_id": preflight.profile_id},
        ),
        verdict=profile_deletion_requires_other_selection_verdict(requested_profile=label),
    )


def _retention_floor_refusal(preflight: ProfileDeletionPreflight) -> Exception:
    """Refuse to destroy a target whose filed records are still legally retained.

    The Administration's right to review a filed self-assessment prescribes four
    years (Ley 58/2003 LGT art. 66/67) and the supporting documentation must be
    conserved for the same window (art. 70.2). The count and the date are read
    from the assessment the maintenance authority computed from the filing
    snapshot and are never recomputed here, so this refusal and the all-profile
    reset's cannot report different numbers for the same records. No override
    is offered because this verb records no reason for one.
    """
    from ....domain.retention.errors import RetentionFloorError

    assessment = preflight.assessment
    retention = None if assessment is None else assessment.retention
    safe_from = None if retention is None else retention.latest_safe_erase_date
    return RetentionFloorError(
        translated_message="errors.refused.refused_retention_floor",
        context={
            "retained_record_count": 0 if retention is None else len(retention.retained),
            "earliest_safe_erase_date": (safe_from.date().isoformat() if safe_from is not None else "unknown"),
            "bucket_id": preflight.profile_id,
        },
    )


def _destroy(ctx: typer.Context, assessment: BucketDeletionAssessment) -> str:
    """Request the owner-supplied deletion service after the product preflight."""
    from ..invocation_services import invocation_services

    return invocation_services(ctx).delete_profile(assessment)


def _result_and_lines(
    assessment: BucketDeletionAssessment,
    *,
    label: str,
    completed_at: str | None,
) -> tuple[ConfigProfileDeleteResult, tuple[str, ...], tuple[Notice, ...]]:
    """Project one outcome onto the registered envelope and its text lines."""
    from cadrumo_client.commands.payloads import ConfigProfileDeleteResult

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
    """Destroy one named profile capsule, after a preflight the operator confirms."""
    from ....application.bucket_maintenance.deletion_preflight import assess_named_profile_deletion
    from ..state_projection_support import bucket_storage

    _activate_subcommand_output_language(ctx, output_language)
    preflight = assess_named_profile_deletion(name, bucket_storage=bucket_storage(ctx))
    refused = _refused(preflight)
    if refused is not None:
        raise refused
    assessment, label = preflight.assessment, preflight.label
    if assessment is None or label is None:
        raise CliRefusedBoundaryError("custody_changed")
    completed_at = _destroy(ctx, assessment) if yes else None
    result, lines, notices = _result_and_lines(
        assessment,
        label=label,
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

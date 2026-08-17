"""Profile readiness helpers for the config CLI surface."""

from __future__ import annotations

import typer

from .._common import emit_envelope, resolve_cli_precondition_action
from ._status_rendering import precondition_action_lines


def _emit_profile_record_missing(ctx: typer.Context, *, profile_id: str, bucket_id: str, label: str) -> None:
    from ....application.workflow import unavailable_profile_record_verdict
    from .._config_payloads import ConfigProfileShowResult

    action = resolve_cli_precondition_action(
        unavailable_profile_record_verdict(
            status="missing_profile_record",
            source="none",
            repairable_by_clearing_pointer=False,
        )
    )
    result = ConfigProfileShowResult(
        profile_id=profile_id,
        bucket_id=bucket_id,
        display_name=label,
        registered_bucket=True,
        profile_record_present=False,
        configured=False,
        precondition_action=action,
    )
    emit_envelope(
        ctx,
        command="config.profile.show",
        result=result,
        lines=(
            "readiness\tmissing_profile_record",
            f"profile_id\t{profile_id}",
            f"bucket_id\t{bucket_id}",
            f"display_name\t{label}",
            "registered_bucket\tpresent",
            "profile_record\tmissing",
            *precondition_action_lines(action),
        ),
    )


def _emit_profile_record_unreadable(
    ctx: typer.Context,
    *,
    profile_id: str,
    bucket_id: str,
    label: str,
    error: Exception,
) -> None:
    from ....application.workflow import unavailable_profile_record_verdict
    from .._config_payloads import ConfigProfileShowResult

    action = resolve_cli_precondition_action(
        unavailable_profile_record_verdict(
            status="profile_record_unreadable",
            source="none",
            repairable_by_clearing_pointer=False,
        )
    )
    result = ConfigProfileShowResult(
        profile_id=profile_id,
        bucket_id=bucket_id,
        display_name=label,
        registered_bucket=True,
        profile_record_present=False,
        status="profile_record_unreadable",
        error=type(error).__name__,
        precondition_action=action,
    )
    emit_envelope(
        ctx,
        command="config.profile.show",
        result=result,
        lines=(
            "readiness\tprofile_record_unreadable",
            f"profile_id\t{profile_id}",
            f"bucket_id\t{bucket_id}",
            f"display_name\t{label}",
            "registered_bucket\tpresent",
            "profile_record\tunreadable",
            *precondition_action_lines(action),
        ),
    )


def _read_profile_record(*, profile_id: str, bucket_id: str):
    """Read a profile record under a bucket session scoped to that profile.

    Resumes ``bucket_id``'s own persisted session when none is already
    serving it. That is not a convenience: the root callback deliberately
    returns early for a verb naming an explicit profile target, on the stated
    ground that such a verb resolves and unlocks its OWN target rather than
    being gated by an unrelated active-profile pointer. Resolving happened
    here; unlocking never did.

    The consequence was a resolution split rather than a missing record. In a
    fresh interpreter the active-profile path was resumed by the root callback
    and reported the record present with its keys, while the named-profile
    path skipped that resume, found no session serving its bucket, and
    reported the same record on the same disk as missing. Neither durability
    nor the key digest was involved, which is why investigations framed around
    those found nothing.

    Resume goes through the single shared authority, so this path and the root
    callback cannot drift: it is fail-closed, opens nothing on any refusal
    branch, and returns a typed reason rather than a bare failure.
    """
    from ....adapters.persistence.storage import active_bucket_session_serves
    from ....application.user_profile import (
        ProfileNotFoundError,
        ProfileRecordRepository,
        bind_resumed_profile_session,
    )

    # Ask the bound session which bucket it serves; matching the pointer and
    # then checking only that SOME session exists leaves it unverified.
    if not active_bucket_session_serves(bucket_id):
        bind_resumed_profile_session(bucket_id=bucket_id)
    if active_bucket_session_serves(bucket_id):
        return ProfileRecordRepository.for_current_session(bucket_id).load(profile_id)
    raise ProfileNotFoundError("profile record requires its active authenticated custody session")


__all__ = [
    "_emit_profile_record_missing",
    "_emit_profile_record_unreadable",
    "_read_profile_record",
]

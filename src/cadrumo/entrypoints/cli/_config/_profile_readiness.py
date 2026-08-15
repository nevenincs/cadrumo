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
    """Read a profile record under a bucket session scoped to that profile."""
    from ....adapters.persistence.storage import active_bucket_session_serves
    from ....application.user_profile import ProfileNotFoundError, ProfileRecordRepository

    # Ask the bound session which bucket it serves; matching the pointer and
    # then checking only that SOME session exists leaves it unverified.
    if active_bucket_session_serves(bucket_id):
        return ProfileRecordRepository.for_current_session(bucket_id).load(profile_id)
    raise ProfileNotFoundError("profile record requires its active authenticated custody session")


__all__ = [
    "_emit_profile_record_missing",
    "_emit_profile_record_unreadable",
    "_read_profile_record",
]

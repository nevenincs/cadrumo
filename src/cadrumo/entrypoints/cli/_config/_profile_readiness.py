"""Profile readiness helpers for the config CLI surface."""

from __future__ import annotations

import typer

from .._common import _emit_envelope
from ._repair_profile import (
    profile_record_missing_next_action as _profile_record_missing_next_action,
)
from ._repair_profile import (
    profile_record_unreadable_next_action as _profile_record_unreadable_next_action,
)


def _emit_profile_record_missing(ctx: typer.Context, *, profile_id: str, bucket_id: str, label: str) -> None:
    from .._config_payloads import ConfigProfileShowResult

    result = ConfigProfileShowResult(
        profile_id=profile_id,
        bucket_id=bucket_id,
        display_name=label,
        registered_bucket=True,
        profile_record_present=False,
        configured=False,
        next_action=_profile_record_missing_next_action(profile_id, label=label),
    )
    _emit_envelope(
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
            f"next_action\t{result.next_action}",
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
    message = str(error).splitlines()[0] if str(error) else type(error).__name__
    from .._config_payloads import ConfigProfileShowResult

    result = ConfigProfileShowResult(
        profile_id=profile_id,
        bucket_id=bucket_id,
        display_name=label,
        registered_bucket=True,
        profile_record_present=False,
        status="profile_record_unreadable",
        error=f"{type(error).__name__}: {message}",
        next_action=_profile_record_unreadable_next_action(profile_id, label=label),
    )
    _emit_envelope(
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
            f"next_action\t{result.next_action}",
        ),
    )


def _read_profile_record(*, profile_id: str, bucket_id: str):
    """Read a profile record under a bucket session scoped to that profile."""
    from ....adapters.persistence.storage.master_key import has_active_bucket_session
    from ....application.user_profile import build_lifecycle_service, profile_storage_session
    from ....core import resolve_active_bucket_id as _resolve_active_bucket_id

    if bucket_id == _resolve_active_bucket_id() and has_active_bucket_session():
        return build_lifecycle_service(bucket_id=bucket_id).read(profile_id)
    with profile_storage_session(bucket_id):
        service = build_lifecycle_service(bucket_id=bucket_id)
        return service.read(profile_id)


__all__ = [
    "_emit_profile_record_missing",
    "_emit_profile_record_unreadable",
    "_read_profile_record",
]

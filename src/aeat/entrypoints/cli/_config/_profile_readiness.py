"""Profile readiness helpers for the config CLI surface."""

from __future__ import annotations

import typer

from ....core.errors import AeatError as _AeatError
from ....core.logging import get_logger as _get_logger
from .._common import _emit
from ._errors import ConfigBoundaryError as _ConfigBoundaryError
from ._repair_profile import (
    profile_record_missing_next_action as _profile_record_missing_next_action,
)
from ._repair_profile import (
    profile_record_unreadable_next_action as _profile_record_unreadable_next_action,
)

_log = _get_logger(__name__)


def _locked_store_refusal(error: BaseException) -> _AeatError | None:
    """Return the locked-store refusal wrapped in ``error``, if any."""
    from ....adapters.persistence.storage.errors import SecretStoreError

    seen: set[int] = set()
    current: BaseException | None = error
    depth = 0
    while current is not None and depth < 16:
        if isinstance(current, SecretStoreError):
            return current
        if id(current) in seen:
            return None
        seen.add(id(current))
        depth += 1
        nxt = getattr(current, "orig", None)
        if not isinstance(nxt, BaseException):
            nxt = current.__cause__ or current.__context__
        current = nxt
    return None


def _assert_profile_record_present(ctx: typer.Context, *, profile_id: str, bucket_id: str, label: str) -> None:
    from ....domain.user_profile import ProfileNotFoundError

    try:
        _read_profile_record(profile_id=profile_id, bucket_id=bucket_id)
    except ProfileNotFoundError:
        _emit_profile_record_missing(ctx, profile_id=profile_id, bucket_id=bucket_id, label=label)
        raise typer.Exit(code=2) from None
    except _AeatError as exc:
        locked = _locked_store_refusal(exc)
        if locked is not None:
            raise locked from exc
        _emit_profile_record_unreadable(ctx, profile_id=profile_id, bucket_id=bucket_id, label=label, error=exc)
        raise typer.Exit(code=2) from exc
    except Exception as exc:
        locked = _locked_store_refusal(exc)
        if locked is not None:
            raise locked from exc
        _log.debug("config profile readiness wrapped unexpected profile-record exception", exc_info=True)
        boundary = _ConfigBoundaryError(exc)
        _emit_profile_record_unreadable(ctx, profile_id=profile_id, bucket_id=bucket_id, label=label, error=boundary)
        raise typer.Exit(code=2) from boundary


def _emit_profile_record_missing(ctx: typer.Context, *, profile_id: str, bucket_id: str, label: str) -> None:
    payload = {
        "profile_id": profile_id,
        "bucket_id": bucket_id,
        "display_name": label,
        "registered_bucket": True,
        "profile_record_present": False,
        "configured": False,
        "next_action": _profile_record_missing_next_action(profile_id, label=label),
    }
    _emit(
        ctx,
        payload,
        (
            "readiness\tmissing_profile_record",
            f"profile_id\t{profile_id}",
            f"bucket_id\t{bucket_id}",
            f"display_name\t{label}",
            "registered_bucket\tpresent",
            "profile_record\tmissing",
            f"next_action\t{payload['next_action']}",
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
    payload = {
        "profile_id": profile_id,
        "bucket_id": bucket_id,
        "display_name": label,
        "registered_bucket": True,
        "profile_record_present": False,
        "status": "profile_record_unreadable",
        "error": f"{type(error).__name__}: {message}",
        "next_action": _profile_record_unreadable_next_action(profile_id, label=label),
    }
    _emit(
        ctx,
        payload,
        (
            "readiness\tprofile_record_unreadable",
            f"profile_id\t{profile_id}",
            f"bucket_id\t{bucket_id}",
            f"display_name\t{label}",
            "registered_bucket\tpresent",
            "profile_record\tunreadable",
            f"next_action\t{payload['next_action']}",
        ),
    )


def _read_profile_record(*, profile_id: str, bucket_id: str):
    """Read a profile record under a bucket session scoped to that profile."""
    from ....adapters.persistence.storage import has_active_bucket_session
    from ....application.user_profile import build_lifecycle_service, profile_storage_session
    from ....core import resolve_active_bucket_id as _resolve_active_bucket_id

    if bucket_id == _resolve_active_bucket_id() and has_active_bucket_session():
        return build_lifecycle_service(bucket_id=bucket_id).read(profile_id)
    with profile_storage_session(bucket_id):
        service = build_lifecycle_service(bucket_id=bucket_id)
        return service.read(profile_id)


__all__ = [
    "_assert_profile_record_present",
    "_emit_profile_record_missing",
    "_emit_profile_record_unreadable",
    "_locked_store_refusal",
    "_read_profile_record",
]

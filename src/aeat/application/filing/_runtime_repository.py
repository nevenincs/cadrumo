"""Runtime-backed repository helpers for filing application persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core._bucket_pointer_io import resolve_active_bucket_id
from .errors import ModeloApplicationError

if TYPE_CHECKING:
    from ...adapters.persistence.storage.sql import SecureObjectRepository


def resolve_application_filing_bucket_id(bucket_id: str | None) -> str:
    """Return an explicit or active profile bucket id for filing application repositories."""
    if bucket_id is not None:
        trimmed = bucket_id.strip()
        if trimmed:
            return trimmed
        raise ModeloApplicationError(
            translated_message="application.workflow.errors.no_active_profile_bucket",
        )
    active = resolve_active_bucket_id()
    if active is None:
        raise ModeloApplicationError(
            translated_message="application.workflow.errors.no_active_profile_bucket",
        )
    return active


def secure_objects_for_application_filing_bucket(bucket_id: str) -> SecureObjectRepository:
    """Return runtime-created secure-object storage for ``bucket_id``.

    The concrete adapter is imported here (not at module scope) so that
    application/filing/_runtime_repository does not carry a module-scope
    import from the adapters layer.  The import-time edge is eliminated;
    the runtime dependency remains transparent.
    """
    from ...adapters.persistence.storage.runtime_repository import (  # noqa: PLC0415
        secure_object_repository_for_bucket,
    )

    return secure_object_repository_for_bucket(bucket_id)


__all__ = [
    "resolve_application_filing_bucket_id",
    "secure_objects_for_application_filing_bucket",
]

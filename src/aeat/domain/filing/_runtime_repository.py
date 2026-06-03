"""Runtime-backed repository helpers for filing persistence.

Provides factory helpers that return a :class:`SecureObjectRepository`
bound to the active profile bucket for use by filing repository classes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core._bucket_pointer_io import resolve_active_bucket_id
from ._errors import ModeloDraftError

if TYPE_CHECKING:  # pragma: no cover — import-cycle guard
    from ...adapters.persistence.storage import SecureObjectRepository


def resolve_filing_repository_bucket_id(bucket_id: str | None) -> str:
    """Return an explicit or active profile bucket id for filing repositories."""
    if bucket_id is not None:
        trimmed = bucket_id.strip()
        if trimmed:
            return trimmed
        raise ModeloDraftError(
            translated_message="application.workflow.errors.no_active_profile_bucket",
        )
    active = resolve_active_bucket_id()
    if active is None:
        raise ModeloDraftError(
            translated_message="application.workflow.errors.no_active_profile_bucket",
        )
    return active


def secure_objects_for_filing_bucket(bucket_id: str) -> SecureObjectRepository:
    """Return runtime-created secure-object storage for ``bucket_id``.

    Returns:
        A :class:`SecureObjectRepository` scoped to the given filing bucket.
    """
    from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket

    return secure_object_repository_for_bucket(bucket_id)


__all__ = [
    "resolve_filing_repository_bucket_id",
    "secure_objects_for_filing_bucket",
]

"""Runtime-backed repository helpers for filing application persistence.

Constructs a :class:`SecureObjectRepository` scoped to the active filing
bucket on demand; the import is deferred to avoid pulling the adapters
layer into the application module graph at import time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core import resolve_repository_bucket_id
from .errors import ModeloApplicationError

if TYPE_CHECKING:
    from ...adapters.persistence.storage.sql import SecureObjectRepository


def resolve_application_filing_bucket_id(bucket_id: str | None) -> str:
    """Return an explicit or active profile bucket id for filing application repositories."""
    return resolve_repository_bucket_id(bucket_id, error_type=ModeloApplicationError)


def secure_objects_for_application_filing_bucket(bucket_id: str) -> SecureObjectRepository:
    """Return runtime-created secure-object storage for ``bucket_id``.

    The concrete adapter is imported here (not at module scope) so that
    application/filing/_runtime_repository does not carry a module-scope
    import from the adapters layer. The import-time edge is eliminated;
    the runtime dependency remains transparent.

    Returns a :class:`SecureObjectRepository` scoped to ``bucket_id``.
    """
    from ...adapters.persistence.storage.runtime_repository import (
        secure_object_repository_for_bucket,
    )

    return secure_object_repository_for_bucket(bucket_id)


__all__ = [
    "resolve_application_filing_bucket_id",
    "secure_objects_for_application_filing_bucket",
]

"""Runtime-backed repository helpers for filing application persistence.

Constructs a
:class:`~adapters.persistence.storage.SecureObjectRepository` scoped to
the active filing bucket on demand. The concrete adapter import is deferred so
the application filing module graph does not acquire an adapters-layer edge at
import time; only callers that actually need runtime storage cross that
boundary.

See Also:
    :class:`application.filing.ModeloHistoryRepository`
        Application repository that consumes these helpers to persist
        filing-history payloads.
    :func:`adapters.persistence.storage.secure_object_repository_for_bucket`
        Storage-runtime factory used after the filing bucket id is resolved.
    :mod:`adapters.persistence.profile._filing_runtime`
        Parallel persistence-adapter helper used by the governed draft and
        amendment repositories.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.bucket_pointer import resolve_repository_bucket_id
from .errors import ModeloApplicationError

if TYPE_CHECKING:
    from ...adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
    from ...domain.modelos.protocols import ModeloRecordCatalogueRepositoryProtocol


def resolve_application_filing_bucket_id(bucket_id: str | None) -> str:
    """Return the explicit or active profile bucket id for application repositories.

    Args:
        bucket_id: Optional bucket id supplied by the caller. Blank values are
            rejected; ``None`` falls back to the active profile bucket.

    Returns:
        Normalized bucket id used to scope application filing storage.

    Raises:
        ModeloApplicationError: When no explicit or active profile bucket is
            available.
    """
    return resolve_repository_bucket_id(bucket_id, error_type=ModeloApplicationError)


def secure_objects_for_application_filing_bucket(bucket_id: str) -> SecureObjectRepository:
    """Return runtime-created secure-object storage for ``bucket_id``.

    The concrete adapter is imported here (not at module scope) so that
    application/filing/_runtime_repository does not carry a module-scope
    import from the adapters layer. The import-time edge is eliminated;
    the runtime dependency remains transparent.

    Returns:
        A :class:`~adapters.persistence.storage.SecureObjectRepository`
        scoped to ``bucket_id``.
    """
    from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket

    return secure_object_repository_for_bucket(bucket_id)


def modelo_record_repository_for_application() -> ModeloRecordCatalogueRepositoryProtocol:
    """Build the concrete filing-record port at the application boundary.

    The modelo application services consume the domain repository protocol;
    this deferred runtime factory is the single application-filing wiring
    point for the encrypted persistence adapter. Keeping construction here
    avoids making calculation orchestration import a persistence detail while
    preserving the existing active-profile default.
    """
    from ...adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository

    return ModeloRecordCatalogueRepository()


__all__ = [
    "modelo_record_repository_for_application",
    "resolve_application_filing_bucket_id",
    "secure_objects_for_application_filing_bucket",
]

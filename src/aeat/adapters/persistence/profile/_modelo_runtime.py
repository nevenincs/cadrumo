"""Runtime-backed repository helpers shared by the modelo persistence adapters.

Shared private helpers for the sibling modelo catalogue repositories
(:mod:`~adapters.persistence.profile.modelos_calculation`,
``modelos_filing``, ``modelos_work_units``, ``modelos_verification_reports``,
and ``participation_index``): a bucket-id resolver and a runtime factory that
returns a
:class:`~adapters.persistence.storage.SecureObjectRepository` bound to the
active profile bucket. Both live in the persistence adapter alongside the
repositories they serve, so the secure-object coupling is a same-layer
``adapters -> adapters.persistence.storage`` import rather than a
``domain -> adapters`` violation.

See Also:
    :func:`~core.resolve_repository_bucket_id`
        Shared resolver for explicit-or-active profile bucket ids.
    :func:`~adapters.persistence.storage.secure_object_repository_for_bucket`
        Runtime storage factory used after the modelo bucket id is resolved.
    :mod:`~adapters.persistence.profile.modelos_calculation`
        Calculation-revision repository consumer of these modelo helpers.
    :mod:`~adapters.persistence.profile.participation_index`
        Participation-index repository consumer with the same runtime boundary.
    :class:`~domain.modelos.CalculationRevisionCatalogueRepositoryProtocol`
        Domain repository port implemented by the calculation-revision adapter.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....core import resolve_repository_bucket_id
from ..storage import secure_object_repository_for_bucket

if TYPE_CHECKING:  # pragma: no cover — type-only imports
    from ....domain.modelos import ModeloError
    from ..storage import SecureObjectRepository


def resolve_modelo_repository_bucket_id(bucket_id: str | None, *, error_type: type[ModeloError]) -> str:
    """Return an explicit or active profile bucket id for modelo repositories."""
    return resolve_repository_bucket_id(bucket_id, error_type=error_type)


def secure_objects_for_modelo_bucket(bucket_id: str) -> SecureObjectRepository:
    """Return runtime-created secure-object storage for ``bucket_id``.

    Returns:
        A :class:`~adapters.persistence.storage.SecureObjectRepository`
        scoped to the given modelo bucket.
    """
    return secure_object_repository_for_bucket(bucket_id)

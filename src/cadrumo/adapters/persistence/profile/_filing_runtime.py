"""Runtime-backed repository helpers shared by the filing persistence adapters.

Shared private helpers for the sibling filing repositories
(:mod:`~adapters.persistence.profile.filing_drafts` and
``filing_amendments``): a bucket-id resolver and a runtime factory that
returns a
:class:`~adapters.persistence.storage.SecureObjectRepository` bound to
the active profile bucket. Both live in the persistence adapter alongside the
repositories they serve, so the secure-object coupling is a same-layer
``adapters -> adapters.persistence.storage`` import rather than a
``domain -> adapters`` violation.

See Also:
    :func:`~core.resolve_repository_bucket_id`
        Shared resolver for explicit-or-active profile bucket ids.
    :func:`~adapters.persistence.storage.secure_object_repository_for_bucket`
        Runtime storage factory used after the filing bucket id is resolved.
    :mod:`~adapters.persistence.profile.filing_drafts`
        Draft repository consumer of these filing runtime helpers.
    :mod:`~application.filing._runtime_repository`
        Application-layer sibling helper that keeps application filing imports
        out of adapter module import time.
    :class:`~domain.filing.ModeloDraftRepositoryProtocol`
        Domain repository port implemented by the filing draft adapter.
"""

from __future__ import annotations

from ....core.bucket_pointer import resolve_repository_bucket_id
from ....domain.filing import ModeloDraftError


def resolve_filing_repository_bucket_id(bucket_id: str | None) -> str:
    """Return an explicit or active profile bucket id for filing repositories."""
    return resolve_repository_bucket_id(bucket_id, error_type=ModeloDraftError)


__all__ = [
    "resolve_filing_repository_bucket_id",
]

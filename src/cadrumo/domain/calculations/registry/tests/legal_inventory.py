"""Own finite fixture projections over real domain and storage kernels."""

from __future__ import annotations

from ..authority import PinnedAuthorityOperation
from ..authority_artifact import AuthorityComponentKind, ReferenceComponentQuery


def legal_reference_ids(self: PinnedAuthorityOperation) -> tuple[str, ...]:
    """Return every published legal declaration identity without hydrating payloads."""
    return tuple(
        query.reference_id
        for query in self._reader.component_queries()
        if isinstance(query, ReferenceComponentQuery) and query.kind is AuthorityComponentKind.LEGAL_REFERENCE
    )

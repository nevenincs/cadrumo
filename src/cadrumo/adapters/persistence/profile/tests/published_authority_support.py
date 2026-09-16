"""The published authority generation persistence tests seed their data from.

Runtime reads the published artifact, so seeded snapshots come from the same
pin rather than from a development compile of the mutable source tree. Helpers
that build snapshots are plain functions without fixture access, so the lease
is held once per worker process and released by the package's session fixture.
"""

from __future__ import annotations

from contextlib import ExitStack
from functools import cache

from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority

_LEASES = ExitStack()


@cache
def published_authority_operation() -> PinnedAuthorityOperation:
    """Lease the published generation once per process, as runtime reads it."""
    return _LEASES.enter_context(bundled_indexed_authority().operation())


def release_published_authority_operation() -> None:
    """Release the process lease so no generation pin outlives the session."""
    published_authority_operation.cache_clear()
    _LEASES.close()


__all__ = ["published_authority_operation", "release_published_authority_operation"]

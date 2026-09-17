"""The published authority generation persistence tests seed their data from.

Runtime reads the published artifact, so seeded snapshots come from the same
pin rather than from a development compile of the mutable source tree. Helpers
that build snapshots are plain functions without fixture access, so the lease
is held once per worker process and released by the package's session fixture.
"""

from __future__ import annotations

import contextvars
from contextlib import ExitStack
from functools import cache

from .....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority

_LEASES = ExitStack()
# Entering a lease scopes governed facts in the entering context; holding it in a
# private context keeps that scope from leaking into whichever test first asked.
_LEASE_CONTEXT = contextvars.copy_context()


def _enter_published_authority_lease() -> PinnedAuthorityOperation:
    """Enter the published-authority lease, returning the pinned operation."""
    return _LEASES.enter_context(bundled_indexed_authority().operation())


@cache
def published_authority_operation() -> PinnedAuthorityOperation:
    """Lease the published generation once per process, as runtime reads it."""
    return _LEASE_CONTEXT.run(_enter_published_authority_lease)


def release_published_authority_operation() -> None:
    """Release the process lease so no generation pin outlives the session."""
    published_authority_operation.cache_clear()
    _LEASE_CONTEXT.run(_LEASES.close)


__all__ = ["published_authority_operation", "release_published_authority_operation"]

"""Session authority leases that scope governed facts only where a test asks.

Entering an authority operation sets the governed-fact scope in the context
that enters it. A wider-scoped fixture that entered it in the session's own
context left that scope set for every later test in the worker, so a test that
never took a lease passed or failed by the order it ran in.
"""

from __future__ import annotations

import contextvars
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager

import pytest

from ..domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ..domain.calculations.registry.governed_fact_scope import validating_governed_facts


@contextmanager
def private_authority_lease() -> Iterator[PinnedAuthorityOperation]:
    """Hold one published-authority lease without scoping the caller's context."""
    lease_context = contextvars.copy_context()
    with ExitStack() as lease:

        def enter() -> PinnedAuthorityOperation:
            return lease.enter_context(bundled_indexed_authority().operation())

        pinned = lease_context.run(enter)
        try:
            yield pinned
        finally:
            lease_context.run(lease.close)


@contextmanager
def scoped_when_requested(request: pytest.FixtureRequest, fixture_name: str) -> Iterator[None]:
    """Scope governed facts to ``fixture_name``'s lease when the test depends on it."""
    if fixture_name not in request.fixturenames:
        yield
        return
    pinned = request.getfixturevalue(fixture_name)
    if not isinstance(pinned, PinnedAuthorityOperation):
        raise TypeError(f"fixture {fixture_name!r} must provide a PinnedAuthorityOperation")
    with validating_governed_facts(pinned):
        yield


__all__ = ["private_authority_lease", "scoped_when_requested"]

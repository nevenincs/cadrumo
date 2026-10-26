"""Fixtures for the corpus sanitiser tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest


@pytest.fixture
def published_authority_scope() -> Iterator[None]:
    """Resolve tax-identity checks in one requesting test against the published authority.

    Synthetic identities are validated through the governed tax-ID format, which
    refuses to run without an explicit authority scope. The lease ends with the
    test, so no other test inherits it.
    """
    from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

    with bundled_indexed_authority().operation():
        yield

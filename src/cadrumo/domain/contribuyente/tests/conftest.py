"""Generation-pinned governed-fact scope for the contribuyente domain tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from ...calculations.registry.authority import bundled_indexed_authority


@pytest.fixture(scope="module", autouse=True)
def governed_fact_scope() -> Iterator[None]:
    """Project registry tokens through one pinned authority generation per module."""
    with bundled_indexed_authority().operation():
        yield

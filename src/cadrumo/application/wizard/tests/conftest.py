"""Registry authority lease shared by the wizard tests in this directory."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority


@pytest.fixture
def authority_operation() -> Iterator[PinnedAuthorityOperation]:
    """Lease one indexed authority generation, scoping governed facts for the whole test."""
    with bundled_indexed_authority().operation() as operation:
        yield operation

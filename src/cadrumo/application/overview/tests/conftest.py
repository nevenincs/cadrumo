"""Authority lease shared by the overview calendar tests in this directory."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority


@pytest.fixture
def calendar_operation() -> Iterator[PinnedAuthorityOperation]:
    """Lease one indexed authority generation for a calendar test."""
    with bundled_indexed_authority().operation() as operation:
        yield operation

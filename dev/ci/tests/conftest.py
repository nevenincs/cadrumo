"""CI-specific governed-fact fixture for tests hosted by the repo root."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts


@pytest.fixture
def governed_fact_scope(operation: PinnedAuthorityOperation) -> Iterator[None]:
    """Resolve registry-validated values in one requesting test against the published lease."""
    with validating_governed_facts(operation):
        yield

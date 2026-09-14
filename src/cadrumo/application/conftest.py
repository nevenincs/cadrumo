"""Generation-pinned source authority shared by application-layer tests."""

from __future__ import annotations

import pytest
from dev.registry.compiler.authority import compiled_bundled_authority

from ..domain.calculations.registry.authority import PinnedAuthorityOperation
from ..domain.calculations.registry.authority_artifact import GovernedFactComponentQuery
from ..domain.calculations.registry.tests.authority_fakes import FakeAuthorityComponentReader


@pytest.fixture(scope="session")
def operation() -> PinnedAuthorityOperation:
    """Expose canonical authored facts without requiring a published package."""
    authority = compiled_bundled_authority()
    reader = FakeAuthorityComponentReader(
        {GovernedFactComponentQuery(str(fact_id)): fact for fact_id, fact in authority.catalogues.facts.facts.items()}
    )
    return PinnedAuthorityOperation(reader, reader.pin())

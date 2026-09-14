"""Generation-pinned authority fixtures for category projection tests."""

from __future__ import annotations

import pytest
from dev.registry.compiler.authority import compiled_bundled_authority

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.authority_artifact import GovernedFactComponentQuery
from ....domain.calculations.registry.tests.authority_fakes import FakeAuthorityComponentReader


@pytest.fixture(scope="session")
def operation() -> PinnedAuthorityOperation:
    """Expose the compiled source authority through the operation contract."""
    authority = compiled_bundled_authority()
    reader = FakeAuthorityComponentReader(
        {GovernedFactComponentQuery(str(fact_id)): fact for fact_id, fact in authority.catalogues.facts.facts.items()}
    )
    return PinnedAuthorityOperation(reader, reader.pin())

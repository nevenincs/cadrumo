"""Generation-pinned authority fixtures for deadline tests."""

from __future__ import annotations

import pytest
from dev.registry.compiler.authority import compiled_bundled_authority

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.authority_artifact import (
    GovernedFactComponentQuery,
    RuntimeCatalogueComponentQuery,
)
from ....domain.calculations.registry.tests.authority_fakes import FakeAuthorityComponentReader


@pytest.fixture(scope="session")
def operation() -> PinnedAuthorityOperation:
    """Expose compiled deadline facts and runtime bands through one operation."""
    authority = compiled_bundled_authority()
    components = {
        **{
            GovernedFactComponentQuery(str(fact_id)): fact for fact_id, fact in authority.catalogues.facts.facts.items()
        },
        RuntimeCatalogueComponentQuery("recargo_bands"): authority.catalogues.runtime.recargo_bands,
    }
    reader = FakeAuthorityComponentReader(components)
    return PinnedAuthorityOperation(reader, reader.pin())

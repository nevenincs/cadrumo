"""Generation-pinned authority fixtures for apoderamiento tests."""

from __future__ import annotations

import pytest
from dev.registry.compiler.authority import compiled_bundled_authority

from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from .....domain.calculations.registry.authority_artifact import RuntimeCatalogueComponentQuery
from .....domain.calculations.registry.tests.authority_fakes import FakeAuthorityComponentReader


@pytest.fixture(scope="session")
def operation() -> PinnedAuthorityOperation:
    """Expose the compiled scope components through one operation."""
    authority = compiled_bundled_authority()
    reader = FakeAuthorityComponentReader(
        {
            RuntimeCatalogueComponentQuery("apoderamientos_scopes"): authority.catalogues.runtime.apoderamientos_scopes,
            RuntimeCatalogueComponentQuery(
                "apoderamientos_version"
            ): authority.catalogues.runtime.apoderamientos_version,
        }
    )
    return PinnedAuthorityOperation(reader, reader.pin())

"""Encrypted-runtime fixtures for outbound LLM adapter tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from dev.registry.compiler.authority import compiled_bundled_authority

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.authority_artifact import GovernedFactComponentQuery
from ....domain.calculations.registry.tests.authority_fakes import FakeAuthorityComponentReader
from ...persistence.storage.tests.secure_sql import TestRuntimeProfile
from ...persistence.tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture

_BUCKET_ID = "70316d3b-62cd-4735-b831-c6712f01a418"


@pytest.fixture(scope="session")
def operation() -> PinnedAuthorityOperation:
    """Expose canonical authored facts without requiring a published package."""
    authority = compiled_bundled_authority()
    reader = FakeAuthorityComponentReader(
        {GovernedFactComponentQuery(str(fact_id)): fact for fact_id, fact in authority.catalogues.facts.facts.items()}
    )
    return PinnedAuthorityOperation(reader, reader.pin())


@pytest.fixture(autouse=True)
def secure_object_test_backend(
    secure_object_test_profile: TestRuntimeProfile,
) -> Iterator[None]:
    """Route LLM cache and usage persistence through a per-test encrypted DB."""

    _ = secure_object_test_profile
    yield


secure_object_test_profile = bucket_scoped_runtime_profile_fixture(
    _BUCKET_ID,
    autouse=False,
    name="secure_object_test_profile",
)

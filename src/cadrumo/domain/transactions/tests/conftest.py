"""Fixtures for generation-pinned transaction prompt tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from dev.registry.compiler.fact_providers import compile_authored_fact_catalogue

from ....core.resources.bundled_data import bundled_path
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.authority_artifact import GovernedFactComponentQuery
from ....domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ....domain.calculations.registry.tests.authority_fakes import FakeAuthorityComponentReader


@pytest.fixture(scope="session")
def operation() -> Iterator[PinnedAuthorityOperation]:
    """Expose the authored facts through one generation-pinned reader."""
    facts = compile_authored_fact_catalogue(bundled_path("registry", "aeat"))
    reader = FakeAuthorityComponentReader(
        {GovernedFactComponentQuery(str(fact_id)): fact for fact_id, fact in facts.facts.items()}
    )
    pinned = PinnedAuthorityOperation(reader, reader.pin())
    with validating_governed_facts(pinned):
        yield pinned

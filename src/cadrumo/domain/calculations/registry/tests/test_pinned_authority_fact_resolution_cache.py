"""Generation-pinned governed facts are validated and resolved only once."""

from __future__ import annotations

from datetime import date

import pytest

from ..authority import PinnedAuthorityOperation
from ..authority_artifact import GovernedFactComponentQuery
from ..facts.resolution import MappingFactQuery
from ..schema_base import DateAxis
from .artifact_runtime_support import minimal_catalogues
from .authority_fakes import FakeAuthorityComponentReader

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_pinned_operation_reuses_one_typed_resolution_for_an_identical_query() -> None:
    fact = minimal_catalogues().facts.facts["spanish-tax-identifier-format"]
    component_query = GovernedFactComponentQuery(str(fact.fact_id))
    reader = FakeAuthorityComponentReader({component_query: fact})
    operation = PinnedAuthorityOperation(reader, reader.pin())
    query = MappingFactQuery(
        fact_id=fact.fact_id,
        date_axis=DateAxis.FILING_PERIOD,
        effective_date=date(2025, 1, 1),
    )

    first = operation.resolve_governed_fact(query)
    second = operation.resolve_governed_fact(query)

    assert second is first
    assert reader.loads == [component_query]

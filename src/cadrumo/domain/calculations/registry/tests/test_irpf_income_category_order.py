"""The IRPF income-category order fails closed when it names no category."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pytest

from ..authority import PinnedAuthorityOperation
from ..errors import RegistryValidationError
from ..facts.resolution import GovernedFactQuery, MappingFactQuery, ResolvedGovernedFact, ResolvedMappingFact
from ..irpf_income_categories import resolve_irpf_income_category_catalogue
from ..schema import SupportedFilingYearsCatalogue
from ..schema_base import DateAxis

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ON = date(2026, 3, 10)
_ORDER_KEY = "irpf_income_category.order"


@dataclass
class _FixedFact:
    resolved: ResolvedMappingFact
    support: SupportedFilingYearsCatalogue

    def resolve_governed_fact(self, query: GovernedFactQuery) -> ResolvedGovernedFact:
        return self.resolved

    def supported_filing_years(self) -> SupportedFilingYearsCatalogue:
        return self.support


def _vocabulary(operation: PinnedAuthorityOperation) -> ResolvedMappingFact:
    resolved = operation.resolve_governed_fact(
        MappingFactQuery(
            fact_id="irpf-income-category-vocabulary",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=_ON,
        ),
    )
    assert isinstance(resolved, ResolvedMappingFact)
    return resolved


def _with_order(resolved: ResolvedMappingFact, value: str) -> ResolvedMappingFact:
    entries = tuple(
        entry.model_copy(update={"value": value}) if entry.key == _ORDER_KEY else entry
        for entry in resolved.payload.entries
    )
    return resolved.model_copy(update={"payload": resolved.payload.model_copy(update={"entries": entries})})


def test_the_authored_order_resolves_every_declared_category(operation: PinnedAuthorityOperation) -> None:
    catalogue = resolve_irpf_income_category_catalogue(effective_date=_ON, authority=operation)

    assert catalogue.definitions
    assert catalogue.activity_token in catalogue.all_categories


@pytest.mark.parametrize("separators", [",,", " , "])
def test_an_order_of_only_separators_is_refused_at_the_order_entry(
    operation: PinnedAuthorityOperation, separators: str
) -> None:
    authority = _FixedFact(_with_order(_vocabulary(operation), separators), operation.supported_filing_years())

    with pytest.raises(RegistryValidationError) as raised:
        resolve_irpf_income_category_catalogue(effective_date=_ON, authority=authority)

    assert str(raised.value) == f"IRPF income-category vocabulary {_ORDER_KEY!r} must contain unique tokens"

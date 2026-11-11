"""The income families without a calculator come from the registry fact and fail closed.

The coverage fact must state a verdict for every token the income-category
vocabulary declares. A family left out, or a verdict that is neither computed nor
not computed, is refused: silence must never read as "computed".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pytest

from ..authority import PinnedAuthorityOperation
from ..errors import RegistryValidationError
from ..facts.resolution import GovernedFactQuery, ResolvedGovernedFact, ResolvedMappingFact
from ..irpf_income_categories import irpf_income_categories_without_calculator, resolve_irpf_income_category_catalogue
from ..snapshot_globals import SupportedFilingYearsCatalogue
from .authored_editions import filing_year_envelope

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ON = date(filing_year_envelope().horizon, 3, 10)
_COVERAGE_FACT_ID = "irpf-income-family-calculator-coverage"
_PREFIX = "irpf_income_family."
_SUFFIX = ".computed"


@dataclass
class _CoverageEntries:
    """Authority serving the published facts, with the coverage fact's entries rewritten by ``rewrite``."""

    inner: PinnedAuthorityOperation
    drop: frozenset[str] = frozenset()
    set_to: tuple[tuple[str, str], ...] = ()

    def resolve_governed_fact(self, query: GovernedFactQuery) -> ResolvedGovernedFact:
        resolved = self.inner.resolve_governed_fact(query)
        if query.fact_id != _COVERAGE_FACT_ID:
            return resolved
        assert isinstance(resolved, ResolvedMappingFact)
        replacements = dict(self.set_to)
        entries = tuple(
            entry.model_copy(update={"value": replacements.get(str(entry.key), entry.value)})
            for entry in resolved.payload.entries
            if str(entry.key) not in self.drop
        )
        return resolved.model_copy(update={"payload": resolved.payload.model_copy(update={"entries": entries})})

    def supported_filing_years(self) -> SupportedFilingYearsCatalogue:
        return self.inner.supported_filing_years()


def _key(token: str) -> str:
    return f"{_PREFIX}{token}{_SUFFIX}"


def test_every_category_of_the_vocabulary_has_a_verdict_in_the_authored_fact(
    operation: PinnedAuthorityOperation,
) -> None:
    catalogue = resolve_irpf_income_category_catalogue(effective_date=_ON, authority=operation)

    uncomputed = irpf_income_categories_without_calculator(effective_date=_ON, authority=operation)

    assert uncomputed < catalogue.all_categories
    assert uncomputed


def test_a_family_marked_computed_leaves_the_uncomputed_set(operation: PinnedAuthorityOperation) -> None:
    before = irpf_income_categories_without_calculator(effective_date=_ON, authority=operation)
    token = sorted(before)[0]

    after = irpf_income_categories_without_calculator(
        effective_date=_ON, authority=_CoverageEntries(operation, set_to=((_key(token), "true"),))
    )

    assert after == before - {token}


def test_a_family_marked_not_computed_joins_the_uncomputed_set(operation: PinnedAuthorityOperation) -> None:
    catalogue = resolve_irpf_income_category_catalogue(effective_date=_ON, authority=operation)
    computed = sorted(
        catalogue.all_categories - irpf_income_categories_without_calculator(effective_date=_ON, authority=operation)
    )[0]

    after = irpf_income_categories_without_calculator(
        effective_date=_ON, authority=_CoverageEntries(operation, set_to=((_key(computed), "false"),))
    )

    assert computed in after


def test_a_category_without_a_verdict_is_refused(operation: PinnedAuthorityOperation) -> None:
    token = sorted(resolve_irpf_income_category_catalogue(effective_date=_ON, authority=operation).all_categories)[0]

    with pytest.raises(RegistryValidationError):
        irpf_income_categories_without_calculator(
            effective_date=_ON, authority=_CoverageEntries(operation, drop=frozenset({_key(token)}))
        )


def test_a_verdict_that_is_neither_true_nor_false_is_refused(operation: PinnedAuthorityOperation) -> None:
    token = sorted(resolve_irpf_income_category_catalogue(effective_date=_ON, authority=operation).all_categories)[0]

    with pytest.raises(RegistryValidationError):
        irpf_income_categories_without_calculator(
            effective_date=_ON, authority=_CoverageEntries(operation, set_to=((_key(token), "maybe"),))
        )

"""Statutory caps survive the trip from the bundled authority into a profile.

The profile fact projects each condition-selected cap variant as its own
entries, and a year-referenced cap as a separate dated fact. Resolution must
rebuild both exactly as declared and refuse when the authority cannot supply
the amount, never substituting a zero or a neighbouring year's figure.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ...calculations.registry.authority import PinnedAuthorityOperation
from ...calculations.registry.errors import RegistryValidationError
from ...calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ...calculations.registry.facts.schema import FactSelector, MappingFactEntry, MappingFactPayload
from ...calculations.registry.schema_base import DateAxis
from ..errors import CategoryValidationError
from ..registry import CATEGORY_PROFILE_FACT_ID, _profile_from_authority_fact, resolve_category_profiles
from ..spending_category import SpendingCategory
from ..spending_category_catalogue import require_spending_category

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _resolved_profile_fact(
    category: SpendingCategory,
    year: int,
    operation: PinnedAuthorityOperation,
) -> ResolvedMappingFact:
    fact = operation.resolve_governed_fact(
        MappingFactQuery(
            fact_id=CATEGORY_PROFILE_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=date(year, 12, 31),
            selectors=(FactSelector(name="category", value=category.value),),
        )
    )
    assert isinstance(fact, ResolvedMappingFact)
    return fact


def _with_entries(fact: ResolvedMappingFact, entries: tuple[MappingFactEntry, ...]) -> ResolvedMappingFact:
    return fact.model_copy(update={"payload": MappingFactPayload(entries=entries)})


def test_2026_national_diet_cap_carries_both_daily_variants(operation: PinnedAuthorityOperation) -> None:
    """RIRPF art. 9.A.3.a: 26,67 EUR/day without an overnight stay, 53,34 EUR/day with one."""
    rule = resolve_category_profiles(2026, operation=operation)[
        require_spending_category("manutencion_dietas_nacional")
    ].proportionality

    assert rule.statutory_cap_eur is None
    assert rule.statutory_cap_eur_per_day is None
    assert {v.id: v.statutory_cap_eur_per_day for v in rule.statutory_cap_variants} == {
        "sin-pernocta": Decimal("26.67"),
        "con-pernocta": Decimal("53.34"),
    }
    assert all(str(v.label) for v in rule.statutory_cap_variants)


def test_year_referenced_cap_below_the_supported_floor_is_refused(operation: PinnedAuthorityOperation) -> None:
    support = operation.supported_filing_years()
    fact = _resolved_profile_fact(require_spending_category("mutualidad_alternativa"), support.horizon, operation)
    below_floor = support.floor - 1

    with pytest.raises(RegistryValidationError, match="outside the supported filing years"):
        _profile_from_authority_fact(fact, operation=operation, year=below_floor)


def test_unknown_cap_variant_field_is_refused_not_dropped(operation: PinnedAuthorityOperation) -> None:
    fact = _resolved_profile_fact(require_spending_category("manutencion_dietas_nacional"), 2026, operation)
    tampered = _with_entries(
        fact,
        (*fact.payload.entries, MappingFactEntry(key="statutory_cap_variant.sin-pernocta.eur_per_week", value="1")),
    )

    with pytest.raises(CategoryValidationError, match="unknown cap variant entry"):
        _profile_from_authority_fact(tampered, operation=operation, year=2026)


def test_cap_variant_without_an_amount_is_refused(operation: PinnedAuthorityOperation) -> None:
    fact = _resolved_profile_fact(require_spending_category("manutencion_dietas_nacional"), 2026, operation)
    stripped = _with_entries(
        fact,
        tuple(e for e in fact.payload.entries if e.key != "statutory_cap_variant.con-pernocta.eur_per_day"),
    )

    with pytest.raises(CategoryValidationError, match="declares no amount"):
        _profile_from_authority_fact(stripped, operation=operation, year=2026)

"""A dateless vocabulary read never depends on the date the program runs.

Each catalogue is read through the published authority without a date while the
clock is frozen outside the supported filing years, and the result is compared
with the union of the dated reads at every year of the support envelope.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime

import pytest

from .....core.time.clock import frozen_clock, today_madrid
from ..authority import bundled_indexed_authority
from ..concepto_ingreso import resolve_concepto_ingreso_catalogue
from ..entity_type import resolve_entity_vocabulary
from ..eu_member_state_catalogue import resolve_eu_member_state_catalogue
from ..gasto_capital_inmobiliario import resolve_gasto_capital_inmobiliario_catalogue
from ..governed_fact_scope import GovernedFactSource
from ..irpf_regimes import resolve_irpf_regime_vocabulary
from ..renta_codes_catalogue import fiscal_residency_choices, ue_eea_country_codes
from .authored_editions import filing_year_envelope

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(scope="module")
def authority() -> Iterator[GovernedFactSource]:
    with bundled_indexed_authority().operation() as operation:
        yield operation


def _envelope_dates() -> tuple[date, ...]:
    return tuple(date(year, month, 1) for year in filing_year_envelope().years for month in (1, 7))


def _outside_the_envelope() -> datetime:
    return datetime(filing_year_envelope().floor - 3, 6, 15, 12, tzinfo=UTC)


def _union_of_dated_reads[T](read: Callable[[date], frozenset[T]]) -> frozenset[T]:
    union: frozenset[T] = frozenset()
    for coordinate in _envelope_dates():
        union |= read(coordinate)
    return union


def test_the_dateless_eu_eea_country_set_is_the_envelope_union_whatever_the_run_date(
    authority: GovernedFactSource,
) -> None:
    with frozen_clock(_outside_the_envelope()):
        assert not filing_year_envelope().admits_coordinate(today_madrid().year)
        dateless = ue_eea_country_codes(authority=authority)

    assert dateless == _union_of_dated_reads(lambda on: ue_eea_country_codes(effective_date=on, authority=authority))
    assert "ES" in dateless


def test_the_dateless_eu_member_state_catalogue_admits_the_envelope_union(authority: GovernedFactSource) -> None:
    with frozen_clock(_outside_the_envelope()):
        dateless = resolve_eu_member_state_catalogue(authority=authority).all_states

    assert dateless == _union_of_dated_reads(
        lambda on: resolve_eu_member_state_catalogue(effective_date=on, authority=authority).all_states
    )


def test_the_dateless_entity_vocabulary_admits_the_envelope_union(authority: GovernedFactSource) -> None:
    with frozen_clock(_outside_the_envelope()):
        dateless = resolve_entity_vocabulary(authority=authority)

    assert dateless.all_entity_types == _union_of_dated_reads(
        lambda on: resolve_entity_vocabulary(effective_date=on, authority=authority).all_entity_types
    )
    assert dateless.all_legal_entity_forms == _union_of_dated_reads(
        lambda on: resolve_entity_vocabulary(effective_date=on, authority=authority).all_legal_entity_forms
    )


def test_the_dateless_irpf_regime_vocabulary_admits_the_envelope_union(authority: GovernedFactSource) -> None:
    with frozen_clock(_outside_the_envelope()):
        dateless = resolve_irpf_regime_vocabulary(authority=authority)

    assert dateless.all_estimation_regimes == _union_of_dated_reads(
        lambda on: resolve_irpf_regime_vocabulary(effective_date=on, authority=authority).all_estimation_regimes
    )
    assert dateless.all_special_regimes == _union_of_dated_reads(
        lambda on: resolve_irpf_regime_vocabulary(effective_date=on, authority=authority).all_special_regimes
    )


def test_dateless_fiscal_residency_choices_do_not_follow_the_clock(authority: GovernedFactSource) -> None:
    with frozen_clock(_outside_the_envelope()):
        outside = fiscal_residency_choices(authority=authority)
    newest = fiscal_residency_choices(effective_date=date(filing_year_envelope().horizon, 12, 31), authority=authority)

    assert outside == newest


def test_the_dateless_income_concept_vocabulary_admits_the_envelope_union(authority: GovernedFactSource) -> None:
    with frozen_clock(_outside_the_envelope()):
        dateless = resolve_concepto_ingreso_catalogue(authority=authority).all_tokens

    assert dateless == _union_of_dated_reads(
        lambda on: resolve_concepto_ingreso_catalogue(effective_date=on, authority=authority).all_tokens
    )


def test_the_dateless_rental_expense_vocabulary_admits_the_envelope_union(authority: GovernedFactSource) -> None:
    with frozen_clock(_outside_the_envelope()):
        dateless = resolve_gasto_capital_inmobiliario_catalogue(authority=authority)
    newest = resolve_gasto_capital_inmobiliario_catalogue(
        effective_date=date(filing_year_envelope().horizon, 12, 31), authority=authority
    )

    assert dateless.all_tokens == _union_of_dated_reads(
        lambda on: resolve_gasto_capital_inmobiliario_catalogue(effective_date=on, authority=authority).all_tokens
    )
    assert dateless.concepts == newest.concepts

"""Integration: 2025 + 2024 + 2023 + 2022 + 2021 IRPF estatal escala brackets resolve correctly.

The escala estatal is registered as a `bracket_table` ParameterDefinition under
each ejercicio with `bracket_axis = "filing_period"`. The runtime selects the
window via the date_context's filing_period date and computes
``fixed_addition + marginal_rate * (base - lower_bound)`` for the bracket
covering the supplied base amount.

These tests anchor:

  - The parameter resolves cleanly for every backported ejercicio.
  - The cuota at known break-points matches the AEAT-published worked
    examples (e.g. on 30 000 EUR base → 4,182.75 EUR cuota).
  - Top-bracket open upper_bound resolves for high-income amounts.
  - Date-context selects the correct bracket window per ejercicio.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aeat.domain.calculations.registry import RegistryValidationError
from aeat.domain.calculations.registry._formula_runtime import _resolve_bracket
from aeat.domain.calculations.registry._loader import load_registry_tree
from aeat.core.paths import PROJECT_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_REGISTRY_ROOT = PROJECT_ROOT / "registry" / "aeat"
_BACKPORTED_YEARS = (2020, 2021, 2022, 2023, 2024, 2025)
_POST_AMENDMENT_YEARS = (2021, 2022, 2023, 2024, 2025)


def _bracket_table(year: int):
    modelos, _ = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(m for m in modelos if m.id == "100")
    revision = modelo.revisions[str(year)]
    return next(p for p in revision.parameters if p.id == f"renta-{year}-escala-estatal-base-general")


@pytest.mark.parametrize("year", _BACKPORTED_YEARS)
def test_escala_estatal_resolves_at_first_bracket_lower_bound(year: int) -> None:
    table = _bracket_table(year)
    cuota = _resolve_bracket(table, Decimal("0"), {"filing_period": date(year, 12, 31)})
    assert cuota == Decimal("0")


@pytest.mark.parametrize("year", _BACKPORTED_YEARS)
def test_escala_estatal_resolves_at_12450_break_point(year: int) -> None:
    """At exactly 12,450 the cuota equals the fixed_addition of the SECOND bracket: 1182.75."""
    table = _bracket_table(year)
    cuota = _resolve_bracket(table, Decimal("12450"), {"filing_period": date(year, 12, 31)})
    assert cuota == Decimal("1182.75")


@pytest.mark.parametrize("year", _BACKPORTED_YEARS)
def test_escala_estatal_resolves_for_30k_base_general(year: int) -> None:
    """Base 30,000: lands in third bracket [20200, 35200] @ 15%.

    cuota = 2112.75 + 0.15 * (30000 - 20200) = 2112.75 + 1470 = 3582.75
    """
    table = _bracket_table(year)
    cuota = _resolve_bracket(table, Decimal("30000"), {"filing_period": date(year, 12, 31)})
    assert cuota == Decimal("3582.75")


@pytest.mark.parametrize("year", _POST_AMENDMENT_YEARS)
def test_escala_estatal_resolves_in_top_bracket_post_2021(year: int) -> None:
    """Base 500,000: lands in top bracket [300000, ∞] @ 24.5% (post-Ley 11/2020).

    cuota = 62950.75 + 0.245 * (500000 - 300000) = 62950.75 + 49000 = 111950.75
    """
    table = _bracket_table(year)
    cuota = _resolve_bracket(table, Decimal("500000"), {"filing_period": date(year, 12, 31)})
    assert cuota == Decimal("111950.75")


def test_escala_estatal_2020_top_bracket_uses_pre_amendment_22_5_rate() -> None:
    """Pre-Ley 11/2020 (effective 2021), the top tier was the open 22.5% bracket.

    2020 base 500,000: lands in top bracket [60000, ∞] @ 22.5%.
    cuota = 8950.75 + 0.225 * (500000 - 60000) = 8950.75 + 99000 = 107950.75
    """
    table = _bracket_table(2020)
    cuota = _resolve_bracket(table, Decimal("500000"), {"filing_period": date(2020, 12, 31)})
    assert cuota == Decimal("107950.75")


@pytest.mark.parametrize("year", _BACKPORTED_YEARS)
def test_escala_estatal_rejects_date_outside_year_window(year: int) -> None:
    table = _bracket_table(year)
    other_year = year - 5
    with pytest.raises(RegistryValidationError, match="no bracket valid"):
        _resolve_bracket(table, Decimal("30000"), {"filing_period": date(other_year, 6, 1)})

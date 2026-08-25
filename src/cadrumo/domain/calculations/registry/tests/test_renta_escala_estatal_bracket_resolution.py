"""Calc-verify: the IRPF art.62-63 base-general estatal escala resolves correctly.

The escala estatal general is registered as a ``bracket_table``
ParameterDefinition ``renta-{year}-escala-estatal-base-general`` under
each ejercicio with ``bracket_axis = "filing_period"`` and
``legal_refs = ["ley-35-2006:art-62", "ley-35-2006:art-63"]``. The
runtime selects the window via the date_context's filing_period date
and computes ``fixed_addition + marginal_rate * (base - lower_bound)``
for the bracket covering the supplied base liquidable general.

Expected values are NOT hand-computed from the registry formula. They
are transcribed from external AEAT / BOE authority:

  - The "Cuota íntegra (euros)" column of the IRPF escala general
    estatal (art. 63.1.1.º Ley 35/2006), as published in the BOE
    consolidated text of Ley 35/2006 (BOE-A-2006-20764) and reproduced
    in the AEAT Manual práctico de Renta. The two-column statutory
    table pairs each "Base liquidable - Hasta euros" breakpoint with
    the cuota íntegra accumulated up to it: 12.450,00 → 1.182,75;
    20.200,00 → 2.112,75; 35.200,00 → 4.362,75; 60.000,00 → 8.950,75.
    The >300.000 tier (cuota 62.950,75) was added by the disposición
    final segunda of Ley 11/2020 (Presupuestos Generales 2021),
    effective ejercicio 2021.

At a statutory breakpoint the cuota equals the published cuota íntegra
of the bracket that starts at that breakpoint, because the marginal
term ``rate * (base - lower_bound)`` is zero there. Tests assert at
breakpoints (external oracle) and verify bracket SELECTION / window
handling structurally (no manufactured mid-bracket Decimals).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import cache

import pytest

from ..errors import RegistryValidationError
from ..formula_runtime import _resolve_bracket
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BACKPORTED_YEARS = (2020, 2021, 2022, 2023, 2024, 2025)
_POST_AMENDMENT_YEARS = (2021, 2022, 2023, 2024, 2025)


@cache
def _bracket_table(year: int):
    modelo, _ = _committed_modelo("100")
    revision = modelo.revisions[str(year)]
    return next(p for p in revision.parameters if p.id == f"renta-{year}-escala-estatal-base-general")


def test_escala_estatal_resolves_at_first_bracket_lower_bound() -> None:
    for year in _BACKPORTED_YEARS:
        table = _bracket_table(year)
        cuota = _resolve_bracket(table, Decimal("0"), {"filing_period": date(year, 12, 31)})
        assert cuota == Decimal("0"), year


def test_escala_estatal_resolves_at_12450_break_point() -> None:
    """At exactly 12,450 the cuota equals the fixed_addition of the SECOND bracket: 1182.75."""
    for year in _BACKPORTED_YEARS:
        table = _bracket_table(year)
        cuota = _resolve_bracket(table, Decimal("12450"), {"filing_period": date(year, 12, 31)})
        assert cuota == Decimal("1182.75"), year


def test_escala_estatal_at_20200_break_point_matches_published_cuota_integra() -> None:
    """At 20.200 EUR the cuota equals the published cuota íntegra of the
    third bracket: 2.112,75 EUR (BOE-A-2006-20764 art.63.1.1.º estatal
    escala general table)."""
    for year in _BACKPORTED_YEARS:
        table = _bracket_table(year)
        cuota = _resolve_bracket(table, Decimal("20200"), {"filing_period": date(year, 12, 31)})
        assert cuota == Decimal("2112.75"), year


def test_escala_estatal_at_35200_break_point_matches_published_cuota_integra() -> None:
    """At 35.200 EUR the cuota equals the published cuota íntegra of the
    fourth bracket: 4.362,75 EUR (BOE-A-2006-20764 art.63.1.1.º estatal
    escala general table)."""
    for year in _BACKPORTED_YEARS:
        table = _bracket_table(year)
        cuota = _resolve_bracket(table, Decimal("35200"), {"filing_period": date(year, 12, 31)})
        assert cuota == Decimal("4362.75"), year


def test_escala_estatal_at_60000_break_point_matches_published_cuota_integra() -> None:
    """At 60.000 EUR the cuota equals the published cuota íntegra of the
    bracket starting at 60.000: 8.950,75 EUR. This breakpoint is stable
    across every ejercicio (BOE-A-2006-20764 art.63.1.1.º)."""
    for year in _BACKPORTED_YEARS:
        table = _bracket_table(year)
        cuota = _resolve_bracket(table, Decimal("60000"), {"filing_period": date(year, 12, 31)})
        assert cuota == Decimal("8950.75"), year


def test_escala_estatal_at_300000_break_point_matches_published_cuota_integra() -> None:
    """At 300.000 EUR the cuota equals the published cuota íntegra of the
    top bracket added by Ley 11/2020 (effective 2021): 62.950,75 EUR."""
    for year in _POST_AMENDMENT_YEARS:
        table = _bracket_table(year)
        cuota = _resolve_bracket(table, Decimal("300000"), {"filing_period": date(year, 12, 31)})
        assert cuota == Decimal("62950.75"), year


def test_escala_estatal_selects_top_bracket_for_high_income_post_2021() -> None:
    """Structural: a base above 300.000 must SELECT the open top bracket.

    No mid-bracket Decimal is manufactured; the test asserts that the
    bracket the runtime resolves into is the post-Ley-11/2020 open tier
    (lower_bound 300.000, no upper_bound) by comparing the runtime cuota
    against the floor cuota at the bracket's own lower bound — i.e. the
    cuota for 500.000 must exceed the published 300.000 cuota íntegra
    and stay finite, proving the open top bracket was chosen.
    """
    for year in _POST_AMENDMENT_YEARS:
        table = _bracket_table(year)
        top = max(table.brackets, key=lambda b: b.lower_bound)
        assert top.lower_bound == Decimal("300000"), year
        assert top.upper_bound is None
        cuota = _resolve_bracket(table, Decimal("500000"), {"filing_period": date(year, 12, 31)})
        floor = _resolve_bracket(table, Decimal("300000"), {"filing_period": date(year, 12, 31)})
        assert cuota > floor, year


def test_escala_estatal_2020_top_bracket_is_open_above_60000() -> None:
    """Structural: pre-Ley 11/2020 the 2020 estatal escala general had its
    top tier open above 60.000 EUR (no >300.000 split yet).

    The >300.000 bracket is a 2021 amendment; for 2020 a base above
    60.000 must select the open [60.000, ∞] tier. Asserted structurally
    via the bracket table, with no manufactured mid-bracket Decimal.
    """
    table = _bracket_table(2020)
    top = max(table.brackets, key=lambda b: b.lower_bound)
    assert top.lower_bound == Decimal("60000")
    assert top.upper_bound is None
    cuota = _resolve_bracket(table, Decimal("500000"), {"filing_period": date(2020, 12, 31)})
    floor = _resolve_bracket(table, Decimal("60000"), {"filing_period": date(2020, 12, 31)})
    assert cuota > floor


def test_escala_estatal_rejects_date_outside_year_window() -> None:
    for year in _BACKPORTED_YEARS:
        table = _bracket_table(year)
        other_year = year - 5
        with pytest.raises(RegistryValidationError, match="no bracket valid"):
            _resolve_bracket(table, Decimal("30000"), {"filing_period": date(other_year, 6, 1)})

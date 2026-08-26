"""Calc-verify: the IRPF art.76 ahorro-base autonomica escala resolves correctly.

The escala autonomica del ahorro is registered as a ``bracket_table``
ParameterDefinition ``renta-{year}-escala-autonomica-base-ahorro`` under
each ejercicio, with ``bracket_axis = "filing_period"`` and
``legal_refs = ["ley-35-2006:art-76"]``. The runtime computes
``fixed_addition + marginal_rate * (base - lower_bound)`` for the
bracket covering the supplied base liquidable del ahorro.

Unlike the autonomica general-base escala (which CCAA legislate
individually, dispatched via ``lookup_bracket_by_ccaa``), the savings
base autonomica scale is fixed by state law: art.76 Ley 35/2006. The
AEAT Manual practico de Renta confirms this scale is identical to the
art.66.1 estatal savings scale for every ejercicio 2020-2025.

Expected values are NOT hand-computed from the registry formula. They
are transcribed from external AEAT authority:

  - The "Incremento en cuota integra estatal (euros)" column published
    in the AEAT Manual practico de Renta, section "Gravamen de la base
    liquidable del ahorro - Gravamen autonomico - Normativa: Art. 76
    Ley IRPF" (Renta 2025 Parte 1, page 953). At each breakpoint the
    cuota equals the published incremento of the bracket starting at
    that breakpoint: 6.000->570, 50.000->5.190, 200.000->22.440,
    300.000->35.940. These figures also appear in the BOE consolidated
    text of art.76 Ley 35/2006 (BOE-A-2006-20764).

  - The worked example on AEAT Manual Renta 2025 Parte 1, page 954
    ("Don A.B.C., residente en Aragon"): base liquidable del ahorro
    2.800 EUR, minimo personal y familiar absorbed in full by the
    general base. Manual: "Gravamen autonomico 2.800 x 9,50% = 266".

The savings tariff was amended across ejercicios: Ley 11/2020 added
the >200.000 bracket effective 2021; Ley 31/2022 added the >300.000
bracket effective 2023; Ley 7/2024 raised the top marginal rate to
15% effective 2025 (art.76 amended by the same three laws as art.66).
Each year's brackets are grounded against that year's AEAT manual.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import cache

import pytest

from ..errors import RegistryValidationError
from ..formula_runtime_ops import resolve_bracket
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ALL_YEARS = (2020, 2021, 2022, 2023, 2024, 2025)
_YEARS_WITH_200K_BRACKET = (2021, 2022, 2023, 2024, 2025)
_YEARS_WITH_300K_BRACKET = (2023, 2024, 2025)


@cache
def _ahorro_table(year: int):
    revision = _revision(year)
    return next(p for p in revision.parameters if p.id == f"renta-{year}-escala-autonomica-base-ahorro")


@cache
def _revision(year: int):
    modelo, _ = _committed_modelo("100")
    return modelo.revisions[str(year)]


#: Each pre-2024 filing year's applicability window predates art.76's current
#: catalogue redaction (effective_from 2024-12-22, Ley 7/2024), so it cites the
#: version-scoped redaction actually in force for that filing year instead of
#: the bare current id.
_ART_76_REF_BY_YEAR = {
    2020: "ley-35-2006:art-76-2015",
    2021: "ley-35-2006:art-76-2021",
    2022: "ley-35-2006:art-76-2021",
    2023: "ley-35-2006:art-76-2023",
    2024: "ley-35-2006:art-76",
    2025: "ley-35-2006:art-76",
}


def test_ahorro_escala_declares_art_76_legal_ref() -> None:
    """The autonomica ahorro escala must carry the art.76 legal grounding."""
    for year in _ALL_YEARS:
        table = _ahorro_table(year)
        assert _ART_76_REF_BY_YEAR[year] in table.legal_refs
        assert table.data_type == "bracket_table"


def test_ahorro_escala_resolves_at_zero_base() -> None:
    for year in _ALL_YEARS:
        table = _ahorro_table(year)
        cuota = resolve_bracket(table, Decimal("0"), {"filing_period": date(year, 12, 31)})
        assert cuota == Decimal("0"), year


def test_ahorro_escala_aeat_manual_2800_worked_example() -> None:
    """AEAT Manual Renta 2025 page 954: 2.800 EUR base liquidable del ahorro.

    The manual states "Gravamen autonomico 2.800 x 9,50% = 266". The first
    bracket marginal rate (9,50%) has been stable across every ejercicio
    covered here, so the published 266 EUR is the oracle for all years.
    """
    for year in _ALL_YEARS:
        table = _ahorro_table(year)
        cuota = resolve_bracket(table, Decimal("2800"), {"filing_period": date(year, 12, 31)})
        assert cuota == Decimal("266.000"), year


def test_ahorro_escala_at_6000_breakpoint_matches_published_incremento() -> None:
    """At 6.000 EUR the cuota equals the published incremento of the
    second bracket: 570 EUR (AEAT manual art.76 autonomica table)."""
    for year in _ALL_YEARS:
        table = _ahorro_table(year)
        cuota = resolve_bracket(table, Decimal("6000"), {"filing_period": date(year, 12, 31)})
        assert cuota == Decimal("570.000"), year


def test_ahorro_escala_at_50000_breakpoint_matches_published_incremento() -> None:
    """At 50.000 EUR the cuota equals the published incremento of the
    third bracket: 5.190 EUR (AEAT manual art.76 autonomica table)."""
    for year in _ALL_YEARS:
        table = _ahorro_table(year)
        cuota = resolve_bracket(table, Decimal("50000"), {"filing_period": date(year, 12, 31)})
        assert cuota == Decimal("5190.000"), year


def test_ahorro_escala_at_200000_breakpoint_matches_published_incremento() -> None:
    """At 200.000 EUR the cuota equals the published incremento of the
    bracket added by Ley 11/2020 (effective 2021): 22.440 EUR."""
    for year in _YEARS_WITH_200K_BRACKET:
        table = _ahorro_table(year)
        cuota = resolve_bracket(table, Decimal("200000"), {"filing_period": date(year, 12, 31)})
        assert cuota == Decimal("22440.000"), year


def test_ahorro_escala_at_300000_breakpoint_matches_published_incremento() -> None:
    """At 300.000 EUR the cuota equals the published incremento of the
    top bracket added by Ley 31/2022 (effective 2023): 35.940 EUR."""
    for year in _YEARS_WITH_300K_BRACKET:
        table = _ahorro_table(year)
        cuota = resolve_bracket(table, Decimal("300000"), {"filing_period": date(year, 12, 31)})
        assert cuota == Decimal("35940.000"), year


def test_ahorro_escala_2020_top_bracket_is_open_11_5_percent() -> None:
    """Pre-Ley 11/2020 the 2020 autonomica ahorro escala had only three
    brackets, the last an open 11,5% tier above 50.000 EUR."""
    table = _ahorro_table(2020)
    assert len(table.brackets) == 3
    top = max(table.brackets, key=lambda b: b.lower_bound)
    assert top.lower_bound == Decimal("50000")
    assert top.upper_bound is None
    assert top.marginal_rate == Decimal("0.115")


def test_ahorro_escala_2025_top_marginal_rate_is_15_percent() -> None:
    """Ley 7/2024 raised the top autonomica ahorro marginal rate to 15%
    effective 2025 (AEAT Manual Renta 2025 page 953)."""
    table = _ahorro_table(2025)
    top = max(table.brackets, key=lambda b: b.lower_bound)
    assert top.lower_bound == Decimal("300000")
    assert top.upper_bound is None
    assert top.marginal_rate == Decimal("0.15")


def test_ahorro_escala_2023_2024_top_marginal_rate_is_14_percent() -> None:
    """Ley 31/2022 set the >300.000 autonomica ahorro tier at 14% for
    ejercicios 2023 and 2024 (AEAT Manual Renta 2023/2024)."""
    for year in (2023, 2024):
        table = _ahorro_table(year)
        top = max(table.brackets, key=lambda b: b.lower_bound)
        assert top.lower_bound == Decimal("300000")
        assert top.marginal_rate == Decimal("0.14")


def test_ahorro_escala_2021_2022_top_marginal_rate_is_13_percent() -> None:
    """Ley 11/2020 set the open >200.000 autonomica ahorro tier at 13% for
    ejercicios 2021 and 2022 (AEAT Manual Renta 2021/2022)."""
    for year in (2021, 2022):
        table = _ahorro_table(year)
        top = max(table.brackets, key=lambda b: b.lower_bound)
        assert top.lower_bound == Decimal("200000")
        assert top.upper_bound is None
        assert top.marginal_rate == Decimal("0.13")


def test_ahorro_escala_matches_estatal_scale() -> None:
    """The art.76 autonomica savings scale is identical to the art.66.1
    estatal savings scale for every ejercicio 2020-2025, as published
    in each year's AEAT Manual practico de Renta.

    This is the structural guard for the BOE finding that drove this
    work: art.76 does not legislate a CCAA-specific savings scale.
    """
    for year in _ALL_YEARS:
        revision = _revision(year)
        autonomica = next(p for p in revision.parameters if p.id == f"renta-{year}-escala-autonomica-base-ahorro")
        estatal = next(p for p in revision.parameters if p.id == f"renta-{year}-escala-estatal-base-ahorro")
        autonomica_brackets = sorted(autonomica.brackets, key=lambda b: b.lower_bound)
        estatal_brackets = sorted(estatal.brackets, key=lambda b: b.lower_bound)
        assert [(b.lower_bound, b.upper_bound, b.fixed_addition, b.marginal_rate) for b in autonomica_brackets] == [
            (b.lower_bound, b.upper_bound, b.fixed_addition, b.marginal_rate) for b in estatal_brackets
        ], year


def test_cuota_base_liquidable_ahorro_autonomica_formula_subtracts_minimo() -> None:
    """Casilla 0541 must be produced by ``subtract(0537, 0539)`` so the
    minimo-personal portion (escala applied to casilla 0524) is removed
    from the gross autonomica savings cuota, per art.76.2 Ley IRPF.
    """
    for year in _ALL_YEARS:
        revision = _revision(year)
        formula = next(f for f in revision.formulas if f.id == f"renta-{year}-cuota-base-liquidable-ahorro-autonomica")
        assert formula.target_casilla_id == "0541", year
        assert formula.expression.op == "subtract", year
        operand_casillas = [arg.casilla_id for arg in formula.expression.args]
        assert operand_casillas == ["0537", "0539"], year


def test_escala_autonomica_formulas_target_savings_casillas() -> None:
    """The autonomica ahorro escala is applied to the base liquidable
    del ahorro (casilla 0510) for casilla 0537 and to the autonomic
    minimo portion (casilla 0524) for casilla 0539.
    """
    for year in _ALL_YEARS:
        revision = _revision(year)
        base_formula = next(
            f for f in revision.formulas if f.id == f"renta-{year}-cuota-escala-autonomica-sobre-base-liquidable-ahorro"
        )
        minimo_formula = next(
            f
            for f in revision.formulas
            if f.id == f"renta-{year}-cuota-escala-autonomica-sobre-minimo-personal-familiar-base-ahorro"
        )
        assert base_formula.target_casilla_id == "0537", year
        assert base_formula.expression.op == "lookup_bracket", year
        assert base_formula.expression.args[0].casilla_id == "0510", year
        assert base_formula.expression.args[1].parameter == f"renta-{year}-escala-autonomica-base-ahorro", year
        assert minimo_formula.target_casilla_id == "0539", year
        assert minimo_formula.expression.op == "lookup_bracket", year
        assert minimo_formula.expression.args[0].casilla_id == "0524", year
        assert minimo_formula.expression.args[1].parameter == f"renta-{year}-escala-autonomica-base-ahorro", year


def test_ahorro_escala_rejects_date_outside_year_window() -> None:
    for year in _ALL_YEARS:
        table = _ahorro_table(year)
        other_year = year - 5
        with pytest.raises(RegistryValidationError, match="no bracket valid"):
            resolve_bracket(table, Decimal("2800"), {"filing_period": date(other_year, 6, 1)})

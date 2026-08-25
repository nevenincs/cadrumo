"""Behavioural + structural guards for the art. 19.2.f otros-gastos compute.

Modelo 100 casilla ``0019`` ("Otros gastos deducibles") is the art. 19.2.f
LIRPF automatic EUR 2.000 "otros gastos" deduction that the AEAT program
applies for any contribuyente with rendimientos del trabajo. It was
previously a bare MANUAL input in every
revision 2021-2025, so a filer who left it blank was over-taxed by a
determinable EUR 2.000. The net-trabajo formula ``0022`` carried
no ``max(0, ...)`` clamp either, so an over-entry of the otros-gastos boxes drove
the net rendimiento negative and the art. 19.2.f letter-f joint cap was
unenforced.

This gate asserts the two compute flips across all five in-scope
revisions:

- ``0019 = min(2.000, max(0, 0018))`` — the EUR 2.000 auto-apply, capped at the
  rendimiento (letter-f cap on the otros-gastos box itself);
- ``0022 = max(0, 0018 - 0019 - 0020 - 0021)`` — the missing clamp, which in one
  expression also enforces the art. 19.2.f letter-f joint cap that the sum of
  otros gastos may not exceed the rendimiento íntegro minorado (casilla 0018).

Expected values are grounded in LIRPF art. 19.2.f ("2.000 euros anuales" and the
letter-f cap "tendrán como límite el rendimiento íntegro del trabajo una vez
minorado por el resto de gastos deducibles"), never re-derived from the formula
under test (``aeat-quality-gates``).
"""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache

import pytest

from ..schema import CasillaId, FormulaDefinition, ModeloRevision
from ._formula_runtime_support import _evaluate
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_IN_SCOPE_REVISIONS: tuple[str, ...] = ("2021", "2022", "2023", "2024", "2025")

# LIRPF art. 19.2.f automatic "otros gastos" figure (bundled consolidated
# ley-35-2006.html, anchor a19: "En concepto de otros gastos distintos de los
# anteriores, 2.000 euros anuales"). The value is authored in the registry per
# revision; this constant is the independent legal oracle the test asserts
# against.
_ART_19_2F_OTROS_GASTOS_EUR = Decimal("2000")


@lru_cache
def _revision(year: str):
    modelo, _catalogues = _committed_modelo("100")
    return modelo.revisions[year]


def _casilla(revision: ModeloRevision, casilla_id: str):
    return next((c for c in revision.casillas if c.id == casilla_id), None)


def _formula_for_target(revision: ModeloRevision, target: str) -> FormulaDefinition:
    formula = next(f for f in revision.formulas if f.target_casilla_id == target)
    return formula


def test_casilla_0019_is_computed_and_grounded() -> None:
    """0019 is a COMPUTED casilla wired to the art. 19.2.f otros-gastos formula."""
    for year in _IN_SCOPE_REVISIONS:
        revision = _revision(year)
        casilla = _casilla(revision, "0019")
        assert casilla is not None, f"M100 {year} must declare casilla 0019"
        assert casilla.input_kind == "computed", (
            f"M100 {year} casilla 0019 must be computed (art. 19.2.f auto-apply), found {casilla.input_kind!r}"
        )
        assert casilla.formula == f"renta-{year}-trabajo-otros-gastos", year
        assert "ley-35-2006:art-19" in casilla.legal_refs, year

        formula = _formula_for_target(revision, "0019")
        assert "ley-35-2006:art-19" in formula.legal_refs, year
        assert formula.expression.op == "min", f"M100 {year} 0019 must cap via min(...)"


def test_casilla_0019_auto_applies_the_2000_euro_otros_gastos() -> None:
    """0019 = min(2.000, max(0, 0018)): the art. 19.2.f EUR 2.000 auto-apply.

    Expected values from LIRPF art. 19.2.f (the EUR 2.000 figure and its cap at
    the rendimiento), not from the formula under test:

    - rendimiento 0018 = 5.000 well above 2.000  -> otros gastos = 2.000 (full);
    - rendimiento 0018 = 1.200 below 2.000       -> otros gastos = 1.200 (capped);
    - rendimiento 0018 = 0 (no trabajo income)   -> otros gastos = 0.
    """
    for year in _IN_SCOPE_REVISIONS:
        expression = _formula_for_target(_revision(year), "0019").expression
        assert _evaluate(expression, {"0018": Decimal("5000")}) == _ART_19_2F_OTROS_GASTOS_EUR, year
        assert _evaluate(expression, {"0018": Decimal("1200")}) == Decimal("1200"), year
        assert _evaluate(expression, {"0018": Decimal("0")}) == Decimal("0"), year


def test_casilla_0022_clamps_net_and_enforces_letter_f_cap() -> None:
    """0022 = max(0, 0018 - 0019 - 0020 - 0021): clamp + art. 19.2.f letter-f cap.

    The letter-f cap ("los gastos deducibles ... tendrán como límite el
    rendimiento íntegro del trabajo una vez minorado por el resto de gastos
    deducibles" = casilla 0018) is mathematically the max(0, ...) clamp, because
    0018 is exactly the rendimiento minorado. Expected values follow art. 19.2.f:

    - rendimiento 0018 = 5.000, otros gastos 0019 = 2.000, no increments ->
      net = 3.000;
    - over-entry: 0018 = 5.000, 0019 = 2.000, mobility increment 0020 = 4.000 ->
      sum of otros gastos (6.000) exceeds the rendimiento, so the letter-f cap
      floors the net at 0 (pre-clamp this drove the net to -1.000).
    """
    for year in _IN_SCOPE_REVISIONS:
        expression = _formula_for_target(_revision(year), "0022").expression
        assert expression.op == "max", f"M100 {year} 0022 must clamp the net rendimiento at zero"

        base = {
            "0018": Decimal("5000"),
            "0019": Decimal("2000"),
            "0020": Decimal("0"),
            "0021": Decimal("0"),
        }
        assert _evaluate(expression, base) == Decimal("3000"), year

        over_entered = {
            "0018": Decimal("5000"),
            "0019": Decimal("2000"),
            "0020": Decimal("4000"),
            "0021": Decimal("0"),
        }
        assert _evaluate(expression, over_entered) == Decimal("0"), year


def test_otros_gastos_feeds_net_end_to_end() -> None:
    """Composing 0019 then 0022 reproduces the AEAT auto-apply chain.

    A contribuyente with rendimiento íntegro minorado 0018 = 5.000 who enters no
    otros-gastos value still receives the automatic EUR 2.000 (0019) and a net
    rendimiento of 3.000 (0022); omitting the auto-apply would over-tax the
    contribuyente by silently dropping the automatic deduction.
    """
    for year in _IN_SCOPE_REVISIONS:
        revision = _revision(year)
        otros = _formula_for_target(revision, "0019").expression
        neto = _formula_for_target(revision, "0022").expression

        values: dict[CasillaId, Decimal] = {"0018": Decimal("5000"), "0020": Decimal("0"), "0021": Decimal("0")}
        values["0019"] = _evaluate(otros, values)
        assert values["0019"] == _ART_19_2F_OTROS_GASTOS_EUR, year
        assert _evaluate(neto, values) == Decimal("3000"), year

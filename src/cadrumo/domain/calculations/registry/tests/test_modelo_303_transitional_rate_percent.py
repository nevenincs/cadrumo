"""Modelo 303 boxes [154] and [166] emit the AEAT-mandated Tipo % constant.

Both are RD-ley 4/2024 transitional rungs of the regimen general devengado
block ([153]/[154]/[155] reducido transitorio, [165]/[166]/[167] super-
reducido transitorio). The bundled AEAT diseño de registro fixes each rung's
rate as a `Constante`, never an operator declaration, and Nota 8/Nota 10 flip
that constant at the 10/4T 2024 filing-period boundary. Before this module's
fix both casillas were `input_kind = "manual"` with no formula, so the
required, `kind = "casilla"` export fields at page-01 offsets 225/974 were
never populated -- a live export-completeness gap for any 2024 filer with a
transitional-rate row.

Ground truth (the bundled 2023, 2024 early/late, 2025, and 2026 AEAT Diseños
de Registros):

    [154] "05" -> 500 (5,00 %) for 2023-01-01..2024-09-30 (Nota 8, pre-flip)
    [154] "05" -> 750 (7,50 %) for 2024-10-01..2024-12-31 (Nota 8, post-flip)
    [154] "05" -> 000 (0,00 %) from 2025-01-01 (2025/2026 designs neutralise it)
    [166] "05" -> 000 (0,00 %) before 2024-10-01 (Nota 10: the rung is unfilled)
    [166] "05" -> 200 (2,00 %) for 2024-10-01..2024-12-31 (Nota 10)
    [166] "05" -> 000 (0,00 %) from 2025-01-01 (2025/2026 designs neutralise it)

These four window boundaries are simple facts read off the bundled design,
never derived from the registry's own dated-parameter mechanism under test.

The date_axis is "filing_period", resolved through the SAME production call
path a real calculation uses --
:func:`~cadrumo.domain.period.calculation_filing_date`, which is the
PERIOD END date (Q3 2024 -> 2024-09-30, Q4 2024 -> 2024-12-31), never the
filing deadline. Confirmed by reading
application/modelo/_calculation_preparation.py's production default
(``filing_period_date or calculation_filing_date(work_unit.period)``) rather
than assumed from the parameter mechanism's own docstring: a deadline
semantics here would misclassify an October-filed Q3 2024 return into the
Q4 window and print 7,5 % where the design states 5 %.

GROUNDING GAP, CARRIED FORWARD FROM THE REGISTRY COMMENT: the DESIGN
authority for every constant and window boundary is revision-specific. The LEGAL authority for the 5 % rate's own
2023 -> 09/3T-2024 span is not fully grounded (real-decreto-ley-4-2024
covers only the 7,5 %/2 %/0 % follow-on from 10/4T 2024; the instrument that
opened the original 5 % window in January 2023 is not yet bundled). This test
suite verifies the DESIGN CONSTANT the registry now emits, not the tax
policy's own legal pedigree.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.period import Period
from ....period import calculation_filing_date
from ..authority import bundled_authority
from ..bindings import resolve_available_bound_inputs_by_casilla_id
from ..errors import RegistryValidationError
from ..formula_runtime import RegistryCalculationResult, calculate_registry_snapshot
from ..ledger_iva_bindings import resolve_ledger_iva_aggregation_binding_values

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CASILLA_154: CasillaId = validated_casilla_id("154", surface="_CASILLA_154")
_CASILLA_166: CasillaId = validated_casilla_id("166", surface="_CASILLA_166")


def _calculate(*, filing_year: int, period: str) -> RegistryCalculationResult:
    """Run the real calculation engine with an empty ledger.

    Every rate-selective ledger binding this scenario does not exercise
    resolves to zero via ``resolve_ledger_iva_aggregation_binding_values``
    over an empty observation set; the three remaining scalar bindings
    (carry-forward compensation, autoconsumo, and the profile attribution
    ratio) are pinned to their no-op values, mirroring the sibling worked-
    example tests in this package.
    """
    authority = bundled_authority()
    snapshot = authority.snapshot("303", filing_year=filing_year, period=period)
    binding_values = {
        "modelo-303-compensacion-pendiente-anteriores": Decimal("0"),
        "modelo-303-autoconsumo-promotor-base": Decimal("0"),
        "modelo-303-profile-state-attribution-ratio": Decimal("100"),
        **resolve_ledger_iva_aggregation_binding_values(snapshot.revision, ()),
    }
    inputs = resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    filing_period_date = calculation_filing_date(Period.from_year_and_code(filing_year, period))
    return calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=binding_values,
        date_context={"filing_period": filing_period_date},
    )


@pytest.mark.parametrize(
    ("filing_year", "period", "expected_154", "expected_166"),
    [
        # Casilla 166 does not exist in the 2023 revision: the transitional
        # recargo boxes arrive with the 2024-late diseno, so `None` here means
        # "this revision declares no such box" rather than "it computes zero".
        (2023, "1T", "5.00", None),
        (2024, "3T", "5.00", "0.00"),
        (2024, "4T", "7.50", "2.00"),
        (2025, "1T", "0.00", "0.00"),
        (2026, "2T", "0.00", "0.00"),
    ],
)
def test_transitional_rate_constant_follows_the_design_window(
    filing_year: int,
    period: str,
    expected_154: str,
    expected_166: str | None,
) -> None:
    result = _calculate(filing_year=filing_year, period=period)

    assert str(result.values[_CASILLA_154]) == expected_154
    if expected_166 is None:
        # Asserted absent, not skipped: a revision that GAINS the box without
        # this table being updated still fails here.
        assert _CASILLA_166 not in result.values
    else:
        assert str(result.values[_CASILLA_166]) == expected_166


def test_the_flip_lands_exactly_on_the_09_3t_to_10_4t_2024_boundary() -> None:
    """Adjacent quarters straddling the flip must disagree, not just differ from a third value."""
    before = _calculate(filing_year=2024, period="3T")
    after = _calculate(filing_year=2024, period="4T")

    assert before.values[_CASILLA_154] != after.values[_CASILLA_154]
    assert before.values[_CASILLA_166] != after.values[_CASILLA_166]


@pytest.mark.parametrize(
    ("filing_year", "period", "expected_revision_id"),
    [(2025, "1T", "2025"), (2026, "2T", "2026-y-siguientes")],
)
def test_the_expired_window_is_not_declared_in_the_revisions_that_neutralise_it(
    filing_year: int,
    period: str,
    expected_revision_id: str,
) -> None:
    """A neutralised revision declares the zero constant and NO transitional window.

    `date_context` is caller-supplied, so a window the revision's own
    `period_selector` can never reach is not inert: a stray in-window date fed to
    a 2025 or 2026 snapshot would have printed 7,5 % on a return whose diseño
    mandates `Constante "00000"`. Each parameter now declares exactly one value,
    so the same stray date refuses instead of publishing a rate the filing cannot
    carry -- fail-closed, not silently wrong.

    Loaded through the committed authority artifact so this exercises the same
    published declaration a shipped calculation consumes.
    """
    snapshot = bundled_authority().snapshot("303", filing_year=filing_year, period=period)
    assert snapshot.revision.id == expected_revision_id

    parameters = {p.id: p for p in snapshot.revision.parameters}
    for parameter_id in (
        "m303-dr303-154-transitional-rate-percent",
        "m303-dr303-166-transitional-rate-percent",
    ):
        values = parameters[parameter_id].values
        assert [v.value for v in values] == [Decimal("0.00")], (
            f"{parameter_id} still declares a rate window this revision cannot reach"
        )

    binding_values = {
        "modelo-303-compensacion-pendiente-anteriores": Decimal("0"),
        "modelo-303-autoconsumo-promotor-base": Decimal("0"),
        "modelo-303-profile-state-attribution-ratio": Decimal("100"),
        **resolve_ledger_iva_aggregation_binding_values(snapshot.revision, ()),
    }
    inputs = resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    with pytest.raises(RegistryValidationError, match="expected exactly one dated value"):
        calculate_registry_snapshot(
            snapshot,
            inputs=inputs,
            binding_values=binding_values,
            date_context={"filing_period": date(2024, 12, 31)},
        )

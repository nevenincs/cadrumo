"""Numeric value-oracle gate for the modelo-130 golden workflow.

Proves the harness's calculate trajectory produces the AEAT-published figure, not
merely that the right casillas are computed (the verification-contract dimension).
It seeds the AEAT DR 130 Instrucciones worked example through
the real registry calculation engine and asserts the resulting instalment casilla
equals the published AEAT figure. This is the figure-level value-oracle dimension
the operator golden eval needs.

Oracle authority (NON-tautological under ``aeat-quality-gates``):
the expected 1.600,00 EUR is the AEAT DR 130 Instrucciones worked example for
estimación directa (ingresos 12.000, gastos 4.000 -> rendimiento neto 8.000 ->
casilla 04 = 20 % x 8.000 = 1.600 -> casilla 07 = 04 - 05 - 06 = 1.600), grounded
in IRPF Ley 35/2006 Art. 99 (BOE-A-2006-20764) and RD 439/2007 Art. 110. The
figure is the published AEAT example, NOT hand-derived from the registry formula
under test: the same oracle grounds
``entrypoints/cli/tests/test_modelo_calculation_through_real_cli.py``. If the
registry rate or formula drifts from AEAT, the engine output diverges from
1.600,00 and this gate reds.

No new bundled registry corpus is required: the AEAT worked example is declared
here as the eval's own fixture and computed through the live engine, so the
figure-level oracle ships now rather than awaiting separate corpus sourcing.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.core.resources import resources
from cadrumo.domain.calculations.registry import (
    RegistryCalculationResult,
    calculate_registry_snapshot,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

# AEAT DR 130 Instrucciones worked example (estimación directa). Casillas 01 and 02
# are the operator leaf inputs; 03/04/07 are computed by the registry formula graph.
_INGRESOS = Decimal("12000.00")  # casilla 01
_GASTOS = Decimal("4000.00")  # casilla 02
# Prior-year economic-activity net income > 12.000 EUR -> minoración (casilla 13) = 0,
# matching the worked example so casilla 07 is the undiminished instalment.
_PRIOR_YEAR_NET_INCOME = Decimal("13000")
_EXPECTED_CASILLA_07 = Decimal("1600.00")

_BINDINGS = {
    "irpf.previous_year_economic_activity_net_income": _PRIOR_YEAR_NET_INCOME,
    "modelo-130-resultados-negativos-anteriores": Decimal("0"),
}


def _calculate_m130(*, ingresos: Decimal, gastos: Decimal):
    snapshot = resources().modelos.authority.snapshot("130", filing_year=2026, period="1T")
    result = calculate_registry_snapshot(
        snapshot,
        inputs={"01": ingresos, "02": gastos},
        date_context={},
        binding_values=_BINDINGS,
    )
    return result


def _value(result: RegistryCalculationResult, casilla_id: str) -> Decimal:
    entry = result.values[casilla_id]
    return Decimal(str(getattr(entry, "value", entry)))


def test_modelo_130_casilla_07_matches_aeat_worked_example() -> None:
    """Casilla 07 equals the AEAT DR 130 worked-example figure of 1.600,00 EUR."""
    result = _calculate_m130(ingresos=_INGRESOS, gastos=_GASTOS)
    casilla_07 = _value(result, "07")
    assert casilla_07 == _EXPECTED_CASILLA_07, (
        f"M130 casilla 07: expected the AEAT DR 130 figure {_EXPECTED_CASILLA_07} "
        f"(20 % x (12000 - 4000); IRPF Art. 99, RD 439/2007 Art. 110), got {casilla_07!r}"
    )


def test_positive_income_yields_a_nonzero_instalment() -> None:
    """A zero-tax result on positive income is suspect: positive net income must pay.

    Encodes the mandate invariant directly: with positive rendimiento neto (8.000),
    the instalment casilla must be strictly positive. A silent zero — the
    under-declaration failure mode the harness must never narrate as correct —
    reds this gate.
    """
    result = _calculate_m130(ingresos=_INGRESOS, gastos=_GASTOS)
    assert _value(result, "03") > Decimal("0"), "rendimiento neto must be positive for this fixture"
    assert _value(result, "07") > Decimal("0"), "positive income must yield a non-zero instalment"


def test_value_oracle_is_input_responsive() -> None:
    """Anti-tautology: the assertion tracks the computed value, not a constant.

    With gastos equal to ingresos the rendimiento neto is zero, so the instalment
    is zero — a different result from the worked example. This proves the engine
    computes from the seeded inputs (so the 1.600,00 assertion has teeth) and that
    a genuinely zero instalment arises only from a non-positive base, not from a
    suppressed positive one.
    """
    result = _calculate_m130(ingresos=_INGRESOS, gastos=_INGRESOS)
    assert _value(result, "03") == Decimal("0"), "rendimiento neto must be zero when gastos == ingresos"
    assert _value(result, "07") == Decimal("0"), "instalment must be zero when the base is zero"

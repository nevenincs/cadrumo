"""A register-owned element's amortization carried through the Modelo 100 chain to the rendimiento.

The sibling worked example of exempt services drives the INCOME leg and types casilla 0208 by
hand, so it says nothing about amortization. This module is the amortization counterpart: the
element and its claim come from the activity-asset register, the real expense resolver turns them
into casilla 0208, and the registry's own formulas carry that figure to the total of gastos and
the rendimiento neto of the 2025 estimacion directa normal.

Hand-worked figures (none is read back from the code under test):

    element basis                       12.000,00
    linear coefficient                  10 % (mobiliario)
    claim for 2025 (full year)          12.000,00 x 10 % = 1.200,00
    ingresos de explotacion (0171)      30.000,00   (income leg: typed, covered by the sibling module)
    gastos previos (0218)               1.200,00    (0208 is the only expense)
    total gastos, normal (0220)         1.200,00 + 0 provisions = 1.200,00
    rendimiento neto (0224)             30.000,00 - 1.200,00 = 28.800,00
    rendimiento neto reducido (0226)    28.800,00 - 0 reducciones (0225) = 28.800,00

The 5 % provision for difficult-to-justify expenses is a simplified-regime deduction, so the
election and the profile binding both name the normal regime and the example does not read it.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.calculations.registry.tests.scenarios import (
    RegistryCalculationScenario,
    RegistryScenarioExpectedOutput,
    RegistryScenarioRunReport,
    assert_registry_scenario_matches,
    run_registry_calculation_scenario,
)
from ...actividad_asset.history import ActivityAssetHistory
from .ledger_source_mesh_support import (
    _register_claim,
    _renta_expense_binding_id,
    _revision,
    register_asset,
    resolve_m100,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_FILING_YEAR = 2025
_CLAIM = Decimal("1200.00")
_INGRESOS = Decimal("30000.00")
_RENDIMIENTO_NETO = Decimal("28800.00")
# The 2025 provenance of the rendimiento neto formula: the 2024 declaration, with the 2025 additions,
# removals and ordering its revision overrides state.
_RENDIMIENTO_NETO_LEGAL_REFS = (
    "ley-35-2006:art-27",
    "ley-35-2006:art-28",
    "ley-35-2006:art-30",
    "ley-35-2006:art-32",
    "orden-hac-277-2026:art-3",
)
_RENDIMIENTO_NETO_SOURCE_REFS = (
    "aeat-dr-100-2025-dictionary",
    "aeat-dr-100-2025-xsd",
    "aeat-renta-2025-manual-parte1",
    "boe-modelo-100-2025-form",
)


def _casilla(code: str) -> CasillaId:
    return validated_casilla_id(code, surface=code)


def _chain(claim_amount: Decimal = _CLAIM, *, expected: Decimal = _RENDIMIENTO_NETO) -> RegistryScenarioRunReport:
    asset = register_asset("furniture", transaction_id="c" * 64)
    claim = _register_claim(asset, amount=claim_amount)
    resolution = resolve_m100(ActivityAssetHistory(revisions=(asset,), claims=(claim,)))
    material = resolution.binding_values[_renta_expense_binding_id(_revision("100", str(_FILING_YEAR)), "0208")]

    return run_registry_calculation_scenario(
        RegistryCalculationScenario(
            id="m100-2025-register-amortization-chain",
            modelo="100",
            revision=str(_FILING_YEAR),
            filing_year=_FILING_YEAR,
            period="0A",
            inputs={_casilla("0171"): _INGRESOS, _casilla("0208"): material},
            binding_values={
                "renta-profile-marriage-full-year": Decimal("0"),
                "renta-profile-marriage-month-start": Decimal("0"),
                "renta-profile-marriage-month-end": Decimal("0"),
                "renta-base-liquidable-negativa-general-anterior": Decimal("0"),
                "renta-profile-declaration-type": Decimal("1"),
                "renta-profile-family-minor-children-in-unit": Decimal("0"),
                "renta-modelo-100-estimacion-directa-es-normal": Decimal("1"),
                "renta-profile-has-economic-activity": Decimal("1"),
            },
            enum_binding_values={"renta-profile-tax-residence-ccaa": "madrid"},
            relation_values={
                "renta-modelo-130-pagos-fraccionados": Decimal("0"),
                "renta-modelo-131-pagos-fraccionados": Decimal("0"),
            },
            date_context={"filing_period": date(_FILING_YEAR, 12, 31)},
            date_binding_values={"renta-profile-taxpayer-birth-date": date(1980, 6, 15)},
            expected_outputs=(
                RegistryScenarioExpectedOutput(
                    target_casilla_id=_casilla("0224"),
                    value=expected,
                    legal_refs=_RENDIMIENTO_NETO_LEGAL_REFS,
                    source_refs=_RENDIMIENTO_NETO_SOURCE_REFS,
                ),
            ),
            hand_typed_bound_casillas={
                _casilla("0171"): "income leg typed; its ledger binding is driven by the exempt-services example",
                _casilla("0208"): "resolved by the register-driven expense resolver and supplied as the scenario input",
            },
        ),
    )


def test_the_register_claim_reaches_0208_and_the_rendimiento_neto() -> None:
    """The 1.200,00 charge lands in 0208, in the total of gastos, and out of the rendimiento neto."""
    report = _chain()
    assert_registry_scenario_matches(report)
    values = report.calculation.values

    assert values[_casilla("0208")] == _CLAIM
    assert values[_casilla("0218")] == _CLAIM
    assert values[_casilla("0220")] == _CLAIM
    assert values[_casilla("0224")] == _RENDIMIENTO_NETO
    assert values[_casilla("0226")] == _RENDIMIENTO_NETO


def test_a_smaller_registered_charge_raises_the_rendimiento_neto_by_the_difference() -> None:
    """A 600,00 charge instead of 1.200,00 leaves 30.000,00 - 600,00 = 29.400,00."""
    report = _chain(Decimal("600.00"), expected=Decimal("29400.00"))
    assert_registry_scenario_matches(report)

    values = report.calculation.values
    assert values[_casilla("0208")] == Decimal("600.00")
    assert values[_casilla("0226")] == Decimal("29400.00")

"""Tests for filed-state comparison against registry calculations."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aeat.core.paths import PROJECT_ROOT

from ._bindings import RegistryFilingObservation
from ._errors import RegistryValidationError
from ._filed_state import compare_calculation_to_filed_observation
from ._formula_runtime import RegistryCalculationResult, calculate_registry_snapshot
from ._loader import load_registry_tree
from ._schema import RegistrySnapshot
from ._snapshot import build_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_PREVIOUS_YEAR_NET_INCOME_BINDING = "irpf.previous_year_economic_activity_net_income"
_MODELO_130_COMPUTED_CASILLAS = ("03", "04", "07", "09", "11", "12", "13", "14", "17", "19")


def _modelo_130_snapshot() -> RegistrySnapshot:
    modelos, catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    modelo = next(item for item in modelos if item.id == "130")
    return build_snapshot(
        modelo,
        catalogues,
        source_root=PROJECT_ROOT,
        filing_year=2026,
        period="1T",
    )


def _modelo_130_calculation() -> RegistryCalculationResult:
    return calculate_registry_snapshot(
        _modelo_130_snapshot(),
        inputs={
            "01": Decimal("10000"),
            "02": Decimal("4000"),
            "05": Decimal("250"),
            "06": Decimal("100"),
            "08": Decimal("2000"),
            "10": Decimal("10"),
            "15": Decimal("0"),
            "16": Decimal("0"),
            "18": Decimal("0"),
        },
        date_context={"filing_period": date(2026, 3, 31)},
        binding_values={_PREVIOUS_YEAR_NET_INCOME_BINDING: Decimal("13000")},
    )


def _filed_observation(calculation: RegistryCalculationResult) -> RegistryFilingObservation:
    return RegistryFilingObservation(
        modelo="130",
        filing_year=2026,
        period="1T",
        casilla_values={casilla_id: calculation.values[casilla_id] for casilla_id in _MODELO_130_COMPUTED_CASILLAS},
    )


def test_filed_state_comparison_satisfies_matching_computed_casillas() -> None:
    calculation = _modelo_130_calculation()

    comparison = compare_calculation_to_filed_observation(
        calculation,
        _filed_observation(calculation),
        required_casillas=_MODELO_130_COMPUTED_CASILLAS,
    )

    assert comparison.status == "satisfied"
    assert comparison.compared_casillas == _MODELO_130_COMPUTED_CASILLAS
    assert comparison.drifts == ()
    assert comparison.missing_filed_casillas == ()


def test_filed_state_comparison_reports_value_drift() -> None:
    calculation = _modelo_130_calculation()
    observation = _filed_observation(calculation)
    filed_values = dict(observation.casilla_values)
    filed_values["19"] = filed_values["19"] + Decimal("0.01")
    observation = observation.model_copy(update={"casilla_values": filed_values})

    comparison = compare_calculation_to_filed_observation(
        calculation,
        observation,
        required_casillas=_MODELO_130_COMPUTED_CASILLAS,
    )

    assert comparison.status == "failed"
    assert len(comparison.drifts) == 1
    assert comparison.drifts[0].casilla_id == "19"
    assert comparison.drifts[0].delta == Decimal("-0.01")


def test_filed_state_comparison_reports_missing_filed_casilla() -> None:
    calculation = _modelo_130_calculation()
    observation = _filed_observation(calculation)
    filed_values = dict(observation.casilla_values)
    del filed_values["19"]
    observation = observation.model_copy(update={"casilla_values": filed_values})

    comparison = compare_calculation_to_filed_observation(
        calculation,
        observation,
        required_casillas=_MODELO_130_COMPUTED_CASILLAS,
    )

    assert comparison.status == "failed"
    assert comparison.missing_filed_casillas == ("19",)
    assert "19" not in comparison.compared_casillas


def test_filed_state_comparison_rejects_modelo_mismatch() -> None:
    calculation = _modelo_130_calculation()
    observation = _filed_observation(calculation).model_copy(update={"modelo": "131"})

    with pytest.raises(RegistryValidationError, match="cannot compare calculation modelo"):
        compare_calculation_to_filed_observation(
            calculation,
            observation,
            required_casillas=_MODELO_130_COMPUTED_CASILLAS,
        )

"""Tests for filed-state comparison against registry calculations."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aeat.core.resources import bundled_path

from ._bindings import CasillaObservation, RegistryModeloObservation
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
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    modelo = next(item for item in modelos if item.id == "130")
    return build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
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


def _filed_observation(calculation: RegistryCalculationResult) -> RegistryModeloObservation:
    return RegistryModeloObservation(
        modelo="130",
        filing_year=2026,
        period="1T",
        observations=tuple(
            CasillaObservation(casilla_id=cid, value=calculation.values[cid]) for cid in _MODELO_130_COMPUTED_CASILLAS
        ),
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


def test_filed_state_comparison_rejects_empty_required_casillas() -> None:
    """Passing an empty ``required_casillas`` set is meaningless and the
    helper must refuse to silently produce a vacuous-satisfied result."""
    calculation = _modelo_130_calculation()

    with pytest.raises(RegistryValidationError, match="requires at least one casilla"):
        compare_calculation_to_filed_observation(
            calculation,
            _filed_observation(calculation),
            required_casillas=(),
        )


def test_filed_state_comparison_reports_missing_local_casilla() -> None:
    """When a required casilla is absent from ``calculation.values`` but
    present in the observation, it lands in ``missing_local_casillas`` —
    a separate failure axis from ``missing_filed_casillas`` and drift."""
    calculation = _modelo_130_calculation()
    observation = _filed_observation(calculation)
    pruned_values = {casilla_id: value for casilla_id, value in calculation.values.items() if casilla_id != "19"}
    calculation = calculation.model_copy(update={"values": pruned_values})

    comparison = compare_calculation_to_filed_observation(
        calculation,
        observation,
        required_casillas=_MODELO_130_COMPUTED_CASILLAS,
    )

    assert comparison.status == "failed"
    assert comparison.missing_local_casillas == ("19",)
    assert comparison.missing_filed_casillas == ()
    assert "19" not in comparison.compared_casillas
    assert comparison.drifts == ()


def test_filed_state_comparison_reports_composite_missing_and_drift() -> None:
    """Each failure axis must populate independently — one casilla missing
    locally, another missing in the filed observation, and a third with a
    numeric drift, all in the same comparison."""
    calculation = _modelo_130_calculation()
    observation = _filed_observation(calculation)
    pruned_local = {casilla_id: value for casilla_id, value in calculation.values.items() if casilla_id != "03"}
    calculation = calculation.model_copy(update={"values": pruned_local})
    filed_values = dict(observation.casilla_values)
    del filed_values["04"]
    filed_values["19"] = filed_values["19"] + Decimal("0.01")
    observation = observation.model_copy(update={"casilla_values": filed_values})

    comparison = compare_calculation_to_filed_observation(
        calculation,
        observation,
        required_casillas=_MODELO_130_COMPUTED_CASILLAS,
    )

    assert comparison.status == "failed"
    assert comparison.missing_local_casillas == ("03",)
    assert comparison.missing_filed_casillas == ("04",)
    assert len(comparison.drifts) == 1
    assert comparison.drifts[0].casilla_id == "19"
    assert comparison.drifts[0].delta == Decimal("-0.01")
    assert "03" not in comparison.compared_casillas
    assert "04" not in comparison.compared_casillas

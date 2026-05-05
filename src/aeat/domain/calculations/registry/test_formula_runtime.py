"""Tests for registry-backed formula runtime."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import cast

import pytest

from aeat.core.paths import PROJECT_ROOT

from ._bindings import (
    RegistryFilingObservation,
    previous_filing_observation_requirements,
    resolve_previous_filing_binding_values,
)
from ._errors import RegistryValidationError
from ._formula_runtime import calculate_registry_snapshot
from ._loader import load_registry_tree
from ._schema import DataBindingDefinition, RegistrySnapshot
from ._snapshot import build_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_PREVIOUS_YEAR_NET_INCOME_BINDING = "irpf.previous_year_economic_activity_net_income"


def _committed_modelo_130_snapshot() -> RegistrySnapshot:
    modelos, catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    modelo = next(item for item in modelos if item.id == "130")
    return build_snapshot(
        modelo,
        catalogues,
        source_root=PROJECT_ROOT,
        filing_year=2026,
        period="1T",
    )


def _committed_modelo_180_snapshot() -> RegistrySnapshot:
    modelos, catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")
    modelo = next(item for item in modelos if item.id == "180")
    return build_snapshot(
        modelo,
        catalogues,
        source_root=PROJECT_ROOT,
        filing_year=2026,
        period="0A",
    )


def test_registry_formula_runtime_calculates_committed_modelo_in_dependency_order() -> None:
    snapshot = _committed_modelo_130_snapshot()

    result = calculate_registry_snapshot(
        snapshot,
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

    order = {entry.target: index for index, entry in enumerate(result.entries)}
    assert order["03"] < order["04"] < order["07"] < order["12"] < order["14"] < order["17"] < order["19"]
    assert order["09"] < order["11"] < order["12"]
    assert result.values["19"] == Decimal("880.00")
    assert result.entries[0].legal_refs == ("rd-439-2007:art-110",)


def test_registry_formula_runtime_preserves_signed_intermediate_results_from_official_instructions() -> None:
    snapshot = _committed_modelo_130_snapshot()

    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            "01": Decimal("1000"),
            "02": Decimal("0"),
            "05": Decimal("300"),
            "06": Decimal("50"),
            "08": Decimal("100"),
            "10": Decimal("10"),
            "15": Decimal("0"),
            "16": Decimal("0"),
            "18": Decimal("0"),
        },
        date_context={"filing_period": date(2026, 3, 31)},
        binding_values={_PREVIOUS_YEAR_NET_INCOME_BINDING: Decimal("13000")},
    )

    assert result.values["07"] == Decimal("-150.00")
    assert result.values["11"] == Decimal("-8.00")
    assert result.values["12"] == Decimal("0.00")


def test_registry_formula_runtime_calculates_income_reduction_from_previous_year_binding() -> None:
    snapshot = _committed_modelo_130_snapshot()

    result = calculate_registry_snapshot(
        snapshot,
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
        binding_values={_PREVIOUS_YEAR_NET_INCOME_BINDING: Decimal("9500")},
    )

    assert result.values["13"] == Decimal("75.00")
    assert result.values["19"] == Decimal("805.00")


def test_previous_filing_binding_resolves_from_observed_irpf_casillas() -> None:
    snapshot = _committed_modelo_130_snapshot()
    binding = _previous_year_net_income_binding(snapshot)
    selector = binding.selector
    source_casillas = selector["source_casillas"]
    assert isinstance(source_casillas, tuple)
    observed_values = {casilla_id: Decimal(index + 1) for index, casilla_id in enumerate(source_casillas)}

    result = resolve_previous_filing_binding_values(
        snapshot.revision,
        (
            RegistryFilingObservation(
                modelo=str(selector["source_modelo"]),
                filing_year=2025,
                period=str(selector["period"]),
                casilla_values=observed_values,
            ),
        ),
        filing_year=2026,
        period="1T",
    )

    assert result == {_PREVIOUS_YEAR_NET_INCOME_BINDING: sum(observed_values.values(), Decimal("0"))}


def test_previous_filing_requirements_are_declared_from_registry_binding_selector() -> None:
    snapshot = _committed_modelo_130_snapshot()
    binding = _previous_year_net_income_binding(snapshot)
    selector = binding.selector

    requirements = previous_filing_observation_requirements(snapshot.revision, filing_year=2026, period="1T")

    assert len(requirements) == 1
    requirement = requirements[0]
    assert requirement.modelo == selector["source_modelo"]
    assert requirement.filing_year == 2025
    assert requirement.period == selector["period"]
    assert requirement.binding_ids == (_PREVIOUS_YEAR_NET_INCOME_BINDING,)
    source_casillas = selector["source_casillas"]
    assert isinstance(source_casillas, tuple)
    assert requirement.source_casillas == tuple(sorted(source_casillas))


def test_previous_filing_requirements_cover_all_source_periods_for_annual_summary() -> None:
    snapshot = _committed_modelo_180_snapshot()

    requirements = previous_filing_observation_requirements(snapshot.revision, filing_year=2026, period="0A")

    assert [requirement.period for requirement in requirements] == ["1T", "2T", "3T", "4T"]
    assert {requirement.modelo for requirement in requirements} == {"115"}
    assert {requirement.filing_year for requirement in requirements} == {2026}
    assert {requirement.binding_ids for requirement in requirements} == {
        (
            "modelo-180-115-base-anual",
            "modelo-180-115-perceptores-anual",
            "modelo-180-115-retenciones-anual",
        )
    }
    assert {requirement.source_casillas for requirement in requirements} == {("01", "02", "03")}


def test_previous_filing_binding_resolves_annual_summary_from_all_source_periods() -> None:
    snapshot = _committed_modelo_180_snapshot()
    observations = tuple(
        RegistryFilingObservation(
            modelo="115",
            filing_year=2026,
            period=period,
            casilla_values={
                "01": Decimal("1"),
                "02": base,
                "03": retention,
            },
        )
        for period, base, retention in (
            ("1T", Decimal("100.00"), Decimal("19.00")),
            ("2T", Decimal("200.00"), Decimal("38.00")),
            ("3T", Decimal("300.00"), Decimal("57.00")),
            ("4T", Decimal("-50.00"), Decimal("0.00")),
        )
    )

    result = resolve_previous_filing_binding_values(
        snapshot.revision,
        observations,
        filing_year=2026,
        period="0A",
    )

    assert result == {
        "modelo-180-115-perceptores-anual": Decimal("4"),
        "modelo-180-115-base-anual": Decimal("550.00"),
        "modelo-180-115-retenciones-anual": Decimal("114.00"),
    }


def test_previous_filing_binding_requires_complete_observed_casillas() -> None:
    snapshot = _committed_modelo_130_snapshot()
    binding = _previous_year_net_income_binding(snapshot)
    selector = binding.selector
    source_casillas = selector["source_casillas"]
    assert isinstance(source_casillas, tuple)

    with pytest.raises(RegistryValidationError, match="requires observed casilla"):
        resolve_previous_filing_binding_values(
            snapshot.revision,
            (
                RegistryFilingObservation(
                    modelo=str(selector["source_modelo"]),
                    filing_year=2025,
                    period=str(selector["period"]),
                    casilla_values={source_casillas[0]: Decimal("1")},
                ),
            ),
            filing_year=2026,
            period="1T",
        )


def test_registry_formula_runtime_rejects_non_decimal_input() -> None:
    snapshot = _committed_modelo_130_snapshot()

    with pytest.raises(Exception, match="must be a Decimal"):
        calculate_registry_snapshot(
            snapshot,
            inputs=cast("dict[str, Decimal]", {"01": 100}),
            date_context={"filing_period": date(2026, 3, 31)},
        )


def test_registry_formula_runtime_rejects_unknown_binding_values() -> None:
    snapshot = _committed_modelo_130_snapshot()

    with pytest.raises(RegistryValidationError, match="unknown registry binding ids"):
        calculate_registry_snapshot(
            snapshot,
            inputs={},
            date_context={"filing_period": date(2026, 3, 31)},
            binding_values={
                _PREVIOUS_YEAR_NET_INCOME_BINDING: Decimal("13000"),
                "unknown-binding": Decimal("1"),
            },
        )


def test_registry_formula_runtime_rejects_unknown_relation_values() -> None:
    snapshot = _committed_modelo_180_snapshot()

    with pytest.raises(RegistryValidationError, match="unknown registry relation ids"):
        calculate_registry_snapshot(
            snapshot,
            inputs={},
            date_context={"filing_period": date(2026, 12, 31)},
            relation_values={
                "modelo-180-rel-115-perceptores-anual": Decimal("4"),
                "modelo-180-rel-115-base-anual": Decimal("550.00"),
                "modelo-180-rel-115-retenciones-anual": Decimal("114.00"),
                "unknown-relation": Decimal("1"),
            },
        )


def test_registry_formula_runtime_rejects_missing_parameter_axis() -> None:
    snapshot = _committed_modelo_130_snapshot()

    with pytest.raises(Exception, match="requires date axis"):
        calculate_registry_snapshot(
            snapshot,
            inputs={
                "01": Decimal("100"),
                "02": Decimal("0"),
                "05": Decimal("0"),
                "06": Decimal("0"),
                "08": Decimal("0"),
                "10": Decimal("0"),
                "15": Decimal("0"),
                "16": Decimal("0"),
                "18": Decimal("0"),
            },
            date_context={},
            binding_values={_PREVIOUS_YEAR_NET_INCOME_BINDING: Decimal("13000")},
        )


def _previous_year_net_income_binding(snapshot: RegistrySnapshot) -> DataBindingDefinition:
    return next(binding for binding in snapshot.revision.bindings if binding.id == _PREVIOUS_YEAR_NET_INCOME_BINDING)

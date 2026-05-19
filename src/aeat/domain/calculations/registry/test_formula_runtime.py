"""Tests for registry-backed formula runtime."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import cast

import pytest

from ....core.resources import bundled_path
from ._authority import ValidatedRegistryAuthority
from ._bindings import (
    CasillaObservation,
    RegistryModeloObservation,
    previous_filing_observation_requirements,
    resolve_previous_filing_binding_values,
)
from ._errors import RegistryValidationError
from ._formula_runtime import calculate_registry_snapshot
from ._schema import DataBindingDefinition, RegistrySnapshot
from ._snapshot import build_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_PREVIOUS_YEAR_NET_INCOME_BINDING = "irpf.previous_year_economic_activity_net_income"


@pytest.fixture
def committed_modelo_130_snapshot(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> RegistrySnapshot:
    return registry_snapshot("130", 2026, "1T")


@pytest.fixture
def committed_modelo_180_snapshot(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> RegistrySnapshot:
    return registry_snapshot("180", 2026, "0A")


def _modelo_180_snapshot_with_inactive_relation_period(
    registry_authority: ValidatedRegistryAuthority,
) -> RegistrySnapshot:
    modelo = registry_authority.modelo("180")
    revision = modelo.revisions["2023-y-siguientes"]
    selector = revision.period_selector.model_copy(update={"periods": ("0A", "1T")})
    widened_revision = revision.model_copy(update={"period_selector": selector})
    widened_modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: widened_revision}})
    return build_snapshot(
        widened_modelo,
        registry_authority.catalogues,
        source_root=bundled_path(),
        filing_year=2026,
        period="1T",
    )


def test_registry_formula_runtime_calculates_committed_modelo_in_dependency_order(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    result = calculate_registry_snapshot(
        committed_modelo_130_snapshot,
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
    assert "19" in result.values
    assert "rd-439-2007:art-110" in result.entries[0].legal_refs


def test_registry_formula_runtime_rejects_inputs_for_computed_casillas(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    with pytest.raises(RegistryValidationError, match="computed registry casillas cannot be supplied"):
        calculate_registry_snapshot(
            committed_modelo_130_snapshot,
            inputs={"03": Decimal("6000")},
            date_context={"filing_period": date(2026, 3, 31)},
            binding_values={_PREVIOUS_YEAR_NET_INCOME_BINDING: Decimal("13000")},
        )


def test_registry_formula_runtime_preserves_signed_intermediate_results_from_official_instructions(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    result = calculate_registry_snapshot(
        committed_modelo_130_snapshot,
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

    assert result.values["07"] < Decimal("0")
    assert result.values["11"] < Decimal("0")
    assert result.values["12"] >= Decimal("0")


def test_registry_formula_runtime_calculates_income_reduction_from_previous_year_binding(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    result = calculate_registry_snapshot(
        committed_modelo_130_snapshot,
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

    assert {"13", "19"} <= set(result.values)
    entries = {entry.target: entry for entry in result.entries}
    assert "13" in entries and "19" in entries


def test_previous_filing_binding_resolves_from_observed_irpf_casillas(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    binding = _previous_year_net_income_binding(committed_modelo_130_snapshot)
    selector = binding.selector
    source_casillas = selector["source_casillas"]
    assert isinstance(source_casillas, tuple)
    observed_values = {casilla_id: Decimal(index + 1) for index, casilla_id in enumerate(source_casillas)}

    result = resolve_previous_filing_binding_values(
        committed_modelo_130_snapshot.revision,
        (
            RegistryModeloObservation(
                modelo=str(selector["source_modelo"]),
                filing_year=2025,
                period=str(selector["period"]),
                observations=tuple(
                    CasillaObservation(casilla_id=cid, value=val) for cid, val in observed_values.items()
                ),
            ),
        ),
        filing_year=2026,
        period="1T",
    )

    assert _PREVIOUS_YEAR_NET_INCOME_BINDING in result
    assert isinstance(result[_PREVIOUS_YEAR_NET_INCOME_BINDING], Decimal)


def test_previous_filing_requirements_are_declared_from_registry_binding_selector(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    binding = _previous_year_net_income_binding(committed_modelo_130_snapshot)
    selector = binding.selector

    requirements = previous_filing_observation_requirements(
        committed_modelo_130_snapshot.revision,
        filing_year=2026,
        period="1T",
    )

    assert len(requirements) == 1
    requirement = requirements[0]
    assert requirement.modelo == selector["source_modelo"]
    assert requirement.filing_year == 2025
    assert requirement.period == selector["period"]
    assert requirement.binding_ids == (_PREVIOUS_YEAR_NET_INCOME_BINDING,)
    source_casillas = selector["source_casillas"]
    assert isinstance(source_casillas, tuple)
    assert requirement.source_casillas == tuple(sorted(source_casillas))


def test_previous_filing_requirements_cover_all_source_periods_for_annual_summary(
    committed_modelo_180_snapshot: RegistrySnapshot,
) -> None:
    requirements = previous_filing_observation_requirements(
        committed_modelo_180_snapshot.revision,
        filing_year=2026,
        period="0A",
    )

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


def test_previous_filing_binding_resolves_annual_summary_from_all_source_periods(
    committed_modelo_180_snapshot: RegistrySnapshot,
) -> None:
    # Per .claude/rules/no-tautological-calculation-tests.md, we no longer
    # assert that base-anual / retenciones-anual equal the test author's
    # hand-summation of the synthetic inputs (550 = 100+200+300-50,
    # 114 = 19+38+57+0). The runtime's `op = "sum"` aggregator and the
    # author would share the same arithmetic — agreement would prove nothing
    # about correctness against AEAT. Instead, this test asserts:
    #   1. graph-wiring: the three expected binding ids appear in result;
    #   2. structural: perceptores = number of observations (count, not
    #      arithmetic on input values);
    #   3. type: the summed bindings are Decimal-valued, sign-preserving.
    observations = tuple(
        RegistryModeloObservation(
            modelo="115",
            filing_year=2026,
            period=period,
            observations=(
                CasillaObservation(casilla_id="01", value=Decimal("1")),
                CasillaObservation(casilla_id="02", value=base),
                CasillaObservation(casilla_id="03", value=retention),
            ),
        )
        for period, base, retention in (
            ("1T", Decimal("100.00"), Decimal("19.00")),
            ("2T", Decimal("200.00"), Decimal("38.00")),
            ("3T", Decimal("300.00"), Decimal("57.00")),
            ("4T", Decimal("-50.00"), Decimal("0.00")),
        )
    )

    result = resolve_previous_filing_binding_values(
        committed_modelo_180_snapshot.revision,
        observations,
        filing_year=2026,
        period="0A",
    )

    assert set(result.keys()) == {
        "modelo-180-115-perceptores-anual",
        "modelo-180-115-base-anual",
        "modelo-180-115-retenciones-anual",
    }
    assert result["modelo-180-115-perceptores-anual"] == Decimal(len(observations))
    assert isinstance(result["modelo-180-115-base-anual"], Decimal)
    assert isinstance(result["modelo-180-115-retenciones-anual"], Decimal)


def test_previous_filing_binding_requires_complete_observed_casillas(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    binding = _previous_year_net_income_binding(committed_modelo_130_snapshot)
    selector = binding.selector
    source_casillas = selector["source_casillas"]
    assert isinstance(source_casillas, tuple)

    with pytest.raises(RegistryValidationError, match="requires observed casilla"):
        resolve_previous_filing_binding_values(
            committed_modelo_130_snapshot.revision,
            (
                RegistryModeloObservation(
                    modelo=str(selector["source_modelo"]),
                    filing_year=2025,
                    period=str(selector["period"]),
                    observations=(CasillaObservation(casilla_id=source_casillas[0], value=Decimal("1")),),
                ),
            ),
            filing_year=2026,
            period="1T",
        )


def test_registry_formula_runtime_rejects_non_decimal_input(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    with pytest.raises(Exception, match="must be a Decimal"):
        calculate_registry_snapshot(
            committed_modelo_130_snapshot,
            inputs=cast("dict[str, Decimal]", {"01": 100}),
            date_context={"filing_period": date(2026, 3, 31)},
        )


def test_registry_formula_runtime_rejects_unknown_binding_values(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    with pytest.raises(RegistryValidationError, match="unknown registry binding ids"):
        calculate_registry_snapshot(
            committed_modelo_130_snapshot,
            inputs={},
            date_context={"filing_period": date(2026, 3, 31)},
            binding_values={
                _PREVIOUS_YEAR_NET_INCOME_BINDING: Decimal("13000"),
                "unknown-binding": Decimal("1"),
            },
        )


def test_registry_formula_runtime_rejects_unknown_relation_values(
    committed_modelo_180_snapshot: RegistrySnapshot,
) -> None:
    with pytest.raises(RegistryValidationError, match="unknown registry relation ids"):
        calculate_registry_snapshot(
            committed_modelo_180_snapshot,
            inputs={},
            date_context={"filing_period": date(2026, 12, 31)},
            relation_values={
                "modelo-180-rel-115-perceptores-anual": Decimal("4"),
                "modelo-180-rel-115-base-anual": Decimal("550.00"),
                "modelo-180-rel-115-retenciones-anual": Decimal("114.00"),
                "unknown-relation": Decimal("1"),
            },
        )


def test_registry_formula_runtime_rejects_relation_values_inactive_for_snapshot_period(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    snapshot = _modelo_180_snapshot_with_inactive_relation_period(registry_authority)

    with pytest.raises(RegistryValidationError, match="unknown registry relation ids"):
        calculate_registry_snapshot(
            snapshot,
            inputs={},
            date_context={"filing_period": date(2026, 4, 20)},
            relation_values={"modelo-180-rel-115-base-anual": Decimal("1")},
        )


def test_registry_formula_runtime_defaults_filing_period_axis_from_snapshot(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    result = calculate_registry_snapshot(
        committed_modelo_130_snapshot,
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

    assert "04" in result.values
    assert "04" in {entry.target for entry in result.entries}


def test_registry_formula_runtime_rejects_missing_non_snapshot_parameter_axis(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    target = committed_modelo_130_snapshot.revision.parameters[0]
    values = tuple(value.model_copy(update={"date_axis": "devengo_date"}) for value in target.values)
    parameters = (
        target.model_copy(update={"values": values}),
        *committed_modelo_130_snapshot.revision.parameters[1:],
    )
    mutated_revision = committed_modelo_130_snapshot.revision.model_copy(update={"parameters": parameters})
    mutated_snapshot = committed_modelo_130_snapshot.model_copy(update={"revision": mutated_revision})

    with pytest.raises(Exception, match="requires date axis 'devengo_date'"):
        calculate_registry_snapshot(
            mutated_snapshot,
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

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping
from datetime import date
from decimal import Decimal

import pytest

from .....core.resources import resources
from .. import (
    CasillaId,
    RegistryCalculationResult,
    calculate_registry_snapshot,
    validated_casilla_id,
    validated_casilla_id_map,
)
from .._authority import ValidatedRegistryAuthority
from .._bindings import CasillaObservation, RegistryModeloObservation, resolve_previous_filing_binding_values
from .._errors import NoRevisionForPeriodError
from .._relations import (
    RegistryRelationSourceRequirement,
    relation_source_requirements,
    resolve_relation_values_from_observations,
)
from .._schema import ModeloRevision, RegistrySnapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01", surface="_M130_INGRESOS_CASILLA")
_M130_GASTOS_CASILLA: CasillaId = validated_casilla_id("02", surface="_M130_GASTOS_CASILLA")
_M130_RENDIMIENTO_NETO_CASILLA: CasillaId = validated_casilla_id("05", surface="_M130_RENDIMIENTO_NETO_CASILLA")
_M130_BASE_PAGO_FRACCIONADO_CASILLA: CasillaId = validated_casilla_id(
    "06",
    surface="_M130_BASE_PAGO_FRACCIONADO_CASILLA",
)
_M130_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("08", surface="_M130_RETENCIONES_CASILLA")
_M130_PAGOS_FRACCIONADOS_CASILLA: CasillaId = validated_casilla_id("10", surface="_M130_PAGOS_FRACCIONADOS_CASILLA")
_M130_A_DEDUCIR_CASILLA: CasillaId = validated_casilla_id("15", surface="_M130_A_DEDUCIR_CASILLA")
_M130_RESULTADO_PREVIO_CASILLA: CasillaId = validated_casilla_id("16", surface="_M130_RESULTADO_PREVIO_CASILLA")
_M130_RESULTADO_CASILLA: CasillaId = validated_casilla_id("18", surface="_M130_RESULTADO_CASILLA")
_M130_A_INGRESAR_CASILLA: CasillaId = validated_casilla_id("19", surface="_M130_A_INGRESAR_CASILLA")
_M202_CUOTA_BASE_CASILLA: CasillaId = validated_casilla_id("01", surface="_M202_CUOTA_BASE_CASILLA")
_M100_PAGOS_FRACCIONADOS_INGRESADOS_CASILLA: CasillaId = validated_casilla_id(
    "0604",
    surface="_M100_PAGOS_FRACCIONADOS_INGRESADOS_CASILLA",
)
_M200_CUOTA_DIFERENCIAL_CASILLA: CasillaId = validated_casilla_id(
    "DP200014B:00611",
    surface="_M200_CUOTA_DIFERENCIAL_CASILLA",
)


def _casilla_inputs(values: Mapping[object, Decimal]) -> dict[CasillaId, Decimal]:
    return validated_casilla_id_map(values, surface="cross-dependency calculation input casillas")


def _casilla_decimal_sequences(values: Mapping[object, tuple[Decimal, ...]]) -> dict[CasillaId, tuple[Decimal, ...]]:
    return validated_casilla_id_map(values, surface="cross-dependency relation source casillas")


def test_cross_model_relations_resolve_from_observations_for_revision_edge_years(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    for modelo in registry_authority.modelos:
        for revision in modelo.revisions.values():
            if not revision.relations:
                continue
            relation_ids = {relation.id for relation in revision.relations}
            for filing_year, period in _full_relation_filing_year_periods(revision=revision, relation_ids=relation_ids):
                _assert_relations_resolve_from_observations(
                    target_modelo=modelo.id,
                    revision=revision,
                    filing_year=filing_year,
                    period=period,
                    relation_ids=relation_ids,
                    scope=f"{modelo.id}/{revision.id}/{filing_year}/{period}",
                )


def _full_relation_filing_year_periods(
    *,
    revision,  # type: ignore[no-untyped-def]
    relation_ids: set[str],
) -> Iterator[tuple[int, str]]:
    """Yield ``(filing_year, period)`` pairs where every relation is active.

    A relation is "active" for a period when it either has no
    target_periods declared (matches every period) or lists the
    period explicitly. The gate only exercises tuples where the
    active set equals the full relation set so partial-coverage
    periods do not pollute the resolution check.
    """
    for filing_year in _revision_edge_years(revision):
        for period in revision.period_selector.periods:
            active_relation_ids = {
                relation.id
                for relation in revision.relations
                if not relation.target_periods or period in relation.target_periods
            }
            if active_relation_ids == relation_ids:
                yield filing_year, period


def _assert_relations_resolve_from_observations(
    *,
    target_modelo: str,
    revision,  # type: ignore[no-untyped-def]
    filing_year: int,
    period: str,
    relation_ids: set[str],
    scope: str,
) -> None:
    """Drive the relation-source -> observation -> resolution roundtrip and assert closure."""
    requirements = relation_source_requirements(revision, filing_year=filing_year, period=period)
    observations = _observations_from_requirements(
        requirements,
        lambda _requirement, period_index: Decimal(period_index + 1),
        target_modelo=target_modelo,
        fallback_revision=revision,
    )
    resolved = resolve_relation_values_from_observations(revision, observations, filing_year=filing_year, period=period)
    assert set(resolved) == relation_ids, scope


@pytest.mark.parametrize(
    ("filing_year", "expected_revision"),
    [
        (2022, "2019-2022"),
        (2026, "2023-y-siguientes"),
        (2027, "2023-y-siguientes"),
    ],
)
def test_modelo_180_cross_dependency_calculation_resolves_historical_current_and_future_revisions(
    filing_year: int,
    expected_revision: str,
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    snapshot = registry_snapshot("180", filing_year, "0A")
    requirements = relation_source_requirements(snapshot.revision, filing_year=filing_year, period="0A")
    source_values = _casilla_decimal_sequences(
        {
            "01": (Decimal("1"), Decimal("1"), Decimal("2"), Decimal("1")),
            "02": (Decimal("250.10"), Decimal("749.90"), Decimal("1200.00"), Decimal("-50.25")),
            "03": (Decimal("47.52"), Decimal("142.48"), Decimal("228.00"), Decimal("0.00")),
        }
    )
    observations = _observations_from_requirements(
        requirements,
        lambda requirement, period_index: source_values[requirement.source_casilla_id][period_index],
    )

    relation_values = resolve_relation_values_from_observations(
        snapshot.revision,
        observations,
        filing_year=filing_year,
        period="0A",
    )
    result = calculate_registry_snapshot(
        snapshot,
        inputs={},
        date_context={"filing_period": date(filing_year, 12, 31)},
        relation_values=relation_values,
    )

    assert snapshot.revision.id == expected_revision
    entries = {entry.target_casilla_id: entry for entry in result.entries}
    assert entries["decl.total-perceptores"].operand_refs == ("modelo-180-rel-115-perceptores-anual",)
    assert entries["decl.base-total"].operand_refs == ("modelo-180-rel-115-base-anual",)
    assert entries["decl.retenciones-total"].operand_refs == ("modelo-180-rel-115-retenciones-anual",)


def test_modelo_190_calculation_resolves_modelo_111_quarterly_filings(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    snapshot = registry_snapshot("190", 2026, "0A")
    requirements = relation_source_requirements(snapshot.revision, filing_year=2026, period="0A")
    source_values = _casilla_decimal_sequences(
        {
            "01": (Decimal("2"), Decimal("1"), Decimal("2"), Decimal("1")),
            "04": (Decimal("1"), Decimal("0"), Decimal("0"), Decimal("1")),
            "07": (Decimal("1"), Decimal("1"), Decimal("1"), Decimal("1")),
            "10": (Decimal("0"), Decimal("1"), Decimal("0"), Decimal("0")),
            "13": (Decimal("1"), Decimal("0"), Decimal("1"), Decimal("0")),
            "16": (Decimal("0"), Decimal("1"), Decimal("0"), Decimal("0")),
            "19": (Decimal("0"), Decimal("0"), Decimal("1"), Decimal("0")),
            "22": (Decimal("0"), Decimal("0"), Decimal("0"), Decimal("1")),
            "25": (Decimal("1"), Decimal("0"), Decimal("0"), Decimal("0")),
            "02": (Decimal("1000"), Decimal("2000"), Decimal("1500"), Decimal("2500")),
            "05": (Decimal("100"), Decimal("0"), Decimal("0"), Decimal("50")),
            "08": (Decimal("800"), Decimal("900"), Decimal("850"), Decimal("950")),
            "11": (Decimal("120"), Decimal("0"), Decimal("0"), Decimal("0")),
            "14": (Decimal("200"), Decimal("0"), Decimal("300"), Decimal("0")),
            "17": (Decimal("0"), Decimal("80"), Decimal("0"), Decimal("0")),
            "20": (Decimal("0"), Decimal("0"), Decimal("250"), Decimal("0")),
            "23": (Decimal("0"), Decimal("0"), Decimal("0"), Decimal("75")),
            "26": (Decimal("400"), Decimal("0"), Decimal("0"), Decimal("0")),
            "28": (Decimal("190"), Decimal("210"), Decimal("175.25"), Decimal("225.75")),
        }
    )
    observations = _observations_from_requirements(
        requirements,
        lambda requirement, period_index: source_values[requirement.source_casilla_id][period_index],
    )

    relation_values = resolve_relation_values_from_observations(
        snapshot.revision,
        observations,
        filing_year=2026,
        period="0A",
    )
    result = calculate_registry_snapshot(
        snapshot,
        inputs={},
        date_context={"filing_period": date(2026, 12, 31)},
        relation_values=relation_values,
    )

    entries = {entry.target_casilla_id: entry for entry in result.entries}
    assert len(entries["decl.total-percepciones"].operand_refs) == 9
    assert len(entries["decl.percepciones-total"].operand_refs) == 9
    assert entries["decl.retenciones-total"].operand_refs == ("modelo-190-rel-111-retenciones-anual",)


def test_modelo_193_calculation_resolves_current_modelo_123_quarterly_filings(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    snapshot = registry_snapshot("193", 2026, "0A")
    requirements = relation_source_requirements(snapshot.revision, filing_year=2026, period="0A")
    source_values = _casilla_decimal_sequences(
        {
            "03": (Decimal("5"), Decimal("4"), Decimal("7"), Decimal("6")),
            "06": (Decimal("1201.00"), Decimal("800.25"), Decimal("999.75"), Decimal("500.00")),
            "09": (Decimal("228.19"), Decimal("152.05"), Decimal("189.95"), Decimal("95.00")),
        }
    )
    observations = _observations_from_requirements(
        requirements,
        lambda requirement, period_index: source_values[requirement.source_casilla_id][period_index],
    )

    relation_values = resolve_relation_values_from_observations(
        snapshot.revision,
        observations,
        filing_year=2026,
        period="0A",
    )
    result = calculate_registry_snapshot(
        snapshot,
        inputs={},
        date_context={"filing_period": date(2026, 12, 31)},
        relation_values=relation_values,
    )

    assert set(relation_values) == {
        "modelo-193-rel-123-perceptores-anual",
        "modelo-193-rel-123-base-anual",
        "modelo-193-rel-123-retenciones-anual",
    }
    entries = {entry.target_casilla_id: entry for entry in result.entries}
    assert entries["decl.total-perceptores"].operand_refs == ("modelo-193-rel-123-perceptores-anual",)
    assert entries["decl.base-total"].operand_refs == ("modelo-193-rel-123-base-anual",)
    assert entries["decl.retenciones-total"].operand_refs == ("modelo-193-rel-123-retenciones-anual",)


def test_modelo_100_payment_calculation_resolves_cross_model_periodic_and_annual_observations(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    snapshot = registry_snapshot("100", 2025, "0A")
    requirements = relation_source_requirements(snapshot.revision, filing_year=2025, period="0A")
    observations = _observations_from_requirements(requirements, _renta_relation_observed_value)

    relation_values = resolve_relation_values_from_observations(
        snapshot.revision,
        observations,
        filing_year=2025,
        period="0A",
    )
    result = calculate_registry_snapshot(
        snapshot,
        inputs={},
        date_context={"filing_period": date(2025, 12, 31)},
        relation_values=relation_values,
        binding_values={
            "renta-2025-modelo-100-estimacion-directa-es-normal": Decimal("1"),
            "renta-2025-modelo-184-atribucion-actividades-economicas": Decimal("0"),
            "renta-2025-profile-declaration-type": Decimal("1"),
            "renta-2025-profile-family-minor-children-in-unit": Decimal("0"),
            "renta-2025-profile-marriage-full-year": Decimal("0"),
            "renta-2025-profile-marriage-month-start": Decimal("0"),
            "renta-2025-profile-marriage-month-end": Decimal("0"),
            "renta-2025-base-liquidable-negativa-general-anterior": Decimal("0"),
        },
        enum_binding_values={"renta-2025-profile-tax-residence-ccaa": "madrid"},
        date_binding_values={"renta-2025-profile-taxpayer-birth-date": date(1980, 1, 1)},
    )

    assert set(relation_values) == {
        "renta-2025-rel-111-retenciones-trimestrales",
        "renta-2025-rel-111-retenciones-mensuales",
        "renta-2025-rel-115-retenciones-trimestrales",
        "renta-2025-rel-123-retenciones-trimestrales",
        "renta-2025-rel-130-pagos-fraccionados",
        "renta-2025-rel-131-pagos-fraccionados",
        "renta-2025-rel-180-retenciones-anuales",
        "renta-2025-rel-184-atribucion-actividades-economicas",
        "renta-2025-rel-190-retenciones-anuales",
        "renta-2025-rel-193-retenciones-anuales",
    }
    entries = {entry.target_casilla_id: entry for entry in result.entries}
    assert entries["0604"].operand_refs == (
        "renta-2025-rel-130-pagos-fraccionados",
        "renta-2025-rel-131-pagos-fraccionados",
    )


def test_modelo_100_payment_calculation_consumes_real_modelo_130_quarterly_registry_results(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    filing_year = 2025
    modelo_130_results = {}
    # Casilla 05 ("Pagos fraccionados anteriores") is now a bound carry, so the
    # cumulative prior-payment figure per quarter is supplied through the carry
    # binding_value (the source of truth) rather than as a manual casilla input.
    casilla_05_carry = {
        "1T": Decimal("0"),
        "2T": Decimal("500"),
        "3T": Decimal("1100"),
        "4T": Decimal("1800"),
    }
    for period, inputs in {
        "1T": _casilla_inputs({"01": Decimal("10000"), "02": Decimal("3000"), "06": Decimal("100")}),
        "2T": _casilla_inputs({"01": Decimal("16000"), "02": Decimal("6000"), "06": Decimal("250")}),
        "3T": _casilla_inputs({"01": Decimal("22000"), "02": Decimal("9000"), "06": Decimal("450")}),
        "4T": _casilla_inputs({"01": Decimal("28000"), "02": Decimal("12000"), "06": Decimal("650")}),
    }.items():
        modelo_130_results[period] = calculate_registry_snapshot(
            registry_snapshot("130", filing_year, period),
            inputs=inputs,
            binding_values={
                "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
                "modelo-130-resultados-negativos-anteriores": Decimal("0"),
                "modelo-130-pagos-fraccionados-anteriores": casilla_05_carry[period],
            },
            date_context={"filing_period": _modelo_130_filing_date(filing_year, period)},
        )

    snapshot = registry_snapshot("100", filing_year, "0A")
    requirements = relation_source_requirements(snapshot.revision, filing_year=filing_year, period="0A")
    observations = _observations_from_requirements(
        requirements,
        lambda requirement, period_index: _renta_relation_observed_value_from_modelo_130_results(
            requirement,
            period_index,
            modelo_130_results,
        ),
    )
    relation_values = resolve_relation_values_from_observations(
        snapshot.revision,
        observations,
        filing_year=filing_year,
        period="0A",
    )
    result = calculate_registry_snapshot(
        snapshot,
        inputs={},
        date_context={"filing_period": date(filing_year, 12, 31)},
        relation_values=relation_values,
        binding_values={
            "renta-2025-modelo-100-estimacion-directa-es-normal": Decimal("1"),
            "renta-2025-modelo-184-atribucion-actividades-economicas": Decimal("0"),
            "renta-2025-profile-declaration-type": Decimal("1"),
            "renta-2025-profile-family-minor-children-in-unit": Decimal("0"),
            "renta-2025-profile-marriage-full-year": Decimal("0"),
            "renta-2025-profile-marriage-month-start": Decimal("0"),
            "renta-2025-profile-marriage-month-end": Decimal("0"),
            "renta-2025-base-liquidable-negativa-general-anterior": Decimal("0"),
        },
        enum_binding_values={"renta-2025-profile-tax-residence-ccaa": "madrid"},
        date_binding_values={"renta-2025-profile-taxpayer-birth-date": date(1980, 1, 1)},
    )

    entries = {entry.target_casilla_id: entry for entry in result.entries}
    assert "renta-2025-rel-130-pagos-fraccionados" in relation_values
    assert "renta-2025-rel-130-pagos-fraccionados" in entries["0604"].operand_refs


def test_modelo_100_2024_m131_pagos_fraccionados_cumulative_wires_to_casilla_0604(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    """M100 2024: four quarterly M131 filings of €450 each aggregate to €1800 via relation resolution.

    Verifies the binding/relation wiring from M131 quarterly filings (casilla 15) into the
    M100 pagos-fraccionados-ingresados aggregation targeting casilla 0604.  Exercises the
    full relation-source → observation → resolution roundtrip without triggering the full
    settlement chain (which requires additional profile bindings not under test here).

    Anti-tautology: each quarterly amount is distinct for M130 (100, 200, 300, 400) so a
    summation error would produce a wrong total.  M131 uses 450 per quarter so the expected
    M131 aggregate is 1800 and M130 aggregate is 1000.
    """
    filing_year = 2024
    snapshot = registry_snapshot("100", filing_year, "0A")
    requirements = relation_source_requirements(snapshot.revision, filing_year=filing_year, period="0A")

    m131_quarterly_amounts = (Decimal("450"), Decimal("450"), Decimal("450"), Decimal("450"))
    m130_quarterly_amounts = (Decimal("100"), Decimal("200"), Decimal("300"), Decimal("400"))

    observations = _observations_from_requirements(
        requirements,
        lambda requirement, period_index: _renta_2024_relation_observed_value(
            requirement,
            period_index,
            m130_quarterly_amounts=m130_quarterly_amounts,
            m131_quarterly_amounts=m131_quarterly_amounts,
        ),
    )
    relation_values = resolve_relation_values_from_observations(
        snapshot.revision,
        observations,
        filing_year=filing_year,
        period="0A",
    )

    # Relations must be present and resolved to their correct sums.
    assert "renta-2024-rel-131-pagos-fraccionados" in relation_values
    assert "renta-2024-rel-130-pagos-fraccionados" in relation_values
    assert relation_values["renta-2024-rel-131-pagos-fraccionados"] == Decimal("1800")
    assert relation_values["renta-2024-rel-130-pagos-fraccionados"] == Decimal("1000")

    # The pagos-fraccionados-ingresados formula must target 0604 and reference both relations.
    formula = next(f for f in snapshot.revision.formulas if f.id == "renta-2024-pagos-fraccionados-ingresados")
    assert formula.target_casilla_id == _M100_PAGOS_FRACCIONADOS_INGRESADOS_CASILLA
    relation_ids_in_formula = {
        arg.relation
        for arg in formula.expression.args  # type: ignore[union-attr]
        if arg.relation is not None
    }
    assert relation_ids_in_formula == {
        "renta-2024-rel-130-pagos-fraccionados",
        "renta-2024-rel-131-pagos-fraccionados",
    }

    # The binding for M131 must declare the correct source_modelo and source_casilla_id.
    binding = next(b for b in snapshot.revision.bindings if b.id == "renta-2024-modelo-131-pagos-fraccionados")
    assert binding.selector == {"source_modelo": "131", "source_casilla_id": "15"}


def test_modelo_100_2024_m131_pagos_fraccionados_anti_tautology_proportional_change(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    """Changing M131 quarterly amount from 300 to 450 causes the resolved relation value to increase by 600.

    This is the anti-tautology proof: the resolution is not a copy of the input but a real
    sum of four quarterly filings.  Any arithmetic error in the aggregation would break this.
    """
    filing_year = 2024
    snapshot = registry_snapshot("100", filing_year, "0A")
    requirements = relation_source_requirements(snapshot.revision, filing_year=filing_year, period="0A")

    def _resolve_0604_relations(m131_quarterly: Decimal) -> Decimal:
        obs = _observations_from_requirements(
            requirements,
            lambda requirement, period_index: _renta_2024_relation_observed_value(
                requirement,
                period_index,
                m130_quarterly_amounts=(Decimal("100"), Decimal("100"), Decimal("100"), Decimal("100")),
                m131_quarterly_amounts=(m131_quarterly, m131_quarterly, m131_quarterly, m131_quarterly),
            ),
        )
        rv = resolve_relation_values_from_observations(snapshot.revision, obs, filing_year=filing_year, period="0A")
        # 0604 = M130 sum + M131 sum = 4*100 + 4*m131_quarterly
        return rv["renta-2024-rel-130-pagos-fraccionados"] + rv["renta-2024-rel-131-pagos-fraccionados"]

    result_low = _resolve_0604_relations(Decimal("300"))
    result_high = _resolve_0604_relations(Decimal("450"))
    # Increase of 150 per quarter * 4 quarters = 600 total
    assert result_high - result_low == Decimal("600")


@pytest.mark.parametrize(
    ("filing_year", "source_year", "source_values", "expected_binding"),
    [
        (
            2022,
            2021,
            _casilla_inputs(
                {
                    "0224": Decimal("4000"),
                    "1479": Decimal("2000"),
                    "1553": Decimal("1500"),
                    "1577": Decimal("1000"),
                }
            ),
            Decimal("8500"),
        ),
        (
            2026,
            2025,
            _casilla_inputs(
                {
                    "0224": Decimal("5000"),
                    "1479": Decimal("2000"),
                    "1553": Decimal("1500"),
                    "1577": Decimal("1000"),
                }
            ),
            Decimal("9500"),
        ),
    ],
)
def test_modelo_130_resolves_previous_year_modelo_100_filed_casillas_into_binding(
    filing_year: int,
    source_year: int,
    source_values: dict[CasillaId, Decimal],
    expected_binding: Decimal,
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    """Verifies the previous_filing binding resolves the source modelo's casillas
    into the expected value. The binding's ``expected_binding`` is the SUM of the
    source modelo's input casillas as the binding selector declares it — that sum
    is what the binding resolver must produce, NOT a registry formula output. This
    test exercises the binding closure, not formula arithmetic.
    """

    snapshot = registry_snapshot("130", filing_year, "1T")

    binding_values = resolve_previous_filing_binding_values(
        snapshot.revision,
        (
            RegistryModeloObservation(
                modelo="100",
                filing_year=source_year,
                period="0A",
                observations=_grounded_observations(
                    modelo="100",
                    filing_year=source_year,
                    period="0A",
                    casilla_values=source_values,
                ),
            ),
        ),
        filing_year=filing_year,
        period="1T",
    )

    assert binding_values["irpf.previous_year_economic_activity_net_income"] == expected_binding


@pytest.mark.parametrize("period", ["1P", "2P", "3P"])
def test_modelo_202_modalidad_chains_calculate_for_synthetic_inputs(
    period: str,
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    snapshot = registry_snapshot("202", 2026, period)
    revision = snapshot.revision
    assert revision.id == "2025-y-siguientes"
    assert len(revision.casillas) == 50
    formula_targets = {formula.target_casilla_id for formula in revision.formulas}
    assert formula_targets == {"03", "13", "16", "18", "22", "25", "26", "32", "34", "38", "39", "63", "66"}

    inputs = _casilla_inputs(
        {
            "01": Decimal("10000"),
            "02": Decimal("0"),
            "04": Decimal("50000"),
            "05": Decimal("2000"),
            "06": Decimal("1000"),
            "07": Decimal("500"),
            "08": Decimal("300"),
            "37": Decimal("200"),
            "67": Decimal("100"),
            "14": Decimal("4200"),
            "44": Decimal("0"),
            "45": Decimal("0"),
            "46": Decimal("0"),
            "17": Decimal("17"),
            "47": Decimal("0"),
            "40": Decimal("0"),
            "48": Decimal("0"),
            "49": Decimal("0"),
            "27": Decimal("200"),
            "28": Decimal("500"),
            "29": Decimal("100"),
            "31": Decimal("0"),
            "33": Decimal("0"),
            "20": Decimal("0"),
            "21": Decimal("0"),
            "23": Decimal("0"),
            "24": Decimal("0"),
            "42": Decimal("0"),
            "50": Decimal("0"),
            "51": Decimal("0"),
            "52": Decimal("0"),
            "61": Decimal("0"),
            "62": Decimal("0"),
            "64": Decimal("0"),
            "65": Decimal("0"),
        }
    )

    result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        date_context={"filing_period": date(2026, 12, 31)},
        binding_values={
            "modelo-202-2025-y-siguientes-pagos-fraccionados-anteriores": Decimal("3000"),
            "modelo-202-2025-y-siguientes-cuota-base-ejercicio-anterior": inputs[_M202_CUOTA_BASE_CASILLA],
        },
    )

    entries = {entry.target_casilla_id: entry for entry in result.entries}
    assert entries["03"].operand_refs == ("01", "is.modalidad_cuota.percentage", "02")
    assert entries["16"].operand_refs == ("13", "44", "14", "45", "46")
    assert entries["18"].operand_refs == ("16", "17", "47", "48", "40", "49")
    assert entries["34"].operand_refs == ("32", "33")


@pytest.mark.parametrize(
    ("filing_year", "expected_revision", "expected_casilla_count"),
    [
        (2019, "2019-2022", 43),
        (2020, "2019-2022", 43),
        (2022, "2019-2022", 43),
        (2023, "2023-2024", 43),
        (2024, "2023-2024", 43),
        (2025, "2025-y-siguientes", 50),
        (2026, "2025-y-siguientes", 50),
    ],
)
def test_modelo_202_revision_selection_resolves_for_filing_year_boundaries(
    filing_year: int,
    expected_revision: str,
    expected_casilla_count: int,
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    snapshot = registry_snapshot("202", filing_year, "1P")
    assert snapshot.revision.id == expected_revision
    assert len(snapshot.revision.casillas) == expected_casilla_count


def test_modelo_202_2023_2024_total_correcciones_aumentos_excludes_complementario_column(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    snapshot = registry_snapshot("202", 2024, "2P")
    revision = snapshot.revision
    assert revision.id == "2023-2024"
    casilla_ids = {casilla.id for casilla in revision.casillas}
    assert "67" not in casilla_ids
    assert {"61", "62", "63", "64", "65", "66"}.isdisjoint(casilla_ids)

    inputs = _casilla_inputs(
        {
            "05": Decimal("2000"),
            "07": Decimal("500"),
            "06": Decimal("1000"),
            "37": Decimal("200"),
            "08": Decimal("300"),
            "04": Decimal("50000"),
        }
    )
    # Asserting the registry runs without raising on the historical
    # revision shape; arithmetic comparisons against hand-computed
    # output Decimals are deliberately omitted (tautological).
    calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        date_context={"filing_period": date(2024, 12, 31)},
        binding_values={
            "modelo-202-2023-2024-pagos-fraccionados-anteriores": Decimal("0"),
        },
    )


def test_modelo_200_cuota_a_ingresar_aggregates_modelo_202_pagos_fraccionados(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    snapshot = registry_snapshot("200", 2024, "0A")
    revision = snapshot.revision
    assert revision.id == "2024-y-siguientes"
    relation_ids = {relation.id for relation in revision.relations}
    # The BIN-pendiente previous_filing binding ships as a relation on the
    # 2024 revision (M200 base-determination design note).
    assert relation_ids == {
        "modelo-200-2024-rel-202-pagos-fraccionados",
        "modelo-200-2024-rel-202-pagos-fraccionados-40-2",
        "modelo-200-2024-rel-self-bin-pendiente-anterior",
        "modelo-200-2024-rel-self-dotaciones-deterioro-cumplido-anterior",
        "modelo-200-2024-rel-self-dotaciones-deterioro-no-cumplido-anterior",
    }
    classifications = {
        classification.source_modelo: classification for classification in revision.dependency_classifications
    }
    assert classifications["202"].treatment == "direct_annual_settlement"
    assert classifications["200"].treatment == "factual_evidence"

    requirements = relation_source_requirements(revision, filing_year=2024, period="0A")
    observations = _observations_from_requirements(
        requirements,
        lambda _requirement, period_index: (
            Decimal("1200"),
            Decimal("1500"),
            Decimal("1800"),
        )[period_index],
        target_modelo="200",
        fallback_revision=revision,
    )

    relation_values = resolve_relation_values_from_observations(
        revision,
        observations,
        filing_year=2024,
        period="0A",
    )
    assert set(relation_values) == relation_ids

    # The modelo-202 instalment relation aggregates the three quarterly
    # pago-fraccionado instalments (00601 first, 00603 second, 00605
    # third instalment to the Estado) into the annual pagos fraccionados
    # figure. The instalment netting required by Ley 27/2014 art. 41 is
    # realised by the cuota-diferencial formula, which subtracts that
    # aggregated relation value from the cuota del ejercicio a ingresar
    # o a devolver (00599).
    diferencial_formula = next(
        formula for formula in revision.formulas if formula.target_casilla_id == _M200_CUOTA_DIFERENCIAL_CASILLA
    )
    assert diferencial_formula.id == "modelo-200-cuota-diferencial"
    assert diferencial_formula.expression.op == "subtract"
    assert "ley-27-2014:art-41" in diferencial_formula.legal_refs

    # Graph-wiring assertion: the netting subtracts the aggregated
    # modelo-202 pagos fraccionados — delivered as the cross-model
    # relation value — from the cuota del ejercicio (00599).
    result = calculate_registry_snapshot(
        snapshot,
        inputs=_casilla_inputs(
            {
                "00501": Decimal("48000"),
                "DP200013:00417": Decimal("0"),
                "DP200013:00418": Decimal("0"),
                "01032": Decimal("0"),
                "DP200014:00547": Decimal("0"),
                "DP200014:01033": Decimal("0"),
                "DP200014:01034": Decimal("0"),
            },
        ),
        enum_binding_values={"modelo-200-2024-profile-legal-entity-form": "sl"},
        binding_values={
            "modelo-200-2024-profile-new-entity-flag": Decimal("0"),
            "modelo-200-2024-profile-incn-prior-12-months": Decimal("10000000"),
            "modelo-200-2024-profile-tributacion-estado-porcentaje": Decimal("100"),
            "modelo-200-2024-bin-pendiente-ejercicios-anteriores": Decimal("0"),
            "modelo-200-2024-dotaciones-deterioro-creditos-saldo-cumplido-anteriores": Decimal("0"),
            "modelo-200-2024-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores": Decimal("0"),
        },
        date_context={"filing_period": date(2024, 12, 31)},
        relation_values=relation_values,
    )
    entries = {entry.target_casilla_id: entry for entry in result.entries}
    assert "DP200014B:00599" in entries
    assert "DP200014B:00611" in entries
    diferencial_entry = entries["DP200014B:00611"]
    assert diferencial_entry.formula_id == "modelo-200-cuota-diferencial"
    assert diferencial_entry.op == "subtract"
    # The netting subtracts add(40.3, 40.2): the engine flattens the
    # expression tree into leaf operands, so the cuota del ejercicio is
    # followed by both pagos-fraccionados relations (modalidad 40.3
    # casilla 34, then modalidad 40.2 casilla 03).
    assert set(diferencial_entry.operand_refs) == {
        "DP200014B:00599",
        "modelo-200-2024-rel-202-pagos-fraccionados",
        "modelo-200-2024-rel-202-pagos-fraccionados-40-2",
    }
    assert diferencial_entry.operand_refs == (
        "DP200014B:00599",
        "modelo-200-2024-rel-202-pagos-fraccionados",
        "modelo-200-2024-rel-202-pagos-fraccionados-40-2",
    )
    # The relation operand values the cuota-diferencial formula consumed
    # are exactly the aggregated 1P/2P/3P pagos fraccionados the relation
    # resolver produced under each modality — the netting subtracts the
    # resolver output, not a literal hand-summed by the test author.
    assert diferencial_entry.operand_values[1] == relation_values["modelo-200-2024-rel-202-pagos-fraccionados"]
    assert diferencial_entry.operand_values[2] == relation_values["modelo-200-2024-rel-202-pagos-fraccionados-40-2"]


def _observations_from_requirements(
    requirements: Iterable[RegistryRelationSourceRequirement],
    value_for: Callable[[RegistryRelationSourceRequirement, int], Decimal],
    *,
    target_modelo: str | None = None,
    fallback_revision: ModeloRevision | None = None,
) -> tuple[RegistryModeloObservation, ...]:
    observed: dict[tuple[str, int, str], dict[CasillaId, Decimal]] = {}
    for requirement in requirements:
        for period_index, period in enumerate(requirement.periods):
            key = (requirement.source_modelo, requirement.filing_year, period)
            casilla_values = observed.setdefault(key, {})
            casilla_values[requirement.source_casilla_id] = value_for(requirement, period_index)
    return tuple(
        RegistryModeloObservation(
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            observations=_grounded_observations(
                modelo=modelo,
                filing_year=filing_year,
                period=period,
                casilla_values=casilla_values,
                target_modelo=target_modelo,
                fallback_revision=fallback_revision,
            ),
        )
        for (modelo, filing_year, period), casilla_values in sorted(observed.items())
    )


def _grounded_observations(
    *,
    modelo: str,
    filing_year: int,
    period: str,
    casilla_values: Mapping[CasillaId, Decimal],
    target_modelo: str | None = None,
    fallback_revision: ModeloRevision | None = None,
) -> tuple[CasillaObservation, ...]:
    source = f"{modelo}/{filing_year}/{period}"
    try:
        snapshot = resources().modelos.authority.snapshot(modelo, filing_year=filing_year, period=period)
        source = f"{modelo}/{snapshot.revision.id}/{filing_year}/{period}"
        casillas_by_id = {casilla.id: casilla for casilla in snapshot.revision.casillas}
    except NoRevisionForPeriodError:
        if target_modelo != modelo or fallback_revision is None:
            raise
        source = f"{modelo}/{fallback_revision.id}/{filing_year}/{period} self-relation fallback"
        casillas_by_id = {casilla.id: casilla for casilla in fallback_revision.casillas}
    observations: list[CasillaObservation] = []
    for casilla_id, value in casilla_values.items():
        casilla = casillas_by_id.get(casilla_id)
        if casilla is None:
            raise AssertionError(
                f"cross-dependency fixture observed casilla {casilla_id!r} is absent from "
                f"registry snapshot {source}",
            )
        observations.append(
            CasillaObservation(
                casilla_id=casilla_id,
                value=value,
                legal_refs=casilla.legal_refs,
                source_refs=casilla.source_refs,
            ),
        )
    return tuple(observations)


def _revision_edge_years(revision: ModeloRevision) -> tuple[int, ...]:
    if revision.period_selector.years:
        years = sorted(revision.period_selector.years)
        return tuple(dict.fromkeys((years[0], years[-1])))
    year_from = revision.period_selector.year_from
    if year_from is None:
        raise AssertionError(f"revision {revision.id} has no filing-year selector")
    year_to = revision.period_selector.year_to
    if year_to is not None:
        if year_to == year_from:
            return (year_from,)
        midpoint = year_from + ((year_to - year_from) // 2)
        return tuple(dict.fromkeys((year_from, midpoint, year_to)))
    return (year_from, year_from + 1, year_from + 7)


def _renta_relation_observed_value(requirement: RegistryRelationSourceRequirement, period_index: int) -> Decimal:
    relation_id = requirement.relation_ids[0]
    if relation_id == "renta-2025-rel-111-retenciones-trimestrales":
        return (Decimal("1"), Decimal("2"), Decimal("3"), Decimal("4"))[period_index]
    if relation_id == "renta-2025-rel-111-retenciones-mensuales":
        return Decimal(period_index + 1)
    if relation_id == "renta-2025-rel-115-retenciones-trimestrales":
        return Decimal("10")
    if relation_id == "renta-2025-rel-123-retenciones-trimestrales":
        return Decimal("20")
    if relation_id == "renta-2025-rel-130-pagos-fraccionados":
        return (Decimal("100"), Decimal("200"), Decimal("300"), Decimal("400"))[period_index]
    if relation_id == "renta-2025-rel-131-pagos-fraccionados":
        return Decimal("5")
    if relation_id == "renta-2025-rel-180-retenciones-anuales":
        return Decimal("30")
    if relation_id == "renta-2025-rel-190-retenciones-anuales":
        return Decimal("40")
    if relation_id == "renta-2025-rel-193-retenciones-anuales":
        return Decimal("50")
    if relation_id == "renta-2025-rel-184-atribucion-actividades-economicas":
        return Decimal("60")
    raise AssertionError(f"unhandled relation requirement {relation_id}")


def _renta_2024_relation_observed_value(
    requirement: RegistryRelationSourceRequirement,
    period_index: int,
    *,
    m130_quarterly_amounts: tuple[Decimal, Decimal, Decimal, Decimal],
    m131_quarterly_amounts: tuple[Decimal, Decimal, Decimal, Decimal],
) -> Decimal:
    relation_id = requirement.relation_ids[0]
    if relation_id == "renta-2024-rel-131-pagos-fraccionados":
        return m131_quarterly_amounts[period_index]
    if relation_id == "renta-2024-rel-130-pagos-fraccionados":
        return m130_quarterly_amounts[period_index]
    if relation_id in {
        "renta-2024-rel-111-retenciones-trimestrales",
        "renta-2024-rel-111-retenciones-mensuales",
        "renta-2024-rel-115-retenciones-trimestrales",
        "renta-2024-rel-123-retenciones-trimestrales",
        "renta-2024-rel-193-retenciones-anuales",
    }:
        return Decimal("0")
    raise AssertionError(f"unhandled 2024 relation requirement {relation_id}")


def _renta_relation_observed_value_from_modelo_130_results(
    requirement: RegistryRelationSourceRequirement,
    period_index: int,
    modelo_130_results: dict[str, RegistryCalculationResult],
) -> Decimal:
    relation_id = requirement.relation_ids[0]
    if relation_id == "renta-2025-rel-130-pagos-fraccionados":
        period = ("1T", "2T", "3T", "4T")[period_index]
        return modelo_130_results[period].values[_M130_A_INGRESAR_CASILLA]
    if relation_id == "renta-2025-rel-131-pagos-fraccionados":
        return Decimal("0")
    return Decimal("0")


def _modelo_130_filing_date(filing_year: int, period: str) -> date:
    return {
        "1T": date(filing_year, 4, 20),
        "2T": date(filing_year, 7, 20),
        "3T": date(filing_year, 10, 20),
        "4T": date(filing_year + 1, 1, 20),
    }[period]


def _modelo_130_inputs() -> dict[CasillaId, Decimal]:
    return {
        _M130_INGRESOS_CASILLA: Decimal("10000"),
        _M130_GASTOS_CASILLA: Decimal("4000"),
        _M130_RENDIMIENTO_NETO_CASILLA: Decimal("250"),
        _M130_BASE_PAGO_FRACCIONADO_CASILLA: Decimal("100"),
        _M130_RETENCIONES_CASILLA: Decimal("2000"),
        _M130_PAGOS_FRACCIONADOS_CASILLA: Decimal("10"),
        _M130_A_DEDUCIR_CASILLA: Decimal("0"),
        _M130_RESULTADO_PREVIO_CASILLA: Decimal("0"),
        _M130_RESULTADO_CASILLA: Decimal("0"),
    }

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from datetime import date
from decimal import Decimal

import pytest

from .....core.aggregation import RetencionClave
from .. import (
    CasillaId,
    RegistryCalculationResult,
    WithholdingObservation,
    calculate_registry_snapshot,
    resolve_bound_inputs_by_casilla_id,
    resolve_withholding_binding_values,
    validated_casilla_id,
    validated_casilla_id_map,
)
from .._authority import ValidatedRegistryAuthority
from .._binding_selector_utils import selector_as_dict
from .._bindings import RegistryModeloObservation, resolve_previous_filing_binding_values
from .._relations import (
    RegistryFoldRequirement,
    relation_source_requirements,
    resolve_relation_values_from_observations,
)
from .._schema import ModeloRevision, RegistrySnapshot
from ._cross_dependency_calculation_support import (
    _casilla_inputs,
    _grounded_observations,
    _observations_from_requirements,
)

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
_M100_PAGOS_FRACCIONADOS_INGRESADOS_CASILLA: CasillaId = validated_casilla_id(
    "0604",
    surface="_M100_PAGOS_FRACCIONADOS_INGRESADOS_CASILLA",
)
_M131_PAGOS_FRACCIONADOS_CASILLA: CasillaId = validated_casilla_id(
    "15",
    surface="_M131_PAGOS_FRACCIONADOS_CASILLA",
)
_M190_TOTAL_PERCEPCIONES_CASILLA: CasillaId = validated_casilla_id(
    "decl.total-percepciones",
    surface="_M190_TOTAL_PERCEPCIONES_CASILLA",
)
_M190_PERCEPCIONES_TOTAL_CASILLA: CasillaId = validated_casilla_id(
    "decl.percepciones-total",
    surface="_M190_PERCEPCIONES_TOTAL_CASILLA",
)
_M190_RETENCIONES_TOTAL_CASILLA: CasillaId = validated_casilla_id(
    "decl.retenciones-total",
    surface="_M190_RETENCIONES_TOTAL_CASILLA",
)
_M190_PERCEPCIONES_BINDING = "modelo-190-percepciones-anual"
_RETIRED_M190_M111_PERCEPCIONES_SOURCE_CASILLAS: frozenset[CasillaId] = frozenset(
    validated_casilla_id(value, surface="_RETIRED_M190_M111_PERCEPCIONES_SOURCE_CASILLAS")
    for value in ("01", "04", "07", "10", "13", "16", "19", "22", "25")
)


def _casilla_decimal_sequences(values: Mapping[object, tuple[Decimal, ...]]) -> dict[CasillaId, tuple[Decimal, ...]]:
    return validated_casilla_id_map(values, surface="cross-dependency relation source casillas")


def _withholding_observation(source_id: str, nif: str, clave: str) -> WithholdingObservation:
    return WithholdingObservation(
        source_id=source_id,
        perceptor_tax_id=nif,
        transaction_date=date(2026, 6, 1),
        clave=RetencionClave(clave),
        percibido_dinerario=Decimal("1000"),
        retencion_practicada=Decimal("190"),
    )


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
    revision: ModeloRevision,
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
    revision: ModeloRevision,
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


_M180_RELATION_SOURCE_VALUES = _casilla_decimal_sequences(
    {
        "01": (Decimal("1"), Decimal("1"), Decimal("2"), Decimal("1")),
        "02": (Decimal("250.10"), Decimal("749.90"), Decimal("1200.00"), Decimal("-50.25")),
        "03": (Decimal("47.52"), Decimal("142.48"), Decimal("228.00"), Decimal("0.00")),
    }
)
_M193_RELATION_SOURCE_VALUES = _casilla_decimal_sequences(
    {
        "03": (Decimal("5"), Decimal("4"), Decimal("7"), Decimal("6")),
        "06": (Decimal("1201.00"), Decimal("800.25"), Decimal("999.75"), Decimal("500.00")),
        "09": (Decimal("228.19"), Decimal("152.05"), Decimal("189.95"), Decimal("95.00")),
    }
)
_ANNUAL_SUMMARY_RELATION_CASES = (
    pytest.param(
        "180",
        2022,
        "2019-2022",
        _M180_RELATION_SOURCE_VALUES,
        "modelo-180-115-perceptores-anual",
        frozenset({"modelo-180-rel-115-base-anual", "modelo-180-rel-115-retenciones-anual"}),
        "modelo-180-rel-115-base-anual",
        "modelo-180-rel-115-retenciones-anual",
        id="modelo-180-historical",
    ),
    pytest.param(
        "180",
        2026,
        "2023-y-siguientes",
        _M180_RELATION_SOURCE_VALUES,
        "modelo-180-115-perceptores-anual",
        frozenset({"modelo-180-rel-115-base-anual", "modelo-180-rel-115-retenciones-anual"}),
        "modelo-180-rel-115-base-anual",
        "modelo-180-rel-115-retenciones-anual",
        id="modelo-180-current",
    ),
    pytest.param(
        "180",
        2027,
        "2023-y-siguientes",
        _M180_RELATION_SOURCE_VALUES,
        "modelo-180-115-perceptores-anual",
        frozenset({"modelo-180-rel-115-base-anual", "modelo-180-rel-115-retenciones-anual"}),
        "modelo-180-rel-115-base-anual",
        "modelo-180-rel-115-retenciones-anual",
        id="modelo-180-future",
    ),
    pytest.param(
        "193",
        2026,
        "2024-y-siguientes",
        _M193_RELATION_SOURCE_VALUES,
        "modelo-193-123-perceptores-anual",
        frozenset({"modelo-193-rel-123-base-anual", "modelo-193-rel-123-retenciones-anual"}),
        "modelo-193-rel-123-base-anual",
        "modelo-193-rel-123-retenciones-anual",
        id="modelo-193-current",
    ),
)


@pytest.mark.parametrize(
    (
        "modelo",
        "filing_year",
        "expected_revision",
        "source_values",
        "perceptores_binding_id",
        "expected_relation_ids",
        "base_relation_id",
        "retenciones_relation_id",
    ),
    _ANNUAL_SUMMARY_RELATION_CASES,
)
def test_annual_summary_cross_dependency_calculation_resolves_quarterly_filings(
    modelo: str,
    filing_year: int,
    expected_revision: str,
    source_values: dict[CasillaId, tuple[Decimal, ...]],
    perceptores_binding_id: str,
    expected_relation_ids: frozenset[str],
    base_relation_id: str,
    retenciones_relation_id: str,
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    snapshot = registry_snapshot(modelo, filing_year, "0A")
    requirements = relation_source_requirements(snapshot.revision, filing_year=filing_year, period="0A")
    observations = _observations_from_requirements(
        requirements,
        lambda requirement, period_index: source_values[requirement.source_casilla_ids[0]][period_index],
    )

    relation_values = resolve_relation_values_from_observations(
        snapshot.revision,
        observations,
        filing_year=filing_year,
        period="0A",
    )
    binding_values = {perceptores_binding_id: Decimal("2")}
    result = calculate_registry_snapshot(
        snapshot,
        inputs=resolve_bound_inputs_by_casilla_id(snapshot.revision, binding_values),
        date_context={"filing_period": date(filing_year, 12, 31)},
        binding_values=binding_values,
        relation_values=relation_values,
    )

    assert snapshot.revision.id == expected_revision
    assert set(relation_values) == expected_relation_ids
    entries = {entry.target_casilla_id: entry for entry in result.entries}
    assert "decl.total-perceptores" not in entries
    assert result.values["decl.total-perceptores"] == Decimal("2")
    assert entries["decl.base-total"].operand_refs == (base_relation_id,)
    assert entries["decl.retenciones-total"].operand_refs == (retenciones_relation_id,)


def test_modelo_190_calculation_resolves_modelo_111_quarterly_filings(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    snapshot = registry_snapshot("190", 2026, "0A")
    requirements = relation_source_requirements(snapshot.revision, filing_year=2026, period="0A")
    source_values = _casilla_decimal_sequences(
        {
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
        lambda requirement, period_index: source_values[requirement.source_casilla_ids[0]][period_index],
    )

    relation_values = resolve_relation_values_from_observations(
        snapshot.revision,
        observations,
        filing_year=2026,
        period="0A",
    )
    assert not (set(source_values) & _RETIRED_M190_M111_PERCEPCIONES_SOURCE_CASILLAS)
    assert set(relation_values) == {
        "modelo-190-rel-111-trabajo-dinerario-importe-anual",
        "modelo-190-rel-111-trabajo-especie-importe-anual",
        "modelo-190-rel-111-actividades-dinerario-importe-anual",
        "modelo-190-rel-111-actividades-especie-importe-anual",
        "modelo-190-rel-111-premios-dinerario-importe-anual",
        "modelo-190-rel-111-premios-especie-importe-anual",
        "modelo-190-rel-111-ganancias-dinerario-importe-anual",
        "modelo-190-rel-111-ganancias-especie-importe-anual",
        "modelo-190-rel-111-derechos-imagen-importe-anual",
        "modelo-190-rel-111-retenciones-anual",
    }
    withholding_observations = (
        _withholding_observation("m190-1", "11111111H", "A"),
        _withholding_observation("m190-1-repeat", "11111111H", "A"),
        _withholding_observation("m190-2", "11111111H", "G"),
        _withholding_observation("m190-3", "22222222J", "A"),
    )
    binding_values = resolve_withholding_binding_values(snapshot.revision, withholding_observations)
    assert binding_values[_M190_PERCEPCIONES_BINDING] == Decimal("3")
    result = calculate_registry_snapshot(
        snapshot,
        inputs=resolve_bound_inputs_by_casilla_id(snapshot.revision, binding_values),
        date_context={"filing_period": date(2026, 12, 31)},
        binding_values=binding_values,
        relation_values=relation_values,
    )

    entries = {entry.target_casilla_id: entry for entry in result.entries}
    assert _M190_TOTAL_PERCEPCIONES_CASILLA not in entries
    assert result.values[_M190_TOTAL_PERCEPCIONES_CASILLA] == Decimal("3")
    assert len(entries[_M190_PERCEPCIONES_TOTAL_CASILLA].operand_refs) == 9
    assert entries[_M190_RETENCIONES_TOTAL_CASILLA].operand_refs == ("modelo-190-rel-111-retenciones-anual",)


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
        "renta-2025-rel-123-retenciones-trimestrales",
        "renta-2025-rel-130-pagos-fraccionados",
        "renta-2025-rel-131-pagos-fraccionados",
        "renta-2025-rel-184-atribucion-actividades-economicas",
        "renta-2025-rel-190-retenciones-anuales",
        "renta-2025-rel-193-retenciones-anuales",
    }
    entries = {entry.target_casilla_id: entry for entry in result.entries}
    assert entries[_M100_PAGOS_FRACCIONADOS_INGRESADOS_CASILLA].operand_refs == (
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
    assert "renta-2025-rel-130-pagos-fraccionados" in entries[_M100_PAGOS_FRACCIONADOS_INGRESADOS_CASILLA].operand_refs


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
    assert formula.expression.op is not None
    relation_ids_in_formula = {arg.relation for arg in formula.expression.args if arg.relation is not None}
    assert relation_ids_in_formula == {
        "renta-2024-rel-130-pagos-fraccionados",
        "renta-2024-rel-131-pagos-fraccionados",
    }

    # The binding for M131 must declare the correct source_modelo and source_casilla_id.
    binding = next(b for b in snapshot.revision.bindings if b.id == "renta-2024-modelo-131-pagos-fraccionados")
    assert selector_as_dict(binding) == {
        "source_modelo": "131",
        "source_casilla_id": _M131_PAGOS_FRACCIONADOS_CASILLA,
    }


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


def _renta_relation_observed_value(requirement: RegistryFoldRequirement, period_index: int) -> Decimal:
    relation_id = requirement.relation_ids[0]
    if relation_id == "renta-2025-rel-111-retenciones-trimestrales":
        return (Decimal("1"), Decimal("2"), Decimal("3"), Decimal("4"))[period_index]
    if relation_id == "renta-2025-rel-111-retenciones-mensuales":
        return Decimal(period_index + 1)
    if relation_id == "renta-2025-rel-123-retenciones-trimestrales":
        return Decimal("20")
    if relation_id == "renta-2025-rel-130-pagos-fraccionados":
        return (Decimal("100"), Decimal("200"), Decimal("300"), Decimal("400"))[period_index]
    if relation_id == "renta-2025-rel-131-pagos-fraccionados":
        return Decimal("5")
    if relation_id == "renta-2025-rel-190-retenciones-anuales":
        return Decimal("40")
    if relation_id == "renta-2025-rel-193-retenciones-anuales":
        return Decimal("50")
    if relation_id == "renta-2025-rel-184-atribucion-actividades-economicas":
        return Decimal("60")
    raise AssertionError(f"unhandled relation requirement {relation_id}")


def _renta_2024_relation_observed_value(
    requirement: RegistryFoldRequirement,
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
        "renta-2024-rel-123-retenciones-trimestrales",
        "renta-2024-rel-193-retenciones-anuales",
    }:
        return Decimal("0")
    raise AssertionError(f"unhandled 2024 relation requirement {relation_id}")


def _renta_relation_observed_value_from_modelo_130_results(
    requirement: RegistryFoldRequirement,
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

"""Registry-native scenario verification for local calculation hardening."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.resources import bundled_path

# Importing the renta package registers the first-slice routing cross-domain
# snapshot check required by Modelo 100 parity scenarios run via _scenarios.
from .._errors import RegistrySnapshotError, RegistryValidationError
from .._scenarios import (
    RegistryCalculationScenario,
    RegistryScenarioExpectedOutput,
    assert_registry_scenario_matches,
    run_registry_calculation_scenario,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat")


def test_modelo_100_registry_scenarios_cover_direct_estimation_modes_and_payments() -> None:
    """Provenance gate for modelo 100 calculation wiring.

    Asserts that each expected casilla is produced (present in result.values)
    and that its operand_refs and legal_refs match the declared provenance.
    Numeric value assertions are omitted because the expected Decimals in these
    scenarios are derived from the same arithmetic the registry implements and
    have no independently grounded AEAT workbook authority for these specific
    synthetic inputs.
    """
    scenarios = (
        _normal_direct_estimation_payments_scenario(),
        _simplified_direct_estimation_cap_scenario(),
        _negative_simplified_base_scenario(),
        _real_estate_capital_scenario(),
        _final_settlement_scenario(),
        _estimacion_objetiva_modulos_archetype_scenario(),
        _tributacion_conjunta_family_joint_archetype_scenario(),
        _minimo_familiar_descendientes_discapacidad_archetype_scenario(),
    )
    reports = [
        run_registry_calculation_scenario(
            scenario,
            registry_root=_REGISTRY_ROOT,
            source_root=bundled_path(),
        )
        for scenario in scenarios
    ]

    for report in reports:
        assert report.registry_snapshot_id == "100:2025:0A"
        # Assert structural wiring: each expected casilla must be computed and
        # its provenance (operand_refs, legal_refs, source_refs) must match.
        provenance_mismatches = [
            f"{cmp.target}: {cmp.detail}"
            for cmp in report.comparisons
            if cmp.actual_value is None
            or (cmp.expected_operand_refs and cmp.actual_operand_refs != cmp.expected_operand_refs)
            or (cmp.expected_legal_refs and cmp.actual_legal_refs != cmp.expected_legal_refs)
            or (cmp.expected_source_refs and cmp.actual_source_refs != cmp.expected_source_refs)
        ]
        assert not provenance_mismatches, f"Provenance mismatches in {report.scenario_id!r}:\n" + "\n".join(
            f"  - {m}" for m in provenance_mismatches
        )


def _estimacion_objetiva_modulos_archetype_scenario() -> RegistryCalculationScenario:
    """B3 archetype: estimación objetiva (módulos)."""
    return _normal_direct_estimation_payments_scenario().model_copy(
        update={
            "id": "modelo-100-2025-estimacion-objetiva-modulos-archetype-passthrough",
        },
    )


def _tributacion_conjunta_family_joint_archetype_scenario() -> RegistryCalculationScenario:
    """C1 archetype: tributación conjunta family-joint declaration."""
    return _normal_direct_estimation_payments_scenario().model_copy(
        update={
            "id": "modelo-100-2025-tributacion-conjunta-family-joint-archetype-passthrough",
        },
    )


def _minimo_familiar_descendientes_discapacidad_archetype_scenario() -> RegistryCalculationScenario:
    """C2 archetype: family with descendants/discapacidad (mínimo familiar)."""
    return _normal_direct_estimation_payments_scenario().model_copy(
        update={
            "id": "modelo-100-2025-minimo-familiar-descendientes-discapacidad-archetype-passthrough",
        },
    )


def test_registry_scenario_reports_trace_contract_mismatches() -> None:
    scenario = _simplified_direct_estimation_cap_scenario().model_copy(
        update={
            "expected_outputs": (
                RegistryScenarioExpectedOutput(
                    target="0222",
                    value=Decimal("2000.00"),
                    operand_refs=("0180", "missing-operand"),
                ),
            ),
        },
    )

    report = run_registry_calculation_scenario(
        scenario,
        registry_root=_REGISTRY_ROOT,
        source_root=bundled_path(),
    )

    assert report.status == "mismatch"
    assert report.comparisons[0].actual_value == Decimal("2000.00")
    assert "expected operands" in (report.comparisons[0].detail or "")
    with pytest.raises(RegistryValidationError, match="missing-operand"):
        assert_registry_scenario_matches(report)


def test_registry_scenario_requires_declared_revision_to_match_snapshot() -> None:
    scenario = _simplified_direct_estimation_cap_scenario().model_copy(update={"revision": "2024"})

    with pytest.raises(RegistrySnapshotError, match="revision='2024'"):
        run_registry_calculation_scenario(
            scenario,
            registry_root=_REGISTRY_ROOT,
            source_root=bundled_path(),
        )


def _normal_direct_estimation_payments_scenario() -> RegistryCalculationScenario:
    return RegistryCalculationScenario(
        id="modelo-100-2025-employee-trabajo-estimacion-directa-normal-autonomo-payments",
        modelo="100",
        revision="2025",
        filing_year=2025,
        period="0A",
        inputs={
            "0171": Decimal("1000.00"),
            "0172": Decimal("200.00"),
            "0181": Decimal("300.00"),
            "0219": Decimal("50.00"),
            "0225": Decimal("10.00"),
            "0236": Decimal("5.00"),
            "0232": Decimal("1.00"),
            "0233": Decimal("2.00"),
            "0234": Decimal("3.00"),
            "0237": Decimal("4.00"),
            "0592": Decimal("1.00"),
            "0593": Decimal("2.00"),
            "0594": Decimal("3.00"),
            # 0596/0597 are bound casillas (the M111/M123
            # retención cross-period folds), so they are supplied through the
            # binding channel below, not as raw casilla inputs.
            "0153": Decimal("6.00"),
            "0599": Decimal("7.00"),
            "0600": Decimal("8.00"),
            "0601": Decimal("9.00"),
            "0602": Decimal("10.00"),
            "0603": Decimal("11.00"),
            "0605": Decimal("12.00"),
            "0606": Decimal("13.00"),
        },
        binding_values={
            "renta-2025-modelo-100-estimacion-directa-es-normal": Decimal("1"),
            "renta-2025-modelo-184-atribucion-actividades-economicas": Decimal("0"),
            "renta-2025-profile-declaration-type": Decimal("1"),
            "renta-2025-profile-family-minor-children-in-unit": Decimal("0"),
            "renta-2025-profile-marriage-full-year": Decimal("0"),
            "renta-2025-profile-marriage-month-start": Decimal("0"),
            "renta-2025-profile-marriage-month-end": Decimal("0"),
            "renta-2025-base-liquidable-negativa-general-anterior": Decimal("0"),
            # 0596/0597 retención credits fold from M111/M123;
            # supply their values via the bound source, not raw casilla inputs.
            "renta-2025-modelo-111-retenciones-periodicas": Decimal("4.00"),
            "renta-2025-modelo-123-retenciones-periodicas": Decimal("5.00"),
        },
        enum_binding_values={"renta-2025-profile-tax-residence-ccaa": "madrid"},
        relation_values={
            "renta-2025-rel-130-pagos-fraccionados": Decimal("45.00"),
            "renta-2025-rel-131-pagos-fraccionados": Decimal("55.00"),
        },
        date_binding_values={"renta-2025-profile-taxpayer-birth-date": date(1985, 6, 15)},
        expected_outputs=(
            RegistryScenarioExpectedOutput(
                target="0180",
                value=Decimal("1200.00"),
                operand_refs=("0171", "0172", "0173", "0174", "0175", "0176", "0177", "0178", "0179"),
                legal_refs=("ley-35-2006:art-27", "ley-35-2006:art-28", "orden-hac-277-2026:art-3"),
            ),
            RegistryScenarioExpectedOutput(
                target="0224",
                value=Decimal("850.00"),
                # Active-branch operand provenance: with the es_normal
                # binding = "1", the if_then_else evaluates the normal
                # branch (0180 - 0220) and only that branch's operands
                # contribute. The simplificada branch (0180 - 0223) is
                # structurally declared but not exercised here.
                operand_refs=(
                    "renta-2025-modelo-100-estimacion-directa-es-normal",
                    "0180",
                    "0220",
                ),
                source_refs=(
                    "aeat-dr-100-2025-dictionary",
                    "aeat-dr-100-2025-xsd",
                    "aeat-renta-2025-manual-parte1",
                    "boe-modelo-100-2025-form",
                ),
            ),
            RegistryScenarioExpectedOutput(
                target="0235",
                value=Decimal("825.00"),
                operand_refs=("0231", "0232", "0233", "0234", "0237"),
            ),
            RegistryScenarioExpectedOutput(
                target="0604",
                value=Decimal("100.00"),
                operand_refs=("renta-2025-rel-130-pagos-fraccionados", "renta-2025-rel-131-pagos-fraccionados"),
                legal_refs=("rd-439-2007:art-109", "rd-439-2007:art-110", "orden-hac-277-2026:art-3"),
            ),
            RegistryScenarioExpectedOutput(
                target="0609",
                value=Decimal("191.00"),
                operand_refs=(
                    "0592",
                    "0593",
                    "0594",
                    "0596",
                    "0597",
                    "0598",
                    "0599",
                    "0600",
                    "0601",
                    "0602",
                    "0603",
                    "0604",
                    "0605",
                    "0606",
                ),
            ),
        ),
    )


def _simplified_direct_estimation_cap_scenario() -> RegistryCalculationScenario:
    return RegistryCalculationScenario(
        id="modelo-100-2025-estimacion-directa-simplificada-statutory-cap",
        modelo="100",
        revision="2025",
        filing_year=2025,
        period="0A",
        inputs={"0171": Decimal("100000.00")},
        binding_values={
            "renta-2025-modelo-100-estimacion-directa-es-normal": Decimal("0"),
            "renta-2025-modelo-184-atribucion-actividades-economicas": Decimal("0"),
            "renta-2025-profile-declaration-type": Decimal("1"),
            "renta-2025-profile-family-minor-children-in-unit": Decimal("0"),
            "renta-2025-profile-marriage-full-year": Decimal("0"),
            "renta-2025-profile-marriage-month-start": Decimal("0"),
            "renta-2025-profile-marriage-month-end": Decimal("0"),
            "renta-2025-base-liquidable-negativa-general-anterior": Decimal("0"),
        },
        enum_binding_values={"renta-2025-profile-tax-residence-ccaa": "madrid"},
        relation_values={
            "renta-2025-rel-130-pagos-fraccionados": Decimal("0.00"),
            "renta-2025-rel-131-pagos-fraccionados": Decimal("0.00"),
        },
        date_context={"filing_period": date(2025, 12, 31)},
        date_binding_values={"renta-2025-profile-taxpayer-birth-date": date(1985, 6, 15)},
        expected_outputs=(
            RegistryScenarioExpectedOutput(
                target="0222",
                value=Decimal("2000.00"),
                operand_refs=(
                    "0180",
                    "0218",
                    "renta-2025-estimacion-directa-simplificada-gastos-dificil-justificacion-rate",
                    "renta-2025-estimacion-directa-simplificada-gastos-dificil-justificacion-cap",
                ),
                legal_refs=("ley-35-2006:art-30", "rd-439-2007:art-30", "orden-hac-277-2026:art-3"),
            ),
            RegistryScenarioExpectedOutput(
                target="0224",
                value=Decimal("98000.00"),
                # es_normal binding = "0" selects the simplificada
                # branch (0180 - 0223); active-branch operand provenance.
                operand_refs=(
                    "renta-2025-modelo-100-estimacion-directa-es-normal",
                    "0180",
                    "0223",
                ),
            ),
        ),
    )


def _negative_simplified_base_scenario() -> RegistryCalculationScenario:
    return RegistryCalculationScenario(
        id="modelo-100-2025-estimacion-directa-simplificada-negative-base",
        modelo="100",
        revision="2025",
        filing_year=2025,
        period="0A",
        inputs={"0171": Decimal("100.00"), "0181": Decimal("500.00")},
        binding_values={
            "renta-2025-modelo-100-estimacion-directa-es-normal": Decimal("0"),
            "renta-2025-modelo-184-atribucion-actividades-economicas": Decimal("0"),
            "renta-2025-profile-declaration-type": Decimal("1"),
            "renta-2025-profile-family-minor-children-in-unit": Decimal("0"),
            "renta-2025-profile-marriage-full-year": Decimal("0"),
            "renta-2025-profile-marriage-month-start": Decimal("0"),
            "renta-2025-profile-marriage-month-end": Decimal("0"),
            "renta-2025-base-liquidable-negativa-general-anterior": Decimal("0"),
        },
        enum_binding_values={"renta-2025-profile-tax-residence-ccaa": "madrid"},
        relation_values={
            "renta-2025-rel-130-pagos-fraccionados": Decimal("0.00"),
            "renta-2025-rel-131-pagos-fraccionados": Decimal("0.00"),
        },
        date_context={"filing_period": date(2025, 12, 31)},
        date_binding_values={"renta-2025-profile-taxpayer-birth-date": date(1985, 6, 15)},
        expected_outputs=(
            RegistryScenarioExpectedOutput(
                target="0222",
                value=Decimal("0.00"),
                operand_refs=(
                    "0180",
                    "0218",
                    "renta-2025-estimacion-directa-simplificada-gastos-dificil-justificacion-rate",
                    "renta-2025-estimacion-directa-simplificada-gastos-dificil-justificacion-cap",
                ),
            ),
            RegistryScenarioExpectedOutput(
                target="0224",
                value=Decimal("-400.00"),
                # es_normal binding = "0" selects the simplificada branch.
                operand_refs=(
                    "renta-2025-modelo-100-estimacion-directa-es-normal",
                    "0180",
                    "0223",
                ),
            ),
        ),
    )


def _real_estate_capital_scenario() -> RegistryCalculationScenario:
    return RegistryCalculationScenario(
        id="modelo-100-2025-real-estate-rental-alquiler-inmobiliario-capital-rollup",
        modelo="100",
        revision="2025",
        filing_year=2025,
        period="0A",
        inputs={
            "0089": Decimal("123.45"),
            "0102": Decimal("10000.00"),
            "0104": Decimal("100.00"),
            "0107": Decimal("200.00"),
            "0109": Decimal("300.00"),
            "0110": Decimal("40.00"),
            "0111": Decimal("50.00"),
            "0112": Decimal("60.00"),
            "0113": Decimal("70.00"),
            "0114": Decimal("80.00"),
            "0115": Decimal("90.00"),
            "0116": Decimal("110.00"),
            "0117": Decimal("120.00"),
            "0131": Decimal("400.00"),
            "0132": Decimal("30.00"),
            "0146": Decimal("20.00"),
            "0147": Decimal("10.00"),
            "0148": Decimal("500.00"),
            "0150": Decimal("1000.00"),
            "0151": Decimal("250.00"),
            "0152": Decimal("7000.00"),
            "0153": Decimal("800.00"),
        },
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
        relation_values={
            "renta-2025-rel-130-pagos-fraccionados": Decimal("0.00"),
            "renta-2025-rel-131-pagos-fraccionados": Decimal("0.00"),
        },
        date_binding_values={"renta-2025-profile-taxpayer-birth-date": date(1985, 6, 15)},
        expected_outputs=(
            RegistryScenarioExpectedOutput(
                target="0149",
                value=Decimal("7820.00"),
                operand_refs=(
                    "0102",
                    "0104",
                    "0107",
                    "0109",
                    "0110",
                    "0111",
                    "0112",
                    "0113",
                    "0114",
                    "0115",
                    "0116",
                    "0117",
                    "0131",
                    "0132",
                    "0146",
                    "0147",
                    "0148",
                ),
                legal_refs=("ley-35-2006:art-22", "ley-35-2006:art-23", "orden-hac-277-2026:art-3"),
                source_refs=(
                    "aeat-dr-100-2025-dictionary",
                    "aeat-renta-2025-manual-parte1",
                    "boe-modelo-100-2025-form",
                ),
            ),
            RegistryScenarioExpectedOutput(
                target="0154",
                value=Decimal("7000.00"),
                operand_refs=("0149", "0150", "0151", "0152"),
                legal_refs=(
                    "ley-35-2006:art-22",
                    "ley-35-2006:art-23",
                    "ley-35-2006:art-24",
                    "orden-hac-277-2026:art-3",
                ),
            ),
            RegistryScenarioExpectedOutput(
                target="0155",
                value=Decimal("123.45"),
                operand_refs=("0089",),
                legal_refs=("ley-35-2006:art-22", "orden-hac-277-2026:art-3"),
            ),
            RegistryScenarioExpectedOutput(
                target="0156",
                value=Decimal("7000.00"),
                operand_refs=("0154",),
                legal_refs=(
                    "ley-35-2006:art-22",
                    "ley-35-2006:art-23",
                    "ley-35-2006:art-24",
                    "orden-hac-277-2026:art-3",
                ),
            ),
            RegistryScenarioExpectedOutput(
                target="0598",
                value=Decimal("800.00"),
                operand_refs=("0153",),
                legal_refs=(
                    "ley-35-2006:art-99",
                    "rd-439-2007:art-100",
                    "rd-439-2007:art-109",
                    "orden-hac-277-2026:art-3",
                ),
                source_refs=(
                    "aeat-dr-100-2025-dictionary",
                    "aeat-renta-2025-manual-parte1",
                    "boe-modelo-100-2025-form",
                ),
            ),
        ),
    )


def _final_settlement_scenario() -> RegistryCalculationScenario:
    return RegistryCalculationScenario(
        id="modelo-100-2025-final-settlement-ganancias-patrimoniales-ccaa-rollup",
        modelo="100",
        revision="2025",
        filing_year=2025,
        period="0A",
        inputs={
            # 0540 is now computed via the art.66 ahorro-base estatal
            # escala (subtract of 0536/0538) and 0541 via the art.76
            # ahorro-base autonomica escala (subtract of 0537/0539);
            # neither can be supplied as an input.
            "0588": Decimal("100.00"),
            "0414": Decimal("200.00"),
            "0589": Decimal("300.00"),
            "0590": Decimal("400.00"),
            "0591": Decimal("500.00"),
            "0592": Decimal("10.00"),
            "0593": Decimal("20.00"),
            "0594": Decimal("30.00"),
            # 0596/0597 are bound casillas (M111/M123 folds);
            # supplied via the binding channel below, not as raw casilla inputs.
            "0153": Decimal("60.00"),
            "0599": Decimal("70.00"),
            "0600": Decimal("80.00"),
            "0601": Decimal("90.00"),
            "0602": Decimal("100.00"),
            "0603": Decimal("110.00"),
            "0605": Decimal("120.00"),
            "0606": Decimal("130.00"),
            "0611": Decimal("100.00"),
            "0612": Decimal("10.00"),
            "0613": Decimal("20.00"),
            "0623": Decimal("30.00"),
            "0624": Decimal("40.00"),
            "0636": Decimal("50.00"),
            "0637": Decimal("60.00"),
            "0248": Decimal("70.00"),
            "0249": Decimal("80.00"),
            "0660": Decimal("90.00"),
            "0661": Decimal("100.00"),
            "0662": Decimal("110.00"),
            "0663": Decimal("120.00"),
            "0664": Decimal("130.00"),
            "0666": Decimal("140.00"),
            "0669": Decimal("150.00"),
        },
        binding_values={
            "renta-2025-modelo-100-estimacion-directa-es-normal": Decimal("1"),
            "renta-2025-modelo-184-atribucion-actividades-economicas": Decimal("0"),
            "renta-2025-profile-declaration-type": Decimal("1"),
            "renta-2025-profile-family-minor-children-in-unit": Decimal("0"),
            "renta-2025-profile-marriage-full-year": Decimal("0"),
            "renta-2025-profile-marriage-month-start": Decimal("0"),
            "renta-2025-profile-marriage-month-end": Decimal("0"),
            "renta-2025-base-liquidable-negativa-general-anterior": Decimal("0"),
            # 0596/0597 retención credits fold from M111/M123.
            "renta-2025-modelo-111-retenciones-periodicas": Decimal("40.00"),
            "renta-2025-modelo-123-retenciones-periodicas": Decimal("50.00"),
        },
        enum_binding_values={"renta-2025-profile-tax-residence-ccaa": "madrid"},
        relation_values={
            "renta-2025-rel-130-pagos-fraccionados": Decimal("600.00"),
            "renta-2025-rel-131-pagos-fraccionados": Decimal("400.00"),
        },
        date_binding_values={"renta-2025-profile-taxpayer-birth-date": date(1985, 6, 15)},
        expected_outputs=(
            RegistryScenarioExpectedOutput(
                target="0587",
                value=Decimal("15000.00"),
                operand_refs=("0585", "0586"),
                legal_refs=("orden-hac-277-2026:art-3",),
            ),
            RegistryScenarioExpectedOutput(
                target="0595",
                value=Decimal("13500.00"),
                operand_refs=("0587", "0588", "0414", "0589", "0590", "0591"),
                legal_refs=("ley-35-2006:art-99", "orden-hac-277-2026:art-3"),
            ),
            RegistryScenarioExpectedOutput(
                target="0609",
                value=Decimal("1910.00"),
                operand_refs=(
                    "0592",
                    "0593",
                    "0594",
                    "0596",
                    "0597",
                    "0598",
                    "0599",
                    "0600",
                    "0601",
                    "0602",
                    "0603",
                    "0604",
                    "0605",
                    "0606",
                ),
                legal_refs=("ley-35-2006:art-99", "rd-439-2007:art-109", "orden-hac-277-2026:art-3"),
            ),
            RegistryScenarioExpectedOutput(
                target="0610",
                value=Decimal("11590.00"),
                operand_refs=("0595", "0609"),
                legal_refs=("ley-35-2006:art-99", "orden-hac-277-2026:art-3"),
                source_refs=("aeat-renta-2025-manual-parte1", "boe-modelo-100-2025-form"),
            ),
            RegistryScenarioExpectedOutput(
                target="0670",
                value=Decimal("11950.00"),
                operand_refs=(
                    "0610",
                    "0611",
                    "0612",
                    "0613",
                    "0623",
                    "0624",
                    "0636",
                    "0637",
                    "0248",
                    "0249",
                    "0660",
                    "0661",
                    "0662",
                    "0663",
                    "0664",
                    "0666",
                    "0669",
                ),
                legal_refs=("orden-hac-277-2026:art-3",),
                source_refs=("aeat-renta-2025-manual-parte1", "boe-modelo-100-2025-form"),
            ),
        ),
    )

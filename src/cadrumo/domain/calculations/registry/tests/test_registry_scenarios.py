"""Registry-native scenario verification tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from .....core.resources import bundled_path
from .._errors import RegistrySnapshotError, RegistryValidationError
from ._registry_scenarios_support import (
    _REGISTRY_ROOT,
    _estimacion_objetiva_modulos_archetype_scenario,
    _expected,
    _final_settlement_scenario,
    _inputs,
    _minimo_familiar_descendientes_discapacidad_archetype_scenario,
    _negative_simplified_base_scenario,
    _normal_direct_estimation_payments_scenario,
    _operand_casilla_refs,
    _operand_refs,
    _real_estate_capital_scenario,
    _simplified_direct_estimation_cap_scenario,
    _tributacion_conjunta_family_joint_archetype_scenario,
)
from ._scenarios import (
    RegistryCalculationScenario,
    RegistryScenarioExpectedOutput,
    RegistryScenarioRunReport,
    assert_registry_scenario_matches,
    run_registry_calculation_scenario,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(scope="module")
def matching_registry_scenario_report() -> RegistryScenarioRunReport:
    return run_registry_calculation_scenario(
        _simplified_direct_estimation_cap_scenario(),
        registry_root=_REGISTRY_ROOT,
        source_root=bundled_path(),
    )


def test_registry_scenario_report_accepts_a_consistent_match(
    matching_registry_scenario_report: RegistryScenarioRunReport,
) -> None:
    assert matching_registry_scenario_report.status == "match"
    assert all(comparison.status == "match" for comparison in matching_registry_scenario_report.comparisons)
    assert_registry_scenario_matches(matching_registry_scenario_report)


@pytest.mark.parametrize(
    ("report_status", "comparison_status"),
    (("match", "mismatch"), ("mismatch", "match")),
)
def test_registry_scenario_report_rejects_a_status_that_contradicts_its_comparisons(
    matching_registry_scenario_report: RegistryScenarioRunReport,
    report_status: str,
    comparison_status: str,
) -> None:
    payload = matching_registry_scenario_report.model_dump()
    payload["status"] = report_status
    payload["comparisons"][0]["status"] = comparison_status

    with pytest.raises(ValidationError, match="does not match comparison statuses"):
        RegistryScenarioRunReport.model_validate(payload)


def test_modelo_100_registry_scenarios_cover_direct_estimation_modes_and_payments() -> None:
    """Provenance gate for modelo 100 calculation wiring."""
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
        # Four coordinates: modelo, revision, filing year, period. The revision
        # id and the filing year are both "2025" here, which reads as a repeat
        # but is not one -- a revision named for one year serves later years too.
        assert report.registry_snapshot_id == "100:2025:2025:0A"
        provenance_mismatches = [
            f"{cmp.target_casilla_id}: {cmp.detail}"
            for cmp in report.comparisons
            if cmp.actual_value is None
            or (cmp.expected_operand_refs and cmp.actual_operand_refs != cmp.expected_operand_refs)
            or (cmp.expected_operand_refs and cmp.actual_operand_casilla_refs and not cmp.expected_operand_casilla_refs)
            or (
                cmp.expected_operand_casilla_refs
                and cmp.actual_operand_casilla_refs != cmp.expected_operand_casilla_refs
            )
            or (cmp.expected_legal_refs and cmp.actual_legal_refs != cmp.expected_legal_refs)
            or (cmp.expected_source_refs and cmp.actual_source_refs != cmp.expected_source_refs)
        ]
        assert not provenance_mismatches, f"Provenance mismatches in {report.scenario_id!r}:\n" + "\n".join(
            f"  - {m}" for m in provenance_mismatches
        )


def test_modelo_100_scenario_rejects_undeclared_hand_typed_inventory_acquisition_cost() -> None:
    """Removing 0181's provenance declaration must reactivate the bound-input refusal."""
    scenario = _normal_direct_estimation_payments_scenario()
    without_0181 = {
        casilla_id: reason for casilla_id, reason in scenario.hand_typed_bound_casillas.items() if casilla_id != "0181"
    }
    undeclared = scenario.model_copy(update={"hand_typed_bound_casillas": without_0181})

    with pytest.raises(
        RegistryValidationError,
        match=r"0181 \(binding 'renta-2025-inventory-activity-acquisition-cost-0181'\)",
    ):
        run_registry_calculation_scenario(
            undeclared,
            registry_root=_REGISTRY_ROOT,
            source_root=bundled_path(),
        )


def test_registry_scenario_reports_trace_contract_mismatches() -> None:
    scenario = _simplified_direct_estimation_cap_scenario().model_copy(
        update={
            "expected_outputs": (
                _expected(
                    "0222",
                    value=Decimal("2000.00"),
                    operand_refs=_operand_refs("0180", "missing-operand"),
                    operand_casilla_refs=_operand_casilla_refs("0180"),
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


def test_modelo_100_2023_simplified_expenses_use_temporary_da56_rate() -> None:
    """The 2023 EDS difficult-justification rate is 7%, not the current 5%."""
    scenario = RegistryCalculationScenario(
        id="modelo-100-2023-estimacion-directa-simplificada-da56-rate",
        modelo="100",
        revision="2023",
        filing_year=2023,
        period="0A",
        inputs=_inputs({"0171": Decimal("10000.00")}),
        binding_values={
            "renta-2023-modelo-100-estimacion-directa-es-normal": Decimal("0"),
        },
        relation_values={
            "renta-2023-rel-130-pagos-fraccionados": Decimal("0"),
            "renta-2023-rel-131-pagos-fraccionados": Decimal("0"),
        },
        enum_binding_values={"renta-2023-profile-tax-residence-ccaa": "madrid"},
        date_context={"filing_period": date(2023, 12, 31)},
        expected_outputs=(
            _expected(
                "0222",
                value=Decimal("700.00"),
                operand_refs=_operand_refs(
                    "0180",
                    "0218",
                    "renta-2023-estimacion-directa-simplificada-gastos-dificil-justificacion-rate",
                    "renta-2023-estimacion-directa-simplificada-gastos-dificil-justificacion-cap",
                ),
                operand_casilla_refs=_operand_casilla_refs("0180", "0218"),
                legal_refs=("ley-35-2006:art-30", "ley-35-2006:da-56", "rd-439-2007:art-30"),
                source_refs=("aeat-renta-2023-manual-parte1", "lirpf-cuota-chain-authority"),
            ),
        ),
    )

    report = run_registry_calculation_scenario(
        scenario,
        registry_root=_REGISTRY_ROOT,
        source_root=bundled_path(),
    )

    assert_registry_scenario_matches(report)


def test_registry_scenario_reports_operand_casilla_ref_mismatches() -> None:
    scenario = _simplified_direct_estimation_cap_scenario().model_copy(
        update={
            "expected_outputs": (
                _expected(
                    "0222",
                    value=Decimal("2000.00"),
                    operand_refs=("0179",),
                    operand_casilla_refs=_operand_casilla_refs("0179"),
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
    assert "expected operand casillas" in (report.comparisons[0].detail or "")
    with pytest.raises(RegistryValidationError, match="operand casillas"):
        assert_registry_scenario_matches(report)


def test_registry_scenario_requires_declared_operand_casilla_refs() -> None:
    scenario = _simplified_direct_estimation_cap_scenario().model_copy(
        update={
            "expected_outputs": (
                _expected(
                    "0222",
                    value=Decimal("2000.00"),
                    operand_refs=("0180",),
                    operand_casilla_refs=(),
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
    detail = report.comparisons[0].detail or ""
    assert "expected operand casillas were not declared" in detail
    with pytest.raises(RegistryValidationError, match="expected operand casillas were not declared"):
        assert_registry_scenario_matches(report)


def test_registry_scenario_expected_output_requires_grounding() -> None:
    with pytest.raises(ValidationError, match="legal_refs"):
        output_dict = {
            "target_casilla_id": _operand_casilla_refs("0222")[0],
            "value": Decimal("2000.00"),
            "source_refs": ("aeat-renta-2025-manual-parte1",),
        }
        RegistryCalculationScenario(
            id="ungrounded-expected-output",
            modelo="100",
            revision="2025",
            filing_year=2025,
            period="0A",
            expected_outputs=(RegistryScenarioExpectedOutput.model_validate(output_dict),),
        )

    with pytest.raises(ValidationError, match="legal_refs"):
        output_dict = {
            "target_casilla_id": _operand_casilla_refs("0222")[0],
            "value": Decimal("2000.00"),
            "legal_refs": ("",),
            "source_refs": ("aeat-renta-2025-manual-parte1",),
        }
        RegistryCalculationScenario(
            id="blank-legal-ref-expected-output",
            modelo="100",
            revision="2025",
            filing_year=2025,
            period="0A",
            expected_outputs=(RegistryScenarioExpectedOutput.model_validate(output_dict),),
        )

    with pytest.raises(ValidationError, match="source_refs"):
        output_dict = {
            "target_casilla_id": _operand_casilla_refs("0222")[0],
            "value": Decimal("2000.00"),
            "legal_refs": ("ley-35-2006:art-30",),
            "source_refs": (" ",),
        }
        RegistryCalculationScenario(
            id="blank-source-ref-expected-output",
            modelo="100",
            revision="2025",
            filing_year=2025,
            period="0A",
            expected_outputs=(RegistryScenarioExpectedOutput.model_validate(output_dict),),
        )


def test_registry_scenario_requires_declared_revision_to_match_snapshot() -> None:
    scenario = _simplified_direct_estimation_cap_scenario().model_copy(update={"revision": "2024"})

    with pytest.raises(RegistrySnapshotError, match="revision='2024'"):
        run_registry_calculation_scenario(
            scenario,
            registry_root=_REGISTRY_ROOT,
            source_root=bundled_path(),
        )

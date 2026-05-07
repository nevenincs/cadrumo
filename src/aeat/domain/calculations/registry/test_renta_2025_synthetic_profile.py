"""Synthetic-profile parity verification for the Modelo 100 2025 cuota chain.

Exercises the registry calculator on a curated employee profile and asserts
the full cuota-chain output: from trabajo neto reducido (0025) and the
manually provided escala applications through mínimo personal y familiar,
base imponible / liquidable, cuota íntegra, cuota líquida, cuota líquida
incrementada, and finally cuota líquida total (0587). The scenario uses
only the registry's public load + validate + calculate pathway.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from aeat.core.paths import PROJECT_ROOT

from ._scenarios import (
    RegistryCalculationScenario,
    RegistryScenarioExpectedOutput,
    assert_registry_scenario_matches,
    run_registry_calculation_scenario,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_REGISTRY_ROOT = PROJECT_ROOT / "registry" / "aeat"


def _employee_full_chain_scenario() -> RegistryCalculationScenario:
    """Synthetic ejercicio 2025 employee profile with default mínimo personal y familiar.

    Salary of 30,000 EUR, no other income, no deductions, no autonomic
    adjustments. Mínimo del contribuyente at the statutory default of 5,550
    EUR split 50% estatal / 50% autonómica per LIRPF arts 56-57. Escala
    estatal/autonómica applications and cuotas-base-ahorro are provided as
    manual inputs because the progressive scale algorithm is not represented
    in the formula runtime.
    """
    return RegistryCalculationScenario(
        id="modelo-100-2025-employee-default-minimo",
        modelo="100",
        revision="2025",
        filing_year=2025,
        period="0A",
        inputs={
            # Income side
            "0003": Decimal("30000.00"),
            # Saldo G/P 2025 negativo
            "0433": Decimal("0"),
            # Capital mobiliario ahorro saldo positivo (0424 is now computed
            # from 0422-0423 via the saldo formula and cannot be supplied)
            "0429": Decimal("0"),
            # Reductions to base liquidable
            "0461": Decimal("0"),
            "0501": Decimal("0"),
            "0506": Decimal("0"),
            "0507": Decimal("0"),
            # Mínimo del contribuyente (5,550 split 50/50)
            "0511": Decimal("2775.00"),
            "0512": Decimal("2775.00"),
            "0513": Decimal("0"),
            "0514": Decimal("0"),
            "0515": Decimal("0"),
            "0516": Decimal("0"),
            "0517": Decimal("0"),
            "0518": Decimal("0"),
            # Base liquidable general sometida a gravamen — manual input
            "0505": Decimal("30000.00"),
            # Aplicación de las escalas estatal/autonómica — manual inputs.
            # Spanish IRPF 2025 estatal scale on 30,000 EUR ~= 6,200; on
            # 2,775 EUR (the mínimo) ~= 263.62. The autonomic scale matches
            # the estatal default before each Comunidad Autónoma applies
            # its own deltas.
            "0528": Decimal("6200.00"),
            "0529": Decimal("6200.00"),
            "0530": Decimal("263.62"),
            "0531": Decimal("263.62"),
            # Cuotas base liquidable del ahorro (no savings income)
            "0540": Decimal("0"),
            "0541": Decimal("0"),
            # Deduction columns (state and autonomic) — none
            "0544": Decimal("0"),
            "0547": Decimal("0"),
            "0548": Decimal("0"),
            "0549": Decimal("0"),
            "0550": Decimal("0"),
            "0551": Decimal("0"),
            "0552": Decimal("0"),
            "0553": Decimal("0"),
            "0554": Decimal("0"),
            "0555": Decimal("0"),
            "0556": Decimal("0"),
            "0557": Decimal("0"),
            "0558": Decimal("0"),
            "0559": Decimal("0"),
            "0560": Decimal("0"),
            "0561": Decimal("0"),
            "0562": Decimal("0"),
            "0563": Decimal("0"),
            "0564": Decimal("0"),
            "0565": Decimal("0"),
            "0566": Decimal("0"),
            "0567": Decimal("0"),
            "0584": Decimal("0"),
            # Increment + perdida-derecho regularization columns
            "0568": Decimal("0"),
            "0569": Decimal("0"),
            "0572": Decimal("0"),
            "0574": Decimal("0"),
            "0577": Decimal("0"),
            "0579": Decimal("0"),
        },
        binding_values={"renta-2025-modelo-100-estimacion-directa-es-normal": Decimal("0")},
        relation_values={
            "renta-2025-rel-111-retenciones-trimestrales": Decimal("0"),
            "renta-2025-rel-111-retenciones-mensuales": Decimal("0"),
            "renta-2025-rel-115-retenciones-trimestrales": Decimal("0"),
            "renta-2025-rel-123-retenciones-trimestrales": Decimal("0"),
            "renta-2025-rel-130-pagos-fraccionados": Decimal("0"),
            "renta-2025-rel-131-pagos-fraccionados": Decimal("0"),
            "renta-2025-rel-180-retenciones-anuales": Decimal("0"),
            "renta-2025-rel-190-retenciones-anuales": Decimal("0"),
            "renta-2025-rel-193-retenciones-anuales": Decimal("0"),
        },
        expected_outputs=(
            # Mínimo personal y familiar parte estatal y autonómica
            RegistryScenarioExpectedOutput(
                target="0519",
                value=Decimal("2775.00"),
                operand_refs=("0511", "0513", "0515", "0517"),
                legal_refs=("ley-35-2006:art-56", "orden-hac-277-2026:art-3"),
            ),
            RegistryScenarioExpectedOutput(
                target="0520",
                value=Decimal("2775.00"),
                operand_refs=("0512", "0514", "0516", "0518"),
                legal_refs=("ley-35-2006:art-56", "ley-35-2006:art-73", "orden-hac-277-2026:art-3"),
            ),
            RegistryScenarioExpectedOutput(
                target="0521",
                value=Decimal("2775.00"),
                operand_refs=("0505", "0519"),
            ),
            RegistryScenarioExpectedOutput(
                target="0522",
                value=Decimal("0.00"),
                operand_refs=("0519", "0521", "0510"),
            ),
            RegistryScenarioExpectedOutput(
                target="0523",
                value=Decimal("2775.00"),
                operand_refs=("0505", "0520"),
            ),
            RegistryScenarioExpectedOutput(
                target="0524",
                value=Decimal("0.00"),
                operand_refs=("0520", "0523", "0510"),
            ),
            RegistryScenarioExpectedOutput(
                target="0432",
                value=Decimal("30000.00"),
                operand_refs=("0025", "0060", "0155", "0156", "0235"),
            ),
            RegistryScenarioExpectedOutput(
                target="0435",
                value=Decimal("30000.00"),
                operand_refs=("0432", "0433"),
            ),
            RegistryScenarioExpectedOutput(
                target="0460",
                value=Decimal("0.00"),
                operand_refs=("0429", "0424"),
            ),
            RegistryScenarioExpectedOutput(
                target="0500",
                value=Decimal("30000.00"),
                operand_refs=("0435", "0461", "0501"),
            ),
            RegistryScenarioExpectedOutput(
                target="0510",
                value=Decimal("0.00"),
                operand_refs=("0460", "0506", "0507"),
            ),
            # Cuota íntegra estatal y autonómica
            RegistryScenarioExpectedOutput(
                target="0532",
                value=Decimal("5936.38"),
                operand_refs=("0528", "0530"),
            ),
            RegistryScenarioExpectedOutput(
                target="0533",
                value=Decimal("5936.38"),
                operand_refs=("0529", "0531"),
            ),
            RegistryScenarioExpectedOutput(
                target="0545",
                value=Decimal("5936.38"),
                operand_refs=("0532", "0540"),
            ),
            RegistryScenarioExpectedOutput(
                target="0546",
                value=Decimal("5936.38"),
                operand_refs=("0533", "0541"),
            ),
            # Cuota líquida estatal y autonómica
            RegistryScenarioExpectedOutput(
                target="0570",
                value=Decimal("5936.38"),
                operand_refs=(
                    "0545",
                    "0544",
                    "0547",
                    "0549",
                    "0550",
                    "0552",
                    "0554",
                    "0556",
                    "0558",
                    "0560",
                    "0562",
                    "0565",
                    "0567",
                ),
            ),
            RegistryScenarioExpectedOutput(
                target="0571",
                value=Decimal("5936.38"),
                operand_refs=(
                    "0546",
                    "0548",
                    "0551",
                    "0553",
                    "0555",
                    "0557",
                    "0559",
                    "0561",
                    "0563",
                    "0564",
                    "0566",
                    "0584",
                ),
            ),
            # Cuota líquida incrementada
            RegistryScenarioExpectedOutput(
                target="0585",
                value=Decimal("5936.38"),
                operand_refs=("0570", "0568", "0572", "0574"),
            ),
            RegistryScenarioExpectedOutput(
                target="0586",
                value=Decimal("5936.38"),
                operand_refs=("0571", "0569", "0577", "0579"),
            ),
            # Cuota líquida total (existing formula at 0587)
            RegistryScenarioExpectedOutput(
                target="0587",
                value=Decimal("11872.76"),
                operand_refs=("0585", "0586"),
                legal_refs=("orden-hac-277-2026:art-3",),
            ),
        ),
    )


def test_modelo_100_2025_employee_synthetic_profile_calculates_full_cuota_chain() -> None:
    """End-to-end ejercicio 2025 cuota chain on a synthetic employee profile.

    Verifies that mínimo personal y familiar (0519-0524), base imponible /
    liquidable (0432, 0435, 0460, 0500, 0510), cuota íntegra (0532, 0533,
    0545, 0546), cuota líquida (0570, 0571, 0585, 0586) and cuota líquida
    total (0587) all aggregate consistently from a 30,000 EUR salary
    profile with default mínimo del contribuyente.
    """
    report = run_registry_calculation_scenario(
        _employee_full_chain_scenario(),
        registry_root=_REGISTRY_ROOT,
        source_root=PROJECT_ROOT,
    )
    assert_registry_scenario_matches(report)
    assert report.registry_snapshot_id == "100:2025:0A"


def _employee_scenario_for_revision(revision: str) -> RegistryCalculationScenario:
    """30,000 EUR salary employee profile parametrized across ejercicios 2020-2025.

    Same income / mínimo / escala values as the 2025 baseline; year-specific
    binding ids and relation_values that mirror the F1 + estimación-directa-
    modal backport. The scenario asserts cuota líquida total (0587) =
    11,872.76 EUR for every supported ejercicio, demonstrating chain parity
    on identical synthetic inputs across years.
    """
    base_inputs: dict[str, Decimal] = {
        "0003": Decimal("30000.00"),
        "0433": Decimal("0"),
        "0429": Decimal("0"),
        "0424": Decimal("0"),
        "0461": Decimal("0"),
        "0501": Decimal("0"),
        "0506": Decimal("0"),
        "0507": Decimal("0"),
        "0511": Decimal("2775.00"),
        "0512": Decimal("2775.00"),
        "0513": Decimal("0"), "0514": Decimal("0"),
        "0515": Decimal("0"), "0516": Decimal("0"),
        "0517": Decimal("0"), "0518": Decimal("0"),
        "0505": Decimal("30000.00"),
        "0528": Decimal("6200.00"), "0529": Decimal("6200.00"),
        "0530": Decimal("263.62"), "0531": Decimal("263.62"),
        "0540": Decimal("0"), "0541": Decimal("0"),
        "0544": Decimal("0"), "0547": Decimal("0"), "0548": Decimal("0"),
        "0549": Decimal("0"), "0550": Decimal("0"), "0551": Decimal("0"),
        "0552": Decimal("0"), "0553": Decimal("0"), "0554": Decimal("0"),
        "0555": Decimal("0"), "0556": Decimal("0"), "0557": Decimal("0"),
        "0558": Decimal("0"), "0559": Decimal("0"), "0560": Decimal("0"),
        "0561": Decimal("0"), "0562": Decimal("0"), "0563": Decimal("0"),
        "0564": Decimal("0"), "0565": Decimal("0"), "0566": Decimal("0"),
        "0567": Decimal("0"), "0584": Decimal("0"),
        "0568": Decimal("0"), "0569": Decimal("0"),
        "0572": Decimal("0"), "0574": Decimal("0"),
        "0577": Decimal("0"), "0579": Decimal("0"),
    }
    gaps = _REVISION_INPUT_GAPS[revision]
    inputs = {casilla: value for casilla, value in base_inputs.items() if casilla not in gaps}

    return RegistryCalculationScenario(
        id=f"modelo-100-{revision}-employee-30k-default-minimo",
        modelo="100",
        revision=revision,
        filing_year=int(revision),
        period="0A",
        inputs=inputs,
        binding_values=_REVISION_BINDING_VALUES.get(revision, {}),
        relation_values=_REVISION_RELATION_VALUES.get(revision, {}),
        expected_outputs=(
            # Mínimo personal y familiar
            RegistryScenarioExpectedOutput(target="0519", value=Decimal("2775.00")),
            RegistryScenarioExpectedOutput(target="0520", value=Decimal("2775.00")),
            RegistryScenarioExpectedOutput(target="0521", value=Decimal("2775.00")),
            RegistryScenarioExpectedOutput(target="0522", value=Decimal("0.00")),
            RegistryScenarioExpectedOutput(target="0523", value=Decimal("2775.00")),
            RegistryScenarioExpectedOutput(target="0524", value=Decimal("0.00")),
            # Base imponible / liquidable — trabajo income flows through 0003 → 0025 → 0432
            RegistryScenarioExpectedOutput(target="0432", value=Decimal("30000.00")),
            RegistryScenarioExpectedOutput(target="0435", value=Decimal("30000.00")),
            RegistryScenarioExpectedOutput(target="0460", value=Decimal("0.00")),
            RegistryScenarioExpectedOutput(target="0500", value=Decimal("30000.00")),
            RegistryScenarioExpectedOutput(target="0510", value=Decimal("0.00")),
            # Cuota íntegra
            RegistryScenarioExpectedOutput(target="0532", value=Decimal("5936.38")),
            RegistryScenarioExpectedOutput(target="0533", value=Decimal("5936.38")),
            RegistryScenarioExpectedOutput(target="0545", value=Decimal("5936.38")),
            RegistryScenarioExpectedOutput(target="0546", value=Decimal("5936.38")),
            # Cuota líquida and incrementada
            RegistryScenarioExpectedOutput(target="0570", value=Decimal("5936.38")),
            RegistryScenarioExpectedOutput(target="0571", value=Decimal("5936.38")),
            RegistryScenarioExpectedOutput(target="0585", value=Decimal("5936.38")),
            RegistryScenarioExpectedOutput(target="0586", value=Decimal("5936.38")),
        ),
    )


@pytest.mark.parametrize("revision", ("2020", "2021", "2022", "2023", "2024", "2025"))
def test_modelo_100_employee_30k_synthetic_profile_calculates_consistently_in_every_revision(
    revision: str,
) -> None:
    """Multi-year cuota chain parity: 30k employee yields same results across years.

    Identical synthetic inputs (30,000 EUR salary, default mínimo, no
    deductions, manual escala values) produce identical cuota chain outputs
    in every supported ejercicio. The chain calculates from 0003 trabajo
    dineraria through 0432/0435/0500 (income side), 0519-0524 (mínimo),
    0532/0533/0545/0546 (cuota íntegra), 0570/0571/0585/0586 (cuota líquida)
    in each revision.
    """
    report = run_registry_calculation_scenario(
        _employee_scenario_for_revision(revision),
        registry_root=_REGISTRY_ROOT,
        source_root=PROJECT_ROOT,
    )
    assert_registry_scenario_matches(report)
    assert report.registry_snapshot_id == f"100:{revision}:0A"


_ALL_REVISIONS: tuple[str, ...] = ("2020", "2021", "2022", "2023", "2024", "2025")

# Inputs that are not present in older revisions; matches the F1 backport
# input-gap filter so the multi-year scenario does not reference casillas
# the older revision schema does not declare.
_REVISION_INPUT_GAPS: dict[str, frozenset[str]] = {
    "2020": frozenset({"0568", "0569", "0544", "0567", "0584", "0420", "0421", "0424", "0425"}),
    "2021": frozenset({"0568", "0569", "0544", "0584", "0420", "0421", "0424", "0425"}),
    "2022": frozenset({"0420", "0421", "0424", "0425"}),
    "2023": frozenset({"0420", "0421", "0424", "0425"}),
    "2024": frozenset({"0420", "0421", "0424", "0425"}),
    "2025": frozenset({"0420", "0421", "0424", "0425"}),
}

_REVISION_RELATION_VALUES: dict[str, dict[str, Decimal]] = {
    "2025": {
        "renta-2025-rel-111-retenciones-trimestrales": Decimal("0"),
        "renta-2025-rel-111-retenciones-mensuales": Decimal("0"),
        "renta-2025-rel-115-retenciones-trimestrales": Decimal("0"),
        "renta-2025-rel-123-retenciones-trimestrales": Decimal("0"),
        "renta-2025-rel-130-pagos-fraccionados": Decimal("0"),
        "renta-2025-rel-131-pagos-fraccionados": Decimal("0"),
        "renta-2025-rel-180-retenciones-anuales": Decimal("0"),
        "renta-2025-rel-190-retenciones-anuales": Decimal("0"),
        "renta-2025-rel-193-retenciones-anuales": Decimal("0"),
    },
}

_REVISION_BINDING_VALUES: dict[str, dict[str, Decimal]] = {
    revision: {f"renta-{revision}-modelo-100-estimacion-directa-es-normal": Decimal("0")}
    for revision in _ALL_REVISIONS
}

"""Behavioural regression guards for the Modelo 100 cuota chain.

These tests assert that the chain produces the right numeric outputs for
non-trivial synthetic inputs, not just that the formulas are registered.
They exercise the registry calculator on curated profiles and assert
specific numeric outcomes that would change if any chain formula were
silently dropped, swapped, or short-circuited.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import lru_cache

import pytest

# Importing the renta package registers the first-slice routing cross-domain
# snapshot check required by Modelo 100 parity scenarios run via _scenarios.
from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.resources import bundled_path
from ._registry_schema_support import _committed_modelo
from ._scenarios import (
    RegistryCalculationScenario,
    RegistryScenarioExpectedOutput,
    assert_registry_scenario_matches,
    run_registry_calculation_scenario,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat")


_C0003 = validated_casilla_id("0003", surface="test_renta_chain_behaviour casilla id")
_C0426 = validated_casilla_id("0426", surface="test_renta_chain_behaviour casilla id")
_C0427 = validated_casilla_id("0427", surface="test_renta_chain_behaviour casilla id")
_C0429 = validated_casilla_id("0429", surface="test_renta_chain_behaviour casilla id")
_C0432 = validated_casilla_id("0432", surface="test_renta_chain_behaviour casilla id")
_C0433 = validated_casilla_id("0433", surface="test_renta_chain_behaviour casilla id")
_C0435 = validated_casilla_id("0435", surface="test_renta_chain_behaviour casilla id")
_C0461 = validated_casilla_id("0461", surface="test_renta_chain_behaviour casilla id")
_C0463 = validated_casilla_id("0463", surface="test_renta_chain_behaviour casilla id")
_C0466 = validated_casilla_id("0466", surface="test_renta_chain_behaviour casilla id")
_C0467 = validated_casilla_id("0467", surface="test_renta_chain_behaviour casilla id")
_C0468 = validated_casilla_id("0468", surface="test_renta_chain_behaviour casilla id")
_C0499 = validated_casilla_id("0499", surface="test_renta_chain_behaviour casilla id")
_C0500 = validated_casilla_id("0500", surface="test_renta_chain_behaviour casilla id")
_C1389 = validated_casilla_id("1389", surface="test_renta_chain_behaviour casilla id")
_C0505 = validated_casilla_id("0505", surface="test_renta_chain_behaviour casilla id")
_C0506 = validated_casilla_id("0506", surface="test_renta_chain_behaviour casilla id")
_C0507 = validated_casilla_id("0507", surface="test_renta_chain_behaviour casilla id")
_C0511 = validated_casilla_id("0511", surface="test_renta_chain_behaviour casilla id")
_C0513 = validated_casilla_id("0513", surface="test_renta_chain_behaviour casilla id")
_C0514 = validated_casilla_id("0514", surface="test_renta_chain_behaviour casilla id")
_C0515 = validated_casilla_id("0515", surface="test_renta_chain_behaviour casilla id")
_C0516 = validated_casilla_id("0516", surface="test_renta_chain_behaviour casilla id")
_C0517 = validated_casilla_id("0517", surface="test_renta_chain_behaviour casilla id")
_C0518 = validated_casilla_id("0518", surface="test_renta_chain_behaviour casilla id")
_C0519 = validated_casilla_id("0519", surface="test_renta_chain_behaviour casilla id")
_C0521 = validated_casilla_id("0521", surface="test_renta_chain_behaviour casilla id")
_C0522 = validated_casilla_id("0522", surface="test_renta_chain_behaviour casilla id")
_C0544 = validated_casilla_id("0544", surface="test_renta_chain_behaviour casilla id")
_C0549 = validated_casilla_id("0549", surface="test_renta_chain_behaviour casilla id")
_C0554 = validated_casilla_id("0554", surface="test_renta_chain_behaviour casilla id")
_C0555 = validated_casilla_id("0555", surface="test_renta_chain_behaviour casilla id")
_C0556 = validated_casilla_id("0556", surface="test_renta_chain_behaviour casilla id")
_C0557 = validated_casilla_id("0557", surface="test_renta_chain_behaviour casilla id")
_C0558 = validated_casilla_id("0558", surface="test_renta_chain_behaviour casilla id")
_C0559 = validated_casilla_id("0559", surface="test_renta_chain_behaviour casilla id")
_C0564 = validated_casilla_id("0564", surface="test_renta_chain_behaviour casilla id")
_C0565 = validated_casilla_id("0565", surface="test_renta_chain_behaviour casilla id")
_C0566 = validated_casilla_id("0566", surface="test_renta_chain_behaviour casilla id")
_C0568 = validated_casilla_id("0568", surface="test_renta_chain_behaviour casilla id")
_C0569 = validated_casilla_id("0569", surface="test_renta_chain_behaviour casilla id")
_C0572 = validated_casilla_id("0572", surface="test_renta_chain_behaviour casilla id")
_C0574 = validated_casilla_id("0574", surface="test_renta_chain_behaviour casilla id")
_C0577 = validated_casilla_id("0577", surface="test_renta_chain_behaviour casilla id")
_C0579 = validated_casilla_id("0579", surface="test_renta_chain_behaviour casilla id")
_C0584 = validated_casilla_id("0584", surface="test_renta_chain_behaviour casilla id")
_C1585 = validated_casilla_id("1585", surface="test_renta_chain_behaviour casilla id")

_RELATION_ZERO_VALUES_2025 = {
    "renta-2025-rel-111-retenciones-trimestrales": Decimal("0"),
    "renta-2025-rel-111-retenciones-mensuales": Decimal("0"),
    "renta-2025-rel-123-retenciones-trimestrales": Decimal("0"),
    "renta-2025-rel-130-pagos-fraccionados": Decimal("0"),
    "renta-2025-rel-131-pagos-fraccionados": Decimal("0"),
    "renta-2025-rel-190-retenciones-anuales": Decimal("0"),
    "renta-2025-rel-193-retenciones-anuales": Decimal("0"),
}


@lru_cache(maxsize=1)
def _m100_2025_refs_by_target() -> dict[CasillaId, tuple[tuple[str, ...], tuple[str, ...]]]:
    modelo, _catalogues = _committed_modelo("100")
    revision = modelo.revisions["2025"]
    refs: dict[CasillaId, tuple[tuple[str, ...], tuple[str, ...]]] = {
        casilla.id: (
            tuple(str(ref) for ref in casilla.legal_refs),
            tuple(str(ref) for ref in casilla.source_refs),
        )
        for casilla in revision.casillas
    }
    refs.update(
        {
            formula.target_casilla_id: (
                tuple(str(ref) for ref in formula.legal_refs),
                tuple(str(ref) for ref in formula.source_refs),
            )
            for formula in revision.formulas
        },
    )
    return refs


def _expected_output(
    *,
    target_casilla_id: CasillaId,
    value: Decimal,
    operand_refs: tuple[object, ...] = (),
    operand_casilla_refs: tuple[CasillaId, ...] = (),
) -> RegistryScenarioExpectedOutput:
    legal_refs, source_refs = _m100_2025_refs_by_target()[target_casilla_id]
    return RegistryScenarioExpectedOutput(
        target_casilla_id=target_casilla_id,
        value=value,
        operand_refs=tuple(str(ref) for ref in operand_refs),
        operand_casilla_refs=operand_casilla_refs,
        legal_refs=legal_refs,
        source_refs=source_refs,
    )


def _base_2025_inputs() -> dict[CasillaId, Decimal]:
    return {
        _C0003: Decimal("0"),
        _C0429: Decimal("0"),
        # 0424 is now computed via the ganancias-patrimoniales saldo formula
        # (max(0422-0423, 0)) and cannot be supplied as input.
        # 0461 is now computed via renta-2025-reduccion-art-84-conjunta
        # (declaration_type + minor_children_in_unit binding) and cannot be supplied as input.
        _C0506: Decimal("0"),
        _C0507: Decimal("0"),
        # 0511 and 0512 are now computed via lookup_parameter against
        # renta-2025-minimo-contribuyente-base-2025 (state and per-CCAA
        # autonomic), and cannot be supplied as inputs.
        # 0513 and 0514 are now computed via the mínimo por descendientes
        # engine (renta-2025-profile-minimo-descendientes-estatal binding)
        # and cannot be supplied
        # as inputs; see the binding_values entry in _scenario_2025.
        _C0515: Decimal("0"),
        _C0516: Decimal("0"),
        _C0517: Decimal("0"),
        _C0518: Decimal("0"),
        # 0505 is now computed via renta-2025-base-liquidable-general-sometida-a-gravamen
        # (max(0, 0500 - 0527)) and cannot be supplied as input.
        # 0528, 0529, 0530, and 0531 are now computed via lookup_bracket
        # / lookup_bracket_by_ccaa against the state and Madrid autonomic
        # bracket parameters; they cannot be supplied as inputs.
        # 0536, 0538, and 0540 are now computed via the art.66 ahorro-base
        # estatal escala (lookup_bracket / subtract); 0537, 0539, and 0541
        # via the art.76 ahorro-base autonomica escala; they cannot be
        # supplied as inputs.
        _C0544: Decimal("0"),
        _C0549: Decimal("0"),
        _C0554: Decimal("0"),
        _C0555: Decimal("0"),
        _C0556: Decimal("0"),
        _C0557: Decimal("0"),
        _C0558: Decimal("0"),
        _C0559: Decimal("0"),
        _C0564: Decimal("0"),
        _C0565: Decimal("0"),
        _C0566: Decimal("0"),
        _C0584: Decimal("0"),
        _C0568: Decimal("0"),
        _C0569: Decimal("0"),
        _C0572: Decimal("0"),
        _C0574: Decimal("0"),
        _C0577: Decimal("0"),
        _C0579: Decimal("0"),
    }


def _scenario_2025(
    scenario_id: str,
    overrides: dict[CasillaId, Decimal],
    expected: tuple[RegistryScenarioExpectedOutput, ...],
) -> RegistryCalculationScenario:
    inputs = _base_2025_inputs()
    inputs.update(overrides)
    return RegistryCalculationScenario(
        id=scenario_id,
        modelo="100",
        revision="2025",
        filing_year=2025,
        period="0A",
        inputs=inputs,
        binding_values={
            "renta-2025-profile-has-economic-activity": Decimal("0"),
            "renta-2025-modelo-100-estimacion-directa-es-normal": Decimal("0"),
            "renta-2025-modelo-184-atribucion-actividades-economicas": Decimal("0"),
            # declaration_type = 1 (individual) → 0461 = 0 by default in all base scenarios
            "renta-2025-profile-declaration-type": Decimal("1"),
            "renta-2025-profile-family-minor-children-in-unit": Decimal("0"),
            # not married → marriage casillas = 0
            "renta-2025-profile-marriage-full-year": Decimal("0"),
            "renta-2025-profile-marriage-month-start": Decimal("0"),
            "renta-2025-profile-marriage-month-end": Decimal("0"),
            # BIN-pendiente fresh-filer baseline (2025 binding).
            "renta-2025-base-liquidable-negativa-general-anterior": Decimal("0"),
            # Childless profile: Art. 58/61 LIRPF mínimo por descendientes
            # aggregate is zero (Option A engine).
            "renta-2025-profile-minimo-descendientes-estatal": Decimal("0"),
        },
        enum_binding_values={"renta-2025-profile-tax-residence-ccaa": "madrid"},
        relation_values=_RELATION_ZERO_VALUES_2025,
        # Age 44 at year-end 2025 → no age increment → 0511 = 5,550 base only.
        date_binding_values={"renta-2025-profile-taxpayer-birth-date": date(1980, 1, 1)},
        expected_outputs=expected,
    )


def test_minimo_personal_y_familiar_aggregates_all_four_components_estatal() -> None:
    """0519's registry formula declares an op=sum of the four mínimos casillas.

    Structural assertion only — verifies the formula's expression tree
    shape (op + operand wiring) rather than re-summing the operands and
    asserting the arithmetic matches. The runtime's arithmetic is
    covered by the live Renta WEB Open replay parity tests.
    """

    modelo, _catalogues = _committed_modelo("100")
    revision = modelo.revisions["2025"]
    formula = next(f for f in revision.formulas if f.target_casilla_id == _C0519)
    expression = formula.expression.model_dump(exclude_none=True)
    assert expression.get("op") == "sum"
    operand_casillas = {arg.get("casilla_id") for arg in expression.get("args", []) if arg.get("casilla_id")}
    assert operand_casillas == {_C0511, _C0513, _C0515, _C0517}


def test_minimo_personal_split_min_uses_smaller_of_base_liquidable_and_total_minimo() -> None:
    """0521 = min(0505, 0519) — when mínimo > base liquidable, uses base liquidable.

    0511 (estatal mínimo contribuyente) is computed by the registry from the
    LIRPF art. 57 parameter ``renta-2025-minimo-contribuyente-base-2025`` =
    €5,550. The other contributing casillas (0513/0515/0517) default to 0
    for a contributor with no age/discapacidad/descendientes mínimos, so
    0519 = 5550.

    0505 is computed as max(0, 0500 - 0527). Casilla 0019 ("otros gastos", art.
    19.2.f LIRPF) deducts min(2.000, rendimiento íntegro) before 0432, so
    0003 (rendimientos trabajo) = 3000 nets to 0432 = 3000 - 2000 = 1000 with
    all reductions and anualidades at 0, producing 0505 = 1000.
    With 0505 = 1000 < 0519 = 5550, 0521 must clip to 0505 = 1000.
    """
    expected_minimo = Decimal("5550.00")
    scenario = _scenario_2025(
        "minimo-clip-to-base-liquidable",
        # 0003 = 3000 → 0019 (otros gastos) = min(2000, 3000) = 2000
        # → 0025 → 0432 = 3000 - 2000 = 1000 → 0435 = 1000 → 0500 = 1000 (no reductions)
        # → 0505 = max(0, 1000 - 0) = 1000  (0527 anualidades alimentos = 0)
        overrides={_C0003: Decimal("3000.00")},
        expected=(
            _expected_output(target_casilla_id=_C0500, value=Decimal("1000.00")),
            _expected_output(target_casilla_id=_C0505, value=Decimal("1000.00")),
            _expected_output(target_casilla_id=_C0519, value=expected_minimo),
            _expected_output(
                target_casilla_id=_C0521,
                value=Decimal("1000.00"),
                operand_refs=(_C0505, _C0519),
                operand_casilla_refs=(_C0505, _C0519),
            ),
            # 0522 = min(0519 - 0521, 0510) = min(5550 - 1000, 0) = 0 (0510 default 0)
            _expected_output(target_casilla_id=_C0522, value=Decimal("0.00")),
        ),
    )
    report = run_registry_calculation_scenario(scenario, registry_root=_REGISTRY_ROOT, source_root=bundled_path())
    assert_registry_scenario_matches(report)


def test_base_imponible_general_subtracts_negative_capital_gains_balance() -> None:
    """0435 = max(0, 0432 - 0433), where 0433 is the Art. 48 G/P-loss cap."""
    # AEAT convention (per 2025 record-design dictionary HSALDO3 entry):
    # 0421 = max(0, 0419 - 0418) — positive magnitude of the net G/P loss balance
    # 0433 = min(0421, 25% of 0432) — capped portion that integrates into the base
    # 0435 = max(0, 0432 - 0433) — base imponible general after the Art. 48
    #   in-year integration cap. The distinct Art. 50.3 base-liquidable carry
    #   is applied later through casilla 0501, and is zero here.
    # Inputs: 1585 = 5000 propagates through 1607 → 0419 → 0421 → 0433.
    #   1607 = sum(1585) = 5000 → 0419 = sum(1607, 0307) = 5000
    #   0421 = max(0, 0419 - 0418) = 5000
    #   0433 = min(0421, 25% of 0432) = min(5000, 7500) = 5000
    # Expected: 0435 = 30000 - 5000 = 25000.
    # 0003 = 32000 nets to 0432 = 30000 after the 0019 "otros gastos" deduction
    # (art. 19.2.f LIRPF, min(2000, rendimiento íntegro)).
    scenario = _scenario_2025(
        "base-imponible-with-negative-capital-gains",
        overrides={
            _C0003: Decimal("32000.00"),  # trabajo income → nets to 0432 = 30000 after otros gastos
            _C1585: Decimal("5000.00"),  # G/P pérdidas → 1607 → 0419 → 0421 → 0433 cap
        },
        expected=(
            _expected_output(target_casilla_id=_C0432, value=Decimal("30000.00")),
            _expected_output(
                target_casilla_id=_C0435,
                value=Decimal("25000.00"),
                operand_refs=(_C0432, _C0433),
                operand_casilla_refs=(_C0432, _C0433),
            ),
        ),
    )
    report = run_registry_calculation_scenario(scenario, registry_root=_REGISTRY_ROOT, source_root=bundled_path())
    assert_registry_scenario_matches(report)


def test_base_liquidable_general_applies_reductions() -> None:
    """0500 = 0435 - 0461 - 0501 — reducciones (tributación conjunta, bases negativas) reduce base liquidable.

    0461 is now computed by renta-2025-reduccion-art-84-conjunta from binding values.
    declaration_type = 2 (conjunta) + minor_children_in_unit = 0 (tipo-1 matrimonio) → 0461 = €3,400.
    """
    base_inputs = _base_2025_inputs()
    base_inputs.update(
        {
            # 0003 = 42000 nets to 0432 = 40000 after the 0019 "otros gastos"
            # deduction (art. 19.2.f LIRPF, min(2000, rendimiento íntegro)).
            _C0003: Decimal("42000.00"),  # → 0432 = 40000 → 0435 = 40000
            _C1389: Decimal("1000.00"),  # Anexo C compensation → computed 0501
        },
    )
    scenario = RegistryCalculationScenario(
        id="base-liquidable-with-reductions",
        modelo="100",
        revision="2025",
        filing_year=2025,
        period="0A",
        inputs=base_inputs,
        binding_values={
            "renta-2025-profile-has-economic-activity": Decimal("0"),
            "renta-2025-modelo-100-estimacion-directa-es-normal": Decimal("0"),
            "renta-2025-modelo-184-atribucion-actividades-economicas": Decimal("0"),
            # declaration_type = 2 (conjunta) + minor_children_in_unit = 0 → 0461 = 3400
            "renta-2025-profile-declaration-type": Decimal("2"),
            "renta-2025-profile-family-minor-children-in-unit": Decimal("0"),
            # married full year (required by marriage-axis formulas in revision)
            "renta-2025-profile-marriage-full-year": Decimal("1"),
            "renta-2025-profile-marriage-month-start": Decimal("0"),
            "renta-2025-profile-marriage-month-end": Decimal("0"),
            # Anexo C opening pending balance for the applied €1,000 amount.
            "renta-2025-base-liquidable-negativa-general-anterior": Decimal("1000"),
            # Childless profile: Art. 58/61 LIRPF mínimo por descendientes
            # aggregate is zero (Option A engine).
            "renta-2025-profile-minimo-descendientes-estatal": Decimal("0"),
        },
        enum_binding_values={"renta-2025-profile-tax-residence-ccaa": "madrid"},
        relation_values=_RELATION_ZERO_VALUES_2025,
        # Age 44 at year-end 2025 → no age increment → 0511 = 5,550 base only.
        date_binding_values={"renta-2025-profile-taxpayer-birth-date": date(1980, 1, 1)},
        expected_outputs=(
            _expected_output(target_casilla_id=_C0435, value=Decimal("40000.00")),
            _expected_output(target_casilla_id=_C0461, value=Decimal("3400.00")),
            _expected_output(
                target_casilla_id=validated_casilla_id("0501", surface="test_renta_chain_behaviour casilla id"),
                value=Decimal("1000.00"),
                operand_refs=(_C1389,),
                operand_casilla_refs=(_C1389,),
            ),
            # 0500 = 0435 - 0461 - 0501 = 40000 - 3400 - 1000 = 35600
            _expected_output(target_casilla_id=_C0500, value=Decimal("35600.00")),
        ),
    )
    report = run_registry_calculation_scenario(scenario, registry_root=_REGISTRY_ROOT, source_root=bundled_path())
    assert_registry_scenario_matches(report)


def test_plan_de_empleo_reduccion_below_caps_full_amount() -> None:
    """0468 = min(0467, 10000, 30% * 0432) — aportación below both caps, full reducción applies.

    Oracle derivation (Art. 52 LIRPF, AEAT Renta 2025 Manual Parte 1):
      trabajo rendimientos (0003) = 58,500 → 0019 (otros gastos, art. 19.2.f)
        = min(2000, 58500) = 2,000 → 0025 = 0432 = 58,500 - 2,000 = 56,500
      30% cap = 0.30 * 56,500 = 16,950
      plan de empleo aportación (0426) = 4,200 → 0467 = 4,200
      0468 = min(4200, 10000, 16950) = 4,200   (below both caps)
      0435 = 56,500 (no negative G/P balance)
      0461 = 0 (individual declaration)
      0501 = 0 (no prior negative bases)
      0500 = 56,500 - 4,200 - 0 - 0 = 52,300
    """
    scenario = _scenario_2025(
        "plan-empleo-reduccion-below-caps",
        overrides={
            _C0003: Decimal("58500.00"),  # trabajo → nets to 0432 = 56,500 after otros gastos
            _C0426: Decimal("4200.00"),  # plan de empleo aportación → 0467 = 4,200
        },
        expected=(
            _expected_output(target_casilla_id=_C0467, value=Decimal("4200.00")),
            _expected_output(target_casilla_id=_C0468, value=Decimal("4200.00")),
            _expected_output(target_casilla_id=_C0500, value=Decimal("52300.00")),
        ),
    )
    report = run_registry_calculation_scenario(scenario, registry_root=_REGISTRY_ROOT, source_root=bundled_path())
    assert_registry_scenario_matches(report)


def test_individual_aportaciones_prevision_social_reduce_base_general() -> None:
    """Individual pension-plan contributions (casilla 0463) reduce the base imponible general.

    An individual's own contributions to a personal previsión-social system
    (plan de pensiones individual) give an Art. 51/52 LIRPF reducción to the
    base imponible general. Casilla 0463 ("Aportaciones individuales y
    contribuciones empresariales ...", semantic_role
    ``irpf_red_prevision_social_aportaciones_individuales``) is the individual
    input box. The existing chain tests exercise the plan-de-empleo worker box
    (0426) and the employer box (0427); this locks the individual-side (0463)
    path, flowing 0463 → 0467 → 0468 → base liquidable general 0500.

    Oracle derivation (Art. 52 LIRPF, AEAT Renta 2025 Manual Parte 1 —
    "Reducciones por aportaciones a sistemas de previsión social"): an
    individual aportación below the general €1.500 individual limit and below
    the 30 % net-yield limit is fully reducible from the base general.
      trabajo rendimientos (0003) = 32,000 → 0019 (otros gastos, art. 19.2.f)
        = min(2000, 32000) = 2,000 → 0025 = 0432 = 32,000 - 2,000 = 30,000
      30% cap = 0.30 * 30,000 = 9,000
      individual aportación (0463) = 1,200 → 0467 = 1,200
      1,200 < 1,500 (individual limit) and 1,200 < 9,000 (30% limit)
      0468 = min(1200, 10000, 9000) = 1,200   (below every cap → full reducción)
      0435 = 30,000 (no negative G/P balance); 0461 = 0; 0501 = 0
      0500 = 30,000 - 1,200 - 0 - 0 = 28,800
    """
    scenario = _scenario_2025(
        "individual-aportaciones-prevision-social-reduces-base",
        overrides={
            _C0003: Decimal("32000.00"),  # trabajo → nets to 0432 = 30,000 after otros gastos
            _C0463: Decimal("1200.00"),  # individual aportación → 0467 = 1,200
        },
        expected=(
            _expected_output(target_casilla_id=_C0467, value=Decimal("1200.00")),
            _expected_output(target_casilla_id=_C0468, value=Decimal("1200.00")),
            _expected_output(target_casilla_id=_C0500, value=Decimal("28800.00")),
        ),
    )
    report = run_registry_calculation_scenario(scenario, registry_root=_REGISTRY_ROOT, source_root=bundled_path())
    assert_registry_scenario_matches(report)


def test_plan_de_empleo_employer_contribution_reduces_base_general() -> None:
    """Employer plan-de-empleo contributions (casilla 0427) reduce the base imponible general.

    The Art. 52 LIRPF reducción for employer pension-plan (plan de empleo)
    contributions must flow through the previsión-social chain and reduce
    the base liquidable general. Casilla 0427 ("Contribuciones empresariales
    a sistemas de previsión social, excepto ... seguros colectivos de
    dependencia") is the employer-side input box; the existing chain tests
    exercise the worker-side box (0426), so this locks the 0427 path.

    Oracle derivation (Art. 51/52 LIRPF, AEAT Renta 2025 Manual Parte 1):
      trabajo rendimientos (0003) = 42,000 → 0019 (otros gastos, art. 19.2.f)
        = min(2000, 42000) = 2,000 → 0025 = 0432 = 42,000 - 2,000 = 40,000
      30% cap = 0.30 * 40,000 = 12,000
      employer contribution (0427) = 6,000 → 0467 = 6,000
      0468 = min(6000, 10000, 12000) = 6,000   (below both caps)
      0435 = 40,000 (no negative G/P balance); 0461 = 0; 0501 = 0
      0500 = 40,000 - 6,000 - 0 - 0 = 34,000
    """
    scenario = _scenario_2025(
        "plan-empleo-employer-contribution-reduces-base",
        overrides={
            _C0003: Decimal("42000.00"),  # trabajo → nets to 0432 = 40,000 after otros gastos
            _C0427: Decimal("6000.00"),  # employer contribution → 0467 = 6,000
        },
        expected=(
            _expected_output(target_casilla_id=_C0467, value=Decimal("6000.00")),
            _expected_output(target_casilla_id=_C0468, value=Decimal("6000.00")),
            _expected_output(target_casilla_id=_C0500, value=Decimal("34000.00")),
        ),
    )
    report = run_registry_calculation_scenario(scenario, registry_root=_REGISTRY_ROOT, source_root=bundled_path())
    assert_registry_scenario_matches(report)


def test_plan_de_empleo_reduccion_capped_at_10000() -> None:
    """0468 capped at €10,000 absolute limit when aportación exceeds the cap.

    Oracle derivation (Art. 52 LIRPF):
      trabajo rendimientos (0003) = 82,000 → 0019 (otros gastos, art. 19.2.f)
        = min(2000, 82000) = 2,000 → 0432 = 82,000 - 2,000 = 80,000
      30% cap = 0.30 * 80,000 = 24,000
      plan de empleo aportación (0426) = 15,000 → 0467 = 15,000
      0468 = min(15000, 10000, 24000) = 10,000   (€10k absolute cap applies)
      0500 = 80,000 - 10,000 = 70,000
    """
    scenario = _scenario_2025(
        "plan-empleo-reduccion-capped-10k",
        overrides={
            _C0003: Decimal("82000.00"),  # trabajo → nets to 0432 = 80,000 after otros gastos
            _C0426: Decimal("15000.00"),  # plan de empleo aportación → 0467 = 15,000
        },
        expected=(
            _expected_output(target_casilla_id=_C0467, value=Decimal("15000.00")),
            # 0468 = min(15000, 10000, 24000) = 10,000
            _expected_output(target_casilla_id=_C0468, value=Decimal("10000.00")),
            _expected_output(target_casilla_id=_C0500, value=Decimal("70000.00")),
        ),
    )
    report = run_registry_calculation_scenario(scenario, registry_root=_REGISTRY_ROOT, source_root=bundled_path())
    assert_registry_scenario_matches(report)


def test_art52_tiered_purely_individual_aportacion_capped_at_1500() -> None:
    """0468 tiered formula: a purely-individual aportación is capped at the EUR 1.500

    general sub-limit, NOT the combined EUR 10.000/30% ceiling — the exact
    art. 52.1.b) boundary the flat formula silently over-granted. This is the boundary the art. 52 advisory
    (``_art52_reduccion_advisory_finding``) flags for the still-MANUAL
    2021-2023 revisions; here the 2025 formula is asserted to compute the
    correct capped value directly.

    Oracle derivation (art. 52.1 LIRPF, verbatim: "1.500 euros anuales... Este
    límite se incrementará... siempre que tal incremento provenga de
    contribuciones empresariales, o de aportaciones del trabajador al mismo
    instrumento de previsión social"): a EUR 3.000 individual aportación (no
    plan-de-empleo, no contribución empresarial, no aportación de empresa por
    decisión del trabajador, no aportación de autónomo) never unlocks the
    EUR 8.500 increment, so the pool is bound by the general EUR 1.500 limit.
      trabajo rendimientos (0003) = 60,000 → 0019 (otros gastos, art. 19.2.f)
        = min(2000, 60000) = 2,000 → 0432 = 60,000 - 2,000 = 58,000
      30% cap = 0.30 * 58,000 = 17,400 (not binding)
      individual aportación (0463) = 3,000 → 0467 = 3,000 (raw sum, unchanged)
      individual pool = 0463 + 0465 = 3,000; employer-linked backing = 0
      pool cap = 1,500 + min(0, 8500) = 1,500
      0468 = min(17400, min(3000, 1500) + min(0, 5000)) = min(17400, 1500) = 1,500
      0500 = 58,000 - 1,500 = 56,500
    """
    scenario = _scenario_2025(
        "art52-tiered-purely-individual-capped-1500",
        overrides={
            _C0003: Decimal("60000.00"),  # trabajo → nets to 0432 = 58,000 after otros gastos
            _C0463: Decimal("3000.00"),  # purely individual aportación, no employer-linked backing
        },
        expected=(
            _expected_output(target_casilla_id=_C0467, value=Decimal("3000.00")),
            # Tiered formula caps the purely-individual pool at EUR 1.500, not
            # the combined EUR 10.000 the earlier flat formula silently
            # granted (min(3000, 10000, 17400) would have yielded 3,000).
            _expected_output(target_casilla_id=_C0468, value=Decimal("1500.00")),
            _expected_output(target_casilla_id=_C0500, value=Decimal("56500.00")),
        ),
    )
    report = run_registry_calculation_scenario(scenario, registry_root=_REGISTRY_ROOT, source_root=bundled_path())
    assert_registry_scenario_matches(report)


def test_art52_tiered_employer_backed_aportacion_unlocks_8500_increment() -> None:
    """0468 tiered formula: employer-backed contributions unlock the full EUR 10.000

    combined ceiling (EUR 1.500 general + EUR 8.500 increment), even when the
    individual pool is zero — the increment capacity is not wasted just
    because no purely-individual aportación exists to consume the base slot.

    Oracle derivation (art. 52.1.1º LIRPF, verbatim: "En 8.500 euros anuales,
    siempre que tal incremento provenga de contribuciones empresariales"):
      trabajo rendimientos (0003) = 90,000 → 0019 (otros gastos, art. 19.2.f)
        = min(2000, 90000) = 2,000 → 0432 = 90,000 - 2,000 = 88,000
      30% cap = 0.30 * 88,000 = 26,400 (not binding)
      employer contribution (0427) = 9,200 → 0467 = 9,200
      individual pool = 0; employer-linked backing = 9,200
      pool cap = 1,500 + min(9200, 8500) = 1,500 + 8,500 = 10,000
      0468 = min(26400, min(9200, 10000) + min(0, 5000)) = min(26400, 9200) = 9,200
      0500 = 88,000 - 9,200 = 78,800
    """
    scenario = _scenario_2025(
        "art52-tiered-employer-backed-unlocks-increment",
        overrides={
            _C0003: Decimal("90000.00"),  # trabajo → nets to 0432 = 88,000 after otros gastos
            _C0427: Decimal("9200.00"),  # contribución empresarial, well within the combined 10k ceiling
        },
        expected=(
            _expected_output(target_casilla_id=_C0467, value=Decimal("9200.00")),
            # Below the combined EUR 10.000 ceiling (1500 + 8500), so the
            # full aportación reduces — unlike the purely-individual case
            # above, which would have been capped at 1,500.
            _expected_output(target_casilla_id=_C0468, value=Decimal("9200.00")),
            _expected_output(target_casilla_id=_C0500, value=Decimal("78800.00")),
        ),
    )
    report = run_registry_calculation_scenario(scenario, registry_root=_REGISTRY_ROOT, source_root=bundled_path())
    assert_registry_scenario_matches(report)


def test_art52_tiered_dependencia_uses_separate_5000_ceiling() -> None:
    """0468 tiered formula: the dependencia pool (0464/0466) has its OWN separate

    EUR 5.000 ceiling, additive to (not sharing) the aportaciones/contribuciones
    pool's EUR 1.500/10.000 ceiling — confirmed against the AEAT Renta 2025
    manual worked example (Cap. 13, "Reducciones de la base imponible
    general"): "Límite de aportaciones y contribuciones: 10.000 euros por
    aportaciones y contribuciones + 5.000 euros por seguros colectivos de
    dependencia."

    Oracle derivation (art. 52.1 LIRPF, final paragraph, verbatim: "Además,
    5.000 euros anuales para las primas a seguros colectivos de dependencia
    satisfechas por la empresa"):
      trabajo rendimientos (0003) = 42,000 → 0019 (otros gastos, art. 19.2.f)
        = min(2000, 42000) = 2,000 → 0432 = 42,000 - 2,000 = 40,000
      30% cap = 0.30 * 40,000 = 12,000 (not binding)
      individual aportación (0463) = 1,000 → within its own 1,500 sub-limit
      contribución seguro colectivo de dependencia (0466) = 6,000 → exceeds
        its own separate 5,000 ceiling, capped there
      0467 = 0463 + 0466 = 1,000 + 6,000 = 7,000 (raw sum, unchanged)
      individual pool = 1,000 (backing = 0) → capped at 1,500 → 1,000
      dependencia pool = 6,000 → capped at 5,000 → 5,000
      0468 = min(12000, 1000 + 5000) = min(12000, 6000) = 6,000
      0500 = 40,000 - 6,000 = 34,000
    """
    scenario = _scenario_2025(
        "art52-tiered-dependencia-separate-5000-ceiling",
        overrides={
            _C0003: Decimal("42000.00"),  # trabajo → nets to 0432 = 40,000 after otros gastos
            _C0463: Decimal("1000.00"),  # individual aportación, within the 1,500 sub-limit
            _C0466: Decimal("6000.00"),  # dependencia contribution, exceeds its own 5,000 ceiling
        },
        expected=(
            _expected_output(target_casilla_id=_C0467, value=Decimal("7000.00")),
            # dependencia contribution (6,000) is capped at its own separate
            # 5,000 ceiling; the individual aportación (1,000) is unaffected
            # by that cap since it belongs to a different pool.
            _expected_output(target_casilla_id=_C0468, value=Decimal("6000.00")),
            _expected_output(target_casilla_id=_C0500, value=Decimal("34000.00")),
        ),
    )
    report = run_registry_calculation_scenario(scenario, registry_root=_REGISTRY_ROOT, source_root=bundled_path())
    assert_registry_scenario_matches(report)


def test_art52_tiered_autonomo_only_aportacion_capped_at_1500_plus_4250() -> None:
    """0468 tiered formula: a purely-autónomo aportación (casilla 0499) unlocks

    only the EUR 4.250 art. 52.1.2º increment, NOT the EUR 8.500 art. 52.1.1º
    increment — the two sub-tiers are grounded on distinct conditions and are
    not interchangeable. A 0499-only filer with no plan-de-empleo/contribución
    empresarial backing (0426/0427/0438 = 0) is bound at EUR 1.500 + EUR 4.250
    = EUR 5.750, not the combined EUR 10.000 (1.500 + 8.500) a formula that
    pools 0499 with the 1º-eligible casillas would silently grant.

    Oracle derivation (art. 52.1 LIRPF, verbatim: "2.º En 4.250 euros
    anuales, siempre que tal incremento provenga de... aportaciones...
    realizadas por trabajadores por cuenta propia o autónomos"; 1.º is
    conditioned on "contribuciones empresariales, o... aportaciones del
    trabajador al mismo instrumento de previsión social", which 0499 is not):
      trabajo rendimientos (0003) = 40,000 → 0019 (otros gastos, art. 19.2.f)
        = min(2000, 40000) = 2,000 → 0432 = 40,000 - 2,000 = 38,000
      30% cap = 0.30 * 38,000 = 11,400 (not binding)
      autónomo aportación (0499) = 6,000 → 0467 = 6,000 (raw sum, unchanged)
      1º backing (0426+0427+0438) = 0 → 1º increment = min(0, 8500) = 0
      2º backing (0499) = 6,000 → 2º increment = min(6000, 4250) = 4,250
      combined increments = min(0 + 4250, 8500) = 4,250
      pool cap = 1,500 + 4,250 = 5,750
      0468 = min(11400, min(6000, 5750)) = 5,750   (bound at 1.500+4.250, not
        the combined EUR 10.000 a uniform employer-linked pool would grant)
      0500 = 38,000 - 5,750 = 32,250
    """
    scenario = _scenario_2025(
        "art52-tiered-autonomo-only-capped-1500-plus-4250",
        overrides={
            _C0003: Decimal("40000.00"),  # trabajo → nets to 0432 = 38,000 after otros gastos
            _C0499: Decimal("6000.00"),  # purely-autónomo aportación, no 1º-eligible backing
        },
        expected=(
            _expected_output(target_casilla_id=_C0467, value=Decimal("6000.00")),
            # Bound by 1.500 (general) + 4.250 (art. 52.1.2º autónomo
            # increment), NOT the combined EUR 10.000 (1.500 + 8.500) a
            # formula pooling 0499 with 0426/0427/0438 would silently grant.
            _expected_output(target_casilla_id=_C0468, value=Decimal("5750.00")),
            _expected_output(target_casilla_id=_C0500, value=Decimal("32250.00")),
        ),
    )
    report = run_registry_calculation_scenario(scenario, registry_root=_REGISTRY_ROOT, source_root=bundled_path())
    assert_registry_scenario_matches(report)


def test_art52_tiered_employer_and_autonomo_increments_jointly_recapped_at_8500() -> None:
    """0468 tiered formula: the art. 52.1.1º (EUR 8.500) and 2º (EUR 4.250)

    increments are additive but jointly re-capped at EUR 8.500 total — "en
    todo caso, la cuantía máxima de reducción por aplicación de los
    incrementos previstos en los números 1.º y 2.º anteriores será de 8.500
    euros anuales". A filer with BOTH a large contribución empresarial (1º)
    and an autónomo aportación (2º) does not get 8.500 + 4.250 = 12.750; the
    joint increment stays capped at 8.500.

    Oracle derivation (art. 52.1 LIRPF, final sentence of the increment
    schedule, verbatim above):
      trabajo rendimientos (0003) = 120,000 → 0019 (otros gastos, art. 19.2.f)
        = min(2000, 120000) = 2,000 → 0432 = 120,000 - 2,000 = 118,000
      30% cap = 0.30 * 118,000 = 35,400 (not binding)
      contribución empresarial (0427) = 7,000; autónomo aportación (0499) = 3,000
      0467 = 7,000 + 3,000 = 10,000 (raw sum, unchanged)
      1º increment = min(7000, 8500) = 7,000
      2º increment = min(3000, 4250) = 3,000
      combined increments = min(7000 + 3000, 8500) = 8,500  (re-capped, not 10,000)
      pool cap = 1,500 + 8,500 = 10,000
      0468 = min(35400, min(10000, 10000)) = 10,000
      0500 = 118,000 - 10,000 = 108,000
    """
    scenario = _scenario_2025(
        "art52-tiered-employer-and-autonomo-jointly-recapped-8500",
        overrides={
            _C0003: Decimal("120000.00"),  # trabajo → nets to 0432 = 118,000 after otros gastos
            _C0427: Decimal("7000.00"),  # contribución empresarial, unlocks the 1º increment
            _C0499: Decimal("3000.00"),  # autónomo aportación, unlocks the 2º increment
        },
        expected=(
            _expected_output(target_casilla_id=_C0467, value=Decimal("10000.00")),
            # 1º (7,000) + 2º (3,000) = 10,000 would exceed EUR 8.500 if
            # uncapped; the joint re-cap binds the increments at 8,500, so
            # the pool cap is 1,500 + 8,500 = 10,000 and the full aportación
            # reduces (it happens to equal the pool cap exactly here).
            _expected_output(target_casilla_id=_C0468, value=Decimal("10000.00")),
            _expected_output(target_casilla_id=_C0500, value=Decimal("108000.00")),
        ),
    )
    report = run_registry_calculation_scenario(scenario, registry_root=_REGISTRY_ROOT, source_root=bundled_path())
    assert_registry_scenario_matches(report)

"""Tests for registry-backed formula runtime."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from .....core.aggregation import BindingAggregation, BindingAggregationOp
from .....core.resources import bundled_path
from .....tests.registry_observations import registry_grounded_modelo_observation
from .._authority import ValidatedRegistryAuthority
from .._bindings import (
    CasillaObservation,
    _PreviousModeloSelector,
    previous_filing_observation_requirements,
    previous_filing_source_reference,
    resolve_previous_filing_binding_values,
)
from .._errors import RegistryValidationError
from .._formula_initial_values import materialise_observations
from .._formula_runtime import calculate_registry_snapshot
from .._ids import validated_casilla_id
from .._relations import relation_source_requirements, resolve_relation_values_from_observations
from .._schema import CasillaId, DataBindingDefinition, RegistrySnapshot
from .._snapshot import build_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PREVIOUS_YEAR_NET_INCOME_BINDING = "irpf.previous_year_economic_activity_net_income"
_PREVIOUS_PERIOD_NEGATIVE_RESULT_BINDING = "modelo-130-resultados-negativos-anteriores"


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test casilla id")
    except ValueError as exc:
        raise AssertionError(f"formula runtime fixture casilla key {value!r} is not a CasillaId") from exc


_M130_INGRESOS_CASILLA: CasillaId = _casilla_id("01")
_M130_GASTOS_CASILLA: CasillaId = _casilla_id("02")
_M130_PAGO_FRACCIONADO_CASILLA: CasillaId = _casilla_id("04")
_M130_RETENCIONES_CASILLA: CasillaId = _casilla_id("06")
_M130_DIFERENCIA_ACTIVIDADES_CASILLA: CasillaId = _casilla_id("07")
_M130_AGRARIAN_VOLUME_CASILLA: CasillaId = _casilla_id("08")
_M130_DIFERENCIA_AGRARIA_CASILLA: CasillaId = _casilla_id("09")
_M130_AGRARIAN_WITHHELD_CASILLA: CasillaId = _casilla_id("10")
_M130_DIFERENCIA_TOTAL_CASILLA: CasillaId = _casilla_id("11")
_M130_RESULTADO_POSITIVO_CASILLA: CasillaId = _casilla_id("12")
_M130_MINORACION_CASILLA: CasillaId = _casilla_id("13")
_M130_RESULTADO_PREVIO_CASILLA: CasillaId = _casilla_id("14")
_M130_HOME_DEDUCTION_CASILLA: CasillaId = _casilla_id("16")
_M130_DIFERENCIA_CASILLA: CasillaId = _casilla_id("17")
_M130_PRIOR_RETURN_RESULT_CASILLA: CasillaId = _casilla_id("18")
_M130_RESULTADO_FINAL_CASILLA: CasillaId = _casilla_id("19")
_M130_SALDO_NEGATIVO_CASILLA: CasillaId = _casilla_id("saldo-negativo-fin-periodo")
_M115_PERCEPTORES_CASILLA: CasillaId = _casilla_id("01")
_M115_BASE_CASILLA: CasillaId = _casilla_id("02")
_M115_RETENCIONES_CASILLA: CasillaId = _casilla_id("03")
_IVA_PRORRATA_PORCENTAJE_CASILLA: CasillaId = _casilla_id("iva.prorrata-porcentaje")
_M100_RENDIMIENTO_NETO_ACTIVIDADES_CASILLA: CasillaId = _casilla_id("0224")
_M100_RETENCIONES_PAGOS_CUENTA_CASILLA: CasillaId = _casilla_id("1479")
_M100_PAGOS_FRACCIONADOS_CASILLA: CasillaId = _casilla_id("1553")
_M100_RESULTADO_AUTOLIQUIDACION_CASILLA: CasillaId = _casilla_id("1577")


def test_registry_calculation_result_refuses_ungrounded_observations() -> None:
    with pytest.raises(ValidationError, match="legal_refs"):
        CasillaObservation.model_validate({"casilla_id": _M130_INGRESOS_CASILLA, "value": Decimal("100")})


def test_materialise_observations_refuses_value_without_registry_casilla() -> None:
    with pytest.raises(RegistryValidationError, match="missing registry casilla definition"):
        materialise_observations(
            values={_M130_INGRESOS_CASILLA: Decimal("100")},
            computed_provenance={},
            casillas_by_id={},
        )


def test_materialise_observations_refuses_registry_casilla_without_grounding(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    casilla = next(
        item for item in committed_modelo_130_snapshot.revision.casillas if item.id == _M130_INGRESOS_CASILLA
    )
    ungrounded = casilla.model_copy(update={"legal_refs": (), "source_refs": ()})

    with pytest.raises(RegistryValidationError, match="missing legal_refs/source_refs"):
        materialise_observations(
            values={_M130_INGRESOS_CASILLA: Decimal("100")},
            computed_provenance={},
            casillas_by_id={_M130_INGRESOS_CASILLA: ungrounded},
        )


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
            _M130_INGRESOS_CASILLA: Decimal("10000"),
            _M130_GASTOS_CASILLA: Decimal("4000"),
            _M130_RETENCIONES_CASILLA: Decimal("100"),
            _M130_AGRARIAN_VOLUME_CASILLA: Decimal("2000"),
            _M130_AGRARIAN_WITHHELD_CASILLA: Decimal("10"),
            _M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
            _M130_PRIOR_RETURN_RESULT_CASILLA: Decimal("0"),
        },
        date_context={"filing_period": date(2026, 3, 31)},
        binding_values={
            _PREVIOUS_YEAR_NET_INCOME_BINDING: Decimal("13000"),
            _PREVIOUS_PERIOD_NEGATIVE_RESULT_BINDING: Decimal("0"),
            # C03 (rendimiento neto) was converted from computed to
            # bound by a parallel campaign; supply the actividad-
            # economica cumulative binding value so the bound
            # casilla resolves.
            "modelo-130-actividad-economica-rendimiento-neto-cumulative": Decimal("6000"),
        },
    )

    # C03 is now bound (not computed) so it does not appear in
    # result.entries. Order assertions adjusted to exclude C03.
    order = {entry.target_casilla_id: index for index, entry in enumerate(result.entries)}
    assert (
        order[_M130_PAGO_FRACCIONADO_CASILLA]
        < order[_M130_DIFERENCIA_ACTIVIDADES_CASILLA]
        < order[_M130_RESULTADO_POSITIVO_CASILLA]
        < order[_M130_RESULTADO_PREVIO_CASILLA]
        < order[_M130_DIFERENCIA_CASILLA]
        < order[_M130_RESULTADO_FINAL_CASILLA]
    )
    assert (
        order[_M130_DIFERENCIA_AGRARIA_CASILLA]
        < order[_M130_DIFERENCIA_TOTAL_CASILLA]
        < order[_M130_RESULTADO_POSITIVO_CASILLA]
    )
    assert _M130_RESULTADO_FINAL_CASILLA in result.values
    assert "rd-439-2007:art-110" in result.entries[0].legal_refs


def test_registry_formula_runtime_rejects_inputs_for_computed_casillas(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    # C04 (Total ingresos) is a computed casilla in the M130 1T
    # snapshot; previously C03 was used but a parallel campaign
    # changed C03 to input_kind="bound" via an actividad-economica
    # cumulative-rendimiento-neto binding.
    with pytest.raises(RegistryValidationError, match="computed registry casillas cannot be supplied"):
        calculate_registry_snapshot(
            committed_modelo_130_snapshot,
            inputs={_M130_PAGO_FRACCIONADO_CASILLA: Decimal("6000")},
            date_context={"filing_period": date(2026, 3, 31)},
            binding_values={_PREVIOUS_YEAR_NET_INCOME_BINDING: Decimal("13000")},
        )


def test_casilla_constraint_violation_message_interpolates_with_raise_site_context() -> None:
    """The casilla-constraint-violation locale template renders cleanly with the
    exact context the raise site supplies.

    Regression for a placeholder leak: the
    ``errors.calc.casilla_constraint_violation`` template references
    ``{violation}``, but the raise site in
    ``_formula_runtime.calculate_registry_snapshot`` originally omitted that key
    from its ``context`` dict. A missing kwarg makes the renderer return the
    template uninterpolated, so EVERY placeholder
    (``{casilla_id}``/``{value}``/``{violation}``/``{legal_refs}``) leaked to the
    operator. This test renders the real template with the raise-site context and
    asserts no ``{name}`` placeholder survives. The AST placeholder-parity gate
    does not cover error ``context=`` dicts, so this guard is explicit.
    """
    from .....core.i18n import tr

    # Mirror the context built at the raise site (keep in sync with
    # _formula_runtime.calculate_registry_snapshot).
    context = {
        "casilla_id": _IVA_PRORRATA_PORCENTAJE_CASILLA,
        "display_number": "prorrata-porcentaje",
        "value": "200",
        "violation": "value 200 above max_value 100",
        "formula_id": "modelo-303-iva-prorrata-porcentaje",
        "legal_refs": "ley-37-1992:art-104",
        "source_refs": "aeat-modelo-303-procedure",
    }
    rendered = tr("errors.calc.casilla_constraint_violation", **context)
    assert _IVA_PRORRATA_PORCENTAJE_CASILLA in rendered
    assert "value 200 above max_value 100" in rendered
    assert "{" not in rendered and "%{" not in rendered, rendered


def test_registry_formula_runtime_preserves_signed_intermediate_results_from_official_instructions(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    """Structural sign-propagation assertion — not a numeric tautology.

    This test asserts no hand-computed Decimal. It exercises two
    structural contracts of the modelo-130 pago-fraccionado graph that
    hold regardless of the exact arithmetic:

    * Sign propagation: the modelo-130 form (AEAT *Diseño de registros*
      modelo 130) carries explicitly signable "diferencia" casillas —
      a pago-fraccionado period whose deductible amounts (05/06/08/10)
      and prior payments outweigh the period's gross liability must
      drive its intermediate "diferencia" casillas (07, 11) negative.
      A formula that clamped these or flipped a subtraction would fail
      the strict-negative assertion.
    * Floor contract: casilla 12 carries a ``MAX(_, 0)`` floor in the
      registry (the period result the operator pays is never negative;
      a refund is carried elsewhere). The ``>= 0`` assertion exercises
      that declared floor, not a derived value.

    Per the no-tautological-calculation-tests rule this is the
    "structural assertion" alternative: it would fail if the registry
    formula graph were wrong against AEAT, yet manufactures no Decimal
    expectation from the formula under test.
    """

    # Casilla 05 ("Pagos fraccionados anteriores") is now a bound carry that is
    # absent-by-design (= 0) at a 1T target, so the negative diferencia is driven
    # by the OTHER deductibles outweighing the gross liability: casilla 06
    # (retenciones) here exceeds casilla 04 (the 20% pago fraccionado on a 1000
    # rendimiento neto), forcing casilla 07 = 04 - 05 - 06 strictly negative.
    result = calculate_registry_snapshot(
        committed_modelo_130_snapshot,
        inputs={
            _M130_INGRESOS_CASILLA: Decimal("1000"),
            _M130_GASTOS_CASILLA: Decimal("0"),
            _M130_RETENCIONES_CASILLA: Decimal("300"),
            _M130_AGRARIAN_VOLUME_CASILLA: Decimal("100"),
            _M130_AGRARIAN_WITHHELD_CASILLA: Decimal("10"),
            _M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
            _M130_PRIOR_RETURN_RESULT_CASILLA: Decimal("0"),
        },
        date_context={"filing_period": date(2026, 3, 31)},
        binding_values={
            _PREVIOUS_YEAR_NET_INCOME_BINDING: Decimal("13000"),
            _PREVIOUS_PERIOD_NEGATIVE_RESULT_BINDING: Decimal("0"),
        },
    )

    assert result.values[_M130_DIFERENCIA_ACTIVIDADES_CASILLA] < Decimal("0")
    assert result.values[_M130_DIFERENCIA_TOTAL_CASILLA] < Decimal("0")
    assert result.values[_M130_RESULTADO_POSITIVO_CASILLA] >= Decimal("0")


def test_registry_formula_runtime_calculates_income_reduction_from_previous_year_binding(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    result = calculate_registry_snapshot(
        committed_modelo_130_snapshot,
        inputs={
            _M130_INGRESOS_CASILLA: Decimal("10000"),
            _M130_GASTOS_CASILLA: Decimal("4000"),
            _M130_RETENCIONES_CASILLA: Decimal("100"),
            _M130_AGRARIAN_VOLUME_CASILLA: Decimal("2000"),
            _M130_AGRARIAN_WITHHELD_CASILLA: Decimal("10"),
            _M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
            _M130_PRIOR_RETURN_RESULT_CASILLA: Decimal("0"),
        },
        date_context={"filing_period": date(2026, 3, 31)},
        binding_values={
            _PREVIOUS_YEAR_NET_INCOME_BINDING: Decimal("9500"),
            _PREVIOUS_PERIOD_NEGATIVE_RESULT_BINDING: Decimal("0"),
        },
    )

    assert {_M130_MINORACION_CASILLA, _M130_RESULTADO_FINAL_CASILLA} <= set(result.values)
    entries = {entry.target_casilla_id: entry for entry in result.entries}
    assert _M130_MINORACION_CASILLA in entries and _M130_RESULTADO_FINAL_CASILLA in entries


def test_previous_filing_binding_resolves_from_observed_irpf_casillas(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    binding = _previous_year_net_income_binding(committed_modelo_130_snapshot)
    source_reference = previous_filing_source_reference(binding)
    source_casilla_ids = source_reference.source_casilla_ids
    observed_values = {casilla_id: Decimal(index + 1) for index, casilla_id in enumerate(source_casilla_ids)}

    result = resolve_previous_filing_binding_values(
        committed_modelo_130_snapshot.revision,
        (
            registry_grounded_modelo_observation(
                modelo=source_reference.source_modelo,
                filing_year=2025,
                period=source_reference.required_periods[0],
                casilla_values=observed_values,
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
    source_reference = previous_filing_source_reference(binding)

    requirements = previous_filing_observation_requirements(
        committed_modelo_130_snapshot.revision,
        filing_year=2026,
        period="1T",
    )

    assert len(requirements) == 1
    requirement = requirements[0]
    assert requirement.modelo == source_reference.source_modelo
    assert requirement.filing_year == 2025
    assert requirement.period == source_reference.required_periods[0]
    assert requirement.binding_ids == (_PREVIOUS_YEAR_NET_INCOME_BINDING,)
    assert requirement.source_casilla_ids == tuple(sorted(source_reference.source_casilla_ids))


def test_relation_requirements_cover_all_source_periods_for_annual_summary(
    committed_modelo_180_snapshot: RegistrySnapshot,
) -> None:
    # M180 ← M115 is canonically a RELATION fold-in (aggregation-taxonomy
    # ruling 2): the slot bindings declare source = "relation_prefill" and the
    # requirement set is produced by the relation requirement resolver, not the
    # previous-filing one (which now skips relation_prefill slots by design).
    requirements = relation_source_requirements(
        committed_modelo_180_snapshot.revision,
        filing_year=2026,
        period="0A",
    )

    # The three 180 annual_summary relations share one source quadruple
    # (115/2026/[1T-4T]) grouped per source_casilla_id; assert the periods cover all
    # four quarters and the relation source modelo/year are correct.
    assert {requirement.source_modelo for requirement in requirements} == {"115"}
    assert {requirement.filing_year for requirement in requirements} == {2026}
    assert all(tuple(requirement.periods) == ("1T", "2T", "3T", "4T") for requirement in requirements)
    target_bindings = {tb for requirement in requirements for tb in requirement.target_bindings}
    assert target_bindings == {
        "modelo-180-115-base-anual",
        "modelo-180-115-perceptores-anual",
        "modelo-180-115-retenciones-anual",
    }
    assert {requirement.source_casilla_id for requirement in requirements} == {
        _M115_PERCEPTORES_CASILLA,
        _M115_BASE_CASILLA,
        _M115_RETENCIONES_CASILLA,
    }


def test_relation_resolves_annual_summary_from_all_source_periods(
    committed_modelo_180_snapshot: RegistrySnapshot,
) -> None:
    # Per .claude/rules/no-tautological-calculation-tests.md, we do not assert
    # base-anual / retenciones-anual equal the author's hand-summation of the
    # synthetic inputs; the runtime's `op = "sum"` aggregator and the author
    # would share the same arithmetic. Instead this test asserts the canonical
    # RELATION resolver (now live) produces:
    #   1. graph-wiring: the three expected relation ids appear in result;
    #   2. structural: perceptores = number of observations (count, not
    #      arithmetic on input values);
    #   3. type: the summed relations are Decimal-valued, sign-preserving.
    observations = tuple(
        registry_grounded_modelo_observation(
            modelo="115",
            filing_year=2026,
            period=period,
            casilla_values={
                _M115_PERCEPTORES_CASILLA: Decimal("1"),
                _M115_BASE_CASILLA: base,
                _M115_RETENCIONES_CASILLA: retention,
            },
        )
        for period, base, retention in (
            ("1T", Decimal("100.00"), Decimal("19.00")),
            ("2T", Decimal("200.00"), Decimal("38.00")),
            ("3T", Decimal("300.00"), Decimal("57.00")),
            ("4T", Decimal("-50.00"), Decimal("0.00")),
        )
    )

    result = resolve_relation_values_from_observations(
        committed_modelo_180_snapshot.revision,
        observations,
        filing_year=2026,
        period="0A",
    )

    assert set(result.keys()) == {
        "modelo-180-rel-115-perceptores-anual",
        "modelo-180-rel-115-base-anual",
        "modelo-180-rel-115-retenciones-anual",
    }
    assert result["modelo-180-rel-115-perceptores-anual"] == Decimal(len(observations))
    assert isinstance(result["modelo-180-rel-115-base-anual"], Decimal)
    assert isinstance(result["modelo-180-rel-115-retenciones-anual"], Decimal)


def test_previous_filing_binding_requires_complete_observed_casillas(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    binding = _previous_year_net_income_binding(committed_modelo_130_snapshot)
    source_reference = previous_filing_source_reference(binding)
    source_casilla_ids = source_reference.source_casilla_ids

    with pytest.raises(RegistryValidationError, match="requires observed casilla"):
        resolve_previous_filing_binding_values(
            committed_modelo_130_snapshot.revision,
            (
                registry_grounded_modelo_observation(
                    modelo=source_reference.source_modelo,
                    filing_year=2025,
                    period=source_reference.required_periods[0],
                    casilla_values={source_casilla_ids[0]: Decimal("1")},
                ),
            ),
            filing_year=2026,
            period="1T",
        )


def test_previous_modelo_selector_max_year_delta_unset_preserves_unbounded_anchors() -> None:
    selector = _PreviousModeloSelector(
        source_modelo="130",
        source_casilla_id=_M130_SALDO_NEGATIVO_CASILLA,
        source_period_offset_from_target=-1,
    )

    assert selector.max_year_delta is None
    assert selector.required_period_anchors_for_target("1T") == ((-1, "4T"),)
    assert selector.required_period_anchors_for_target("2T") == ((0, "1T"),)


def test_previous_modelo_selector_max_year_delta_zero_drops_cross_ejercicio_offset_anchor() -> None:
    selector = _PreviousModeloSelector(
        source_modelo="130",
        source_casilla_id=_M130_SALDO_NEGATIVO_CASILLA,
        source_period_offset_from_target=-1,
        max_year_delta=0,
    )

    assert selector.required_period_anchors_for_target("1T") == ()


def test_previous_modelo_selector_max_year_delta_zero_admits_same_ejercicio_offset_anchors() -> None:
    selector = _PreviousModeloSelector(
        source_modelo="130",
        source_casilla_id=_M130_SALDO_NEGATIVO_CASILLA,
        source_period_offset_from_target=-1,
        max_year_delta=0,
    )

    assert selector.required_period_anchors_for_target("2T") == ((0, "1T"),)
    assert selector.required_period_anchors_for_target("3T") == ((0, "2T"),)
    assert selector.required_period_anchors_for_target("4T") == ((0, "3T"),)


def test_previous_modelo_selector_max_year_delta_one_admits_one_year_cross_ejercicio_anchor() -> None:
    selector = _PreviousModeloSelector(
        source_modelo="130",
        source_casilla_id=_M130_SALDO_NEGATIVO_CASILLA,
        source_period_offset_from_target=-1,
        max_year_delta=1,
    )

    assert selector.required_period_anchors_for_target("1T") == ((-1, "4T"),)
    assert selector.required_period_anchors_for_target("2T") == ((0, "1T"),)


def test_previous_modelo_selector_max_year_delta_rejects_negative_values() -> None:
    with pytest.raises(ValidationError, match="max_year_delta must be non-negative"):
        _PreviousModeloSelector(
            source_modelo="130",
            source_casilla_id=_M130_SALDO_NEGATIVO_CASILLA,
            source_period_offset_from_target=-1,
            max_year_delta=-1,
        )


def test_previous_filing_requirements_walker_skips_cap_suppressed_binding(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    base_binding = _previous_year_net_income_binding(committed_modelo_130_snapshot)
    capped_binding = base_binding.model_copy(
        update={
            "id": "test-cap-suppressed-binding",
            "selector": {
                "source": "previous_filing",
                "source_modelo": "130",
                "source_casilla_id": "saldo-negativo-fin-periodo",
                "source_period_offset_from_target": -1,
                "max_year_delta": 0,
            },
            "aggregation": BindingAggregation(op=BindingAggregationOp.COPY),
        },
    )
    extended_revision = committed_modelo_130_snapshot.revision.model_copy(
        update={"bindings": (*committed_modelo_130_snapshot.revision.bindings, capped_binding)},
    )

    requirements_first_period = previous_filing_observation_requirements(
        extended_revision,
        filing_year=2026,
        period="1T",
    )
    assert all(
        "test-cap-suppressed-binding" not in requirement.binding_ids for requirement in requirements_first_period
    )

    requirements_second_period = previous_filing_observation_requirements(
        extended_revision,
        filing_year=2026,
        period="2T",
    )
    matching = [
        requirement
        for requirement in requirements_second_period
        if "test-cap-suppressed-binding" in requirement.binding_ids
    ]
    assert len(matching) == 1
    assert matching[0].modelo == "130"
    assert matching[0].filing_year == 2026
    assert matching[0].period == "1T"


def test_previous_filing_resolver_skips_cap_suppressed_binding(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    base_binding = _previous_year_net_income_binding(committed_modelo_130_snapshot)
    capped_binding = base_binding.model_copy(
        update={
            "id": "test-cap-suppressed-binding-resolve",
            "selector": {
                "source": "previous_filing",
                "source_modelo": "130",
                "source_casilla_id": "saldo-negativo-fin-periodo",
                "source_period_offset_from_target": -1,
                "max_year_delta": 0,
            },
            "aggregation": BindingAggregation(op=BindingAggregationOp.COPY),
        },
    )
    extended_revision = committed_modelo_130_snapshot.revision.model_copy(
        update={"bindings": (*committed_modelo_130_snapshot.revision.bindings, capped_binding)},
    )

    m100_observation = registry_grounded_modelo_observation(
        modelo="100",
        filing_year=2025,
        period="0A",
        casilla_values={
            _M100_RENDIMIENTO_NETO_ACTIVIDADES_CASILLA: Decimal("1"),
            _M100_RETENCIONES_PAGOS_CUENTA_CASILLA: Decimal("1"),
            _M100_PAGOS_FRACCIONADOS_CASILLA: Decimal("1"),
            _M100_RESULTADO_AUTOLIQUIDACION_CASILLA: Decimal("1"),
        },
    )

    resolved = resolve_previous_filing_binding_values(
        extended_revision,
        observations=(m100_observation,),
        filing_year=2026,
        period="1T",
    )

    assert "test-cap-suppressed-binding-resolve" not in resolved
    assert _PREVIOUS_YEAR_NET_INCOME_BINDING in resolved


def test_registry_formula_runtime_rejects_non_decimal_input(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    with pytest.raises(Exception, match="must be a Decimal"):
        calculate_registry_snapshot(
            committed_modelo_130_snapshot,
            inputs={_M130_INGRESOS_CASILLA: 100},
            date_context={"filing_period": date(2026, 3, 31)},
        )


def test_registry_formula_runtime_rejects_non_string_input_key_at_entry(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    with pytest.raises(RegistryValidationError, match=r"input keys must be canonical casilla\.id strings"):
        calculate_registry_snapshot(
            committed_modelo_130_snapshot,
            inputs={1: Decimal("1")},
            date_context={"filing_period": date(2026, 3, 31)},
        )


def test_registry_formula_runtime_rejects_noncanonical_text_input_keys_at_entry(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    with pytest.raises(RegistryValidationError, match=r"text_input keys must be canonical casilla\.id strings"):
        calculate_registry_snapshot(
            committed_modelo_130_snapshot,
            inputs={},
            text_inputs={1: "general"},
            date_context={"filing_period": date(2026, 3, 31)},
        )

    with pytest.raises(RegistryValidationError, match=r"text_input keys must be canonical casilla\.id strings"):
        calculate_registry_snapshot(
            committed_modelo_130_snapshot,
            inputs={},
            text_inputs={"bad key": "general"},
            date_context={"filing_period": date(2026, 3, 31)},
        )


def test_registry_formula_runtime_rejects_binding_id_supplied_as_casilla_input(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    with pytest.raises(RegistryValidationError, match="unknown registry input casilla ids"):
        calculate_registry_snapshot(
            committed_modelo_130_snapshot,
            inputs={_PREVIOUS_YEAR_NET_INCOME_BINDING: Decimal("13000")},
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
            _M130_INGRESOS_CASILLA: Decimal("100"),
            _M130_GASTOS_CASILLA: Decimal("0"),
            _M130_RETENCIONES_CASILLA: Decimal("0"),
            _M130_AGRARIAN_VOLUME_CASILLA: Decimal("0"),
            _M130_AGRARIAN_WITHHELD_CASILLA: Decimal("0"),
            _M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
            _M130_PRIOR_RETURN_RESULT_CASILLA: Decimal("0"),
        },
        date_context={},
        binding_values={
            _PREVIOUS_YEAR_NET_INCOME_BINDING: Decimal("13000"),
            _PREVIOUS_PERIOD_NEGATIVE_RESULT_BINDING: Decimal("0"),
        },
    )

    assert _M130_PAGO_FRACCIONADO_CASILLA in result.values
    assert _M130_PAGO_FRACCIONADO_CASILLA in {entry.target_casilla_id for entry in result.entries}


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
                _M130_INGRESOS_CASILLA: Decimal("100"),
                _M130_GASTOS_CASILLA: Decimal("0"),
                _M130_RETENCIONES_CASILLA: Decimal("0"),
                _M130_AGRARIAN_VOLUME_CASILLA: Decimal("0"),
                _M130_AGRARIAN_WITHHELD_CASILLA: Decimal("0"),
                _M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
                _M130_PRIOR_RETURN_RESULT_CASILLA: Decimal("0"),
            },
            date_context={},
            binding_values={
                _PREVIOUS_YEAR_NET_INCOME_BINDING: Decimal("13000"),
                _PREVIOUS_PERIOD_NEGATIVE_RESULT_BINDING: Decimal("0"),
            },
        )


def _previous_year_net_income_binding(snapshot: RegistrySnapshot) -> DataBindingDefinition:
    return next(binding for binding in snapshot.revision.bindings if binding.id == _PREVIOUS_YEAR_NET_INCOME_BINDING)

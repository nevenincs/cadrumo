"""Core registry formula runtime and materialisation tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ..bindings import CasillaObservation
from ..errors import RegistryValidationError
from ..formula_initial_values import materialise_observations
from ..formula_runtime import RegistryCalculationEntry, calculate_registry_snapshot
from ..schema import RegistrySnapshot
from ._formula_runtime_support import (
    _IVA_PRORRATA_PORCENTAJE_CASILLA,
    _M130_AGRARIAN_VOLUME_CASILLA,
    _M130_AGRARIAN_WITHHELD_CASILLA,
    _M130_DIFERENCIA_ACTIVIDADES_CASILLA,
    _M130_DIFERENCIA_AGRARIA_CASILLA,
    _M130_DIFERENCIA_CASILLA,
    _M130_DIFERENCIA_TOTAL_CASILLA,
    _M130_GASTOS_CASILLA,
    _M130_HOME_DEDUCTION_CASILLA,
    _M130_INGRESOS_CASILLA,
    _M130_MINORACION_CASILLA,
    _M130_PAGO_FRACCIONADO_CASILLA,
    _M130_PRIOR_RETURN_RESULT_CASILLA,
    _M130_RESULTADO_FINAL_CASILLA,
    _M130_RESULTADO_POSITIVO_CASILLA,
    _M130_RESULTADO_PREVIO_CASILLA,
    _M130_RETENCIONES_CASILLA,
    _PREVIOUS_PERIOD_NEGATIVE_RESULT_BINDING,
    _PREVIOUS_YEAR_NET_INCOME_BINDING,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_registry_calculation_result_refuses_ungrounded_observations() -> None:
    with pytest.raises(ValidationError, match="legal_refs"):
        CasillaObservation.model_validate({"casilla_id": _M130_INGRESOS_CASILLA, "value": Decimal("100")})


def test_registry_calculation_entry_rejects_blank_grounding_refs() -> None:
    with pytest.raises(ValidationError, match="legal_refs"):
        RegistryCalculationEntry(
            formula_id="modelo-130-test-formula",
            target_casilla_id=_M130_RESULTADO_FINAL_CASILLA,
            op="add",
            operand_refs=(),
            operand_casilla_refs=(),
            operand_values=(),
            value=Decimal("1"),
            legal_refs=("",),
            source_refs=("aeat-modelo-130-instructions",),
        )

    with pytest.raises(ValidationError, match="source_refs"):
        RegistryCalculationEntry(
            formula_id="modelo-130-test-formula",
            target_casilla_id=_M130_RESULTADO_FINAL_CASILLA,
            op="add",
            operand_refs=(),
            operand_casilla_refs=(),
            operand_values=(),
            value=Decimal("1"),
            legal_refs=("rd-439-2007:art-110",),
            source_refs=(" ",),
        )


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
            # C03 (rendimiento neto) is bound, not computed; supply the
            # actividad-economica cumulative binding value so the bound
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
    # snapshot; C03 is input_kind="bound" via an actividad-economica
    # cumulative-rendimiento-neto binding, not computed.
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

    Per the aeat-quality-gates rule this is the
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

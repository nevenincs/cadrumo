"""Box 0564 of the Modelo 100 sums the autonomic deductions of the comunidad of residence.

Each edition's formula carries one term per comunidad, with the operand boxes the
official dictionary prints for that comunidad's total. The comunidad of residence
contributes its boxes. Any other comunidad whose boxes hold an amount leaves 0564
without a value for a typed reason, because the return carries one comunidad's
deductions. A box the official sum names but the formula leaves out is never added:
while it holds an amount, 0564 has no value, for its own typed reason. A box with no
value of its own counts as zero, and an operator-typed 0564 replaces the formula. LIRPF art. 77.2 keeps the autonomic cuota líquida (0571)
from going negative.

Editions and boxes are read from the registry: the terms come from the hydrated
formula, never from a list here.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date
from decimal import Decimal

import pytest

from .....core.aggregation import BindingSourceKind
from .....core.authority_grade import RegistryAuthorityGrade
from .....core.casilla_id import CasillaId, validated_casilla_id
from ..autonomic_deduccion_enrolment_checks import autonomic_deduccion_enrolments
from ..bindings import CasillaObservation, resolve_available_bound_inputs_by_casilla_id
from ..formula_runtime import RegistryCalculationResult, calculate_registry_snapshot
from ..formula_runtime_ops import RegistryUnresolvedOutcomeReason
from ..schema import ModeloRevision, RegistrySnapshot
from ..schema_formula import FormulaExpression
from ..schema_input_kind import InputKind
from .authored_editions import supported_authored_exercises
from .modelo_100_registry_support import neutral_binding_values

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SALARY: CasillaId = validated_casilla_id("0003", surface="_SALARY")
_SUM: CasillaId = validated_casilla_id("0564", surface="_SUM")
_AUTONOMIC_CUOTA: CasillaId = validated_casilla_id("0571", surface="_AUTONOMIC_CUOTA")
_MADRID_LATE_BOX: CasillaId = validated_casilla_id("1115", surface="_MADRID_LATE_BOX")
_RESIDENCE_BINDING = "renta-profile-tax-residence-ccaa"
_MADRID = "madrid"
_AMOUNT = Decimal("150.00")

type Terms = dict[str, tuple[tuple[int, CasillaId], ...]]
type Guards = dict[str, tuple[CasillaId, ...]]


def _snapshot(registry_snapshot: Callable[..., RegistrySnapshot], year: int) -> RegistrySnapshot:
    return registry_snapshot("100", year, "0A", grade=RegistryAuthorityGrade.CALCULATION)


def _calculate(
    snapshot: RegistrySnapshot,
    *,
    residence: str = _MADRID,
    inputs: Mapping[CasillaId, Decimal] | None = None,
    bindings: Mapping[str, Decimal] | None = None,
    formula_overrides: Mapping[CasillaId, CasillaObservation] | None = None,
) -> RegistryCalculationResult:
    decimals, booleans, dates, enums = neutral_binding_values(
        binding for binding in snapshot.revision.bindings if binding.source is not BindingSourceKind.RELATION_PREFILL
    )
    booleans["renta-modelo-100-estimacion-directa-es-normal"] = True
    decimals |= {"renta-profile-declaration-type": Decimal(1), **(bindings or {})}
    enums[_RESIDENCE_BINDING] = residence
    return calculate_registry_snapshot(
        snapshot,
        inputs={
            **resolve_available_bound_inputs_by_casilla_id(snapshot.revision, decimals),
            _SALARY: Decimal("30000.00"),
            **(inputs or {}),
        },
        date_context={"filing_period": date(snapshot.filing_year, 12, 31)},
        binding_values=decimals,
        enum_binding_values=enums,
        relation_values={
            "renta-modelo-130-pagos-fraccionados": Decimal(0),
            "renta-modelo-131-pagos-fraccionados": Decimal(0),
        },
        date_binding_values=dates,
        boolean_binding_values=booleans,
        formula_overrides=formula_overrides,
    )


def _signed(expression: FormulaExpression) -> tuple[int, CasillaId]:
    if expression.casilla_id is not None:
        return 1, expression.casilla_id
    (negated,) = expression.args
    assert expression.op == "negate" and negated.casilla_id is not None
    return -1, negated.casilla_id


def _resident(resident: FormulaExpression) -> tuple[FormulaExpression, tuple[CasillaId, ...]]:
    """The resident sum and the left-out boxes whose magnitude guards it."""
    if resident.op == "sum":
        return resident, ()
    test, summed, _unresolved = resident.args
    magnitudes = test.args[0].args
    guards = tuple(magnitude.args[0].casilla_id for magnitude in magnitudes)
    assert all(guard is not None for guard in guards)
    return summed, tuple(guard for guard in guards if guard is not None)


def _decoded(revision: ModeloRevision) -> tuple[Terms, Guards]:
    """Each comunidad's signed operand boxes and left-out guards, read from the edition's 0564 formula."""
    casilla = next(item for item in revision.casillas if item.id == _SUM)
    formula = next(item for item in revision.formulas if item.id == casilla.formula)
    terms: Terms = {}
    guards: Guards = {}
    for term in formula.expression.args:
        predicate, resident, _other = term.args
        _binding, literal = predicate.args
        assert literal.text_literal is not None
        summed, guarded = _resident(resident)
        terms[literal.text_literal] = tuple(_signed(arg) for arg in summed.args)
        guards[literal.text_literal] = guarded
    return terms, guards


def _terms(revision: ModeloRevision) -> Terms:
    return _decoded(revision)[0]


def _guarded_cases(registry_snapshot: Callable[..., RegistrySnapshot]) -> list[tuple[int, str, CasillaId]]:
    """Every (edition, comunidad, left-out box) the registry guards, across the authored editions."""
    return [
        (year, residence, box)
        for year in supported_authored_exercises("100")
        for residence, boxes in _decoded(_snapshot(registry_snapshot, year).revision)[1].items()
        for box in boxes
    ]


def _typed_box(revision: ModeloRevision, operands: tuple[tuple[int, CasillaId], ...]) -> CasillaId:
    """The first added operand an operator types by hand."""
    manual = {casilla.id for casilla in revision.casillas if casilla.input_kind is InputKind.MANUAL}
    return next(box for sign, box in operands if sign > 0 and box in manual)


def _unresolved_reasons(result: RegistryCalculationResult, casilla_id: CasillaId) -> list[str]:
    return [outcome.reason.value for outcome in result.unresolved_outcomes if outcome.casilla_id == casilla_id]


def _enrolled_count_binding(revision: ModeloRevision, box: CasillaId) -> str | None:
    """The count binding of the enrolled deducción that computes ``box``, if one does."""
    return next(
        (
            str(enrolment.count_binding)
            for formula, enrolment in autonomic_deduccion_enrolments(revision)
            if formula.target_casilla_id == box
        ),
        None,
    )


def _editions_computing_the_late_madrid_box(registry_snapshot: Callable[..., RegistrySnapshot]) -> list[int]:
    return [
        year
        for year in supported_authored_exercises("100")
        if (1, _MADRID_LATE_BOX) in _terms(revision := _snapshot(registry_snapshot, year).revision)[_MADRID]
        and _enrolled_count_binding(revision, _MADRID_LATE_BOX) is not None
    ]


@pytest.mark.parametrize("year", supported_authored_exercises("100"))
def test_every_edition_computes_the_sum_with_one_term_per_comunidad(
    registry_snapshot: Callable[..., RegistrySnapshot], year: int
) -> None:
    snapshot = _snapshot(registry_snapshot, year)
    casilla = next(item for item in snapshot.revision.casillas if item.id == _SUM)
    terms = _terms(snapshot.revision)

    assert casilla.input_kind is InputKind.COMPUTED
    assert _MADRID in terms
    assert all(operands for operands in terms.values())


@pytest.mark.parametrize("year", supported_authored_exercises("100"))
def test_a_box_with_no_value_counts_as_zero(registry_snapshot: Callable[..., RegistrySnapshot], year: int) -> None:
    result = _calculate(_snapshot(registry_snapshot, year))

    assert result.values[_SUM] == Decimal("0.00")
    assert _unresolved_reasons(result, _SUM) == []


def test_the_madrid_ascendant_deduccion_flows_through_the_sum_into_the_autonomic_cuota(
    registry_snapshot: Callable[..., RegistrySnapshot],
) -> None:
    """One qualifying ascendant puts the deducción amount in 1115, the sum and the cuota."""
    years = _editions_computing_the_late_madrid_box(registry_snapshot)
    assert years, "no edition sums an enrolled late Madrid box"
    for year in years:
        snapshot = _snapshot(registry_snapshot, year)
        count_binding = _enrolled_count_binding(snapshot.revision, _MADRID_LATE_BOX)
        assert count_binding is not None
        baseline = _calculate(snapshot)

        result = _calculate(snapshot, bindings={count_binding: Decimal(1)})

        deduccion = result.values[_MADRID_LATE_BOX]
        assert deduccion > 0, year
        assert baseline.values[_SUM] == Decimal("0.00"), year
        assert result.values[_SUM] == deduccion, year
        assert result.values[_AUTONOMIC_CUOTA] == baseline.values[_AUTONOMIC_CUOTA] - deduccion, year


@pytest.mark.parametrize("year", supported_authored_exercises("100"))
def test_another_comunidads_amount_leaves_the_sum_unresolved_for_its_reason(
    registry_snapshot: Callable[..., RegistrySnapshot], year: int
) -> None:
    snapshot = _snapshot(registry_snapshot, year)
    other, operands = next((ccaa, operands) for ccaa, operands in _terms(snapshot.revision).items() if ccaa != _MADRID)
    box = _typed_box(snapshot.revision, operands)

    result = _calculate(snapshot, inputs={box: _AMOUNT})

    assert _SUM not in result.values, other
    assert _unresolved_reasons(result, _SUM) == [
        RegistryUnresolvedOutcomeReason.AUTONOMIC_DEDUCTION_OTHER_COMUNIDAD.value
    ]
    assert _AUTONOMIC_CUOTA not in result.values


def test_an_operator_typed_sum_wins_over_the_formula(registry_snapshot: Callable[..., RegistrySnapshot]) -> None:
    for year in supported_authored_exercises("100"):
        snapshot = _snapshot(registry_snapshot, year)
        baseline = _calculate(snapshot)
        typed = next(item for item in baseline.observations if item.casilla_id == _SUM).model_copy(
            update={"value": _AMOUNT}
        )
        other_operands = next(operands for ccaa, operands in _terms(snapshot.revision).items() if ccaa != _MADRID)
        other_box = _typed_box(snapshot.revision, other_operands)

        result = _calculate(snapshot, inputs={other_box: _AMOUNT}, formula_overrides={_SUM: typed})

        assert result.values[_SUM] == _AMOUNT, year
        assert _unresolved_reasons(result, _SUM) == [], year
        assert result.values[_AUTONOMIC_CUOTA] == baseline.values[_AUTONOMIC_CUOTA] - _AMOUNT, year


@pytest.mark.parametrize("year", supported_authored_exercises("100"))
def test_a_comunidad_without_an_enrolled_deduccion_sums_its_typed_boxes(
    registry_snapshot: Callable[..., RegistrySnapshot], year: int
) -> None:
    snapshot = _snapshot(registry_snapshot, year)
    enrolled = {enrolment.ccaa for _formula, enrolment in autonomic_deduccion_enrolments(snapshot.revision)}
    residence, operands = next(
        (ccaa, operands) for ccaa, operands in _terms(snapshot.revision).items() if ccaa not in enrolled
    )
    box = _typed_box(snapshot.revision, operands)

    result = _calculate(snapshot, residence=residence, inputs={box: _AMOUNT})

    assert result.values[_SUM] == _AMOUNT
    assert _unresolved_reasons(result, _SUM) == []


@pytest.mark.parametrize("year", supported_authored_exercises("100"))
def test_the_autonomic_cuota_never_goes_negative(registry_snapshot: Callable[..., RegistrySnapshot], year: int) -> None:
    snapshot = _snapshot(registry_snapshot, year)
    box = _typed_box(snapshot.revision, _terms(snapshot.revision)[_MADRID])
    baseline = _calculate(snapshot)
    excess = baseline.values[_AUTONOMIC_CUOTA] + _AMOUNT

    result = _calculate(snapshot, inputs={box: excess})

    assert result.values[_SUM] == excess
    assert result.values[_AUTONOMIC_CUOTA] == Decimal("0.00")


def test_a_left_out_box_holding_an_amount_leaves_the_sum_unresolved_for_its_reason(
    registry_snapshot: Callable[..., RegistrySnapshot],
) -> None:
    cases = _guarded_cases(registry_snapshot)
    assert cases, "no edition guards a left-out box"
    for year, residence, box in cases:
        result = _calculate(_snapshot(registry_snapshot, year), residence=residence, inputs={box: _AMOUNT})

        assert _SUM not in result.values, (year, residence, box)
        assert _unresolved_reasons(result, _SUM) == [
            RegistryUnresolvedOutcomeReason.AUTONOMIC_DEDUCTION_UNSUMMED_BOX.value
        ], (year, residence, box)
        assert _AUTONOMIC_CUOTA not in result.values, (year, residence, box)


def test_an_operator_typed_sum_wins_over_a_left_out_box(registry_snapshot: Callable[..., RegistrySnapshot]) -> None:
    for year, residence, box in _guarded_cases(registry_snapshot):
        snapshot = _snapshot(registry_snapshot, year)
        baseline = _calculate(snapshot, residence=residence)
        typed = next(item for item in baseline.observations if item.casilla_id == _SUM).model_copy(
            update={"value": _AMOUNT}
        )

        result = _calculate(snapshot, residence=residence, inputs={box: _AMOUNT}, formula_overrides={_SUM: typed})

        assert result.values[_SUM] == _AMOUNT, (year, residence, box)
        assert _unresolved_reasons(result, _SUM) == [], (year, residence, box)


def test_a_guarded_comunidad_sums_its_boxes_while_every_left_out_box_is_empty(
    registry_snapshot: Callable[..., RegistrySnapshot],
) -> None:
    for year, residence in sorted({(year, residence) for year, residence, _box in _guarded_cases(registry_snapshot)}):
        snapshot = _snapshot(registry_snapshot, year)
        box = _typed_box(snapshot.revision, _terms(snapshot.revision)[residence])

        result = _calculate(snapshot, residence=residence, inputs={box: _AMOUNT})

        assert result.values[_SUM] == _AMOUNT, (year, residence)
        assert _unresolved_reasons(result, _SUM) == [], (year, residence)

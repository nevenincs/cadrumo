"""An edit changes only what it names; every other operator value survives.

Driven over real encrypted storage through the production edit executor and
calculation boundary. Each edit is admitted afresh, as the workspace does, and
each resulting revision is read back from storage. All values are synthetic.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ...application.modelo.action_errors import ModeloEditRefusedError
from ...application.modelo.calculation_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ...application.modelo.edit_models import (
    ModeloEditScalarAddressV1,
    ModeloEditScalarIntentKind,
    ModeloEditWritableScalarSurfaceEntryV1,
    ModeloScalarEditIntentV1,
)
from ...core.casilla_id import CasillaId, validated_casilla_id
from ...core.operations import OperationEffect
from ...domain.filing.schema import ModeloScalar
from ...domain.modelos.calculation_revision_operator_layer import CalculationOperatorLayer
from .modelo_operator_work_storage import SEEDED_AT, AppliedEdit, SeededOperatorWork, seeded_operator_work

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_C06 = validated_casilla_id("06")
_C08 = validated_casilla_id("08")


def _set(casilla_id: CasillaId, value: ModeloScalar) -> ModeloScalarEditIntentV1:
    return ModeloScalarEditIntentV1(
        address=ModeloEditScalarAddressV1(casilla_id=casilla_id),
        kind=ModeloEditScalarIntentKind.SET_TYPED_VALUE,
        value=value,
    )


def _intent(casilla_id: CasillaId, kind: ModeloEditScalarIntentKind) -> ModeloScalarEditIntentV1:
    return ModeloScalarEditIntentV1(address=ModeloEditScalarAddressV1(casilla_id=casilla_id), kind=kind)


def _updated(applied: AppliedEdit) -> str:
    assert applied.refusal is None, f"the edit was refused: {applied.refusal!r}"
    assert applied.effects[-1] is OperationEffect.UPDATED
    assert applied.calculation_revision_id is not None
    return applied.calculation_revision_id


def _refused_without_effect(work: SeededOperatorWork, applied: AppliedEdit, *, head_before: str) -> None:
    assert isinstance(applied.refusal, ModeloEditRefusedError)
    assert applied.effects[-1] is OperationEffect.NONE
    assert work.require_head().calculation_revision_id == head_before


def test_a_second_edit_keeps_the_first_edits_value(tmp_path: Path) -> None:
    with seeded_operator_work(tmp_path) as work:
        _updated(work.apply(scalar=(_set(_C06, "100.00"),)))
        _updated(work.apply(scalar=(_set(_C08, "50"),)))
        head = work.require_head()

    assert head.operator_layer == CalculationOperatorLayer(decimal_casilla_inputs={_C06: "100", _C08: "50"})
    assert head.casilla_values[_C06] == Decimal("100")
    assert head.casilla_values[_C08] == Decimal("50")


def test_restore_returns_one_casilla_to_its_source_and_keeps_the_rest(tmp_path: Path) -> None:
    with seeded_operator_work(tmp_path) as work:
        source_value = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work.work_unit_id, ports=work.ports, record_operator_layer=True, clock=SEEDED_AT
        ).revision.input_values_by_casilla_id.get(_C06)
        _updated(work.apply(scalar=(_set(_C06, "100"), _set(_C08, "50"))))
        _updated(work.apply(scalar=(_intent(_C06, ModeloEditScalarIntentKind.RESTORE_SOURCE_VALUE),)))
        head = work.require_head()

    assert head.operator_layer == CalculationOperatorLayer(decimal_casilla_inputs={_C08: "50"})
    assert head.input_values_by_casilla_id.get(_C06) == source_value
    assert _C06 not in head.cleared_casilla_ids


def test_a_clear_is_recorded_distinct_from_zero_and_a_later_set_withdraws_it(tmp_path: Path) -> None:
    with seeded_operator_work(tmp_path) as work:
        _updated(work.apply(scalar=(_set(_C06, "100"), _set(_C08, "50"))))
        _updated(work.apply(scalar=(_intent(_C08, ModeloEditScalarIntentKind.CLEAR_DECLARED_VALUE),)))
        cleared = work.require_head()
        _updated(work.apply(scalar=(_set(_C08, "0"),)))
        zero = work.require_head()

    assert cleared.cleared_casilla_ids == (_C08,)
    assert _C08 not in cleared.input_values_by_casilla_id
    assert cleared.operator_layer == CalculationOperatorLayer(decimal_casilla_inputs={_C06: "100"})
    assert zero.cleared_casilla_ids == ()
    assert zero.operator_layer == CalculationOperatorLayer(decimal_casilla_inputs={_C06: "100", _C08: "0"})


def test_clearing_a_casilla_a_source_feeds_is_refused_and_writes_nothing(tmp_path: Path) -> None:
    with seeded_operator_work(tmp_path) as work:
        head = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work.work_unit_id, ports=work.ports, record_operator_layer=True, clock=SEEDED_AT
        ).revision
        source_fed = next(
            entry.casilla_id
            for entry in work.baseline().permitted_surface
            if isinstance(entry, ModeloEditWritableScalarSurfaceEntryV1)
            and entry.casilla_id in head.input_values_by_casilla_id
        )
        applied = work.apply(scalar=(_intent(source_fed, ModeloEditScalarIntentKind.CLEAR_DECLARED_VALUE),))

        _refused_without_effect(work, applied, head_before=head.calculation_revision_id)


@pytest.mark.parametrize("lexeme", ["1.234,56", "1e3", "NaN", "12,5", "abc", "12.345"])
def test_a_malformed_amount_is_a_typed_refusal_not_a_raw_error(tmp_path: Path, lexeme: str) -> None:
    with seeded_operator_work(tmp_path) as work:
        _updated(work.apply(scalar=(_set(_C06, "100"),)))
        before = work.require_head().calculation_revision_id

        applied = work.apply(scalar=(_set(_C08, lexeme),))

        _refused_without_effect(work, applied, head_before=before)


def test_a_modelo_303_edit_replays_its_filing_evidence_and_keeps_earlier_values(tmp_path: Path) -> None:
    with seeded_operator_work(tmp_path, modelo="303") as work:
        first = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work.work_unit_id,
            ports=work.ports,
            filing_instance_evidence=work.m303_filing_evidence(),
            record_operator_layer=True,
            clock=SEEDED_AT,
        ).revision
        free_money = [
            entry.casilla_id
            for entry in work.baseline().permitted_surface
            if isinstance(entry, ModeloEditWritableScalarSurfaceEntryV1)
            and entry.data_type == "money"
            and entry.casilla_id not in first.input_values_by_casilla_id
        ]
        one, two = free_money[0], free_money[1]
        _updated(work.apply(scalar=(_set(one, "10"),)))
        _updated(work.apply(scalar=(_set(two, "20"),)))
        head = work.require_head()

    assert head.filing_instance_evidence == first.filing_instance_evidence
    assert head.operator_layer == CalculationOperatorLayer(decimal_casilla_inputs={one: "10", two: "20"})


def test_a_ratio_is_not_held_to_the_money_scale_on_its_way_to_the_engine(tmp_path: Path) -> None:
    """A three-decimal ratio crosses the wire and the executor; the money bound once refused it."""
    with seeded_operator_work(tmp_path, modelo="303") as work:
        first = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work.work_unit_id,
            ports=work.ports,
            filing_instance_evidence=work.m303_filing_evidence(),
            record_operator_layer=True,
            clock=SEEDED_AT,
        ).revision
        ratio = next(
            entry.casilla_id
            for entry in work.baseline().permitted_surface
            if isinstance(entry, ModeloEditWritableScalarSurfaceEntryV1)
            and entry.data_type == "ratio"
            and entry.grammar.minimum_value() in {None, Decimal(0)}
            and entry.grammar.maximum_value() in {None, Decimal(1), Decimal(100)}
            and entry.casilla_id not in first.input_values_by_casilla_id
        )
        _updated(work.apply(scalar=(_set(ratio, "0.125"),)))
        head = work.require_head()

    assert head.operator_layer == CalculationOperatorLayer(decimal_casilla_inputs={ratio: "0.125"})

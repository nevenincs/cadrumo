"""A calculation missing an input the operator supplies is a refusal naming that input and its door."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from ....core.aggregation import BindingSourceKind
from ....core.authority_grade import RegistryAuthorityGrade
from ....core.errors.error_codes import ErrorCategory, current_error_code, get_registered_error_code
from ....core.operator_action_enums import ActionArgumentStatus
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.calculations.registry.binding_targets import sole_bound_casilla
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ...operations.error_detail import build_operation_error_detail
from ...operations.next_step import OperationOpenWorkStepV1
from ..calculation_source_policy import BUCKET_AGGREGATION_LOCK_SOURCES, CALLER_OVERRIDABLE_CARRY_SOURCES
from ..printed_boxes import snapshot_printed_boxes
from ..work_missing_input import ModeloWorkMissingInputError, input_required, override_admitted

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_YEAR = filing_year_envelope().horizon
_BUCKET_ID = "34343434-3434-4343-8343-343434343434"
_MODELO = "130"
_PERIOD = Period.from_year_and_code(_YEAR, "2T")


@pytest.fixture(scope="module")
def operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as pinned:
        yield pinned


def _work_unit() -> WorkUnit:
    created_at = datetime(_YEAR, 7, 2, tzinfo=UTC)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo=ModeloCode(_MODELO),
            filing_year=_YEAR,
            period=_PERIOD,
            revision_id="input-required",
        ),
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode(_MODELO),
        filing_year=_YEAR,
        period=_PERIOD,
        revision_id="input-required",
        name="input-required-130",
        created_at=created_at,
        updated_at=created_at,
    )


def _snapshot() -> RegistrySnapshot:
    return published_snapshot(_MODELO, filing_year=_YEAR, period=_PERIOD.registry_token)


def _missing(binding_id: str) -> ModeloWorkMissingInputError:
    engine = RegistryValidationError(
        "engine sentence",
        translated_message="errors.calc.binding_value_missing",
        context={"binding_id": binding_id, "op": "synthetic_op"},
    )
    missing = ModeloWorkMissingInputError.from_registry_error(engine)
    assert missing is not None
    return missing


def test_the_missing_input_is_registered_as_a_refusal() -> None:
    assert get_registered_error_code(ModeloWorkMissingInputError).category is ErrorCategory.REFUSED
    assert get_registered_error_code(ModeloWorkMissingInputError).code == "REFUSED_MODELO_WORK_INPUT_REQUIRED"
    assert current_error_code("ERROR_MODELO_WORK_INPUT_REQUIRED") == "REFUSED_MODELO_WORK_INPUT_REQUIRED"


def test_the_refusal_names_the_binding_and_box_and_opens_the_work_and_its_bindings(
    operation: PinnedAuthorityOperation,
) -> None:
    snapshot = _snapshot()
    boxes = snapshot_printed_boxes(operation, snapshot)
    printed = next(
        (binding.id, boxes.number(casilla_id))
        for binding in snapshot.revision.bindings
        if (casilla_id := sole_bound_casilla(snapshot.revision, binding.id)) is not None and boxes.prints(casilla_id)
    )
    binding_id, box = printed
    assert box is not None
    work_unit = _work_unit()

    refusal = input_required(_missing(binding_id), work_unit=work_unit, snapshot=snapshot, boxes=boxes)
    detail = build_operation_error_detail(refusal)

    assert detail is not None
    assert detail.error_code == "REFUSED_MODELO_WORK_INPUT_REQUIRED"
    assert detail.message_key == "application.modelo.errors.input_required"
    assert detail.refusal_words is not None
    assert "%{" not in detail.refusal_words
    assert binding_id in detail.refusal_words
    assert box in detail.refusal_words
    assert str(_YEAR) in detail.refusal_words
    assert isinstance(detail.next_step, OperationOpenWorkStepV1)
    assert detail.next_step.work_unit_id == work_unit.work_unit_id
    assert detail.precondition_verdict_json is not None
    verdict = json.loads(detail.precondition_verdict_json)
    assert verdict["action"]["action_id"] == "operator.modelo.bindings.list"
    assert verdict["failed_condition_id"] == "modelo.work.calculate.input.supplied"
    bound = {entry["argument_name"]: entry for entry in verdict["argument_bindings"]}
    assert {name: entry["value"] for name, entry in bound.items()} == {
        "modelo": _MODELO,
        "year": _YEAR,
        "period": _PERIOD.registry_token,
    }
    assert {entry["status"] for entry in bound.values()} == {ActionArgumentStatus.RESOLVED.value}


def test_an_input_no_box_prints_is_named_by_its_binding_alone(operation: PinnedAuthorityOperation) -> None:
    snapshot = _snapshot()
    boxes = snapshot_printed_boxes(operation, snapshot)

    refusal = input_required(_missing("synthetic.unprinted"), work_unit=_work_unit(), snapshot=snapshot, boxes=boxes)
    detail = build_operation_error_detail(refusal)

    assert detail is not None
    assert detail.message_key == "application.modelo.errors.input_required_unprinted"
    assert detail.refusal_words is not None
    assert "synthetic.unprinted" in detail.refusal_words
    assert "%{" not in detail.refusal_words
    assert isinstance(detail.next_step, OperationOpenWorkStepV1)


#: Declarations whose revisions read every carry kind the caller-override precedence ladder admits.
_CARRY_DECLARATIONS: tuple[tuple[str, str], ...] = (("130", "1T"), ("303", "1T"), ("100", "0A"), ("390", "0A"))


def _calculation_snapshot(operation: PinnedAuthorityOperation, modelo: str, period: str) -> RegistrySnapshot:
    """The revision the declaration calculates against, at the grade a calculation needs."""
    return operation.snapshot(modelo, filing_year=_YEAR, period=period, grade=RegistryAuthorityGrade.CALCULATION)


def _overridable_carries(operation: PinnedAuthorityOperation) -> dict[BindingSourceKind, tuple[str, str, str]]:
    """One carry the edit admission lets the operator state, per carry kind, with its modelo and period."""
    found: dict[BindingSourceKind, tuple[str, str, str]] = {}
    for modelo, period in _CARRY_DECLARATIONS:
        snapshot = _calculation_snapshot(operation, modelo, period)
        layout = operation.form_layout(modelo, snapshot.revision.id)
        for binding in snapshot.revision.bindings:
            if (
                binding.source in CALLER_OVERRIDABLE_CARRY_SOURCES
                and binding.source not in found
                and override_admitted(snapshot, binding.id, period=period, layout=layout)
            ):
                found[binding.source] = (modelo, period, binding.id)
    return found


def test_every_carry_kind_the_operator_may_state_opens_the_override_bound_to_the_work_unit_and_input(
    operation: PinnedAuthorityOperation,
) -> None:
    carries = _overridable_carries(operation)
    assert set(carries) == set(CALLER_OVERRIDABLE_CARRY_SOURCES)
    for kind, (modelo, period, binding_id) in carries.items():
        snapshot = _calculation_snapshot(operation, modelo, period)
        unit = _work_unit().model_copy(
            update={"modelo": ModeloCode(modelo), "period": Period.from_year_and_code(_YEAR, period)}
        )
        refusal = input_required(
            _missing(binding_id),
            work_unit=unit,
            snapshot=snapshot,
            boxes=snapshot_printed_boxes(operation, snapshot),
            overridable=True,
        )
        detail = build_operation_error_detail(refusal)

        assert detail is not None, kind
        assert detail.error_code == "REFUSED_MODELO_WORK_INPUT_REQUIRED"
        assert detail.refusal_words is not None
        assert "%{" not in detail.refusal_words
        assert binding_id in detail.refusal_words
        assert detail.precondition_verdict_json is not None
        verdict = json.loads(detail.precondition_verdict_json)
        assert verdict["action"]["action_id"] == "operator.modelo.work.override", kind
        assert verdict["failed_condition_id"] == "modelo.work.calculate.input.supplied"
        bound = {entry["argument_name"]: entry for entry in verdict["argument_bindings"]}
        assert bound["work_unit_id"]["value"] == unit.work_unit_id
        assert bound["binding_id"]["value"] == binding_id
        assert {bound[name]["status"] for name in ("work_unit_id", "binding_id")} == {
            ActionArgumentStatus.RESOLVED.value
        }
        # The amount is the operator's to state; the door never supplies it.
        assert bound["value"]["status"] == ActionArgumentStatus.MISSING.value


def test_a_source_the_ladder_locks_is_never_offered_as_an_override(operation: PinnedAuthorityOperation) -> None:
    snapshot = _snapshot()
    layout = operation.form_layout(_MODELO, snapshot.revision.id)
    locked = [binding.id for binding in snapshot.revision.bindings if binding.source in BUCKET_AGGREGATION_LOCK_SOURCES]
    assert locked
    assert not any(
        override_admitted(snapshot, binding_id, period=_PERIOD.registry_token, layout=layout) for binding_id in locked
    )

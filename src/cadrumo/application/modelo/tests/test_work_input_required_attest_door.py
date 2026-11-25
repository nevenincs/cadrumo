"""A carry no held earlier return supplies refuses calculation with the statement of its figure beside the override.

The Modelo 200 preceding-period turnover is read from the preceding Modelo 200.
Where the application holds none, the calculation refuses before publication and
serves the override and, after it, the filer's statement of the earlier return's
figure; where the carry is not attestable only the override is served.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from ....core.authority_grade import RegistryAuthorityGrade
from ....core.operator_action_enums import ActionConditionality
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ...operations.error_detail import build_operation_error_detail
from ...operator_actions.models import PreconditionVerdict
from ...operator_surface.action_targets import resolve_recorded_precondition_action
from ..preconditions import ATTEST_PRIOR_VALUE_ACTION_ID
from ..printed_boxes import snapshot_printed_boxes
from ..work_missing_input import ModeloWorkMissingInputError, input_required, override_admitted

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "35353535-3535-4353-8353-353535353535"
_MODELO = "200"
_PERIOD = "0A"


@pytest.fixture(scope="module")
def operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as pinned:
        yield pinned


def _turnover_carry(snapshot: RegistrySnapshot) -> str | None:
    return next((binding.id for binding in snapshot.revision.bindings if binding.zero_needs_attestation), None)


def _calculation_snapshot(operation: PinnedAuthorityOperation, year: int) -> RegistrySnapshot:
    return operation.snapshot(_MODELO, filing_year=year, period=_PERIOD, grade=RegistryAuthorityGrade.CALCULATION)


def _years(operation: PinnedAuthorityOperation) -> tuple[int, ...]:
    return tuple(
        year
        for year in operation.supported_filing_years().years
        if _turnover_carry(_calculation_snapshot(operation, year)) is not None
    )


def _work_unit(year: int) -> WorkUnit:
    created_at = datetime(year, 7, 2, tzinfo=UTC)
    period = Period.from_year_and_code(year, _PERIOD)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID, modelo=ModeloCode(_MODELO), filing_year=year, period=period, revision_id="attest-door"
        ),
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode(_MODELO),
        filing_year=year,
        period=period,
        revision_id="attest-door",
        name="attest-door-200",
        created_at=created_at,
        updated_at=created_at,
    )


def _missing(binding_id: str) -> ModeloWorkMissingInputError:
    engine = RegistryValidationError(
        "engine sentence",
        translated_message="errors.calc.binding_value_missing",
        context={"binding_id": binding_id, "op": "synthetic_op"},
    )
    missing = ModeloWorkMissingInputError.from_registry_error(engine)
    assert missing is not None
    return missing


def test_some_supported_year_declares_the_turnover_carry(operation: PinnedAuthorityOperation) -> None:
    assert _years(operation)


@pytest.mark.parametrize("attestable", [True, False])
def test_an_unstated_carry_serves_the_statement_only_when_no_earlier_return_is_held(
    operation: PinnedAuthorityOperation, attestable: bool
) -> None:
    for year in _years(operation):
        snapshot = _calculation_snapshot(operation, year)
        carry = _turnover_carry(snapshot)
        assert carry is not None
        assert override_admitted(
            snapshot, carry, period=_PERIOD, layout=operation.form_layout(_MODELO, snapshot.revision.id)
        )
        work_unit = _work_unit(year)

        refusal = input_required(
            _missing(carry),
            work_unit=work_unit,
            snapshot=snapshot,
            boxes=snapshot_printed_boxes(operation, snapshot),
            overridable=True,
            attestable=attestable,
        )
        detail = build_operation_error_detail(refusal)
        assert detail is not None
        assert detail.error_code == "REFUSED_MODELO_WORK_INPUT_REQUIRED"
        assert detail.precondition_verdict_json is not None
        verdict = json.loads(detail.precondition_verdict_json)
        assert verdict["action"]["action_id"] == "operator.modelo.work.override"
        recorded = refusal.terminal_precondition_verdict
        assert isinstance(recorded, PreconditionVerdict)
        resolved = resolve_recorded_precondition_action(recorded)
        if not attestable:
            assert resolved.alternative_actions == ()
            continue
        assert [item.action.action_id for item in resolved.alternative_actions] == [ATTEST_PRIOR_VALUE_ACTION_ID]
        statement = resolved.alternative_actions[0]
        assert statement.action.target_command_key == "modelo.work.attest_prior_value"
        assert statement.conditionality is ActionConditionality.REQUIRES_ARGUMENTS
        assert statement.missing_argument_names == ("value",)
        bound = {item.argument_name: item.value for item in statement.argument_bindings if item.value is not None}
        assert bound == {
            "work_unit_id": work_unit.work_unit_id,
            "modelo": _MODELO,
            "year": year,
            "period": _PERIOD,
            "binding_id": carry,
        }

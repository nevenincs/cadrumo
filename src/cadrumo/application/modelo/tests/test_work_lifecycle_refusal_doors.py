"""Work lookup, selector, mutation and revision-state refusals open the door of their cause."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from ....domain.modelos.work_unit import WorkUnitCatalogue
from ...cli_exception_preconditions import nested_terminal_precondition_verdict
from ...operator_actions.models import PreconditionVerdict
from ..action_errors import (
    CalculationRevisionStateError,
    ModeloRevisionNotSealedError,
    WorkUnitMutationRefusedError,
    WorkUnitNotFoundError,
)
from ..preconditions import ModeloPreconditionFailure
from ..work_address_errors import ModeloWorkSelectorContradictionError
from ..work_lifecycle_refusal_failures import (
    amendment_duplicate_failure,
    amendment_unchanged_failure,
    ceded_modelo_failure,
    selector_incoherent_failure,
)
from ..work_selection import ModeloWorkSelectorRequest, select_modelo_work_resolution

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_UNIT = "ab" * 32


def _verdict(error: BaseException) -> PreconditionVerdict:
    verdict = nested_terminal_precondition_verdict(error)
    assert verdict is not None
    return verdict


def _bound(verdict: PreconditionVerdict) -> dict[str, str]:
    return {item.argument_name: str(item.value) for item in verdict.argument_bindings if item.value is not None}


def test_an_absent_work_unit_opens_the_work_list() -> None:
    verdict = _verdict(WorkUnitNotFoundError(context={"work_unit_id": _UNIT}))

    assert verdict.action is not None
    assert verdict.action.action_id == "operator.modelo.work.list"
    assert not verdict.argument_bindings
    assert not verdict.missing_argument_names


def test_a_contradictory_selector_opens_the_work_list() -> None:
    request = ModeloWorkSelectorRequest(work_unit_id=_UNIT, bucket_id="bucket-a")
    with pytest.raises(ModeloWorkSelectorContradictionError) as raised:
        select_modelo_work_resolution(request, catalogue=WorkUnitCatalogue(), bucket_id="bucket-b")

    verdict = _verdict(raised.value)
    assert verdict.action is not None
    assert verdict.action.action_id == "operator.modelo.work.list"


def test_an_incoherent_resolution_is_terminal_and_names_no_command() -> None:
    error = ModeloWorkSelectorContradictionError("incoherent", precondition_failure=selector_incoherent_failure())

    verdict = _verdict(error)
    assert verdict.action is None
    assert verdict.no_recovery_outcome is not None
    assert verdict.no_recovery_outcome.value == "terminal"


def test_a_mutation_refused_for_a_changed_unit_opens_its_status_bound_to_it() -> None:
    verdict = _verdict(WorkUnitMutationRefusedError(context={"work_unit_id": _UNIT, "reason": "filing_baseline_stale"}))

    assert verdict.action is not None
    assert verdict.action.action_id == "operator.modelo.work.status"
    assert _bound(verdict) == {"work_unit_id": _UNIT}


def test_a_mutation_refused_without_its_unit_leaves_the_unit_to_the_operator() -> None:
    verdict = _verdict(WorkUnitMutationRefusedError("stale"))

    assert verdict.action is not None
    assert verdict.action.action_id == "operator.modelo.work.status"
    assert set(verdict.missing_argument_names) == {"work_unit_id"}


def test_a_ceded_modelo_refusal_is_terminal() -> None:
    error = WorkUnitMutationRefusedError(context={"modelo": "x"}, precondition_failure=ceded_modelo_failure("x"))

    verdict = _verdict(error)
    assert verdict.action is None
    assert verdict.no_recovery_outcome is not None
    assert verdict.no_recovery_outcome.value == "terminal"


def test_a_revision_state_refusal_opens_the_unit_revisions_bound_to_it() -> None:
    verdict = _verdict(CalculationRevisionStateError(context={"work_unit_id": _UNIT}))

    assert verdict.action is not None
    assert verdict.action.action_id == "operator.modelo.work.revisions"
    assert _bound(verdict) == {"work_unit_id": _UNIT}


def test_a_revision_state_refusal_without_its_unit_leaves_the_unit_to_the_operator() -> None:
    verdict = _verdict(CalculationRevisionStateError(context={"calculation_revision_id": "r", "state": "x"}))

    assert verdict.action is not None
    assert set(verdict.missing_argument_names) == {"work_unit_id"}


@pytest.mark.parametrize("failure", [amendment_unchanged_failure, amendment_duplicate_failure])
def test_an_amendment_that_restates_nothing_is_the_operators_decision(
    failure: Callable[[], ModeloPreconditionFailure],
) -> None:
    error = CalculationRevisionStateError(precondition_failure=failure())

    verdict = _verdict(error)
    assert verdict.action is None
    assert verdict.no_recovery_outcome is not None
    assert verdict.no_recovery_outcome.value == "operator_decision"


def test_an_unsealed_revision_keeps_the_step_its_raise_site_chose() -> None:
    error = ModeloRevisionNotSealedError("not sealed")

    assert nested_terminal_precondition_verdict(error) is None

"""Proofs for the destructive discard enrolment.

Two properties matter here that do not arise for the other C4 actions: the
approval is bound to a state the operator actually saw, and cancellation is
declared unsupported so no surface may offer it.

See Also:
    :mod:`cadrumo.entrypoints.tui.modelo.action.discard`
"""

from __future__ import annotations

import ast
import inspect
import pathlib
from datetime import UTC, datetime

import pytest

from .....application.modelo.operation_definitions import (
    MODELO_WORK_DISCARD_OPERATION_DEFINITION_ID,
    ModeloWorkDiscardRequest,
    build_modelo_work_discard_definition,
)
from .....application.operations.models import OperationRequest
from .....application.operations.registry import OperationBaselinePolicy, OperationCancellation
from ..action import discard as discard_action
from ..actions import MODELO_ACTION_DISPATCH

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_WORK_UNIT_ID = "a" * 64
_OBSERVED_AT = datetime(2026, 1, 10, tzinfo=UTC)


def _request(
    *,
    work_unit_id: str = _WORK_UNIT_ID,
    observed_name: str = "130-2026-1T",
    observed_updated_at: datetime = _OBSERVED_AT,
    actor_ref: str = "operator:test",
    reason: str | None = None,
) -> OperationRequest[ModeloWorkDiscardRequest]:
    """Build one discard request, each field defaulted and individually overridable."""
    return discard_action.build_discard_operation_request(
        work_unit_id=work_unit_id,
        observed_name=observed_name,
        observed_updated_at=observed_updated_at,
        actor_ref=actor_ref,
        reason=reason,
    )


def test_the_request_is_addressed_to_the_registered_discard_operation() -> None:
    """A request naming anything else would submit into nothing."""
    request = _request()

    assert request.definition_id == MODELO_WORK_DISCARD_OPERATION_DEFINITION_ID
    assert isinstance(request.payload, ModeloWorkDiscardRequest)
    assert request.subject_ref == _WORK_UNIT_ID


def test_the_baseline_carries_the_state_the_operator_was_actually_shown() -> None:
    """Exact approval is only exact if the baseline is the observed state.

    Passed through unchanged rather than resolved here. This is the assertion
    that a re-reading implementation would fail.
    """
    request = _request(observed_name="a name the operator saw")

    assert request.payload.baseline.name == "a name the operator saw"
    assert request.payload.baseline.observed_updated_at == _OBSERVED_AT
    assert request.payload.baseline.work_unit_id == _WORK_UNIT_ID


def test_two_approvals_of_different_observed_states_are_distinguishable() -> None:
    """Staleness must be DETECTABLE, which requires the baselines to differ.

    If the observed timestamp did not reach the payload, an approval given
    against yesterday's state would be indistinguishable from one given
    against today's, and the platform's compare-and-swap would have nothing to
    compare.
    """
    stale = _request(observed_updated_at=datetime(2026, 1, 9, tzinfo=UTC))
    fresh = _request(observed_updated_at=_OBSERVED_AT)

    assert stale.payload.baseline.observed_updated_at != fresh.payload.baseline.observed_updated_at
    assert stale.payload != fresh.payload


def test_the_action_does_not_resolve_the_baseline_for_itself() -> None:
    """A self-resolved baseline would always match and never refuse.

    Asserted on the signature: the observed values are REQUIRED parameters, so
    the function cannot be called without a caller supplying what the operator
    saw. A default, or a repository read, would make the exact-approval check
    a formality.
    """
    signature = inspect.signature(discard_action.build_discard_operation_request)

    for name in ("observed_name", "observed_updated_at"):
        parameter = signature.parameters[name]
        assert parameter.default is inspect.Parameter.empty, f"{name} must not have a default"


def test_cancellation_is_unsupported_so_no_surface_may_offer_it() -> None:
    """Read from the operation's own declaration, not restated here.

    An affordance that cannot work is worse than its absence on a destructive
    action: an operator who believes they cancelled, and did not, finds out
    from the absence of the thing they wanted to keep.
    """
    definition = build_modelo_work_discard_definition()
    assert definition.capabilities.cancellation is OperationCancellation.UNSUPPORTED

    # Matched on STRUCTURE, not spelling. An earlier version of this assertion
    # searched the source for the word "cancel" and fired on the module's own
    # docstring explaining that cancellation is unsupported -- forbidding the
    # explanation rather than the affordance. The property is that no call
    # REQUESTS cancellation, so the AST is what gets asked.
    tree = ast.parse(pathlib.Path(inspect.getfile(discard_action)).read_text(encoding="utf-8"))
    requests = [
        ast.unparse(node)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and "cancel" in ast.unparse(node.func).lower()
    ]
    assert not requests, f"the discard enrolment requests cancellation, which its operation refuses: {requests}"


def test_the_operation_declares_exact_approval() -> None:
    """The baseline this module builds is only meaningful under that policy.

    Pinned so that a change of the operation's baseline policy surfaces here,
    where the baseline is constructed, rather than as a silently weakened
    guarantee.
    """
    definition = build_modelo_work_discard_definition()

    assert definition.capabilities.baseline is OperationBaselinePolicy.EXACT_APPROVAL


def test_a_discarded_subject_does_not_land_back_on_its_own_workspace() -> None:
    """The destination is read from the dispatch table and must not be a workspace."""
    assert discard_action.DISCARD_ACTION is MODELO_ACTION_DISPATCH[MODELO_WORK_DISCARD_OPERATION_DEFINITION_ID]
    assert discard_action.DISCARD_ACTION.destroys_subject is True
    assert not discard_action.DISCARD_ACTION.result_destination.startswith("modelo.workspace.")


def test_the_module_reaches_no_lifecycle_writer() -> None:
    """The wrong path succeeds, so it is refused structurally rather than by review."""
    tree = ast.parse(pathlib.Path(inspect.getfile(discard_action)).read_text(encoding="utf-8"))

    reached: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            reached.extend(f"{node.module}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Import):
            reached.extend(alias.name for alias in node.names)

    forbidden = [name for name in reached if "work_lifecycle" in name or "discard_work_unit" in name]
    assert not forbidden, f"the discard action reaches a lifecycle writer directly: {forbidden}"


def test_submission_does_not_start_the_run() -> None:
    """A destructive run must not execute with no window observing it."""
    source = inspect.getsource(discard_action.submit_discard)

    assert "submission.submit(" in source
    assert "submission.start(" not in source, "starting belongs to the presenting modal"


def test_a_reason_is_optional_but_a_blank_one_is_refused() -> None:
    """Recording no reason and recording an empty reason are different claims.

    An empty string would read, later, as a reason that was given and lost.
    """
    assert _request().payload.reason is None
    assert _request(reason="superseded by an amendment").payload.reason == "superseded by an amendment"

    with pytest.raises(ValueError):
        _request(reason="")

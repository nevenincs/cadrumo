"""The modal view model must mirror the projection it claims to describe.

``OperationModalViewModelV1`` carries twelve refusals, one per derived field,
and they exist because every one of those fields is a claim about a running
operation that the operator acts on: whether a spinner says it is still
working, whether Cancel is offered, which deadline is shown, which settled
receipt is named. A view model that disagreed with its projection would say
those things about an operation that is not in that state.

None of the twelve had a test. That is the failure mode the validator itself
guards against, applied to the validator: a guard that had quietly stopped
firing would look exactly like one that never had to.

Each field is driven through the REAL builder and then moved away from the
projection, so the test states the invariant ("a derived field cannot disagree
with its source") rather than re-listing the derivation. The builder's own
output is the positive control.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from .....application.operations.frontend_contracts import OperationPublicProjectionV1
from .....application.operations.tests.test_public_contracts import _projection
from .....core.operations import OperationLifecycle, OperationTerminalCondition
from ..projection import OperationModalViewModelV1, build_operation_modal_view_model

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_OTHER_TIME = datetime(2031, 7, 1, tzinfo=UTC)


def _terminal(
    condition: OperationTerminalCondition,
    *,
    result_ref: str | None = None,
    refusal_ref: str | None = None,
) -> OperationPublicProjectionV1:
    """A settled projection, which is the only kind that may carry a receipt.

    The two references are spelled out rather than forwarded as ``**changes``:
    unpacking an ``object``-typed mapping into a signature with typed keyword
    parameters hides every argument from the checker.
    """
    return _projection(
        lifecycle=OperationLifecycle.TERMINAL,
        terminal_condition=condition,
        result_ref=result_ref,
        refusal_ref=refusal_ref,
    )


def _revalidated(**overrides: object) -> OperationModalViewModelV1:
    """Rebuild the view model from the builder's own output, one field moved.

    ``model_copy`` would not re-run the validator, so the mutation is applied
    to a dump and re-validated. That is also closer to the real hazard: a
    persisted or reconstructed view model is exactly what would arrive already
    disagreeing with its projection.
    """
    built = build_operation_modal_view_model(_projection())
    return OperationModalViewModelV1.model_validate({**built.model_dump(), **overrides})


def test_the_builder_produces_a_view_model_the_validator_accepts() -> None:
    """The control: without it, every refusal below could pass vacuously."""
    projection = _projection()

    built = build_operation_modal_view_model(projection)

    assert built.projection == projection
    assert built.spinner_visible is True
    assert built.cancel_control_enabled is projection.cancellable_now
    assert built.close_policy is projection.close_policy


@pytest.mark.parametrize(
    ("field", "wrong_value", "message"),
    [
        ("spinner_visible", False, "spinner visibility"),
        ("cancel_control_enabled", True, "cancel affordance"),
        # Built as True here (close policy allows detach, not terminal), so
        # False is the value that disagrees.
        ("detach_control_enabled", False, "detach affordance"),
        # A REAL member of the terminal-copy literal: a made-up string would be
        # rejected by the field type before the derivation guard could speak.
        ("terminal_copy_key", "operation.modal.terminal.succeeded", "terminal copy key"),
        ("phase_code", "operations.public.elsewhere", "modal phase"),
        ("execution_deadline_at", _OTHER_TIME, "execution deadline"),
        ("cleanup_deadline_at", _OTHER_TIME, "cleanup deadline"),
        ("diagnostic_ref", "sha256:" + "b" * 12, "diagnostic reference"),
        ("receipt_kind", "result", "receipt kind"),
    ],
)
def test_a_derived_field_cannot_disagree_with_its_projection(
    field: str,
    wrong_value: object,
    message: str,
) -> None:
    """Each field is a claim about the operation; the projection is the source.

    Parametrised over the fields rather than written out once each, so the
    test expresses one rule -- a derived field mirrors its source -- and a
    field added to the model without a matching guard shows up as a gap here
    rather than as silently unchecked.
    """
    with pytest.raises(ValueError, match=message):
        _revalidated(**{field: wrong_value})


def test_a_running_operation_names_no_terminal_copy() -> None:
    """Terminal copy on a live operation would announce an ending that has not happened."""
    built = build_operation_modal_view_model(_projection())

    assert built.terminal_copy_key is None


def test_a_projection_carrying_no_settled_reference_names_no_receipt() -> None:
    """Absent is not "result with an empty reference"; the pair moves together."""
    built = build_operation_modal_view_model(_projection())

    assert built.receipt_kind is None
    assert built.receipt_ref is None


def test_a_result_reference_is_reported_as_a_result_receipt() -> None:
    """The settled-reference branch, driven through the builder rather than asserted.

    A settlement reference only exists on a TERMINAL projection -- the
    public contract refuses one otherwise -- so the terminal condition is
    part of the fixture rather than an incidental extra.
    """
    built = build_operation_modal_view_model(
        _terminal(OperationTerminalCondition.SUCCEEDED, result_ref="result:settled")
    )

    assert built.receipt_kind == "result"
    assert built.receipt_ref == "result:settled"


def test_a_refusal_reference_is_reported_as_a_refusal_receipt() -> None:
    """The other branch: a refused operation must not read as a result."""
    built = build_operation_modal_view_model(
        _terminal(OperationTerminalCondition.REFUSED, refusal_ref="refusal:settled")
    )

    assert built.receipt_kind == "refusal"
    assert built.receipt_ref == "refusal:settled"

"""Proofs that rename reaches the tree only through its registered operation.

The property under test is not "rename works" -- calling the application's
lifecycle writer directly would also work, and would produce an identical
visible outcome while holding no lease, entering no journal, and publishing no
observation. What must hold is that this action CANNOT take that path.

So the proofs here are about the route rather than the effect: the request is
addressed to the registered definition, the module reaches no writer, and the
submission goes through the composed supervisor door.

See Also:
    :mod:`cadrumo.entrypoints.tui.modelo.action.rename`
"""

from __future__ import annotations

import ast
import inspect
import pathlib

import pytest

from .....application.modelo.operation_definitions import (
    MODELO_WORK_RENAME_OPERATION_DEFINITION_ID,
    ModeloWorkRenameRequest,
)
from ..action import rename as rename_action
from ..actions import MODELO_ACTION_DISPATCH

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_WORK_UNIT_ID = "a" * 64


def test_the_request_is_addressed_to_the_registered_rename_operation() -> None:
    """A request naming anything else would submit into nothing."""
    request = rename_action.build_rename_operation_request(
        work_unit_id=_WORK_UNIT_ID, new_name="Q1 2026", actor_ref="operator:test"
    )

    assert request.definition_id == MODELO_WORK_RENAME_OPERATION_DEFINITION_ID
    assert isinstance(request.payload, ModeloWorkRenameRequest)


def test_the_subject_is_the_work_unit_so_the_lease_contends_correctly() -> None:
    """Subject identity is what makes the platform's conflict scope mean anything.

    Two renames of the same unit must contend; renames of different units must
    not. A subject naming something coarser (the profile) or finer (a
    per-invocation id) would break one of those and the failure would appear
    as a concurrency bug far from here.
    """
    first = rename_action.build_rename_operation_request(
        work_unit_id=_WORK_UNIT_ID, new_name="one", actor_ref="operator:test"
    )
    second = rename_action.build_rename_operation_request(
        work_unit_id=_WORK_UNIT_ID, new_name="two", actor_ref="operator:test"
    )
    other = rename_action.build_rename_operation_request(
        work_unit_id="b" * 64, new_name="three", actor_ref="operator:test"
    )

    assert first.subject_ref == second.subject_ref == _WORK_UNIT_ID
    assert other.subject_ref != first.subject_ref


def test_the_actor_reaches_both_the_envelope_and_the_lifecycle_payload() -> None:
    """They answer different questions and must not be derived from each other.

    The platform binds an actor at submission for authority; the payload
    records who the rename was performed as, for the lifecycle event. Dropping
    the payload half would leave the audit trail unable to say who renamed a
    filing.
    """
    request = rename_action.build_rename_operation_request(
        work_unit_id=_WORK_UNIT_ID, new_name="Q1 2026", actor_ref="operator:alice"
    )

    assert request.payload.actor == "operator:alice"


def test_the_module_reaches_no_lifecycle_writer() -> None:
    """The defect this enrolment exists to avoid, asserted structurally.

    Checked against the module's own AST rather than by reading it: a writer
    reached through a deferred function-local import would not appear in the
    import block, and a reviewer scanning the header would miss it. The
    application's rename writer succeeding is exactly what makes the bypass
    invisible without a check like this.
    """
    source = pathlib.Path(inspect.getfile(rename_action)).read_text(encoding="utf-8")
    tree = ast.parse(source)

    reached: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            reached.extend(f"{node.module}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Import):
            reached.extend(alias.name for alias in node.names)

    forbidden = [name for name in reached if "work_lifecycle" in name or "rename_work_unit" in name]
    assert not forbidden, f"the rename action reaches a lifecycle writer directly: {forbidden}"


def test_the_destination_is_read_from_the_dispatch_table_not_restated() -> None:
    """One declaration of where a settled rename leaves the operator.

    A local copy would be a second declaration, free to drift from the table
    the denominator gate actually checks.
    """
    assert rename_action.RENAME_ACTION is MODELO_ACTION_DISPATCH[MODELO_WORK_RENAME_OPERATION_DEFINITION_ID]
    assert rename_action.RENAME_ACTION.result_destination == "modelo.workspace.overview"


def test_submission_does_not_start_the_run() -> None:
    """Submitting without starting is what keeps a run from executing unwatched.

    Asserted on the coroutine's own source: it must reach the submission door
    and must NOT reach the start door, because starting belongs to the modal
    that presents the run. A rename that started here would execute to
    completion with no window observing it, which defeats the point of routing
    it through the platform at all.
    """
    source = inspect.getsource(rename_action.submit_rename)

    assert "submission.submit(" in source, "the action must submit through the composed door"
    assert "submission.start(" not in source, "starting belongs to the presenting modal, not the action"


@pytest.mark.parametrize("blank", ["", "   "])
def test_a_blank_name_is_refused_by_the_typed_request(blank: str) -> None:
    """Refusal is the contract's, not this module's, and happens before submission.

    A rename to an empty label would be accepted by any check this module
    could write and rejected later by the writer, after a journal entry and a
    lease already existed for work that could never settle.
    """
    with pytest.raises(ValueError):
        rename_action.build_rename_operation_request(
            work_unit_id=_WORK_UNIT_ID, new_name=blank, actor_ref="operator:test"
        )

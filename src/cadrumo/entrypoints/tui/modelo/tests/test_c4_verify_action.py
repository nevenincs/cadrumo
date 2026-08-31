"""Proofs for the verify enrolment.

The property that distinguishes this action is a REPLAY-SAFETY one: the
taxpayer profile must not reach the journalled request, so a replay cannot
verify against circumstances the taxpayer has since changed.

See Also:
    :mod:`cadrumo.entrypoints.tui.modelo.action.verify`
"""

from __future__ import annotations

import ast
import inspect
import pathlib

import pytest

from .....application.modelo.operation_definitions import (
    MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
    ModeloWorkVerifyRequest,
    build_modelo_work_verify_definition,
)
from .....application.modelo.workspace_models import ModeloWorkspaceCapabilityName
from .....application.operations.registry import OperationCancellation
from ..action import verify as verify_action
from ..actions import MODELO_ACTION_DISPATCH

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_WORK_UNIT_ID = "a" * 64
_REVISION_ID = "rev-2026-1T-0001"


def test_the_request_is_addressed_to_the_registered_verify_operation() -> None:
    """A request naming anything else would submit into nothing."""
    request = verify_action.build_verify_operation_request(
        work_unit_id=_WORK_UNIT_ID, calculation_revision_id=_REVISION_ID, actor_ref="operator:test"
    )

    assert request.definition_id == MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID
    assert isinstance(request.payload, ModeloWorkVerifyRequest)
    assert request.payload.calculation_revision_id == _REVISION_ID


def test_the_subject_is_the_work_unit_and_not_the_revision() -> None:
    """Subject identity decides what contends, and the two are not interchangeable.

    Two verifications of different revisions of the SAME unit must serialise,
    because they read the same evolving state. Keying the subject on the
    revision would let them run concurrently against a unit moving underneath
    both.
    """
    first = verify_action.build_verify_operation_request(
        work_unit_id=_WORK_UNIT_ID, calculation_revision_id="rev-a", actor_ref="operator:test"
    )
    second = verify_action.build_verify_operation_request(
        work_unit_id=_WORK_UNIT_ID, calculation_revision_id="rev-b", actor_ref="operator:test"
    )

    assert first.subject_ref == second.subject_ref == _WORK_UNIT_ID
    assert first.payload.calculation_revision_id != second.payload.calculation_revision_id


def test_the_taxpayer_profile_never_reaches_the_journalled_request() -> None:
    """The replay-safety property, asserted on the payload's whole field set.

    The gates are evaluated against a profile resolved at EXECUTION from live
    state. A profile carried in the request would be frozen into the journal,
    and a replay would then produce a verdict that was true when submitted and
    is not true now -- on the one surface whose job is telling an operator
    whether their filing is sound.

    Asserted over every declared field rather than by naming one suspect, so a
    profile arriving later under any spelling fails here.
    """
    fields = set(ModeloWorkVerifyRequest.model_fields)

    assert fields == {"calculation_revision_id", "actor"}, (
        f"the verify request's field set changed; check nothing taxpayer-scoped was added: {sorted(fields)}"
    )


def test_cancellation_is_cooperative_unlike_the_destructive_action() -> None:
    """A surface MAY offer to cancel a verification, and that is a real difference.

    Read from the operation rather than restated. Verification reads and
    reports, so abandoning one part-way leaves nothing half-written -- which
    is precisely why discard, whose operation declares cancellation
    unsupported, must not offer the same affordance.
    """
    definition = build_modelo_work_verify_definition()

    assert definition.capabilities.cancellation is OperationCancellation.COOPERATIVE


def test_the_action_is_gated_on_the_verification_readiness_capability() -> None:
    """The gate is the workspace's own, read from the dispatch row.

    Offering verification on a workspace whose projection never measured
    readiness would invite the operator to act on an answer the admission
    cannot give.
    """
    assert verify_action.VERIFY_ACTION is MODELO_ACTION_DISPATCH[MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID]
    assert verify_action.VERIFY_ACTION.capability is ModeloWorkspaceCapabilityName.VERIFICATION_READINESS


def test_a_settled_verification_lands_on_the_verification_destination() -> None:
    """Findings belong on the destination that renders them, not the overview."""
    assert verify_action.VERIFY_ACTION.result_destination == "modelo.workspace.verification"
    assert verify_action.VERIFY_ACTION.destroys_subject is False


def test_the_module_reaches_no_verification_writer() -> None:
    """The wrong path succeeds, so it is refused structurally rather than by review."""
    tree = ast.parse(pathlib.Path(inspect.getfile(verify_action)).read_text(encoding="utf-8"))

    reached: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            reached.extend(f"{node.module}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Import):
            reached.extend(alias.name for alias in node.names)

    forbidden = [name for name in reached if "verification" in name.lower() and "workspace_models" not in name]
    assert not forbidden, f"the verify action reaches a verification writer directly: {forbidden}"


def test_submission_does_not_start_the_run() -> None:
    """Starting belongs to the presenting modal, which also owns cancellation here."""
    source = inspect.getsource(verify_action.submit_verify)

    assert "submission.submit(" in source
    assert "submission.start(" not in source


@pytest.mark.parametrize("blank", ["", "   "])
def test_a_blank_revision_id_is_refused_before_submission(blank: str) -> None:
    """A verification of nothing would journal and lease work that cannot settle."""
    with pytest.raises(ValueError):
        verify_action.build_verify_operation_request(
            work_unit_id=_WORK_UNIT_ID, calculation_revision_id=blank, actor_ref="operator:test"
        )

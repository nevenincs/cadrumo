"""Enrolment of modelo verification as a C4 action.

Verify is gated on the workspace's own VERIFICATION_READINESS capability, and
that gate is read from the dispatch row rather than decided here. A surface
offering verification on a workspace whose projection never measured readiness
would be inviting the operator to act on an answer the admission cannot give.

TWO THINGS SEPARATE VERIFY FROM THE OTHER ENROLMENTS.

The request carries the calculation revision and NOTHING ABOUT THE TAXPAYER.
The profile the gates evaluate against is resolved at execution from live
state, deliberately, so a request replayed later cannot verify against a
profile the taxpayer has since changed. Carrying the profile here would make a
journalled request a frozen copy of a taxpayer's circumstances, and a replay
would then produce a verdict that was true once and is not true now -- on a
surface whose whole purpose is telling an operator whether their filing is
sound.

And cancellation is COOPERATIVE rather than unsupported, so unlike discard a
surface MAY offer to cancel a verification in flight. Verification reads and
reports; abandoning one part-way leaves nothing half-written.

See Also:
    :mod:`cadrumo.entrypoints.tui.modelo.action.discard`
        The contrasting case, where cancellation is unsupported.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .....application.modelo.operation_definitions import (
    MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
    ModeloWorkVerifyRequest,
)
from .....application.operations.registry import OperationRequest
from ..actions import MODELO_ACTION_DISPATCH

if TYPE_CHECKING:
    from .....application.operations.composition import OperationComposedServices
    from ...operations.controller import OperationController

__all__ = [
    "VERIFY_ACTION",
    "build_verify_operation_request",
    "submit_verify",
]


VERIFY_ACTION = MODELO_ACTION_DISPATCH[MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID]
"""This action's dispatch row, carrying the capability that governs it."""


def build_verify_operation_request(
    *,
    work_unit_id: str,
    calculation_revision_id: str,
    actor_ref: str,
) -> OperationRequest[ModeloWorkVerifyRequest]:
    """Build the typed submission for one verification.

    The subject is the WORK UNIT while the payload names the REVISION, and the
    two are not interchangeable. Subject identity decides what contends: two
    verifications of different revisions of the same unit should serialise,
    because they read the same evolving state. Keying the subject on the
    revision instead would let them run concurrently and report against a unit
    that moved underneath both.
    """
    return OperationRequest(
        definition_id=MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
        subject_ref=work_unit_id,
        payload=ModeloWorkVerifyRequest(
            calculation_revision_id=calculation_revision_id,
            actor=actor_ref,
        ),
    )


async def submit_verify(
    services: OperationComposedServices,
    *,
    work_unit_id: str,
    calculation_revision_id: str,
    actor_ref: str,
) -> OperationController:
    """Submit the verification and return the controller bound to it.

    Submits without starting, as the sibling enrolments do: the presenting
    modal owns starting, observing, and -- for this action specifically -- the
    operator's cancellation, which its operation supports.
    """
    from ...operations.controller import OperationController

    submission = await services.submission.submit(
        build_verify_operation_request(
            work_unit_id=work_unit_id,
            calculation_revision_id=calculation_revision_id,
            actor_ref=actor_ref,
        ),
        actor_ref=actor_ref,
    )
    return OperationController(services=services, submission=submission, actor_ref=actor_ref)

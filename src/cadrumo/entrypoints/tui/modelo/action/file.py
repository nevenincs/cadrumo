"""Enrolment of local modelo filing as a C4 action.

FILING HERE IS LOCAL AND ENDS IN A HUMAN HANDOFF. This application never
submits to the AEAT sede. It builds, validates, verifies and records what the
taxpayer intends to declare, and a person files it outside the application.
That is not a limitation awaiting removal -- it is the standing prohibition on
live submission, and this action exists inside it.

The consequence that matters for correctness: what this records is NOT official
evidence. An observation produced by this path is stamped ``app_filing``, which
:meth:`ObservationSourceKind.is_official_aeat` answers ``False`` for, while the
three official kinds are all AEAT-sourced -- a stamped justificante, a live
sede capture, a CSV register entry. Treating a local filing as official would
let a downstream cross-period gate believe the AEAT accepted something the AEAT
has never seen.

APPROVAL NAMES BOTH THE REVISION AND THE VERIFICATION THAT JUSTIFIED IT.
Filing is a durable declaration of intent, so approving "this revision" is not
enough: a revision re-verified since the operator looked at it is a different
fact, and filing on the strength of the older look would record an intent
nobody formed. Both ids are required parameters here for the same reason the
discard baseline is -- a function that resolved either for itself would produce
an approval that always matches and never refuses.

See Also:
    :mod:`cadrumo.entrypoints.tui.modelo.action.verify`
        The action that produces the verification report this one approves.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .....application.modelo.operation_definitions import (
    MODELO_WORK_FILE_OPERATION_DEFINITION_ID,
    ModeloWorkFileApproval,
    ModeloWorkFileRequest,
)
from .....application.operations.registry import OperationRequest
from ..actions import MODELO_ACTION_DISPATCH

if TYPE_CHECKING:
    from .....application.operations.composition import OperationComposedServices
    from .....core.payment_election import PaymentElection
    from .....core.refund_election import RefundElection
    from ...operations.controller import OperationController

__all__ = [
    "FILE_ACTION",
    "build_file_operation_request",
    "submit_file",
]


FILE_ACTION = MODELO_ACTION_DISPATCH[MODELO_WORK_FILE_OPERATION_DEFINITION_ID]
"""This action's dispatch row, carrying the filing-readiness capability."""


def build_file_operation_request(
    *,
    work_unit_id: str,
    calculation_revision_id: str,
    verification_report_id: str,
    actor_ref: str,
    refund_election: RefundElection | None = None,
    payment_election: PaymentElection | None = None,
    notes: str | None = None,
) -> OperationRequest[ModeloWorkFileRequest]:
    """Build the typed submission for one local filing.

    The elections are passed through only when the operator chose one. Leaving
    them ``None`` lets the request type's own declared defaults apply, rather
    than this module restating them -- a second copy of a default is a second
    place for it to be wrong, and these two decide whether a refund is
    compensated or paid out.
    """
    elections: dict[str, object] = {}
    if refund_election is not None:
        elections["refund_election"] = refund_election
    if payment_election is not None:
        elections["payment_election"] = payment_election

    return OperationRequest(
        definition_id=MODELO_WORK_FILE_OPERATION_DEFINITION_ID,
        subject_ref=work_unit_id,
        payload=ModeloWorkFileRequest(
            approval=ModeloWorkFileApproval(
                calculation_revision_id=calculation_revision_id,
                verification_report_id=verification_report_id,
            ),
            notes=notes,
            actor=actor_ref,
            **elections,  # type: ignore[arg-type]
        ),
    )


async def submit_file(
    services: OperationComposedServices,
    *,
    work_unit_id: str,
    calculation_revision_id: str,
    verification_report_id: str,
    actor_ref: str,
    refund_election: RefundElection | None = None,
    payment_election: PaymentElection | None = None,
    notes: str | None = None,
) -> OperationController:
    """Submit the local filing and return the controller bound to it.

    Submits without starting, as the sibling enrolments do.
    """
    from ...operations.controller import OperationController

    submission = await services.submission.submit(
        build_file_operation_request(
            work_unit_id=work_unit_id,
            calculation_revision_id=calculation_revision_id,
            verification_report_id=verification_report_id,
            actor_ref=actor_ref,
            refund_election=refund_election,
            payment_election=payment_election,
            notes=notes,
        ),
        actor_ref=actor_ref,
    )
    return OperationController(services=services, submission=submission, actor_ref=actor_ref)

"""Enrolment of the modelo work-unit rename as a C4 action.

Rename reaches the tree through exactly one path: the REGISTERED
``modelo.work.rename`` operation, submitted through the composed supervisor and
driven by the shared :class:`OperationController`. It never calls
``rename_work_unit`` -- the application's lifecycle writer -- directly.

That distinction is the whole of this module's value. Calling the writer would
succeed, rename the unit, and produce the same visible outcome, while the run
held no lease, entered no journal, could not be cancelled, could not be resumed
after a crash, and published no observation any surface could watch. A live
operator path executing outside the platform that governs it is the defect
W07.P16.S340 records against the spreadsheet export; this module exists so the
rename action does not repeat it.

NOTHING HERE PRESENTS A MODAL OR OWNS A SCREEN. Presentation is
:func:`present_operation_modal`'s job and the controller is the shared one, so
this module contributes only the two things that are rename-specific: building
the typed request, and naming where a settled rename leaves the operator.

See Also:
    :mod:`cadrumo.entrypoints.tui.operations.facade`
        The single door for presenting a bound operation.
    :mod:`cadrumo.entrypoints.tui.modelo.actions`
        The dispatch row this action's destination comes from.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .....application.modelo.operation_definitions import (
    MODELO_WORK_RENAME_OPERATION_DEFINITION_ID,
    ModeloWorkRenameRequest,
)
from .....application.operations.registry import OperationRequest
from ..actions import MODELO_ACTION_DISPATCH

if TYPE_CHECKING:
    from .....application.operations.composition import OperationComposedServices
    from ...operations.controller import OperationController

__all__ = [
    "RENAME_ACTION",
    "build_rename_operation_request",
    "submit_rename",
]


RENAME_ACTION = MODELO_ACTION_DISPATCH[MODELO_WORK_RENAME_OPERATION_DEFINITION_ID]
"""This action's dispatch row, read from the closed table rather than restated.

Reading it here means the destination an operator lands on after a rename is
declared in exactly one place. A local copy would be a second declaration free
to disagree with the table the denominator gate checks.
"""


def build_rename_operation_request(
    *,
    work_unit_id: str,
    new_name: str,
    actor_ref: str,
) -> OperationRequest[ModeloWorkRenameRequest]:
    """Build the typed submission for one rename.

    The subject is the work unit, which is what makes concurrent renames of
    DIFFERENT units independent while two renames of the SAME unit contend --
    the platform's conflict scope is keyed on the subject, so naming it
    correctly here is what makes the lease mean anything.

    ``actor_ref`` is carried on both the envelope and the payload because they
    answer different questions: the platform binds an actor at submission for
    authority, and the payload records who the rename was performed as for the
    lifecycle event. Deriving one from the other would couple an audit fact to
    a transport detail.
    """
    return OperationRequest(
        definition_id=MODELO_WORK_RENAME_OPERATION_DEFINITION_ID,
        subject_ref=work_unit_id,
        payload=ModeloWorkRenameRequest(
            work_unit_id=work_unit_id,
            new_name=new_name,
            actor=actor_ref,
        ),
    )


async def submit_rename(
    services: OperationComposedServices,
    *,
    work_unit_id: str,
    new_name: str,
    actor_ref: str,
) -> OperationController:
    """Submit the rename and return the controller bound to that submission.

    Submits without starting. The caller hands the returned controller to
    :func:`present_operation_modal`, which owns starting, observing and the
    operator's detach choice -- so a surface cannot accidentally run a rename
    to completion with no window watching it.
    """
    from ...operations.controller import OperationController

    submission = await services.submission.submit(
        build_rename_operation_request(
            work_unit_id=work_unit_id,
            new_name=new_name,
            actor_ref=actor_ref,
        ),
        actor_ref=actor_ref,
    )
    return OperationController(services=services, submission=submission, actor_ref=actor_ref)

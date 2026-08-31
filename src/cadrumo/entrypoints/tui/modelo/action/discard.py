"""Enrolment of the modelo work-unit discard as a destructive C4 action.

Discard differs from every other action in this cohort in two ways the surface
must respect rather than paper over.

FIRST, IT IS EXACT-APPROVAL. The registered operation declares
``OperationBaselinePolicy.EXACT_APPROVAL``, and the request carries a
:class:`ModeloWorkDiscardBaseline` holding the unit's name and
``observed_updated_at`` AS THE OPERATOR SAW THEM. That is not redundant
addressing: it is the compare-and-swap that makes an approval specific to a
state. If the unit changed between the operator reading it and approving the
discard, the approval was given for something that no longer exists, and the
platform refuses. Re-reading the unit here to fill the baseline would defeat
it exactly -- the values would always match, the check would always pass, and
the operator would be recorded as approving a state they never saw.

SECOND, CANCELLATION IS UNSUPPORTED, declared on the operation itself. A
surface must not offer to cancel a discard. An affordance that cannot work is
worse than its absence on a destructive action specifically: an operator who
believes they cancelled, and did not, learns otherwise only from the absence
of the thing they were trying to keep.

Like the rename enrolment, this reaches the registered operation and never the
lifecycle writer -- see that module for why the wrong path is dangerous
precisely because it succeeds.

See Also:
    :mod:`cadrumo.entrypoints.tui.modelo.action.rename`
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .....application.modelo.operation_definitions import (
    MODELO_WORK_DISCARD_OPERATION_DEFINITION_ID,
    ModeloWorkDiscardBaseline,
    ModeloWorkDiscardRequest,
)
from .....application.operations.registry import OperationRequest
from ..actions import MODELO_ACTION_DISPATCH

if TYPE_CHECKING:
    from datetime import datetime

    from .....application.operations.composition import OperationComposedServices
    from ...operations.controller import OperationController

__all__ = [
    "DISCARD_ACTION",
    "build_discard_operation_request",
    "submit_discard",
]


DISCARD_ACTION = MODELO_ACTION_DISPATCH[MODELO_WORK_DISCARD_OPERATION_DEFINITION_ID]
"""This action's dispatch row, including the destination a settled discard lands on.

Read from the closed table rather than restated. The destination matters more
here than elsewhere: a discarded unit has no workspace to return to, so the row
deliberately does not name one.
"""


def build_discard_operation_request(
    *,
    work_unit_id: str,
    observed_name: str,
    observed_updated_at: datetime,
    actor_ref: str,
    reason: str | None = None,
) -> OperationRequest[ModeloWorkDiscardRequest]:
    """Build the typed submission for one discard, from OBSERVED state.

    ``observed_name`` and ``observed_updated_at`` must be the values the
    operator was shown when they approved, passed through from the surface
    unchanged. They are parameters rather than something this function reads
    for itself, and that is the point: a function that resolved them would
    produce a baseline matching the tree by construction, turning the
    platform's exact-approval check into a formality that can never refuse.
    """
    return OperationRequest(
        definition_id=MODELO_WORK_DISCARD_OPERATION_DEFINITION_ID,
        subject_ref=work_unit_id,
        payload=ModeloWorkDiscardRequest(
            baseline=ModeloWorkDiscardBaseline(
                work_unit_id=work_unit_id,
                name=observed_name,
                observed_updated_at=observed_updated_at,
            ),
            reason=reason,
            actor=actor_ref,
        ),
    )


async def submit_discard(
    services: OperationComposedServices,
    *,
    work_unit_id: str,
    observed_name: str,
    observed_updated_at: datetime,
    actor_ref: str,
    reason: str | None = None,
) -> OperationController:
    """Submit the discard and return the controller bound to that submission.

    Submits without starting, as the rename enrolment does: the presenting
    modal owns starting and observing, so a destructive run cannot execute
    with no window watching it.
    """
    from ...operations.controller import OperationController

    submission = await services.submission.submit(
        build_discard_operation_request(
            work_unit_id=work_unit_id,
            observed_name=observed_name,
            observed_updated_at=observed_updated_at,
            actor_ref=actor_ref,
            reason=reason,
        ),
        actor_ref=actor_ref,
    )
    return OperationController(services=services, submission=submission, actor_ref=actor_ref)

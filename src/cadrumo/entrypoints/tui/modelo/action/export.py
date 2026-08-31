"""Enrolment of the modelo fichero export as a C4 action.

NOT THE SPREADSHEET EXPORT. This is the registered ``modelo.export``
operation, which writes the official fichero artefact. The Google Sheets
export is a separate registered operation (``export.google-sheets``) reached
from the CLI, and it is the one currently executing OUTSIDE the supervisor --
a defect recorded against the architecture lane. Conflating the two would
attribute that bypass to this action, which does not have it: this enrolment
submits through the composed supervisor like its siblings.

WHAT THE REQUEST DOES NOT CARRY IS THE POINT. It names the revision and the
operator's chosen destination, and the EXPORTED BYTES NEVER ENTER IT -- nor the
result. An operation request is journalled, and a filing artefact is the most
sensitive thing this application produces: a taxpayer's complete declared
position. Putting the bytes in the request would copy them out of the encrypted
store and into the operations journal, which is a different store with a
different lifetime. The path is journalled because a location is not content.

Cancellation is UNSUPPORTED on this operation, so no surface may offer it --
the same discipline the discard enrolment follows, and for the same reason: a
half-written fichero is worse than one the operator waited for.

See Also:
    :mod:`cadrumo.entrypoints.tui.modelo.action.file`
        The local filing this export renders an artefact for.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .....application.modelo.operation_definitions import (
    MODELO_EXPORT_OPERATION_DEFINITION_ID,
    ModeloExportRequest,
)
from .....application.operations.registry import OperationRequest
from ..actions import MODELO_ACTION_DISPATCH

if TYPE_CHECKING:
    from .....application.operations.composition import OperationComposedServices
    from ...operations.controller import OperationController

__all__ = [
    "EXPORT_ACTION",
    "build_export_operation_request",
    "submit_export",
]


EXPORT_ACTION = MODELO_ACTION_DISPATCH[MODELO_EXPORT_OPERATION_DEFINITION_ID]
"""This action's dispatch row, carrying the export-readiness capability."""


def build_export_operation_request(
    *,
    work_unit_id: str,
    calculation_revision_id: str,
    output_path: str,
    actor_ref: str,
) -> OperationRequest[ModeloExportRequest]:
    """Build the typed submission for one fichero export.

    The subject is the WORK UNIT rather than the revision, so two exports of
    the same unit serialise. They write artefacts derived from the same
    evolving state, and letting them run concurrently would produce two files
    whose relative currency nobody could establish afterwards.
    """
    return OperationRequest(
        definition_id=MODELO_EXPORT_OPERATION_DEFINITION_ID,
        subject_ref=work_unit_id,
        payload=ModeloExportRequest(
            calculation_revision_id=calculation_revision_id,
            output_path=output_path,
            actor=actor_ref,
        ),
    )


async def submit_export(
    services: OperationComposedServices,
    *,
    work_unit_id: str,
    calculation_revision_id: str,
    output_path: str,
    actor_ref: str,
) -> OperationController:
    """Submit the export and return the controller bound to it.

    Submits without starting, as the sibling enrolments do.
    """
    from ...operations.controller import OperationController

    submission = await services.submission.submit(
        build_export_operation_request(
            work_unit_id=work_unit_id,
            calculation_revision_id=calculation_revision_id,
            output_path=output_path,
            actor_ref=actor_ref,
        ),
        actor_ref=actor_ref,
    )
    return OperationController(services=services, submission=submission, actor_ref=actor_ref)

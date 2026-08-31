"""Enrolment of modelo amendment as a distinct C4 action.

Amendment is not a second kind of edit. Every other action in this cohort
operates on a work unit the operator still holds; an amendment corrects a
return that has ALREADY BEEN FILED with the tax authority, so it is addressed
to a FILING RECORD rather than a work unit. The baseline supplies the full
casilla map of what was filed, and the overrides replace only what changed.

THREE THINGS THE CONTRACT REQUIRES THAT NO SIBLING DOES, each carried through
here rather than softened:

A REASON IS MANDATORY. An amendment is a declaration to the tax authority that
a previously filed figure was wrong. Discard's reason is optional because
abandoning local work owes nobody an explanation; this one does not have that
luxury, and a correction with no stated reason is not something an operator
should be able to file.

AT LEAST ONE OVERRIDE. An amendment with no corrections is not an amendment --
it is a re-filing of the same numbers, which would tell the authority a figure
changed when none did.

VALUES CROSS AS EXACT CHARACTERS. An override's value is a pattern-checked
string rather than a Decimal, because a Decimal accepts number-or-string and
emits string, so a journalled request would not round-trip to what the operator
typed. On a correction to a filed return, the digits are the whole content.

THE AMEND WIZARD IS A DIFFERENT ACTION AND IS NOT REPLACED HERE.
``modelo.work.amend_wizard`` stays FLOW_OWNED, owned by the guided-flow
renderer; this module enrols ``modelo.work.amend``, which is a separate
registered operation. Enrolling one does not assign the other a disposition.

See Also:
    :mod:`cadrumo.entrypoints.tui.modelo.action.file`
        The local filing an amendment eventually corrects the record of.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .....application.modelo.operation_definitions import (
    MODELO_WORK_AMEND_OPERATION_DEFINITION_ID,
    ModeloWorkAmendBaseline,
    ModeloWorkAmendOverride,
    ModeloWorkAmendRequest,
)
from .....application.operations.registry import OperationRequest
from ..actions import MODELO_ACTION_DISPATCH

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .....application.operations.composition import OperationComposedServices
    from .....domain.modelos.calculation_revision_amendment import (
        CalculationRevisionAmendmentKind,
        M303RectificativaMotive,
    )
    from ...operations.controller import OperationController

__all__ = [
    "AMEND_ACTION",
    "build_amend_operation_request",
    "submit_amend",
]


AMEND_ACTION = MODELO_ACTION_DISPATCH[MODELO_WORK_AMEND_OPERATION_DEFINITION_ID]
"""This action's dispatch row."""


def build_amend_operation_request(
    *,
    from_filing_record_id: str,
    amendment_kind: CalculationRevisionAmendmentKind,
    overrides: Mapping[str, str],
    reason: str,
    actor_ref: str,
    m303_rectificativa_motive: M303RectificativaMotive | None = None,
) -> OperationRequest[ModeloWorkAmendRequest]:
    """Build the typed submission for one amendment.

    The subject is the FILING RECORD, not a work unit. Two amendments of the
    same filed return must contend -- they describe competing corrections to
    one declaration -- while amendments of different returns are independent.
    Keying the subject on a work unit would let two corrections to the same
    filed return proceed concurrently.

    ``overrides`` arrives as a casilla-to-value mapping so the caller cannot
    submit the same casilla twice with different corrections; a sequence would
    admit that and leave the contract to decide which one counted.
    """
    return OperationRequest(
        definition_id=MODELO_WORK_AMEND_OPERATION_DEFINITION_ID,
        subject_ref=from_filing_record_id,
        payload=ModeloWorkAmendRequest(
            baseline=ModeloWorkAmendBaseline(from_filing_record_id=from_filing_record_id),
            amendment_kind=amendment_kind,
            overrides=tuple(
                ModeloWorkAmendOverride(casilla_id=casilla_id, value=value)
                for casilla_id, value in overrides.items()
            ),
            reason=reason,
            m303_rectificativa_motive=m303_rectificativa_motive,
            actor=actor_ref,
        ),
    )


async def submit_amend(
    services: OperationComposedServices,
    *,
    from_filing_record_id: str,
    amendment_kind: CalculationRevisionAmendmentKind,
    overrides: Mapping[str, str],
    reason: str,
    actor_ref: str,
    m303_rectificativa_motive: M303RectificativaMotive | None = None,
) -> OperationController:
    """Submit the amendment and return the controller bound to it."""
    from ...operations.controller import OperationController

    submission = await services.submission.submit(
        build_amend_operation_request(
            from_filing_record_id=from_filing_record_id,
            amendment_kind=amendment_kind,
            overrides=overrides,
            reason=reason,
            actor_ref=actor_ref,
            m303_rectificativa_motive=m303_rectificativa_motive,
        ),
        actor_ref=actor_ref,
    )
    return OperationController(services=services, submission=submission, actor_ref=actor_ref)

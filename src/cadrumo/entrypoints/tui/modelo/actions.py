"""The C4 lifecycle actions a Modelo workspace offers, as data rather than behaviour.

This module DESCRIBES actions; it performs none. Every row is inert: no
callbacks, no bound methods, no service handles, no executor or repository
references. A row states which registered operation an action invokes, which
capability governs it, and where its result lands -- and nothing else. The
controller that acts on a row resolves the port itself.

That is the whole point rather than a style preference. A view row carrying a
callback is a hidden edge from a rendering surface into whatever the callback
closed over, invisible to the import graph and to any reader of the row. The
last cohort removed exactly that shape, and re-introducing it here would
reconnect the TUI to writers through a field the type system would not object
to.

WHAT AN ACTION IS, and why the denominator is the registered operations rather
than a hand-listed set: every C4 action is a REGISTERED OPERATION with a
definition id, a journal, a lease and a recovery action. Naming the ids here
means the dispatch table cannot drift from the platform's own registry without
the id failing to resolve. A hand-listed action set would be a second
declaration of what exists, free to fall behind the first.

THE DENOMINATOR IS WIDER THAN THIS TABLE, and the gap is declared rather than
hidden. The action denominator classifies THIRTY-ONE modelo candidates as
pending C4 mutations. Exactly SIX of those have a registered operation
definition -- rename, discard, verify, file, export and amend -- so TWENTY-FIVE
remain undispatchable and are listed in
:data:`MODELO_ACTIONS_WITHOUT_REGISTERED_OPERATIONS`. Note ``modelo.work.calculate``
is among the twenty-five: it is classified a pending C4 mutation but has no
registered definition, so it cannot be dispatched here despite looking like a
sibling of the six.

The table below holds SEVEN rows, not six, because ``modelo.edit.apply`` is a
registered operation that is NOT one of the denominator's thirty-one -- it
arrived with the C3 editor. Seven dispatchable plus twenty-five pending does
not sum to thirty-one, and that is correct rather than an arithmetic slip:
the two sets overlap in six members and each holds one the other does not.

See Also:
    :mod:`cadrumo.application.modelo.operation_definitions`
        The registered operations these rows name.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from ....application.modelo.operation_definitions import (
    MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID,
    MODELO_EXPORT_OPERATION_DEFINITION_ID,
    MODELO_WORK_AMEND_OPERATION_DEFINITION_ID,
    MODELO_WORK_DISCARD_OPERATION_DEFINITION_ID,
    MODELO_WORK_FILE_OPERATION_DEFINITION_ID,
    MODELO_WORK_RENAME_OPERATION_DEFINITION_ID,
    MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
)
from ....application.modelo.workspace_models import ModeloWorkspaceCapabilityName

__all__ = [
    "MODELO_ACTIONS_WITHOUT_REGISTERED_OPERATIONS",
    "MODELO_ACTION_DISPATCH",
    "ModeloActionPort",
    "ModeloActionView",
    "action_for_operation",
]


class ModeloActionPort(StrEnum):
    """The public port a controller reaches for to carry out one action.

    Closed on purpose. A row naming a port outside this set would describe a
    reach the cohort has not adjudicated, and the point of enumerating them is
    that adding a new one is a visible decision rather than a new import.
    """

    OPERATION = "operation"
    """Submitted through the operation supervisor, which owns journal and lease."""

    EDIT = "edit"
    """Staged through the application-owned edit session, then submitted as an operation."""


@dataclass(frozen=True, slots=True)
class ModeloActionView:
    """One lifecycle action, described completely and inertly.

    Frozen and slotted so a row cannot acquire a handle after construction --
    the inertness is enforced by the type rather than promised by a comment.
    """

    action_id: str
    """The registered operation's definition id; never a locally minted name."""

    port: ModeloActionPort
    """Which public port carries this action out."""

    capability: ModeloWorkspaceCapabilityName | None
    """The workspace capability governing availability, or ``None`` when the
    action's availability is not a workspace-capability question. ``None`` is
    an answer here, not a gap: rename and discard are lifecycle operations on
    the work unit itself and are not gated by what the projection could
    measure."""

    result_destination: str
    """The route identity a completed run lands on. Stated per action because
    'where did this leave me' is the question an operator asks after every
    mutation, and a shared default would answer it wrongly for some."""

    destroys_subject: bool = False
    """Whether the action removes the thing it addresses. Separated from the
    capability axis because a destructive action needs an exact-approval
    interaction regardless of which capability permits it."""


_WORKSPACE_OVERVIEW: Final = "modelo.workspace.overview"
_WORKSPACE_VERIFICATION: Final = "modelo.workspace.verification"
_WORKSPACE_FILING: Final = "modelo.workspace.filing"
_WORKSPACE_RESULTS: Final = "modelo.workspace.results"


MODELO_ACTION_DISPATCH: Final[dict[str, ModeloActionView]] = {
    MODELO_WORK_RENAME_OPERATION_DEFINITION_ID: ModeloActionView(
        action_id=MODELO_WORK_RENAME_OPERATION_DEFINITION_ID,
        port=ModeloActionPort.OPERATION,
        capability=None,
        result_destination=_WORKSPACE_OVERVIEW,
    ),
    MODELO_WORK_DISCARD_OPERATION_DEFINITION_ID: ModeloActionView(
        action_id=MODELO_WORK_DISCARD_OPERATION_DEFINITION_ID,
        port=ModeloActionPort.OPERATION,
        capability=None,
        # A discarded work unit has no workspace to return to, so the
        # destination is deliberately NOT the overview it was invoked from.
        result_destination="modelo.work.select",
        destroys_subject=True,
    ),
    MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID: ModeloActionView(
        action_id=MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
        port=ModeloActionPort.OPERATION,
        capability=ModeloWorkspaceCapabilityName.VERIFICATION_READINESS,
        result_destination=_WORKSPACE_VERIFICATION,
    ),
    MODELO_WORK_FILE_OPERATION_DEFINITION_ID: ModeloActionView(
        action_id=MODELO_WORK_FILE_OPERATION_DEFINITION_ID,
        port=ModeloActionPort.OPERATION,
        capability=ModeloWorkspaceCapabilityName.FILING_DRAFT_READINESS,
        result_destination=_WORKSPACE_FILING,
    ),
    MODELO_EXPORT_OPERATION_DEFINITION_ID: ModeloActionView(
        action_id=MODELO_EXPORT_OPERATION_DEFINITION_ID,
        port=ModeloActionPort.OPERATION,
        capability=ModeloWorkspaceCapabilityName.FILING_EXPORT_READINESS,
        result_destination=_WORKSPACE_FILING,
    ),
    MODELO_WORK_AMEND_OPERATION_DEFINITION_ID: ModeloActionView(
        action_id=MODELO_WORK_AMEND_OPERATION_DEFINITION_ID,
        port=ModeloActionPort.OPERATION,
        capability=ModeloWorkspaceCapabilityName.CALCULATION_MATERIALIZATION,
        result_destination=_WORKSPACE_OVERVIEW,
    ),
    MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID: ModeloActionView(
        action_id=MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID,
        port=ModeloActionPort.EDIT,
        capability=ModeloWorkspaceCapabilityName.CALCULATION_MATERIALIZATION,
        result_destination=_WORKSPACE_RESULTS,
    ),
}
"""Every modelo action with a registered operation behind it, keyed by its id.

Closed: a controller may dispatch what this table names and nothing else. The
key IS the definition id rather than a parallel enum, so a row cannot name an
operation the platform does not register.
"""


MODELO_ACTIONS_WITHOUT_REGISTERED_OPERATIONS: Final[tuple[str, ...]] = (
    "modelo.aggregate",
    "modelo.audit.export",
    "modelo.filing_record.import",
    "modelo.filing_record.observe_local",
    "modelo.iva_wallet.correct",
    "modelo.iva_wallet.override",
    "modelo.iva_wallet.seed",
    "modelo.m036.alta",
    "modelo.m036.baja",
    "modelo.m036.modificacion",
    "modelo.m145.create",
    "modelo.m145.export",
    "modelo.m145.mark_delivered_to_payer",
    "modelo.m145.mark_locally_completed",
    "modelo.reconcile.import",
    "modelo.reconcile.pull",
    "modelo.review_package.build",
    "modelo.review_package.counter_sign",
    "modelo.review_package.decrypt",
    "modelo.review_package.import_feedback",
    "modelo.review_package.sign",
    "modelo.spreadsheet.calculate",
    "modelo.spreadsheet.pull",
    "modelo.spreadsheet.push",
    "modelo.work.calculate",
)
"""Modelo mutations classified as pending C4 work that have NO registered operation.

Declared so the dispatch table above cannot be mistaken for the whole surface.
Each of these is a direct-effect mutation an operator can reach today through
some other path, running outside the platform that would journal and lease it.
They are NOT dispatchable here and must not be added to the table until each
has a registered definition; a row pointing at an unregistered id would submit
into nothing.
"""


def action_for_operation(definition_id: str) -> ModeloActionView | None:
    """Return the action row for one registered operation, or ``None``.

    ``None`` means this cohort does not dispatch that operation -- which is a
    different statement from "no such operation exists", and the caller must
    not collapse the two.
    """
    return MODELO_ACTION_DISPATCH.get(definition_id)

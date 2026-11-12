"""Prepare a correction of a declaration recorded as filed from the workbench.

The correction is offered only on a form the application closed to editing
because the declaration is recorded as filed, and only through a door that
reads the correction the current filing offers. The filer prepares it in
:class:`~cadrumo.entrypoints.tui.modelo.amendment.ModeloAmendmentScreen`, and
it is submitted once through the supervised operation, which records it
locally; nothing is sent to the AEAT. A refusal is shown in its served words
with its served ways out. An outcome that may have committed is never treated
as done or as not done: no further correction is offered from this workbench
until the filer has checked that operation.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from cadrumo_client.contracts.contracts import RefusalError
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

from .....application.modelo.work_form_declaration_facts import ModeloFormEditClosure
from .....core.errors.error_codes import resolve_error_message
from .....core.errors.hierarchy import CadrumoError
from .....core.i18n.render import tr
from .....core.logging import get_logger
from .....core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition
from ...refusal.served import served_refusal
from ..amendment import ModeloAmendmentAnswerV1, ModeloAmendmentScreen, ModeloWorkbenchAmendmentV1

if TYPE_CHECKING:
    from .....application.modelo.work_amend_correction import ModeloAmendmentCorrectionContextV1
    from .screen import ModeloWorkbenchScreen

AMENDMENT_KEY = "m"
"""The workbench key that prepares a correction of a declaration recorded as filed."""
_UNAVAILABLE_LOCALE_KEY = "workspace.modelo.correction.unavailable"
_UNKNOWN_LOCALE_KEY = "tui.modelo.amendment.unknown"


def _effect_unknown(error: CadrumoError) -> bool:
    """Whether a submission failed after the runtime may already have admitted it."""
    context = error.context or {}
    return context.get("effect") == OperationEffect.UNKNOWN.value or "operation_id" in context


class WorkbenchAmendmentMixin:
    """Own the correction of a declaration recorded as filed for the modelo workbench."""

    #: Set once a submitted correction's outcome is unknown; it is never offered again from this workbench.
    _amendment_unknown: bool = False

    def _amendment_door(self: ModeloWorkbenchScreen) -> ModeloWorkbenchAmendmentV1 | None:
        actions = self._actions
        return actions if isinstance(actions, ModeloWorkbenchAmendmentV1) else None

    def _offers_amendment(self: ModeloWorkbenchScreen) -> bool:
        """Whether the form says the declaration is recorded as filed and a correction door is bound."""
        form = self.form
        return (
            form is not None
            and form.edit_closure is ModeloFormEditClosure.RECORDED_AS_FILED
            and self._amendment_door() is not None
        )

    def action_amend(self: ModeloWorkbenchScreen) -> None:
        """Read what correcting this declaration offers, then ask the filer for the correction."""
        door = self._amendment_door()
        if not self._offers_amendment() or door is None:
            return
        if self._amendment_unknown:
            self._notice(tr(_UNKNOWN_LOCALE_KEY))
            return
        if self._operation_in_flight:
            return
        self._notice(tr("workspace.modelo.correction.loading"))
        self.run_worker(partial(self._open_amendment, door), group="workbench-amendment", exclusive=True)

    async def _open_amendment(self: ModeloWorkbenchScreen, door: ModeloWorkbenchAmendmentV1) -> None:
        try:
            context = await door.amendment_context(self._language)
        except FrontendRefusedError as refused:
            self._show_operation_refusal(served_refusal(None, refusal_code=refused.reason))
            self._notice(tr(_UNAVAILABLE_LOCALE_KEY))
            return
        except RefusalError:
            self._notice(tr(_UNAVAILABLE_LOCALE_KEY))
            return
        except CadrumoError as error:
            self._notice(resolve_error_message(error))
            return
        except Exception as failure:
            get_logger(__name__).error(
                "modelo workbench could not read the correction: %s", type(failure).__qualname__, exc_info=True
            )
            self._notice(tr(_UNAVAILABLE_LOCALE_KEY))
            return
        if not context.kinds:
            self._notice(tr(_UNAVAILABLE_LOCALE_KEY))
            return
        self._notice("")
        self._show_operation_refusal(None)
        self.app.push_screen(
            ModeloAmendmentScreen(context, parse=door.parse_correction),
            partial(self._amendment_answered, door, context),
        )

    def _amendment_answered(
        self: ModeloWorkbenchScreen,
        door: ModeloWorkbenchAmendmentV1,
        context: ModeloAmendmentCorrectionContextV1,
        answer: ModeloAmendmentAnswerV1 | None,
    ) -> None:
        if answer is None or self._amendment_unknown or self._operation_in_flight:
            return
        self._operation_in_flight = True
        self.run_worker(
            partial(self._submit_amendment, door, context.filed.filing_record_id, answer),
            group="workbench-operation",
            exclusive=True,
        )

    async def _submit_amendment(
        self: ModeloWorkbenchScreen,
        door: ModeloWorkbenchAmendmentV1,
        filing_record_id: str,
        answer: ModeloAmendmentAnswerV1,
    ) -> None:
        from ...operations.modal import OperationModal

        try:
            controller = await door.amend(filing_record_id, answer)
        except CadrumoError as error:
            self._operation_in_flight = False
            if _effect_unknown(error):
                self._hold_unknown_amendment()
            else:
                self._notice(resolve_error_message(error))
            return
        except Exception as failure:
            # Submission may have reached the runtime before it failed here.
            self._operation_in_flight = False
            get_logger(__name__).error(
                "modelo workbench correction failed after submission began: %s",
                type(failure).__qualname__,
                exc_info=True,
            )
            self._hold_unknown_amendment()
            return
        self.app.push_screen(OperationModal(controller), self._amendment_settled)

    def _amendment_settled(self: ModeloWorkbenchScreen, outcome: object) -> None:
        from ...operations.modal import OperationModalSettledOutcomeV1

        self._operation_in_flight = False
        if isinstance(outcome, OperationModalSettledOutcomeV1):
            projection = outcome.view_model.projection
            if projection.terminal_condition is OperationTerminalCondition.SUCCEEDED:
                self._settle_succeeded_operation(False, outcome)
                self._notice(tr("tui.modelo.amendment.done"))
                return
            if projection.lifecycle is OperationLifecycle.TERMINAL and projection.effect is OperationEffect.NONE:
                self._show_operation_refusal(outcome.refusal)
                self._notice(tr("workspace.modelo.outcome.refused"))
                return
        # Detached, closed before settling, or stopped with an effect that may have committed.
        self._hold_unknown_amendment()

    def _hold_unknown_amendment(self: ModeloWorkbenchScreen) -> None:
        self._amendment_unknown = True
        self._notice(tr(_UNKNOWN_LOCALE_KEY))


__all__ = ["AMENDMENT_KEY", "WorkbenchAmendmentMixin"]

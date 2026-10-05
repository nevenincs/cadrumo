"""Registered-operation lifecycle for the Modelo workbench screen."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from functools import partial
from typing import TYPE_CHECKING

from .....application.modelo.action_errors import ModeloEditBaselineStaleError
from .....application.modelo.operation_definitions import (
    MODELO_EXPORT_OPERATION_DEFINITION_ID,
    MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
)
from .....application.modelo.work_form_models import ModeloWorkForm
from .....application.modelo.work_form_service import ModeloWorkFormLoadV1, modelo_work_form_changes
from .....core.errors.error_codes import resolve_error_message
from .....core.errors.hierarchy import CadrumoError
from .....core.i18n.render import tr
from .....core.logging import get_logger
from .....core.operations import OperationTerminalCondition
from ...components.dialogs import ConfirmScreen
from ...operations.controller_port import OperationControllerPort
from ...operations.refusal_explanation import public_refusal_explanation
from ..export_result import ModeloExportResultScreen
from .casilla_list_models import AddressKey
from .export import WorkbenchExportScreen
from .header import result_view
from .ports import ModeloWorkbenchActionsV1, WorkbenchExportRequest
from .progress import NextAction
from .result import WorkbenchResultScreen, result_lines
from .screen_constants import (
    _BLOCKED_LOCALE_KEY,
    _CHECKED_LOCALE_KEYS,
    _FILE_OUT_OF_DATE_LOCALE_KEY,
    _NEXT_KEYS,
    _SELF_REPORTING_OPERATIONS,
    _VALUE_CHANGING_OPERATIONS,
    _WITHHELD_LOCALE_KEY,
)
from .wording import day_text

if TYPE_CHECKING:
    from .....application.operations.frontend_projection import OperationPublicProjectionV1
    from ...operations.modal import OperationModalSettledOutcomeV1
    from .screen import ModeloWorkbenchScreen


class WorkbenchOperationMixin:
    """Own the operation behavior for the modelo workbench."""

    def _file_out_of_date(self: ModeloWorkbenchScreen) -> bool:
        """Refuse to record the filing while the latest file was made from an earlier calculation, and say so.

        That file no longer matches the declaration, so it must be created
        again; there is no way past this but a new file, or a correction when
        the older file was already filed.
        """
        form = self.form
        export = None if form is None else form.last_export
        if export is None or export.current:
            return False
        self._notice(tr(_FILE_OUT_OF_DATE_LOCALE_KEY, date=day_text(export.exported_at, self._language)))
        return True

    def _filing_withheld(self: ModeloWorkbenchScreen) -> bool:
        """Refuse the file for the AEAT and recording the filing while anything withholds them, and say why.

        Something that blocks filing, found by the check or by the
        calculation, comes first: the notice says so and the issue list opens
        on it. Otherwise an assumed value is the reason: the notice says so and
        the confirm step opens on the next assumed values.
        """
        load = self._load
        if load is None:
            return False
        if self._active_apply_prerequisite() is not None:
            self.action_issues()
            self._state_apply_prerequisite()
            return True
        if self._session.dirty:
            action = tr("tui.modelo.workbench.next.apply", count=len(self._session.changes))
            self._notice(f"{action} [{_NEXT_KEYS[NextAction.APPLY]}]")
            return True
        progress = self._progress(load)
        if not progress.filing_withheld:
            return False
        if progress.blocking:
            self.action_issues()
            self._notice(tr(_BLOCKED_LOCALE_KEY, count=progress.blocking))
            return True
        if self._may_confirm():
            self._confirm_next()
        self._notice(tr(_WITHHELD_LOCALE_KEY, count=progress.assumed))
        return True

    def action_export(self: ModeloWorkbenchScreen) -> None:
        """Export the verified declaration where and how the filer asks, once nothing withholds it."""
        actions = self._actions
        load = self._load
        if actions is None or load is None:
            self._edit_unavailable()
            return
        if self._filing_withheld():
            return
        if not load.verified:
            self._notice(tr("tui.modelo.workbench.export.verify_first"))
            return

        def asked(request: WorkbenchExportRequest | None) -> None:
            if request is not None and not self._filing_withheld():
                self._run_operation(partial(actions.export, request))

        self.app.push_screen(WorkbenchExportScreen(actions.export_offer()), asked)

    def _confirm_file(self: ModeloWorkbenchScreen, submit: Callable[[], Awaitable[OperationControllerPort]]) -> None:
        if self._filing_withheld() or self._file_out_of_date():
            return

        def closed(confirmed: bool | None) -> None:
            if confirmed:
                if not self._filing_withheld() and not self._file_out_of_date():
                    self._run_operation(submit)
            else:
                self._notice(tr("application.modelo.lifecycle.file_cancelled"))

        self.app.push_screen(
            ConfirmScreen(
                title=tr("application.modelo.lifecycle.file_confirm_title"),
                message=tr("application.modelo.lifecycle.file_confirm_message"),
                confirm_label=tr("application.modelo.lifecycle.file_confirm_accept"),
                cancel_label=tr("application.modelo.lifecycle.file_confirm_cancel"),
            ),
            closed,
        )

    def _run_operation(
        self: ModeloWorkbenchScreen,
        submit: Callable[[], Awaitable[OperationControllerPort]],
        *,
        applies_changes: bool = False,
    ) -> None:
        if self._operation_in_flight:
            return
        self._operation_in_flight = True
        self.run_worker(
            partial(self._open_operation, submit, applies_changes), group="workbench-operation", exclusive=True
        )

    async def _open_operation(
        self: ModeloWorkbenchScreen, submit: Callable[[], Awaitable[OperationControllerPort]], applies_changes: bool
    ) -> None:
        from ...operations.modal import OperationModal

        try:
            controller = await submit()
        except ModeloEditBaselineStaleError:
            self._operation_in_flight = False
            if applies_changes and await self._rebase() and self._session.dirty:
                await self._open_review(rebased=True)
            return
        except CadrumoError as refusal:
            self._operation_in_flight = False
            self._notice(resolve_error_message(refusal))
            return
        except Exception as failure:
            self._operation_in_flight = False
            get_logger(__name__).error(
                "modelo workbench operation failed before it opened: %s", type(failure).__qualname__, exc_info=True
            )
            self._notice(tr("operation.modal.terminal.failed"))
            return
        self.app.push_screen(OperationModal(controller), partial(self._operation_settled, applies_changes))

    def _operation_settled(self: ModeloWorkbenchScreen, applies_changes: bool, outcome: object) -> None:
        from ...operations.modal import OperationModalSettledOutcomeV1

        self._operation_in_flight = False
        if not isinstance(outcome, OperationModalSettledOutcomeV1):
            return
        condition = outcome.view_model.projection.terminal_condition
        if condition is not OperationTerminalCondition.SUCCEEDED:
            self._settle_refused_operation(applies_changes, outcome, condition)
            return
        self._settle_succeeded_operation(applies_changes, outcome)

    def _settle_refused_operation(
        self: ModeloWorkbenchScreen,
        applies_changes: bool,
        outcome: OperationModalSettledOutcomeV1,
        condition: OperationTerminalCondition | None,
    ) -> None:
        self._apply_prerequisite = None
        notice = self._operation_refusal_notice(outcome)
        if applies_changes:
            refused = condition is OperationTerminalCondition.REFUSED
            self.run_worker(partial(self._read_refused_apply, notice, refused), group="workbench-read", exclusive=True)
        else:
            self._notice(notice)

    @staticmethod
    def _operation_refusal_notice(outcome: OperationModalSettledOutcomeV1) -> str:
        # The stopped executor's own message, when it recorded one, says more than the registry's generic sentence.
        explanation = outcome.error_explanation or (
            public_refusal_explanation(outcome.view_model.receipt_ref)
            if outcome.view_model.receipt_kind == "refusal"
            else None
        )
        message = tr("tui.modelo.workbench.operation.not_done")
        return message if explanation is None else f"{message} {explanation}"

    def _settle_succeeded_operation(
        self: ModeloWorkbenchScreen, applies_changes: bool, outcome: OperationModalSettledOutcomeV1
    ) -> None:
        self._apply_prerequisite = None
        yours = frozenset(change.key for change in self._session.changes) if applies_changes else frozenset()
        if applies_changes:
            self._session.discard()
        projection = outcome.view_model.projection
        definition = str(projection.definition_id)
        reports_itself = not applies_changes and definition in _SELF_REPORTING_OPERATIONS
        if not reports_itself:
            self._notice(tr("tui.modelo.workbench.operation.done"))
        actions = self._actions
        if actions is not None:
            self.run_worker(partial(asyncio.to_thread, actions.refresh_product), group="workbench-refresh")
        before = self._load
        self._finish_successful_operation(actions, projection, before, yours, definition if reports_itself else None)

    def _finish_successful_operation(
        self: ModeloWorkbenchScreen,
        actions: ModeloWorkbenchActionsV1 | None,
        projection: OperationPublicProjectionV1,
        before: ModeloWorkFormLoadV1 | None,
        yours: frozenset[AddressKey],
        reporting: str | None,
    ) -> None:
        if projection.definition_id == MODELO_EXPORT_OPERATION_DEFINITION_ID and actions is not None:
            self.run_worker(partial(self._state_export_result, actions, projection), group="workbench-export")
        changes_values = projection.definition_id in _VALUE_CHANGING_OPERATIONS
        original = before if changes_values else None
        self.run_worker(
            partial(self._read_after, original, yours, reporting),
            group="workbench-read",
            exclusive=True,
        )

    async def _read_refused_apply(self: ModeloWorkbenchScreen, notice: str, refused: bool) -> None:
        """Say why the Apply was not done, naming its prerequisite when it named one, then refresh.

        A refused Apply's named source is read once from where it ran, off the
        event loop; a refresh never replaces that named refusal with a bare
        retry message.
        """
        actions = self._actions
        self._apply_prerequisite = None
        if refused and actions is not None:
            try:
                self._apply_prerequisite = await actions.take_apply_prerequisite()
            except Exception as failure:
                get_logger(__name__).error(
                    "modelo workbench could not read the refused change's prerequisite: %s",
                    type(failure).__qualname__,
                    exc_info=True,
                )
        if not self._state_apply_prerequisite():
            self._notice(notice)
        await self._rebase()
        self._state_apply_prerequisite()

    async def _read_after(
        self: ModeloWorkbenchScreen,
        before: ModeloWorkFormLoadV1 | None,
        yours: frozenset[AddressKey],
        reporting: str | None = None,
    ) -> None:
        """Read the declaration again, say what a calculation or a check concluded, and show what changed."""
        await self._read()
        after = self._load
        if reporting is not None and after is not None:
            self._notice(self._outcome_text(reporting, after.form))
        if before is None or after is None or after is before:
            return
        changes = modelo_work_form_changes(before.form, after.form)
        if not changes:
            self._notice(tr("tui.modelo.workbench.result_diff.nothing_changed"))
            return
        lines = result_lines(
            changes,
            before=before.form,
            after=after.form,
            yours=yours,
            language=self._language,
        )

        def closed(key: AddressKey | None) -> None:
            if key is not None:
                self._go_to(key)

        self.app.push_screen(WorkbenchResultScreen(lines), closed)

    def _outcome_text(self: ModeloWorkbenchScreen, definition: str, form: ModeloWorkForm) -> str:
        """What a finished calculation or check concluded, in the filer's words."""
        if definition == str(MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID):
            verdict = form.verification
            if verdict is None:
                return tr("tui.modelo.workbench.operation.done")
            return tr(_CHECKED_LOCALE_KEYS[verdict], key="i")
        view = result_view(form, self._language, staged=0, recorded=self.recorded)
        if view is None or view.settled is None:
            return tr("tui.modelo.workbench.operation.done")
        direction, value = view.settled
        return tr("tui.modelo.workbench.operation.calculated", direction=direction, value=value)

    async def _state_export_result(
        self: ModeloWorkbenchScreen, actions: ModeloWorkbenchActionsV1, projection: OperationPublicProjectionV1
    ) -> None:
        self.app.push_screen(ModeloExportResultScreen(await actions.export_result(projection)))

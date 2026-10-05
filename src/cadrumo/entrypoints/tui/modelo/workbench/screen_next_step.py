"""Next-step guidance and prerequisite handling for the workbench."""

from __future__ import annotations

from dataclasses import replace
from functools import partial
from typing import TYPE_CHECKING

from .....application.modelo.work_form_models import ModeloFormField, ModeloWorkForm, address_key
from .....application.modelo.work_form_service import ModeloWorkFormLoadV1
from .....core.i18n.render import tr
from ...components.dialogs import ConfirmScreen
from ..m303_evidence import OrdinaryM303FilingEvidenceScreen, OrdinaryM303FilingEvidenceSubmission
from .editor import open_area_target
from .issue_scale import CalculateAgain, ConfirmAssumedValues, IssueLevel, IssueLine, IssuesChoice
from .issues import WorkbenchIssuesScreen
from .ports import ModeloWorkbenchActionsV1, WorkbenchApplyPrerequisite
from .progress import NextAction, WorkbenchProgress, workbench_progress
from .review import recalculation_risk_text
from .screen_constants import (
    _DIALOG_FRAME,
)
from .sources import OpenSourceSurface, earlier_filing_text

if TYPE_CHECKING:
    from .screen import ModeloWorkbenchScreen


class WorkbenchNextStepMixin:
    """Own the next step behavior for the modelo workbench."""

    def action_next_step(self: ModeloWorkbenchScreen) -> None:
        """Run the next step the stepper offers."""
        load = self._load
        if load is None:
            return
        progress = self._progress(load)
        action = progress.next_action
        if self._run_direct_next_step(load, progress):
            return
        actions = self._actions
        if actions is None:
            self._edit_unavailable()
            return
        self._run_operation_next_step(action, actions)

    def _run_direct_next_step(
        self: ModeloWorkbenchScreen, load: ModeloWorkFormLoadV1, progress: WorkbenchProgress
    ) -> bool:
        action = progress.next_action
        if action is NextAction.RECORDED:
            self._edit_unavailable()
        elif action is NextAction.APPLY:
            self.action_review()
        elif action is NextAction.CONFIRM:
            self._confirm_next()
        elif progress.findings_lead or (
            action is NextAction.RESOLVE and (load.form.verification is not None or load.form.calculation_notes)
        ):
            self.action_issues()
        elif action in {NextAction.FILL, NextAction.RESOLVE}:
            self._advance_attention(1)
        else:
            return False
        return True

    def _run_operation_next_step(
        self: ModeloWorkbenchScreen, action: NextAction, actions: ModeloWorkbenchActionsV1
    ) -> None:
        if action in {NextAction.CALCULATE, NextAction.RECALCULATE}:
            self._calculate(actions)
        elif action is NextAction.VERIFY:
            self._run_operation(actions.verify)
        elif action in {NextAction.EXPORT, NextAction.EXPORT_AGAIN}:
            if not self._file_out_of_date():
                self.action_export()
        else:
            self._confirm_file(actions.file)

    def action_calculate(self: ModeloWorkbenchScreen) -> None:
        """Recalculate the declaration now, keeping the filer's values."""
        actions = self._actions
        if actions is None or self.recorded:
            self._edit_unavailable()
            return
        if self._session.dirty:
            self._notice(tr("tui.modelo.workbench.calculate.apply_first"))
            return
        self._calculate(actions)

    def _calculate(self: ModeloWorkbenchScreen, actions: ModeloWorkbenchActionsV1) -> None:
        """Recalculate, first asking the filer to accept losing values nobody is recorded as having typed."""
        form = self.form
        if form is None or not self._entries_unknown(form):
            self._calculate_now(actions)
            return

        def closed(proceed: bool | None) -> None:
            if proceed:
                self._calculate_now(actions)
            else:
                self._notice(tr("tui.modelo.workbench.calculate.kept"))

        self.app.push_screen(
            ConfirmScreen(
                title=tr("tui.modelo.workbench.calculate.at_risk_title"),
                message=recalculation_risk_text(
                    self._unattributed_boxes(form),
                    console=self.app.console,
                    width=max(self._width() - _DIALOG_FRAME, 1),
                ),
                confirm_label=tr("tui.modelo.workbench.calculate.at_risk_proceed"),
                cancel_label=tr("tui.modelo.workbench.calculate.at_risk_cancel"),
            ),
            closed,
        )

    def _calculate_now(self: ModeloWorkbenchScreen, actions: ModeloWorkbenchActionsV1) -> None:
        need = actions.calculation_evidence()
        if need is None:
            self._run_operation(actions.calculate)
            return

        def answered(submission: OrdinaryM303FilingEvidenceSubmission | None) -> None:
            if submission is None:
                self._notice(tr("tui.modelo.m303_evidence.cancelled"))
            elif submission.work_unit_id != need.work_unit_id:
                self._notice(tr("tui.modelo.m303_evidence.stale_context"))
            else:
                self._run_operation(partial(actions.calculate, submission))

        self.app.push_screen(
            OrdinaryM303FilingEvidenceScreen(work_unit_id=need.work_unit_id, asks_modelo_390=need.asks_modelo_390),
            answered,
        )

    def action_issues(self: ModeloWorkbenchScreen) -> None:
        """List everything to look at, what the last check found and the assumed values, and go where one leads.

        A finding leads to its box, or to the area of the product that owns
        its value; asking to confirm the assumed values goes to the confirm
        step for the section, or the page, holding the box chosen there,
        never the whole declaration at once.
        """
        form = self.form
        if form is None:
            return

        def closed(choice: IssuesChoice | None) -> None:
            if isinstance(choice, OpenSourceSurface):
                self._open_surface(choice)
            elif isinstance(choice, ConfirmAssumedValues):
                # The part of the form that holds the chosen box, as b there offers it: its section, else its page.
                self._go_to(choice.at)
                self.action_bulk_confirm()
            elif isinstance(choice, CalculateAgain):
                self.action_calculate()
            elif choice is not None:
                self._go_to(choice)

        prerequisite = self._apply_prerequisite_line()
        self.app.push_screen(
            WorkbenchIssuesScreen(
                form,
                status_line=self._status_line(),
                additional_lines=() if prerequisite is None else (prerequisite,),
                changes_unapplied=self._session.dirty,
            ),
            closed,
        )

    def _active_apply_prerequisite(self: ModeloWorkbenchScreen) -> WorkbenchApplyPrerequisite | None:
        """Keep the diagnostic only while the failed calculation and unresolved intent still match."""
        prerequisite = self._apply_prerequisite
        form = self.form
        if prerequisite is None:
            return None
        key = address_key(prerequisite.address)
        if (
            form is None
            or self.recorded
            or not self._session.dirty
            or prerequisite.calculation_revision_id != form.calculation_revision_id
            or not any(field.address == prerequisite.address for field in form.fields())
            or any(change.key == key for change in self._session.changes)
        ):
            self._apply_prerequisite = None
            return None
        return prerequisite

    def _apply_prerequisite_line(self: ModeloWorkbenchScreen) -> IssueLine | None:
        """Name this failed calculation's source without relabeling the saved value as missing."""
        prerequisite = self._active_apply_prerequisite()
        form = self.form
        if prerequisite is None or form is None:
            return None
        field = next(field for field in form.fields() if field.address == prerequisite.address)
        message = self._prerequisite_message(form, field, prerequisite)
        return IssueLine(
            level=IssueLevel.BLOCKS,
            box=field.box or "·",
            where=field.label.text,
            message=message,
            action=tr("tui.modelo.workbench.apply_prerequisite.action"),
            detail="",
            technical="",
            key=address_key(field.address),
            area=open_area_target(field),
            action_targets_box=True,
        )

    def _prerequisite_message(
        self: ModeloWorkbenchScreen,
        form: ModeloWorkForm,
        field: ModeloFormField,
        prerequisite: WorkbenchApplyPrerequisite,
    ) -> str:
        source = field.source
        filings = () if source is None else source.earlier_filings
        message = tr(
            "tui.modelo.workbench.apply_prerequisite.earlier"
            if filings
            else "tui.modelo.workbench.apply_prerequisite.what"
        )
        if not form.operator_entries_known:
            message += "\n" + tr("tui.modelo.workbench.apply_prerequisite.legacy")
        if filings:
            message += "\n" + earlier_filing_text(filings)
        if prerequisite.source_boxes:
            message += "\n" + tr(
                "tui.modelo.workbench.apply_prerequisite.source_boxes",
                boxes=", ".join(f"[{box}]" for box in prerequisite.source_boxes),
            )
        return message

    def _state_apply_prerequisite(self: ModeloWorkbenchScreen) -> bool:
        line = self._apply_prerequisite_line()
        if line is None:
            return False
        self._notice(tr("tui.modelo.workbench.apply_prerequisite.notice", box=f"[{line.box}]"))
        self._render_progress()
        return True

    def _progress(self: ModeloWorkbenchScreen, load: ModeloWorkFormLoadV1) -> WorkbenchProgress:
        """Where the declaration stands now, with the changes staged here."""
        progress = workbench_progress(
            load.form, staged=len(self._session.changes), verified=load.verified, filed=self.recorded
        )
        if self._active_apply_prerequisite() is not None:
            return replace(
                progress, next_action=NextAction.RESOLVE, count=1, blocking=progress.blocking + 1, findings_lead=True
            )
        return progress

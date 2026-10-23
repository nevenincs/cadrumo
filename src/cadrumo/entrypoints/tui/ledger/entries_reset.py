"""Reset ledger: ``ledger.reset``, always previewed with a dry run before the real run.

The real run is submitted only from a reviewed preview without blockers, only
with a reason, and only after a second confirmation that names the
consequence. Declining that confirmation writes nothing.
"""

from __future__ import annotations

from itertools import count
from typing import ClassVar, Final, override

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Input, Static

from ....application.ledger.reset_operation import LedgerResetOperationResult, LedgerResetRequest
from ....core.errors.hierarchy import CadrumoError, InternalInvariantError
from ....core.i18n.render import tr
from ..account import AccountSessionExpiredError
from ..components.dialogs import ConfirmScreen
from ..components.language import localized
from ..components.theme import tokenised
from ..components.workspace_host import replace_workspace_body
from .controller import LedgerWorkspaceController
from .entries_common import joined
from .entries_doors import LedgerEntriesDoorsV1
from .models import LedgerFlowState
from .workspace_presentation import LedgerConfirmationFlowScreen, door_refusal_text, ledger_workspace_page

#: Starting a flow again replaces its screen while the outgoing one is still
#: being removed, so each instance carries its own identity.
_SCREEN_SERIALS: Final = count()


def reset_preview_lines(preview: LedgerResetOperationResult) -> tuple[str, ...]:
    """Say what resetting would do, as the dry run reported it."""
    report = preview.report
    lines = [
        tr("tui.ledger.entry_tools.reset.would_remove", count=len(report.removed_transaction_ids)),
        tr(
            "tui.ledger.entry_tools.reset.cascade",
            evidence=len(report.cascaded_purchase_invoice_evidence_ids),
            attachments=len(report.cascaded_attachment_ids),
        ),
    ]
    if report.stale_draft_revision_references:
        lines.append(tr("tui.ledger.entry_tools.stale_drafts", count=len(report.stale_draft_revision_references)))
    if report.blocking_modelo_references:
        lines.append(tr("tui.ledger.entry_tools.reset.blocked"))
        lines.extend(
            tr(
                "tui.ledger.entry_tools.blocker",
                modelo=item.modelo,
                year=item.filing_year,
                period=item.period,
                state=item.revision_state,
            )
            for item in report.blocking_modelo_references
        )
    return tuple(lines)


class LedgerResetScreen(LedgerConfirmationFlowScreen):
    """Preview the reset, then reset only after a second, named confirmation."""

    FLOW_NAME = "ledger_reset"
    CSS: ClassVar[str] = LedgerConfirmationFlowScreen.CSS + tokenised(
        """
        .entries-reset-row { height: auto; width: 100%; }
        .entries-reset-row > * { width: 1fr; min-width: 0; }
        #entries-reset-preview { height: auto; }
        #entries-reset-again { display: none; }
        #entries-reset-again.-open { display: block; }
        """
    )

    def __init__(self, controller: LedgerWorkspaceController, doors: LedgerEntriesDoorsV1) -> None:
        """Keep the injected doors; nothing has been previewed."""
        super().__init__(controller, id=f"ledger-reset-screen-{next(_SCREEN_SERIALS)}")
        self.doors = doors
        self.preview: LedgerResetOperationResult | None = None
        self.previewed: LedgerResetRequest | None = None
        self.result: LedgerResetOperationResult | None = None
        self.busy = False

    @property
    @override
    def in_flight(self) -> bool:
        """The preview or the reset itself is out through the door."""
        return self.busy or super().in_flight

    @override
    def compose(self) -> ComposeResult:
        yield localized(
            Static(tr("tui.ledger.entry_tools.reset.title"), classes="cadrumo-banner"),
            "tui.ledger.entry_tools.reset.title",
        )
        with ledger_workspace_page() as navigation:
            yield navigation
            yield localized(
                Static(tr("tui.ledger.entry_tools.reset.prompt"), markup=False), "tui.ledger.entry_tools.reset.prompt"
            )
            yield localized(
                Static(tr("tui.ledger.entry_tools.reset.reason"), markup=False), "tui.ledger.entry_tools.reset.reason"
            )
            yield Input(max_length=500, id="entries-reset-reason")
            with Horizontal(classes="entries-reset-row"):
                yield localized(
                    Button(tr("tui.ledger.entry_tools.reset.preview"), id="entries-reset-preview-button"),
                    "tui.ledger.entry_tools.reset.preview",
                )
                yield localized(
                    Button(
                        tr("tui.ledger.entry_tools.reset.run"), id="entries-reset-run", variant="error", disabled=True
                    ),
                    "tui.ledger.entry_tools.reset.run",
                )
                yield localized(
                    Button(tr("tui.ledger.entry_tools.cancel"), id="entries-reset-cancel"),
                    "tui.ledger.entry_tools.cancel",
                )
            yield Static("", id="entries-reset-preview", markup=False)
            yield Static("", id="ledger-flow-status", markup=False)
            yield localized(
                Button(tr("tui.ledger.entry_tools.reset.again"), id="entries-reset-again"),
                "tui.ledger.entry_tools.reset.again",
            )
            yield Static("", id="ledger-refusal", classes="ledger-refusal", markup=False)

    def on_mount(self) -> None:
        """Start at the reason the reset must carry."""
        self.populate_navigation()
        self.query_one("#entries-reset-reason", Input).focus()

    @override
    async def refresh_language(self) -> None:
        """Reword the preview and outcome in place."""
        await super().refresh_language()
        if self.preview is not None:
            self.query_one("#entries-reset-preview", Static).update(joined(reset_preview_lines(self.preview)))
        if self.result is not None:
            self.query_one("#ledger-flow-status", Static).update(self._result_text(self.result))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Preview, confirm and reset through the flow's guarded transitions."""
        notice = self.query_one("#ledger-refusal", Static)
        if self.busy:
            self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.flow.in_flight_refusal"))
            return
        match event.button.id:
            case "entries-reset-preview-button" if self.flow_state is LedgerFlowState.EDITING:
                reason = self.query_one("#entries-reset-reason", Input).value.strip()
                if not reason:
                    notice.update(tr("tui.ledger.entry_tools.reset.reason_required"))
                    return
                notice.update("")
                request = LedgerResetRequest(profile_id=self.doors.profile_id, reason=reason, dry_run=True)
                self._hold(True)
                self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.entry_tools.reset.previewing"))
                self.run_worker(self._run_preview(request), exclusive=True)
            case "entries-reset-run" if self.flow_state is LedgerFlowState.EDITING and self._may_reset():
                self._transition(LedgerFlowState.CONFIRMING)
                self._ask_confirmation()
            case "entries-reset-cancel" if self.flow_state in {LedgerFlowState.EDITING, LedgerFlowState.CONFIRMING}:
                self._cancel_flow()
            case "entries-reset-again" if self.flow_state in {
                LedgerFlowState.SUCCEEDED,
                LedgerFlowState.FAILED,
                LedgerFlowState.CANCELLED,
            }:
                self.refresh_after_write(self._start_again)
            case _:
                return

    def _may_reset(self) -> bool:
        preview = self.preview
        return preview is not None and self.previewed is not None and not preview.report.blocking_modelo_references

    def _hold(self, busy: bool) -> None:
        self.busy = busy
        self.query_one("#entries-reset-preview-button", Button).disabled = busy or self.preview is not None
        self.query_one("#entries-reset-reason", Input).disabled = busy or self.preview is not None
        self.query_one("#entries-reset-run", Button).disabled = busy or not self._may_reset()

    async def _run_preview(self, request: LedgerResetRequest) -> None:
        status = self.query_one("#ledger-flow-status", Static)
        try:
            preview = await self.doors.reset(request)
        except CadrumoError as error:
            if isinstance(error, AccountSessionExpiredError):
                self.query_one("#entries-reset-reason", Input).value = ""
            self._hold(False)
            status.update("")
            self.query_one("#ledger-refusal", Static).update(door_refusal_text(error))
            return
        self.preview, self.previewed = preview, request
        self.query_one("#entries-reset-preview", Static).update(joined(reset_preview_lines(preview)))
        status.update(
            tr("tui.ledger.entry_tools.reset.previewed")
            if self._may_reset()
            else tr("tui.ledger.entry_tools.reset.cannot_reset")
        )
        self._hold(False)

    def _ask_confirmation(self) -> None:
        preview = self.preview
        if preview is None:
            raise InternalInvariantError("a reset was confirmed without a preview")
        count = len(preview.report.removed_transaction_ids)

        def decided(accepted: bool | None) -> None:
            if accepted is not True:
                self._cancel_flow()
                return
            self._transition(LedgerFlowState.SUBMITTING)
            self._hold(True)
            self.query_one("#entries-reset-cancel", Button).disabled = True
            self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.entry_tools.reset.resetting"))
            self.run_worker(self._submit(), exclusive=True)

        self.app.push_screen(
            ConfirmScreen(
                title=tr("tui.ledger.entry_tools.reset.confirm_title"),
                message=tr("tui.ledger.entry_tools.reset.confirm_message", count=count),
                confirm_label=tr("tui.ledger.entry_tools.reset.run"),
                cancel_label=tr("tui.ledger.entry_tools.reset.keep"),
            ),
            decided,
        )

    async def _submit(self) -> None:
        """Run exactly the previewed request for real."""
        previewed = self.previewed
        if previewed is None:
            raise InternalInvariantError("the previewed reset disappeared before submission")
        request = previewed.model_copy(update={"dry_run": False})
        status = self.query_one("#ledger-flow-status", Static)
        try:
            result = await self.doors.reset(request)
        except CadrumoError as error:
            self._transition(LedgerFlowState.FAILED)
            status.update(self.failed_write_status(error, "tui.ledger.records.failed"))
            self.query_one("#ledger-refusal", Static).update(door_refusal_text(error))
        else:
            self.result = result
            self._transition(LedgerFlowState.SUCCEEDED if result.report.reset else LedgerFlowState.FAILED)
            status.update(self._result_text(result))
        self.busy = False
        self._offer_again()

    @staticmethod
    def _result_text(result: LedgerResetOperationResult) -> str:
        if result.report.reset:
            return tr("tui.ledger.entry_tools.reset.done", count=len(result.report.removed_transaction_ids))
        return tr("tui.ledger.entry_tools.reset.not_done")

    def _offer_again(self) -> None:
        again = self.query_one("#entries-reset-again", Button)
        again.add_class("-open")
        again.focus()

    def _start_again(self) -> None:
        screen = LedgerResetScreen(self.controller, self.doors)
        screen.back_area = self.back_area
        replace_workspace_body(self.app, screen)

    @override
    def _cancel_flow(self) -> None:
        if self.flow_state not in {LedgerFlowState.EDITING, LedgerFlowState.CONFIRMING}:
            return
        self._transition(LedgerFlowState.CANCELLED)
        for button_id in ("#entries-reset-preview-button", "#entries-reset-run", "#entries-reset-cancel"):
            self.query_one(button_id, Button).disabled = True
        self.query_one("#entries-reset-reason", Input).disabled = True
        self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.entry_tools.reset.cancelled"))
        self._offer_again()


__all__ = ["LedgerResetScreen", "reset_preview_lines"]

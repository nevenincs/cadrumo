"""The one confirmed write step every evidence and attachment change passes through.

A tool stages a typed request and opens this screen with a review of exactly
what will change. Nothing is sent until the operator confirms; a destructive
change asks once more in a dialog. The outcome is read from the operation's own
result, and Back returns to the tool over a re-read workspace. The review and
the outcome are worded on demand, so a language change rewords them in place.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import ClassVar, Final, cast, override

from pydantic import ValidationError
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, DataTable, Static

from ....application.ledger.workspace import LedgerWorkspaceArea
from ....core.errors.hierarchy import CadrumoError
from ....core.i18n.render import tr
from ..account import AccountSessionExpiredError
from ..components.dialogs import ConfirmScreen
from ..components.language import localized, repaint_tables
from ..components.widgets import ContentDataTable
from ..components.workspace_host import replace_workspace_body
from ..operations.outcome import OperationOutcomeUnknownError, unknown_outcome_of
from .controller import LedgerWorkspaceController
from .evidence_files_common import EVIDENCE_FILES_CSS, EvidenceFilesPager, paging_controls, paint_paging
from .models import LedgerFlowState
from .workspace_presentation import LedgerConfirmationFlowScreen, door_refusal_text, ledger_workspace_page
from .workspace_screen import LedgerWorkspaceScreen

type EvidenceFilesOutcomeRowV1 = tuple[str, tuple[str, ...]]
"""One outcome row: its semantic key and its cells."""


@dataclass(frozen=True, slots=True)
class EvidenceFilesOutcomeV1:
    """What a settled write reported, worded for the operator."""

    lines: tuple[str, ...]
    """Summary lines, or the refusal's own messages when ``refused``."""
    refused: bool = False
    """Whether the operation refused the change before writing anything."""
    partial: bool = False
    """Whether the operation completed only part of the change."""
    columns: tuple[str, ...] = ()
    """The worded names of the per-record outcome columns."""
    rows: tuple[EvidenceFilesOutcomeRowV1, ...] = ()
    """One row per record the operation reported on."""


type EvidenceFilesWordingV1 = Callable[[], EvidenceFilesOutcomeV1]
"""Word a settled result in the operator's current language."""

type EvidenceFilesSubmitV1 = Callable[[], Awaitable[EvidenceFilesWordingV1]]
"""Send exactly the reviewed change and return how to word what its operation reported."""

type EvidenceFilesReviewV1 = Callable[[], tuple[str, ...]]
"""Word the staged change in the operator's current language."""

_STATUS_LOCALE_KEYS: Final[dict[LedgerFlowState, str]] = {
    LedgerFlowState.CONFIRMING: "tui.ledger.evidence_files.write.confirming",
    LedgerFlowState.SUBMITTING: "tui.ledger.evidence_files.write.saving",
    LedgerFlowState.FAILED: "tui.ledger.evidence_files.write.failed",
}


class LedgerEvidenceFilesWriteScreen(LedgerConfirmationFlowScreen):
    """Review one staged evidence change, submit it once confirmed, and show its outcome."""

    FLOW_NAME: ClassVar[str] = "evidence files"
    CSS = LedgerConfirmationFlowScreen.CSS + EVIDENCE_FILES_CSS

    def __init__(
        self,
        controller: LedgerWorkspaceController,
        *,
        title: Callable[[], str],
        review: EvidenceFilesReviewV1,
        destructive: bool,
        submit: EvidenceFilesSubmitV1,
        origin: Callable[[LedgerWorkspaceController], LedgerWorkspaceScreen],
        origin_area: LedgerWorkspaceArea | None,
    ) -> None:
        """Hold the reviewed change; ``submit`` sends exactly that change when called."""
        super().__init__(controller, id="ledger-evidence-files-write-screen")
        self._title = title
        self._review = review
        self._review_withdrawn = False
        self.destructive = destructive
        self._submit_change = submit
        self._origin = origin
        self._origin_area = origin_area
        self._wording: EvidenceFilesWordingV1 | None = None
        self._failure: CadrumoError | ValidationError | None = None
        self._outcome_rows: EvidenceFilesPager[EvidenceFilesOutcomeRowV1] = EvidenceFilesPager()

    @property
    def review_lines(self) -> tuple[str, ...]:
        """The staged change as the operator reads it now; nothing once the session is lost."""
        return () if self._review_withdrawn else self._review()

    @property
    def outcome(self) -> EvidenceFilesOutcomeV1 | None:
        """What the settled operation reported, worded now; ``None`` before it settles."""
        return None if self._wording is None else self._wording()

    @override
    def compose(self) -> ComposeResult:
        yield Static("", id="evidence-files-title", classes="cadrumo-banner", markup=False)
        with ledger_workspace_page() as navigation:
            yield navigation
            yield localized(
                Static(tr("tui.ledger.evidence_files.write.review_heading"), classes="cadrumo-heading", markup=False),
                "tui.ledger.evidence_files.write.review_heading",
            )
            yield Static("", id="evidence-files-review", markup=False)
            with Horizontal(id="evidence-files-decision", classes="evidence-files-actions"):
                yield localized(
                    Button(
                        tr("tui.ledger.evidence_files.write.confirm"), id="evidence-files-confirm", variant="primary"
                    ),
                    "tui.ledger.evidence_files.write.confirm",
                )
                yield localized(
                    Button(tr("tui.ledger.evidence_files.write.cancel"), id="evidence-files-cancel"),
                    "tui.ledger.evidence_files.write.cancel",
                )
            yield Static("", id="ledger-flow-status", markup=False)
            yield Static("", id="ledger-refusal", classes="ledger-refusal", markup=False)
            yield Static("", id="evidence-files-outcome", classes="evidence-files-detail", markup=False)
            yield ContentDataTable[str](id="evidence-files-outcome-rows", cursor_type="row", zebra_stripes=True)
            yield from paging_controls("evidence-files-outcome")
            yield localized(
                Button(tr("tui.ledger.evidence_files.write.done"), id="evidence-files-done"),
                "tui.ledger.evidence_files.write.done",
            )

    def on_mount(self) -> None:
        """The change arrives staged, so the screen opens at its confirmation."""
        self.populate_navigation()
        self._transition(LedgerFlowState.CONFIRMING)
        self._paint_words()
        self._show_outcome_controls()
        self.query_one("#evidence-files-confirm", Button).focus()

    @override
    async def refresh_language(self) -> None:
        await super().refresh_language()
        repaint_tables(self, self._paint)
        self._paint_words()

    def _paint(self) -> None:
        self.populate_navigation()
        self._paint_outcome_rows()

    def _paint_words(self) -> None:
        """Word the review, the state, the refusal and the outcome in the current language."""
        self.query_one("#evidence-files-title", Static).update(self._title())
        self.query_one("#evidence-files-review", Static).update("\n".join(self.review_lines))
        outcome = self.outcome
        refusal = ""
        outcome_text = ""
        status_key = _STATUS_LOCALE_KEYS.get(self.flow_state)
        if self._failure is not None:
            refusal = door_refusal_text(self._failure)
            if unknown_outcome_of(self._failure) is not None:
                status_key = "tui.ledger.flow.outcome_unknown"
        elif outcome is not None and outcome.refused:
            refusal = "\n".join(outcome.lines)
            status_key = "tui.ledger.evidence_files.write.refused"
        elif outcome is not None:
            outcome_text = "\n".join(outcome.lines)
            status_key = (
                "tui.ledger.evidence_files.write.partial"
                if outcome.partial
                else "tui.ledger.evidence_files.write.saved"
            )
        self.query_one("#ledger-flow-status", Static).update("" if status_key is None else tr(status_key))
        self.query_one("#ledger-refusal", Static).update(refusal)
        self.query_one("#evidence-files-outcome", Static).update(outcome_text)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Confirm, cancel, page the outcome, or return to the tool."""
        match event.button.id:
            case "evidence-files-confirm" if self.flow_state is LedgerFlowState.CONFIRMING:
                if self.destructive:
                    self.app.push_screen(
                        ConfirmScreen(
                            title=self._title,
                            message=lambda: "\n".join(self.review_lines),
                            confirm_label=lambda: tr("tui.ledger.evidence_files.write.confirm_destructive"),
                            cancel_label=lambda: tr("tui.ledger.evidence_files.write.keep"),
                        ),
                        self._on_destructive_decision,
                    )
                else:
                    self._submit()
            case "evidence-files-cancel":
                self.action_back()
            case "evidence-files-outcome-previous":
                self._outcome_rows.previous()
                self._paint_outcome_rows()
            case "evidence-files-outcome-next":
                self._outcome_rows.next()
                self._paint_outcome_rows()
            case "evidence-files-done":
                self.action_back()
            case _:
                return

    def _on_destructive_decision(self, accepted: bool | None) -> None:
        if accepted is True and self.flow_state is LedgerFlowState.CONFIRMING:
            self._submit()

    def _submit(self) -> None:
        self._transition(LedgerFlowState.SUBMITTING)
        self.query_one("#evidence-files-decision", Horizontal).display = False
        self._paint_words()
        self.run_worker(self._send(), exclusive=True)

    async def _send(self) -> None:
        try:
            wording = await self._submit_change()
        except (CadrumoError, ValidationError) as error:
            self._failure = error
            self._review_withdrawn = isinstance(error, AccountSessionExpiredError)
            self.write_outcome_unknown = isinstance(error, OperationOutcomeUnknownError)
            self._transition(LedgerFlowState.FAILED)
        else:
            self._wording = wording
            self._transition(LedgerFlowState.FAILED if wording().refused else LedgerFlowState.SUCCEEDED)
        self._paint_words()
        self._paint_outcome_rows()
        self._show_outcome_controls()

    def _show_outcome_controls(self) -> None:
        settled = self.flow_state in {LedgerFlowState.SUCCEEDED, LedgerFlowState.FAILED}
        has_rows = bool(self._outcome_rows.items)
        self.query_one("#evidence-files-outcome-rows", DataTable).display = has_rows
        self.query_one("#evidence-files-outcome-paging", Horizontal).display = has_rows
        self.query_one("#evidence-files-outcome-position", Static).display = has_rows
        done = self.query_one("#evidence-files-done", Button)
        done.display = settled
        if settled:
            done.focus()

    def _paint_outcome_rows(self) -> None:
        table = cast("DataTable[str]", self.query_one("#evidence-files-outcome-rows", DataTable))
        table.clear(columns=True)
        outcome = self.outcome
        if outcome is None or outcome.refused or not outcome.columns:
            return
        # Rows are re-worded with the outcome; the pager keeps its page over the fresh wording.
        self._outcome_rows.load(outcome.rows)
        for column in outcome.columns:
            table.add_column(column)
        for row_key, cells in self._outcome_rows.page():
            table.add_row(*cells, key=row_key)
        paint_paging(self, "evidence-files-outcome", self._outcome_rows)

    @override
    def _cancel_flow(self) -> None:
        if self.flow_state is not LedgerFlowState.CONFIRMING:
            return
        self._transition(LedgerFlowState.CANCELLED)
        self._return_to_origin()

    @override
    def action_back(self) -> None:
        """Refuse while a write is out; otherwise return to the tool that staged the change."""
        if self.refuse_leaving():
            return
        if self.flow_state is LedgerFlowState.CONFIRMING:
            self._cancel_flow()
            return
        if self.flow_state is LedgerFlowState.FAILED:
            # A refused or failed write can still leave an uncertain effect, so the tool re-reads either way.
            self.refresh_then(self._return_to_origin)
            return
        self.refresh_after_write(self._return_to_origin)

    def _return_to_origin(self) -> None:
        screen = self._origin(self.controller)
        screen.back_area = self._origin_area
        replace_workspace_body(self.app, screen)


__all__ = [
    "EvidenceFilesOutcomeRowV1",
    "EvidenceFilesOutcomeV1",
    "EvidenceFilesReviewV1",
    "EvidenceFilesSubmitV1",
    "EvidenceFilesWordingV1",
    "LedgerEvidenceFilesWriteScreen",
]

"""Export entries: ``ledger.export`` to a path the operator types, reviewed before it is written.

The screen reports what the export says it wrote. An export whose outcome is
unknown, or whose file was published but whose ledger record was not, is
reported as unknown or partial, in words, because the file may exist although
the ledger does not list the export.
"""

from __future__ import annotations

from itertools import count
from typing import ClassVar, Final, cast, override

from pydantic import ValidationError
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Checkbox, Input, Select, Static

from ....application.export.tabular import ExportSerializationFormat
from ....application.ledger.export_operation import LedgerExportProjection, LedgerExportRequest
from ....core.errors.hierarchy import CadrumoError, InternalInvariantError
from ....core.i18n.render import tr
from ....core.operations import OperationEffect
from ..account import AccountSessionExpiredError
from ..components.language import localized
from ..components.theme import tokenised
from ..components.workspace_host import replace_workspace_body
from ..operations.outcome import OperationOutcomeUnknownError
from .controller import LedgerWorkspaceController
from .entries_common import joined, period_label, period_options, read_period, selected_value
from .entries_doors import LedgerEntriesDoorsV1
from .models import LedgerFlowState
from .workspace_presentation import LedgerConfirmationFlowScreen, door_refusal_text, ledger_workspace_page

_FORMAT_LOCALE_KEYS: Final[dict[ExportSerializationFormat, str]] = {
    ExportSerializationFormat.CSV: "tui.ledger.entry_tools.export.format.csv",
    ExportSerializationFormat.JSONL: "tui.ledger.entry_tools.export.format.jsonl",
    ExportSerializationFormat.XLSX: "tui.ledger.entry_tools.export.format.xlsx",
}

#: Starting a flow again replaces its screen while the outgoing one is still
#: being removed, so each instance carries its own identity.
_SCREEN_SERIALS: Final = count()


def _format_options() -> list[tuple[str, str]]:
    return [(tr(key), member.value) for member, key in _FORMAT_LOCALE_KEYS.items()]


def staged_export_lines(request: LedgerExportRequest) -> tuple[str, ...]:
    """Name what the reviewed export will write and where."""
    return (
        tr("tui.ledger.entry_tools.export.staged.path", path=request.output_path),
        tr("tui.ledger.entry_tools.export.staged.format", format=tr(_FORMAT_LOCALE_KEYS[request.export_format])),
        tr("tui.ledger.entry_tools.export.staged.period", period=period_label(request.period)),
        tr(
            "tui.ledger.entry_tools.export.staged.inactive_included"
            if request.include_inactive
            else "tui.ledger.entry_tools.export.staged.inactive_left_out"
        ),
    )


def export_outcome_lines(
    outcome: LedgerExportProjection | OperationOutcomeUnknownError, request: LedgerExportRequest
) -> tuple[str, ...]:
    """Say what the export reports it wrote, or that it is partial or unknown."""
    if isinstance(outcome, LedgerExportProjection):
        return (
            tr("tui.ledger.entry_tools.export.written", path=outcome.output_path),
            tr(
                "tui.ledger.entry_tools.export.written_facts",
                rows=outcome.row_count,
                bytes=outcome.byte_size,
                format=tr(_FORMAT_LOCALE_KEYS[outcome.export_format]),
            ),
            tr("tui.ledger.entry_tools.export.digest", digest=outcome.sha256),
        )
    headline = tr(
        "tui.ledger.entry_tools.export.partial"
        if outcome.effect is OperationEffect.PARTIAL
        else "tui.ledger.entry_tools.export.unknown",
        path=request.output_path,
    )
    reason = "" if outcome.reason is None else door_refusal_text(outcome.reason)
    return (headline, reason, door_refusal_text(outcome))


class LedgerEntriesExportScreen(LedgerConfirmationFlowScreen):
    """Choose the format, period and destination, review, then export."""

    FLOW_NAME = "entries_export"
    CSS: ClassVar[str] = LedgerConfirmationFlowScreen.CSS + tokenised(
        """
        .entries-export-row { height: auto; width: 100%; }
        .entries-export-row > * { width: 1fr; min-width: 0; }
        #entries-export-summary { height: auto; }
        #entries-export-again { display: none; }
        #entries-export-again.-open { display: block; }
        """
    )

    def __init__(self, controller: LedgerWorkspaceController, doors: LedgerEntriesDoorsV1) -> None:
        """Keep the injected doors; nothing is staged yet."""
        super().__init__(controller, id=f"ledger-entries-export-screen-{next(_SCREEN_SERIALS)}")
        self.doors = doors
        self.staged: LedgerExportRequest | None = None
        self.outcome: LedgerExportProjection | OperationOutcomeUnknownError | None = None

    @override
    def compose(self) -> ComposeResult:
        yield localized(
            Static(tr("tui.ledger.entry_tools.export.title"), classes="cadrumo-banner"),
            "tui.ledger.entry_tools.export.title",
        )
        with ledger_workspace_page() as navigation:
            yield navigation
            yield localized(
                Static(tr("tui.ledger.entry_tools.export.prompt"), markup=False),
                "tui.ledger.entry_tools.export.prompt",
            )
            with Horizontal(classes="entries-export-row"):
                yield Select[str](
                    _format_options(),
                    value=ExportSerializationFormat.CSV.value,
                    allow_blank=False,
                    id="entries-export-format",
                )
                yield localized(
                    Input(placeholder=tr("tui.ledger.entry_tools.field.year"), max_length=4, id="entries-export-year"),
                    "tui.ledger.entry_tools.field.year",
                )
                yield Select[str](
                    period_options(), prompt=tr("tui.ledger.entry_tools.period.any"), id="entries-export-period"
                )
            yield Checkbox(tr("tui.ledger.entry_tools.export.include_inactive"), id="entries-export-inactive")
            yield localized(
                Static(tr("tui.ledger.entry_tools.export.path"), markup=False), "tui.ledger.entry_tools.export.path"
            )
            yield Input(id="entries-export-path")
            with Horizontal(classes="entries-export-row"):
                yield localized(
                    Button(tr("tui.ledger.entry_tools.export.review"), id="entries-export-review", variant="primary"),
                    "tui.ledger.entry_tools.export.review",
                )
                yield localized(
                    Button(tr("tui.ledger.entry_tools.confirm"), id="entries-export-confirm", disabled=True),
                    "tui.ledger.entry_tools.confirm",
                )
                yield localized(
                    Button(tr("tui.ledger.entry_tools.cancel"), id="entries-export-cancel"),
                    "tui.ledger.entry_tools.cancel",
                )
            yield Static("", id="entries-export-summary", markup=False)
            yield Static("", id="ledger-flow-status", markup=False)
            yield localized(
                Button(tr("tui.ledger.entry_tools.export.again"), id="entries-export-again"),
                "tui.ledger.entry_tools.export.again",
            )
            yield Static("", id="ledger-refusal", classes="ledger-refusal", markup=False)

    def on_mount(self) -> None:
        """Start at the destination the operator must type."""
        self.populate_navigation()
        self.query_one("#entries-export-path", Input).focus()

    @override
    async def refresh_language(self) -> None:
        """Reword choices and the reviewed or written facts in place."""
        await super().refresh_language()
        select = cast("Select[str]", self.query_one("#entries-export-format", Select))
        value = select.value
        select.set_options(_format_options())
        select.value = value
        self.query_one("#entries-export-inactive", Checkbox).label = tr(
            "tui.ledger.entry_tools.export.include_inactive"
        )
        if self.staged is not None:
            self.query_one("#entries-export-summary", Static).update(joined(staged_export_lines(self.staged)))
            if self.outcome is not None:
                self.query_one("#ledger-flow-status", Static).update(
                    joined(export_outcome_lines(self.outcome, self.staged))
                )

    def _form_request(self) -> LedgerExportRequest:
        period = read_period(
            self.query_one("#entries-export-year", Input).value,
            selected_value(self.query_one("#entries-export-period", Select)),
        )
        try:
            return LedgerExportRequest(
                profile_id=self.doors.profile_id,
                output_path=self.query_one("#entries-export-path", Input).value.strip(),
                export_format=ExportSerializationFormat(
                    str(cast("Select[str]", self.query_one("#entries-export-format", Select)).value)
                ),
                include_inactive=self.query_one("#entries-export-inactive", Checkbox).value,
                period=period,
            )
        except ValidationError:
            raise ValueError(tr("tui.ledger.entry_tools.export.path_invalid")) from None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Route each control through the flow's guarded transitions."""
        notice = self.query_one("#ledger-refusal", Static)
        status = self.query_one("#ledger-flow-status", Static)
        match event.button.id:
            case "entries-export-review" if self.flow_state is LedgerFlowState.EDITING:
                try:
                    self.staged = self._form_request()
                except ValueError as error:
                    notice.update(str(error))
                    return
                notice.update("")
                self.query_one("#entries-export-summary", Static).update(joined(staged_export_lines(self.staged)))
                self._lock_form()
                self._transition(LedgerFlowState.CONFIRMING)
                status.update(tr("tui.ledger.entry_tools.export.confirming"))
                confirm = self.query_one("#entries-export-confirm", Button)
                confirm.disabled = False
                confirm.focus()
            case "entries-export-cancel" if self.flow_state in {LedgerFlowState.EDITING, LedgerFlowState.CONFIRMING}:
                self._cancel_flow()
            case "entries-export-confirm" if self.flow_state is LedgerFlowState.CONFIRMING:
                self._transition(LedgerFlowState.SUBMITTING)
                event.button.disabled = True
                self.query_one("#entries-export-cancel", Button).disabled = True
                status.update(tr("tui.ledger.entry_tools.export.writing"))
                self.run_worker(self._submit(), exclusive=True)
            case "entries-export-again" if self.flow_state in {
                LedgerFlowState.SUCCEEDED,
                LedgerFlowState.FAILED,
                LedgerFlowState.CANCELLED,
            }:
                self.refresh_after_write(self._start_again)
            case _:
                return

    def _start_again(self) -> None:
        screen = LedgerEntriesExportScreen(self.controller, self.doors)
        screen.back_area = self.back_area
        replace_workspace_body(self.app, screen)

    def _lock_form(self) -> None:
        for widget in self.query(Input):
            widget.disabled = True
        for widget in self.query(Select):
            widget.disabled = True
        self.query_one("#entries-export-inactive", Checkbox).disabled = True
        self.query_one("#entries-export-review", Button).disabled = True

    async def _submit(self) -> None:
        """Write exactly the reviewed export and report what it wrote."""
        status = self.query_one("#ledger-flow-status", Static)
        notice = self.query_one("#ledger-refusal", Static)
        request = self.staged
        if request is None:
            raise InternalInvariantError("the reviewed export disappeared before submission")
        try:
            written = await self.doors.export(request)
        except OperationOutcomeUnknownError as error:
            # The file may exist although the ledger does not list it, so the workspace is re-read on leaving.
            self.outcome = error
            self.write_outcome_unknown = True
            self._transition(LedgerFlowState.FAILED)
            status.update(joined(export_outcome_lines(error, request)))
        except AccountSessionExpiredError as error:
            self._transition(LedgerFlowState.FAILED)
            status.update(tr("tui.ledger.entry_tools.export.failed"))
            notice.update(door_refusal_text(error))
        except CadrumoError as error:
            self._transition(LedgerFlowState.FAILED)
            status.update(tr("tui.ledger.entry_tools.export.failed"))
            notice.update(door_refusal_text(error))
        else:
            self.outcome = written
            self._transition(LedgerFlowState.SUCCEEDED)
            status.update(joined(export_outcome_lines(written, request)))
        again = self.query_one("#entries-export-again", Button)
        again.add_class("-open")
        again.focus()

    @override
    def _cancel_flow(self) -> None:
        if self.flow_state not in {LedgerFlowState.EDITING, LedgerFlowState.CONFIRMING}:
            return
        self._transition(LedgerFlowState.CANCELLED)
        self._lock_form()
        self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.entry_tools.cancelled"))
        self.query_one("#entries-export-confirm", Button).disabled = True
        self.query_one("#entries-export-cancel", Button).disabled = True
        again = self.query_one("#entries-export-again", Button)
        again.add_class("-open")
        again.focus()


__all__ = ["LedgerEntriesExportScreen", "export_outcome_lines", "staged_export_lines"]

"""Invoice book import in the Ledger workspace.

The registered invoice import has no dry run, so the review shows the file the
operator chose as the host found it: its name, size and SHA-256. Applying sends
that digest with the request, so a file whose bytes changed after the review is
refused instead of imported. The outcome then shows every count and refused
row the operation reports, and calls a partly refused import partial.
"""

from __future__ import annotations

from collections import Counter
from typing import Annotated, ClassVar, Final, Protocol, cast, override
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, DataTable, Input, Select, Static

from ....application.invoices.catalogue_intake_contracts import InvoiceImportProjection, InvoiceImportRequest
from ....core.errors.hierarchy import CadrumoError
from ....core.hex import Hex64Str
from ....core.i18n.render import tr
from ....core.models import STRICT_FROZEN_CONFIG
from ....domain.iva.schema import InvoiceKind
from ..components.language import localized, repaint_tables
from ..components.theme import tokenised
from ..components.widgets import ContentDataTable
from ..components.workspace_host import replace_workspace_body
from .controller import LedgerWorkspaceController
from .models import LedgerFlowState
from .workspace_presentation import LedgerConfirmationFlowScreen, door_refusal_text, ledger_workspace_page

_KIND_LOCALE_KEYS: Final = {
    InvoiceKind.RECEIVED: "tui.ledger.invoice.kind.received",
    InvoiceKind.ISSUED: "tui.ledger.invoice.kind.issued",
}
_FORM_CONTROLS: Final = (
    "#ledger-invoices-import-kind",
    "#ledger-invoices-import-path",
    "#ledger-invoices-import-country",
)


class LedgerInvoiceImportSourceV1(BaseModel):
    """The file a review found, as the host read it."""

    model_config = STRICT_FROZEN_CONFIG

    source_path: Annotated[str, Field(min_length=1, max_length=4096)]
    """The absolute reference the import will read."""
    file_name: str
    size_bytes: Annotated[int, Field(ge=0)]
    sha256: Hex64Str


class LedgerInvoiceImportFormV1(BaseModel):
    """What the operator typed, carried into a fresh form after an import settles."""

    model_config = STRICT_FROZEN_CONFIG

    kind: InvoiceKind = InvoiceKind.RECEIVED
    source_path: str = ""
    country: str = ""


class LedgerInvoiceImportDoorV1(Protocol):
    """Injected door to ``ledger.invoice.import`` for one admitted profile."""

    @property
    def profile_id(self) -> UUID:
        """The profile every request through this door must name."""
        ...

    async def preview(self, source_path: str) -> LedgerInvoiceImportSourceV1:
        """Find the typed file on the host and digest its bytes, writing nothing."""
        ...

    async def apply(self, request: InvoiceImportRequest) -> InvoiceImportProjection:
        """Import the reviewed file, refused if its bytes no longer match the reviewed digest."""
        ...


def _kind_label(kind: InvoiceKind) -> str:
    return tr(_KIND_LOCALE_KEYS[kind])


class LedgerInvoiceImportScreen(LedgerConfirmationFlowScreen):
    """Review one invoice book by its digest, then import exactly that file."""

    FLOW_NAME: ClassVar[str] = "invoice_import"
    DEFAULT_CSS = tokenised(
        """
        .ledger-invoices-actions { height: auto; margin-bottom: $cadrumo-stack; }
        .ledger-invoices-actions Button { margin-right: $cadrumo-space-1; }
        #ledger-invoices-import-summary { height: auto; text-style: bold; }
        """
    )

    def __init__(
        self,
        controller: LedgerWorkspaceController,
        door: LedgerInvoiceImportDoorV1,
        *,
        form: LedgerInvoiceImportFormV1 | None = None,
    ) -> None:
        """Keep the injected door and the values a previous attempt left in the form."""
        super().__init__(controller, id="ledger-invoices-import-screen")
        self.door = door
        self.form = form or LedgerInvoiceImportFormV1()
        self.source: LedgerInvoiceImportSourceV1 | None = None
        self.request: InvoiceImportRequest | None = None
        self.outcome: InvoiceImportProjection | None = None
        self._previewing = False

    @override
    def compose(self) -> ComposeResult:
        yield localized(
            Static(tr("tui.ledger.invoices.import.title"), classes="cadrumo-banner"), "tui.ledger.invoices.import.title"
        )
        with ledger_workspace_page() as navigation:
            yield navigation
            yield localized(
                Static(tr("tui.ledger.invoices.import.prompt"), markup=False), "tui.ledger.invoices.import.prompt"
            )
            yield localized(Static(tr("tui.ledger.invoice.field.kind"), markup=False), "tui.ledger.invoice.field.kind")
            yield Select[str](
                tuple((_kind_label(kind), kind.value) for kind in InvoiceKind),
                value=self.form.kind.value,
                allow_blank=False,
                id="ledger-invoices-import-kind",
            )
            yield localized(
                Static(tr("tui.ledger.invoices.import.path"), markup=False), "tui.ledger.invoices.import.path"
            )
            yield Input(value=self.form.source_path, id="ledger-invoices-import-path")
            yield localized(
                Static(tr("tui.ledger.invoices.import.country"), markup=False), "tui.ledger.invoices.import.country"
            )
            yield Input(value=self.form.country, max_length=2, id="ledger-invoices-import-country")
            with Horizontal(classes="ledger-invoices-actions"):
                yield localized(
                    Button(tr("tui.ledger.invoices.import.review"), id="ledger-invoices-import-review"),
                    "tui.ledger.invoices.import.review",
                )
            yield Static("", id="ledger-invoices-import-summary", markup=False)
            with Horizontal(id="ledger-invoices-import-decision", classes="ledger-invoices-actions"):
                yield localized(
                    Button(
                        tr("tui.ledger.invoices.import.confirm"),
                        id="ledger-invoices-import-confirm",
                        variant="primary",
                        disabled=True,
                    ),
                    "tui.ledger.invoices.import.confirm",
                )
                yield localized(
                    Button(tr("tui.ledger.records.cancel"), id="ledger-invoices-import-cancel", disabled=True),
                    "tui.ledger.records.cancel",
                )
            yield Static("", id="ledger-flow-status", markup=False)
            yield Static("", id="ledger-refusal", classes="ledger-refusal", markup=False)
            yield Static("", id="ledger-invoices-import-outcome", markup=False)
            yield ContentDataTable[str](id="ledger-invoices-import-refused", cursor_type="row", zebra_stripes=True)
            yield localized(
                Button(tr("tui.ledger.invoices.import.again"), id="ledger-invoices-import-again"),
                "tui.ledger.invoices.import.again",
            )

    @override
    async def refresh_language(self) -> None:
        """Reword the refused-row table without re-reading anything."""
        await super().refresh_language()
        repaint_tables(self, self._repaint)

    def on_mount(self) -> None:
        """Start at the path the operator types."""
        self.query_one("#ledger-invoices-import-decision", Horizontal).display = False
        self.query_one("#ledger-invoices-import-again", Button).display = False
        self._repaint()
        self.query_one("#ledger-invoices-import-path", Input).focus()

    def _repaint(self) -> None:
        self.populate_navigation()
        table = cast("DataTable[str]", self.query_one("#ledger-invoices-import-refused", DataTable))
        table.add_column(tr("tui.ledger.invoices.import.column.row"), key="row", width=6)
        table.add_column(tr("tui.ledger.invoices.import.column.field"), key="field", width=18)
        table.add_column(tr("tui.ledger.invoices.import.column.reason"), key="reason", width=40)
        refused = () if self.outcome is None else self.outcome.refused
        seen: Counter[tuple[int, str]] = Counter()
        for row in refused:
            seen[(row.row_number, row.field)] += 1
            table.add_row(
                str(row.row_number),
                row.field,
                row.reason,
                key=f"{row.row_number}:{row.field}:{seen[(row.row_number, row.field)]}",
                height=None,
            )
        table.display = bool(refused)

    def _entered_form(self) -> LedgerInvoiceImportFormV1:
        return LedgerInvoiceImportFormV1(
            kind=InvoiceKind(str(cast("Select[str]", self.query_one("#ledger-invoices-import-kind", Select)).value)),
            source_path=self.query_one("#ledger-invoices-import-path", Input).value.strip(),
            country=self.query_one("#ledger-invoices-import-country", Input).value.strip().upper(),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Review the file, import exactly the reviewed file, cancel, or start again."""
        button_id = event.button.id
        if button_id == "ledger-invoices-import-again":
            self._start_again()
        elif button_id == "ledger-invoices-import-review" and self.flow_state is LedgerFlowState.EDITING:
            self._review()
        elif button_id == "ledger-invoices-import-cancel" and self.flow_state is LedgerFlowState.CONFIRMING:
            self._cancel_flow()
        elif button_id == "ledger-invoices-import-confirm" and self.flow_state is LedgerFlowState.CONFIRMING:
            self._confirm()

    def _review(self) -> None:
        if self._previewing:
            self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.flow.in_flight_refusal"))
            return
        refusal = self.query_one("#ledger-refusal", Static)
        refusal.update("")
        self.form = self._entered_form()
        if not self.form.source_path:
            refusal.update(tr("tui.ledger.invoices.import.path_required"))
            return
        self._previewing = True
        self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.invoices.import.reading"))
        self.run_worker(self._preview(self.form.source_path), exclusive=True)

    async def _preview(self, source_path: str) -> None:
        status = self.query_one("#ledger-flow-status", Static)
        try:
            source = await self.door.preview(source_path)
            request = InvoiceImportRequest(
                profile_id=self.door.profile_id,
                kind=self.form.kind,
                source_path=source.source_path,
                source_sha256=source.sha256,
                country=self.form.country or None,
            )
        except (CadrumoError, ValidationError) as error:
            self.query_one("#ledger-refusal", Static).update(door_refusal_text(error))
            status.update("")
            return
        finally:
            self._previewing = False
        self.source = source
        self.request = request
        self._transition(LedgerFlowState.CONFIRMING)
        self.query_one("#ledger-invoices-import-summary", Static).update(
            "\n".join(
                (
                    tr("tui.ledger.invoices.import.summary.file", name=source.file_name, size=str(source.size_bytes)),
                    tr("tui.ledger.invoices.import.summary.digest", digest=source.sha256),
                    tr(
                        "tui.ledger.invoices.import.summary.kind",
                        kind=_kind_label(request.kind),
                        country=request.country or "-",
                    ),
                    tr("tui.ledger.invoices.import.summary.no_preview"),
                )
            )
        )
        status.update(tr("tui.ledger.invoices.import.confirming"))
        self._set_form_disabled(disabled=True)
        self.query_one("#ledger-invoices-import-decision", Horizontal).display = True
        self.query_one("#ledger-invoices-import-confirm", Button).disabled = False
        self.query_one("#ledger-invoices-import-cancel", Button).disabled = False
        self.query_one("#ledger-invoices-import-confirm", Button).focus()

    def _confirm(self) -> None:
        request = self.request
        if request is None:
            return
        self._transition(LedgerFlowState.SUBMITTING)
        self.query_one("#ledger-invoices-import-confirm", Button).disabled = True
        self.query_one("#ledger-invoices-import-cancel", Button).disabled = True
        self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.invoices.import.importing"))
        self.run_worker(self._apply(request), exclusive=True)

    async def _apply(self, request: InvoiceImportRequest) -> None:
        status = self.query_one("#ledger-flow-status", Static)
        try:
            outcome = await self.door.apply(request)
        except CadrumoError as error:
            self._transition(LedgerFlowState.FAILED)
            self.query_one("#ledger-refusal", Static).update(door_refusal_text(error))
            status.update(tr("tui.ledger.invoices.import.failed"))
            self._settled()
            return
        self._transition(LedgerFlowState.SUCCEEDED)
        self.outcome = outcome
        status.update(self._headline(outcome))
        self.query_one("#ledger-invoices-import-outcome", Static).update("\n".join(self._outcome_lines(outcome)))
        repaint_tables(self, self._repaint)
        self._settled()

    @staticmethod
    def _headline(outcome: InvoiceImportProjection) -> str:
        if outcome.created == 0:
            return tr("tui.ledger.invoices.import.nothing_created")
        if outcome.refused:
            return tr("tui.ledger.invoices.import.partial")
        return tr("tui.ledger.invoices.import.succeeded")

    @staticmethod
    def _outcome_lines(outcome: InvoiceImportProjection) -> list[str]:
        lines = [
            tr(
                "tui.ledger.invoices.import.counts",
                rows=str(outcome.rows),
                created=str(outcome.created),
                skipped=str(outcome.skipped_duplicate),
                refused=str(len(outcome.refused)),
            ),
            tr("tui.ledger.invoices.import.summary.digest", digest=outcome.source_sha256),
        ]
        if outcome.unmapped_column_headers:
            lines.append(tr("tui.ledger.invoices.import.unmapped", columns=", ".join(outcome.unmapped_column_headers)))
        lines.extend(outcome.mapping_reasons)
        return lines

    def _settled(self) -> None:
        self.query_one("#ledger-invoices-import-decision", Horizontal).display = False
        again = self.query_one("#ledger-invoices-import-again", Button)
        again.display = True
        again.focus()

    @override
    def _cancel_flow(self) -> None:
        """Cancel before anything is submitted; nothing has been written."""
        if self.flow_state not in {LedgerFlowState.EDITING, LedgerFlowState.CONFIRMING}:
            return
        self._transition(LedgerFlowState.CANCELLED)
        self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.invoices.import.cancelled"))
        self._settled()

    def _set_form_disabled(self, *, disabled: bool) -> None:
        for selector in _FORM_CONTROLS:
            self.query_one(selector).disabled = disabled
        self.query_one("#ledger-invoices-import-review", Button).disabled = disabled

    def _start_again(self) -> None:
        """Open a fresh form carrying what was typed, once this attempt has settled."""
        if self.flow_state not in {LedgerFlowState.SUCCEEDED, LedgerFlowState.FAILED, LedgerFlowState.CANCELLED}:
            return
        form = self.form

        def reopen() -> None:
            screen = LedgerInvoiceImportScreen(self.controller, self.door, form=form)
            screen.back_area = self.back_area
            replace_workspace_body(self.app, screen)

        self.refresh_after_write(reopen)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Answer the area navigation; refused rows are read-only."""
        if self.flow_state is LedgerFlowState.SUBMITTING:
            self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.flow.in_flight_refusal"))
            return
        self.handle_navigation_selection(event)


__all__ = [
    "LedgerInvoiceImportDoorV1",
    "LedgerInvoiceImportFormV1",
    "LedgerInvoiceImportScreen",
    "LedgerInvoiceImportSourceV1",
]

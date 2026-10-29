"""Ledger evidence: drafts waiting for review, the attachment queue, local invoice documents, and adding one.

The drafts waiting for review are the registered review-queue read's own
answer for the admitted profile, read off the event loop when the area opens.
That read has no paging, so its whole answer is held and one page of it is
rendered at a time.
"""

from __future__ import annotations

from typing import ClassVar, Final, Protocol, cast, override
from uuid import UUID

from pydantic import ValidationError
from textual import on
from textual.app import ComposeResult
from textual.widgets import Button, DataTable, Input, Select, Static

from ....application.ledger.evidence_followup_contracts import (
    EvidenceReviewQueueRowProjection,
    LedgerEvidenceReviewListProjection,
    LedgerEvidenceReviewListRequest,
)
from ....application.ledger.workspace import LedgerWorkspaceArea
from ....core.confirmation_gate import ReviewAdvisoryKind
from ....core.errors.hierarchy import CadrumoError
from ....core.i18n.render import tr
from ....domain.iva.schema import InvoiceKind
from ..account import AccountSessionExpiredError
from ..components.language import localized
from ..components.widgets import ContentDataTable, ContentScroll
from .controller import LedgerWorkspaceController
from .evidence_files_common import EvidenceFilesPager, paging_controls, paint_paging, short_identity
from .evidence_files_review import review_reason_label
from .evidence_records import LedgerEvidenceRecordActions
from .models import (
    LedgerEvidenceDraftV1,
    LedgerEvidenceRecordRowV1,
)
from .workspace_presentation import door_refusal_text
from .workspace_screen import LedgerEvidenceReviewRequested

_KIND_LOCALE_KEYS: Final[dict[InvoiceKind, str]] = {
    InvoiceKind.RECEIVED: "tui.ledger.invoice.kind.received",
    InvoiceKind.ISSUED: "tui.ledger.invoice.kind.issued",
}
_ADVISORY_LOCALE_KEYS: Final[dict[ReviewAdvisoryKind, str]] = {
    ReviewAdvisoryKind.PARTY_ATTRIBUTION: "tui.ledger.evidence.review_queue.advisory.party_attribution",
    ReviewAdvisoryKind.COUNTRY_CODE_UNASSIGNED: "tui.ledger.evidence.review_queue.advisory.country_code_unassigned",
    ReviewAdvisoryKind.COUNTRY_CODE_UNCATALOGUED: (
        "tui.ledger.evidence.review_queue.advisory.country_code_uncatalogued"
    ),
}
_REVIEW_QUEUE: Final = "ledger-evidence-review-queue"
"""The id of the drafts-waiting-for-review table, and the prefix of its paging controls."""


class LedgerEvidenceReviewListDoorV1(Protocol):
    """Injected door to ``ledger.evidence.review.list`` for one admitted profile."""

    @property
    def profile_id(self) -> UUID:
        """The profile every request through this door must name."""
        ...

    async def __call__(self, request: LedgerEvidenceReviewListRequest) -> LedgerEvidenceReviewListProjection:
        """Read the drafts waiting for review, correlated with the operation's terminal receipt."""
        ...


def review_queue_detail_lines(row: EvidenceReviewQueueRowProjection) -> tuple[str, ...]:
    """Word one waiting draft: who read it and when, what blocks it, and what is worth a look."""
    return (
        tr(
            "tui.ledger.evidence.review_queue.detail",
            reference=row.evidence_reference,
            extractor=row.extractor,
            date=row.drafted_at.date().isoformat(),
        ),
        tr("tui.ledger.evidence.review_queue.blocking", count=row.blocking_count),
        *(f"  - {review_reason_label(reason)}" for reason in row.reasons),
        tr("tui.ledger.evidence.review_queue.advisories", count=row.advisory_count),
        *(f"  - {tr(_ADVISORY_LOCALE_KEYS[advisory])}" for advisory in row.advisories),
    )


class LedgerEvidenceScreen(LedgerEvidenceRecordActions):
    """Render safe evidence metadata without document contents or source locators."""

    WORKSPACE_AREA: ClassVar[LedgerWorkspaceArea | None] = LedgerWorkspaceArea.EVIDENCE

    def __init__(self, controller: LedgerWorkspaceController) -> None:
        """Retain an injected canonical review queue."""
        super().__init__(controller, id="ledger-evidence-screen")
        self.selected_evidence_id: str | None = None
        self.selected_record_id: str | None = None
        self._reviewed_evidence_id: str | None = None
        self.requested_review: LedgerEvidenceReviewRequested | None = None
        self._records: tuple[LedgerEvidenceRecordRowV1, ...] | None = None
        self.draft: LedgerEvidenceDraftV1 | None = None
        self.reading = False
        """Whether a read, an addition or a confirmation is out; a second press waits for it."""
        self.add_awaits_reread = False
        self.records_loads = 0
        self.add_reread_after = 0
        self.review_queue: EvidenceFilesPager[EvidenceReviewQueueRowProjection] = EvidenceFilesPager()
        """Every draft waiting for review the last read returned; only one page of it is rendered."""
        self.selected_draft: EvidenceReviewQueueRowProjection | None = None

    @override
    def compose(self) -> ComposeResult:
        yield localized(Static(tr("tui.ledger.evidence.title"), classes="cadrumo-banner"), "tui.ledger.evidence.title")
        with ContentScroll(id="ledger-page", classes="cadrumo-scroll ledger-page"):
            yield ContentDataTable[str](id="ledger-navigation", cursor_type="row", zebra_stripes=True)
            yield localized(
                Static(tr("tui.ledger.evidence.safe_metadata"), markup=False), "tui.ledger.evidence.safe_metadata"
            )
            if self.controller.evidence_review_door is not None:
                yield localized(
                    Static(tr("tui.ledger.evidence.review_queue.heading"), classes="cadrumo-heading", markup=False),
                    "tui.ledger.evidence.review_queue.heading",
                )
                yield localized(
                    Static(tr("tui.ledger.evidence.review_queue.prompt"), markup=False),
                    "tui.ledger.evidence.review_queue.prompt",
                )
                yield ContentDataTable[str](id=_REVIEW_QUEUE, cursor_type="row", zebra_stripes=True)
                yield from paging_controls(_REVIEW_QUEUE)
                yield Static("", id=f"{_REVIEW_QUEUE}-status", markup=False)
                yield Static("", id=f"{_REVIEW_QUEUE}-detail", markup=False)
            if self._has_attachment_review_queue:
                yield localized(
                    Static(tr("tui.ledger.evidence.queue_heading"), classes="cadrumo-heading", markup=False),
                    "tui.ledger.evidence.queue_heading",
                )
                yield ContentDataTable[str](id="ledger-evidence", cursor_type="row", zebra_stripes=True)
                yield Static("", id="ledger-evidence-detail", markup=False)
            if self.controller.evidence_door is not None:
                yield localized(
                    Static(tr("tui.ledger.evidence.records_heading"), classes="cadrumo-heading", markup=False),
                    "tui.ledger.evidence.records_heading",
                )
                yield Static("", id="ledger-evidence-reader", markup=False)
                yield ContentDataTable[str](id="ledger-evidence-records", cursor_type="row", zebra_stripes=True)
                yield Static("", id="ledger-evidence-record-detail", markup=False)
                yield localized(
                    Button(tr("tui.ledger.evidence.extract"), id="ledger-evidence-extract", disabled=True),
                    "tui.ledger.evidence.extract",
                )
                yield Static("", id="ledger-evidence-draft", markup=False)
                yield localized(
                    Static(tr("tui.ledger.invoice.field.kind"), markup=False), "tui.ledger.invoice.field.kind"
                )
                yield Select[str](
                    tuple((tr(_KIND_LOCALE_KEYS[kind]), kind.value) for kind in InvoiceKind),
                    value=InvoiceKind.RECEIVED.value,
                    allow_blank=False,
                    id="ledger-evidence-kind",
                )
                yield localized(
                    Static(tr("tui.ledger.invoice.field.country_code"), markup=False),
                    "tui.ledger.invoice.field.country_code",
                )
                yield Input(value="ES", max_length=2, id="ledger-evidence-country")
                yield localized(
                    Static(
                        tr("tui.ledger.invoice.optional", label=tr("tui.ledger.invoice.field.counterparty_name")),
                        markup=False,
                    ),
                    "tui.ledger.invoice.optional",
                    label=tr("tui.ledger.invoice.field.counterparty_name"),
                )
                yield Input(id="ledger-evidence-counterparty")
                yield localized(
                    Button(tr("tui.ledger.evidence.confirm"), id="ledger-evidence-confirm", disabled=True),
                    "tui.ledger.evidence.confirm",
                )
                yield localized(
                    Static(tr("tui.ledger.evidence.add_label"), markup=False), "tui.ledger.evidence.add_label"
                )
                yield localized(
                    Input(placeholder=tr("tui.ledger.evidence.path_placeholder"), id="ledger-evidence-path"),
                    "tui.ledger.evidence.path_placeholder",
                )
                yield localized(
                    Button(tr("tui.ledger.evidence.add"), id="ledger-evidence-add", variant="primary"),
                    "tui.ledger.evidence.add",
                )
                yield Static("", id="ledger-flow-status", markup=False)
            yield Static(id="ledger-refusal", classes="ledger-refusal", markup=False)

    def on_mount(self) -> None:
        """Populate application-supplied safe metadata with semantic row keys."""
        self.populate_navigation()
        door = self.controller.evidence_review_door
        if door is not None:
            self._paint_review_queue()
            self.query_one(f"#{_REVIEW_QUEUE}-status", Static).update(tr("tui.ledger.evidence.review_queue.loading"))
            self.run_worker(self._load_review_queue(door), group="ledger-evidence-review-queue", exclusive=True)
        if self._has_attachment_review_queue:
            self._mount_attachment_review_queue()
        if self.controller.evidence_door is not None:
            self._mount_evidence_records()
        self._focus_initial_table()

    async def _load_review_queue(self, door: LedgerEvidenceReviewListDoorV1) -> None:
        status = self.query_one(f"#{_REVIEW_QUEUE}-status", Static)
        try:
            result = await door(LedgerEvidenceReviewListRequest(profile_id=door.profile_id))
        except AccountSessionExpiredError as error:
            self._forget_review_queue()
            status.update(tr("tui.ledger.evidence.review_queue.failed"))
            self.query_one("#ledger-refusal", Static).update(door_refusal_text(error))
            return
        except (CadrumoError, ValidationError) as error:
            status.update(tr("tui.ledger.evidence.review_queue.failed"))
            self.query_one("#ledger-refusal", Static).update(door_refusal_text(error))
            return
        self.review_queue.load(result.rows)
        status.update("" if result.rows else tr("tui.ledger.evidence.review_queue.empty"))
        self._paint_review_queue()

    def _paint_review_queue(self) -> None:
        """Repaint the page of drafts, keeping the cursor on the draft it was on when that draft is still listed."""
        table = cast("DataTable[str]", self.query_one(f"#{_REVIEW_QUEUE}", DataTable))
        kept = table.coordinate_to_cell_key(table.cursor_coordinate).row_key if table.row_count else None
        table.clear(columns=True)
        table.add_column(tr("tui.ledger.evidence.review_queue.column.reference"), key="reference")
        table.add_column(tr("tui.ledger.evidence.review_queue.column.drafted"), key="drafted")
        table.add_column(tr("tui.ledger.evidence.review_queue.column.blocking"), key="blocking")
        table.add_column(tr("tui.ledger.evidence.review_queue.column.advisories"), key="advisories")
        for row in self.review_queue.page():
            table.add_row(
                short_identity(row.evidence_reference),
                row.drafted_at.date().isoformat(),
                str(row.blocking_count),
                str(row.advisory_count),
                key=row.evidence_reference,
            )
        if kept is not None and kept in table.rows:
            table.move_cursor(row=table.get_row_index(kept))
        paint_paging(self, _REVIEW_QUEUE, self.review_queue)
        self._paint_review_detail()

    def _paint_review_detail(self) -> None:
        """Show the chosen draft's findings, or nothing when none is chosen."""
        draft = self.selected_draft
        self.query_one(f"#{_REVIEW_QUEUE}-detail", Static).update(
            "" if draft is None else "\n".join(review_queue_detail_lines(draft))
        )

    def _forget_review_queue(self) -> None:
        """Discard the waiting drafts once the admitted session is lost."""
        self.review_queue.clear()
        self.selected_draft = None
        self._paint_review_queue()

    @override
    def _handle_expired_session(self, error: AccountSessionExpiredError) -> None:
        """Discard the waiting drafts too when a document read finds the session lost."""
        super()._handle_expired_session(error)
        if self.controller.evidence_review_door is not None:
            self._forget_review_queue()

    @override
    async def refresh_language(self) -> None:
        """Reword the drafts waiting for review after the shared copy."""
        await super().refresh_language()
        if self.controller.evidence_review_door is not None:
            self._paint_review_queue()

    @on(Button.Pressed, f"#{_REVIEW_QUEUE}-previous")
    def _previous_review_page(self) -> None:
        self.review_queue.previous()
        self._paint_review_queue()

    @on(Button.Pressed, f"#{_REVIEW_QUEUE}-next")
    def _next_review_page(self) -> None:
        self.review_queue.next()
        self._paint_review_queue()

    def _mount_attachment_review_queue(self) -> None:
        table = cast("DataTable[str]", self.query_one("#ledger-evidence", DataTable))
        table.add_column(tr("tui.ledger.column.entry"))
        table.add_column(tr("tui.ledger.evidence.column.type"))
        table.add_column(tr("tui.ledger.evidence.column.status"))
        rows = self.controller.evidence_rows()
        for position, row in enumerate(rows, start=1):
            status_key = "tui.ledger.evidence.pending" if row.pending_review else "tui.ledger.evidence.reviewed"
            table.add_row(str(position), row.mime_type, tr(status_key), key=row.attachment_id)
        if not rows:
            self.query_one("#ledger-evidence-detail", Static).update(tr("tui.ledger.evidence.empty"))
        restored = self.controller.restored_evidence_id()
        if restored is not None:
            index = next(index for index, row in enumerate(table.ordered_rows) if row.key.value == restored)
            table.move_cursor(row=index)

    def _mount_evidence_records(self) -> None:
        records = cast("DataTable[str]", self.query_one("#ledger-evidence-records", DataTable))
        records.add_column(tr("tui.ledger.column.entry"), key="position")
        records.add_column(tr("tui.ledger.evidence.column.file"), key="file")
        records.add_column(tr("tui.ledger.evidence.column.invoice"), key="invoice")
        records.add_column(tr("tui.ledger.evidence.column.status"), key="status")
        self._show_records()
        self.run_worker(self._measure_reader(), group="ledger-evidence-reader")

    def _focus_initial_table(self) -> None:
        if self.controller.evidence_review_door is not None:
            self.query_one(f"#{_REVIEW_QUEUE}", DataTable).focus()
        elif self._has_attachment_review_queue:
            self.query_one("#ledger-evidence", DataTable).focus()
        elif self.controller.evidence_door is not None:
            self.query_one("#ledger-evidence-records", DataTable).focus()
        else:
            self.query_one("#ledger-navigation", DataTable).focus()

    @property
    def _has_attachment_review_queue(self) -> bool:
        """Show attachment review only when its independent query supplied rows."""
        return self.controller.evidence_action is not None and self.controller.evidence_items is not None

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Show safe detail for the selected evidence identity."""
        if self.handle_navigation_selection(event):
            return
        table = cast("DataTable[str]", event.data_table)
        if event.row_key.value is None:
            return
        if table.id == "ledger-evidence-records":
            self._select_record(str(event.row_key.value))
            return
        if table.id == _REVIEW_QUEUE:
            reference = str(event.row_key.value)
            self.selected_draft = next(row for row in self.review_queue.items if row.evidence_reference == reference)
            # Only the detail changes; repainting the list would put the cursor back on its first row.
            self._paint_review_detail()
            return
        if table.id != "ledger-evidence":
            return
        evidence_id = str(event.row_key.value)
        row = next(item for item in self.controller.evidence_rows() if item.attachment_id == evidence_id)
        self.selected_evidence_id = evidence_id
        request = LedgerEvidenceReviewRequested(attachment_id=evidence_id, action=row.action)
        self.requested_review = request
        self.post_message(request)
        self.query_one("#ledger-evidence-detail", Static).update(
            tr(
                "tui.ledger.evidence.detail",
                size=row.bytes_size,
                captured=row.captured_at,
            )
        )


__all__ = ["LedgerEvidenceReviewListDoorV1", "LedgerEvidenceScreen", "review_queue_detail_lines"]

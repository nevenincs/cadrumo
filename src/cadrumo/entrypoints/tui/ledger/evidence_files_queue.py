"""Attachment queue: stored attachments no invoice is linked to yet, and one in detail.

Both are reads of the attachment manifest; neither discloses the attachment's
bytes nor where the attachment was fetched from.
"""

from __future__ import annotations

from typing import cast, override

from textual.app import ComposeResult
from textual.widgets import Button, DataTable, Static

from ....application.ledger.attachment_review import AttachmentReviewItem
from ....application.ledger.evidence_followup_contracts import (
    LedgerEvidenceAttachmentQueueRequest,
    LedgerEvidenceAttachmentViewRequest,
)
from ....core.i18n.render import tr
from ..components.language import localized, repaint_tables
from ..components.widgets import ContentDataTable
from .controller import LedgerWorkspaceController
from .evidence_files_common import (
    EvidenceFilesPager,
    EvidenceFilesToolScreen,
    paging_controls,
    paint_paging,
    short_identity,
)
from .evidence_files_doors import LedgerEvidenceFilesDoorsV1
from .workspace_presentation import ledger_workspace_page


def attachment_detail_lines(item: AttachmentReviewItem) -> tuple[str, ...]:
    """Word one attachment's manifest facts, without its bytes or its fetch location."""
    state = (
        "tui.ledger.evidence_files.queue.pending" if item.pending_review else "tui.ledger.evidence_files.queue.linked"
    )
    return (
        tr(
            "tui.ledger.evidence_files.queue.detail.identity",
            attachment=short_identity(item.attachment_id),
            digest=short_identity(item.sha256),
        ),
        tr(
            "tui.ledger.evidence_files.queue.detail.file",
            type=item.mime_type,
            size=item.bytes_size,
            source=tr(f"tui.ledger.evidence_files.source.{item.source.value.lower()}"),
        ),
        tr(
            "tui.ledger.evidence_files.queue.detail.state",
            captured=item.captured_at[:10],
            invoices=len(item.linked_invoice_ids),
            state=tr(state),
        ),
    )


class LedgerEvidenceFilesQueueScreen(EvidenceFilesToolScreen):
    """The pending attachment queue, one page at a time, and the chosen attachment's manifest."""

    def __init__(self, controller: LedgerWorkspaceController, doors: LedgerEvidenceFilesDoorsV1) -> None:
        """Open over the injected doors."""
        super().__init__(controller, doors, id="ledger-evidence-files-queue-screen")
        self.queue: EvidenceFilesPager[AttachmentReviewItem] = EvidenceFilesPager()
        self.selected_id: str | None = None
        self.selected: AttachmentReviewItem | None = None

    @override
    def compose(self) -> ComposeResult:
        yield self.banner(tr("tui.ledger.evidence_files.queue.title"), "tui.ledger.evidence_files.queue.title")
        with ledger_workspace_page() as navigation:
            yield navigation
            yield localized(
                Static(tr("tui.ledger.evidence_files.queue.prompt"), markup=False),
                "tui.ledger.evidence_files.queue.prompt",
            )
            yield ContentDataTable[str](id="evidence-files-queue", cursor_type="row", zebra_stripes=True)
            yield from paging_controls("evidence-files-queue")
            yield Static("", id="ledger-flow-status", markup=False)
            yield Static("", id="ledger-refusal", classes="ledger-refusal", markup=False)
            yield Static("", id="evidence-files-queue-detail", classes="evidence-files-detail", markup=False)

    def on_mount(self) -> None:
        """Show the shell, then read the queue off the event loop."""
        self._paint()
        self.start(self._load)

    @override
    async def refresh_language(self) -> None:
        await super().refresh_language()
        repaint_tables(self, self._paint)
        self._paint_detail()

    def _paint(self) -> None:
        self.populate_navigation()
        self._paint_queue()

    def _paint_queue(self) -> None:
        table = cast("DataTable[str]", self.query_one("#evidence-files-queue", DataTable))
        table.clear(columns=True)
        table.add_column(tr("tui.ledger.evidence_files.column.attachment"), key="attachment")
        table.add_column(tr("tui.ledger.evidence_files.column.type"), key="type")
        table.add_column(tr("tui.ledger.evidence_files.column.size"), key="size")
        table.add_column(tr("tui.ledger.evidence_files.column.captured"), key="captured")
        for item in self.queue.page():
            table.add_row(
                short_identity(item.attachment_id),
                item.mime_type,
                str(item.bytes_size),
                item.captured_at[:10],
                key=item.attachment_id,
            )
        selected = next(
            (index for index, row in enumerate(table.ordered_rows) if row.key.value == self.selected_id), None
        )
        if selected is not None:
            table.move_cursor(row=selected, animate=False)
        paint_paging(self, "evidence-files-queue", self.queue)

    def _paint_detail(self) -> None:
        item = self.selected
        self.query_one("#evidence-files-queue-detail", Static).update(
            "" if item is None else "\n".join(attachment_detail_lines(item))
        )

    async def _load(self) -> None:
        self.status(tr("tui.ledger.evidence_files.loading"))
        result = await self.ask(
            self.doors.attachment_queue(LedgerEvidenceAttachmentQueueRequest(profile_id=self.doors.profile_id))
        )
        if result is None:
            return
        self.queue.load(result.rows)
        self._paint_queue()
        self.status("" if result.count else tr("tui.ledger.evidence_files.queue.empty"))

    async def _view(self, attachment_id: str) -> None:
        result = await self.ask(
            self.doors.attachment_view(
                LedgerEvidenceAttachmentViewRequest(profile_id=self.doors.profile_id, attachment_id=attachment_id)
            )
        )
        if result is None:
            return
        self.selected_id = result.item.attachment_id
        self.selected = result.item
        self._paint_detail()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Read the chosen attachment's manifest."""
        if self.handle_navigation_selection(event):
            return
        if event.data_table.id != "evidence-files-queue" or event.row_key.value is None:
            return
        attachment_id = str(event.row_key.value)
        self.start(lambda: self._view(attachment_id))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Page the queue."""
        match event.button.id:
            case "evidence-files-queue-previous":
                self.queue.previous()
                self._paint_queue()
            case "evidence-files-queue-next":
                self.queue.next()
                self._paint_queue()
            case _:
                return

    @override
    def clear_private_view(self) -> None:
        self.queue.clear()
        self.selected_id = None
        self.selected = None
        self._paint_queue()
        self._paint_detail()


__all__ = ["LedgerEvidenceFilesQueueScreen", "attachment_detail_lines"]

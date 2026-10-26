"""Attachments: link stored evidence to the selected entry, or unlink it.

The tool acts on the entry chosen in Entries and says how to choose one when
none is. Pending attachments can be picked from the queue; an attach or detach
is reviewed before it is sent, a detach asks once more, and unlinking keeps the
stored file. Each outcome reports the entry's attachments as the operation
returned them, and any finalized Modelo revision that will not see the change.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Final, cast, override

from pydantic import ValidationError
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, DataTable, Input, Static

from ....application.ledger.attachment_mutation_operation import (
    LEDGER_ATTACH_OPERATION_DEFINITION_ID,
    LedgerAttachmentOperationResult,
    LedgerAttachRequest,
    LedgerDetachRequest,
)
from ....application.ledger.attachment_review import AttachmentReviewItem
from ....application.ledger.evidence_followup_contracts import LedgerEvidenceAttachmentQueueRequest
from ....core.i18n.render import tr
from ....core.identity.transaction_ids import TransactionId
from ..components.language import localized, repaint_tables
from ..components.widgets import ContentDataTable
from ..components.workspace_host import replace_workspace_body
from .controller import LedgerWorkspaceController, LedgerWorkspaceScreen
from .evidence_files_common import (
    EvidenceFilesPager,
    EvidenceFilesToolScreen,
    blank_to_none,
    paging_controls,
    paint_paging,
    short_identity,
)
from .evidence_files_doors import LedgerEvidenceFilesDoorsV1
from .evidence_files_write import (
    EvidenceFilesOutcomeV1,
    EvidenceFilesReviewV1,
    EvidenceFilesSubmitV1,
    EvidenceFilesWordingV1,
    LedgerEvidenceFilesWriteScreen,
)
from .workspace_presentation import door_refusal_text, ledger_workspace_page

_CONTROLS: Final = (
    "#evidence-files-attach-ids",
    "#evidence-files-attach-evidence",
    "#evidence-files-detach-ids",
    "#evidence-files-review-attach",
    "#evidence-files-review-detach",
)

type AttachedMemoryV1 = dict[str, tuple[str, ...]]
"""The attachments each entry was last reported to hold, by transaction identity."""


def parse_identities(text: str) -> tuple[str, ...]:
    """Split typed identities on spaces, commas or semicolons, keeping the first of any repeat."""
    return tuple(dict.fromkeys(text.replace(",", " ").replace(";", " ").split()))


def _toggle(text: str, identity: str) -> str:
    identities = parse_identities(text)
    if identity in identities:
        return " ".join(item for item in identities if item != identity)
    return " ".join((*identities, identity))


def attachment_outcome(result: LedgerAttachmentOperationResult) -> EvidenceFilesOutcomeV1:
    """Word an attach or detach result: a refusal's own messages, or the entry's attachments now."""
    if result.outcome == "validation_error" or result.result is None:
        return EvidenceFilesOutcomeV1(lines=result.validation_messages, refused=True)
    projection = result.result
    attached = projection.transaction.attachment_ids
    lines = [
        tr(
            "tui.ledger.evidence_files.attachments.outcome.attached"
            if result.operation_id == LEDGER_ATTACH_OPERATION_DEFINITION_ID
            else "tui.ledger.evidence_files.attachments.outcome.detached",
            count=len(attached),
        )
    ]
    if not projection.bucket_event_ids:
        lines.append(tr("tui.ledger.evidence_files.attachments.outcome.unchanged"))
    lines.extend(
        tr("tui.ledger.evidence_files.attachments.outcome.attachment", attachment=short_identity(item))
        for item in attached
    )
    if projection.stale_finalized_revisions:
        lines.append(
            tr(
                "tui.ledger.evidence_files.attachments.outcome.stale",
                count=len(projection.stale_finalized_revisions),
            )
        )
        lines.extend(
            tr(
                "tui.ledger.evidence_files.attachments.outcome.revision",
                modelo=revision.modelo,
                year=revision.filing_year,
                period=revision.period,
                state=revision.revision_state,
            )
            for revision in projection.stale_finalized_revisions
        )
    return EvidenceFilesOutcomeV1(lines=tuple(lines))


class LedgerEvidenceFilesAttachmentsScreen(EvidenceFilesToolScreen):
    """Attach stored evidence to the selected entry, or detach it, through the reviewed write step."""

    def __init__(
        self,
        controller: LedgerWorkspaceController,
        doors: LedgerEvidenceFilesDoorsV1,
        *,
        attached: AttachedMemoryV1 | None = None,
    ) -> None:
        """Open over the injected doors for the entry the workspace has selected."""
        super().__init__(controller, doors, id="ledger-evidence-files-attachments-screen")
        self.target: TransactionId | None = controller.classification_target
        self.attached: AttachedMemoryV1 = {} if attached is None else attached
        self.pending: EvidenceFilesPager[AttachmentReviewItem] = EvidenceFilesPager()

    @override
    def compose(self) -> ComposeResult:
        yield self.banner(
            tr("tui.ledger.evidence_files.attachments.title"), "tui.ledger.evidence_files.attachments.title"
        )
        with ledger_workspace_page() as navigation:
            yield navigation
            yield Static("", id="evidence-files-attachments-entry", classes="cadrumo-heading", markup=False)
            yield Static("", id="ledger-flow-status", markup=False)
            yield Static("", id="ledger-refusal", classes="ledger-refusal", markup=False)
            yield localized(
                Static(
                    tr("tui.ledger.evidence_files.attachments.attach_heading"), classes="cadrumo-heading", markup=False
                ),
                "tui.ledger.evidence_files.attachments.attach_heading",
            )
            yield localized(
                Static(tr("tui.ledger.evidence_files.attachments.pending_hint"), markup=False),
                "tui.ledger.evidence_files.attachments.pending_hint",
            )
            yield ContentDataTable[str](id="evidence-files-attachments-pending", cursor_type="row", zebra_stripes=True)
            yield from paging_controls("evidence-files-attachments-pending")
            yield localized(
                Input(placeholder=tr("tui.ledger.evidence_files.attachments.ids"), id="evidence-files-attach-ids"),
                "tui.ledger.evidence_files.attachments.ids",
            )
            yield localized(
                Input(
                    placeholder=tr("tui.ledger.evidence_files.attachments.evidence"),
                    id="evidence-files-attach-evidence",
                ),
                "tui.ledger.evidence_files.attachments.evidence",
            )
            with Horizontal(classes="evidence-files-actions"):
                yield localized(
                    Button(
                        tr("tui.ledger.evidence_files.attachments.review_attach"), id="evidence-files-review-attach"
                    ),
                    "tui.ledger.evidence_files.attachments.review_attach",
                )
            yield localized(
                Static(
                    tr("tui.ledger.evidence_files.attachments.detach_heading"), classes="cadrumo-heading", markup=False
                ),
                "tui.ledger.evidence_files.attachments.detach_heading",
            )
            yield Static("", id="evidence-files-attachments-linked-hint", markup=False)
            yield ContentDataTable[str](id="evidence-files-attachments-linked", cursor_type="row", zebra_stripes=True)
            yield localized(
                Input(placeholder=tr("tui.ledger.evidence_files.attachments.ids"), id="evidence-files-detach-ids"),
                "tui.ledger.evidence_files.attachments.ids",
            )
            with Horizontal(classes="evidence-files-actions"):
                yield localized(
                    Button(
                        tr("tui.ledger.evidence_files.attachments.review_detach"), id="evidence-files-review-detach"
                    ),
                    "tui.ledger.evidence_files.attachments.review_detach",
                )

    def on_mount(self) -> None:
        """Name the selected entry, or say how to choose one; read the pending queue only for an entry."""
        self._paint()
        if self.target is None:
            for selector in _CONTROLS:
                self.query_one(selector).disabled = True
            return
        self.start(self._load_pending)

    @override
    async def refresh_language(self) -> None:
        await super().refresh_language()
        repaint_tables(self, self._paint)

    def _paint(self) -> None:
        self.populate_navigation()
        entry = self.query_one("#evidence-files-attachments-entry", Static)
        entry.update(
            tr("tui.ledger.evidence_files.attachments.choose_entry")
            if self.target is None
            else tr("tui.ledger.evidence_files.attachments.entry", entry=self.controller.entry_label(self.target))
        )
        self._paint_pending()
        self._paint_linked()

    def _paint_pending(self) -> None:
        table = cast("DataTable[str]", self.query_one("#evidence-files-attachments-pending", DataTable))
        table.clear(columns=True)
        table.add_column(tr("tui.ledger.evidence_files.column.attachment"), key="attachment")
        table.add_column(tr("tui.ledger.evidence_files.column.type"), key="type")
        table.add_column(tr("tui.ledger.evidence_files.column.captured"), key="captured")
        for item in self.pending.page():
            table.add_row(
                short_identity(item.attachment_id), item.mime_type, item.captured_at[:10], key=item.attachment_id
            )
        paint_paging(self, "evidence-files-attachments-pending", self.pending)

    def _known_attachments(self) -> tuple[str, ...] | None:
        return None if self.target is None else self.attached.get(self.target)

    def _paint_linked(self) -> None:
        known = self._known_attachments()
        hint = self.query_one("#evidence-files-attachments-linked-hint", Static)
        table = cast("DataTable[str]", self.query_one("#evidence-files-attachments-linked", DataTable))
        table.clear(columns=True)
        table.display = bool(known)
        if known is None:
            hint.update(tr("tui.ledger.evidence_files.attachments.linked_unknown"))
            return
        if not known:
            hint.update(tr("tui.ledger.evidence_files.attachments.linked_none"))
            return
        hint.update(tr("tui.ledger.evidence_files.attachments.linked_hint"))
        table.add_column(tr("tui.ledger.evidence_files.column.attachment"), key="attachment")
        for identity in known:
            table.add_row(short_identity(identity), key=identity)

    async def _load_pending(self) -> None:
        self.status(tr("tui.ledger.evidence_files.loading"))
        result = await self.ask(
            self.doors.attachment_queue(LedgerEvidenceAttachmentQueueRequest(profile_id=self.doors.profile_id))
        )
        if result is None:
            return
        self.pending.load(result.rows)
        self._paint_pending()
        self.status("" if result.count else tr("tui.ledger.evidence_files.attachments.pending_empty"))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Add or remove the chosen attachment in the matching identity field."""
        if self.handle_navigation_selection(event):
            return
        if event.row_key.value is None or self.target is None:
            return
        identity = str(event.row_key.value)
        if event.data_table.id == "evidence-files-attachments-pending":
            field = self.query_one("#evidence-files-attach-ids", Input)
        elif event.data_table.id == "evidence-files-attachments-linked":
            field = self.query_one("#evidence-files-detach-ids", Input)
        else:
            return
        field.value = _toggle(field.value, identity)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Page the queue, or stage an attach or a detach for review."""
        match event.button.id:
            case "evidence-files-attachments-pending-previous":
                self.pending.previous()
                self._paint_pending()
            case "evidence-files-attachments-pending-next":
                self.pending.next()
                self._paint_pending()
            case "evidence-files-review-attach":
                self._stage_attach()
            case "evidence-files-review-detach":
                self._stage_detach()
            case _:
                return

    def _stage_attach(self) -> None:
        target = self.target
        if target is None or self.busy:
            return
        identities = parse_identities(self.query_one("#evidence-files-attach-ids", Input).value)
        evidence = blank_to_none(self.query_one("#evidence-files-attach-evidence", Input).value)
        if not identities and evidence is None:
            self.refuse(tr("tui.ledger.evidence_files.attachments.attach_required"))
            return
        try:
            request = LedgerAttachRequest(
                profile_id=self.doors.profile_id,
                transaction_id=target,
                purchase_invoice_evidence_id=evidence,
                attachment_ids=identities,
            )
        except ValidationError as error:
            self.refuse(door_refusal_text(error))
            return

        def review() -> tuple[str, ...]:
            return (
                tr("tui.ledger.evidence_files.attachments.stage.attach", entry=self.controller.entry_label(target)),
                *(
                    tr("tui.ledger.evidence_files.attachments.outcome.attachment", attachment=short_identity(item))
                    for item in identities
                ),
                *(
                    ()
                    if evidence is None
                    else (tr("tui.ledger.evidence_files.attachments.stage.evidence", record=short_identity(evidence)),)
                ),
            )

        doors, attached = self.doors, self.attached

        async def submit() -> EvidenceFilesWordingV1:
            result = await doors.attach(request)
            if result.result is not None:
                attached[target] = result.result.transaction.attachment_ids
            return lambda: attachment_outcome(result)

        self._open_write(
            lambda: tr("tui.ledger.evidence_files.attachments.attach_title"), review, submit, destructive=False
        )

    def _stage_detach(self) -> None:
        target = self.target
        if target is None or self.busy:
            return
        identities = parse_identities(self.query_one("#evidence-files-detach-ids", Input).value)
        if not identities:
            self.refuse(tr("tui.ledger.evidence_files.attachments.detach_required"))
            return
        try:
            request = LedgerDetachRequest(
                profile_id=self.doors.profile_id, transaction_id=target, attachment_ids=identities
            )
        except ValidationError as error:
            self.refuse(door_refusal_text(error))
            return

        def review() -> tuple[str, ...]:
            return (
                tr("tui.ledger.evidence_files.attachments.stage.detach", entry=self.controller.entry_label(target)),
                *(
                    tr("tui.ledger.evidence_files.attachments.outcome.attachment", attachment=short_identity(item))
                    for item in identities
                ),
                tr("tui.ledger.evidence_files.attachments.stage.kept"),
            )

        doors, attached = self.doors, self.attached

        async def submit() -> EvidenceFilesWordingV1:
            result = await doors.detach(request)
            if result.result is not None:
                attached[target] = result.result.transaction.attachment_ids
            return lambda: attachment_outcome(result)

        self._open_write(
            lambda: tr("tui.ledger.evidence_files.attachments.detach_title"), review, submit, destructive=True
        )

    def _open_write(
        self,
        title: Callable[[], str],
        review: EvidenceFilesReviewV1,
        submit: EvidenceFilesSubmitV1,
        *,
        destructive: bool,
    ) -> None:
        replace_workspace_body(
            self.app,
            LedgerEvidenceFilesWriteScreen(
                self.controller,
                title=title,
                review=review,
                destructive=destructive,
                submit=submit,
                origin=self._origin(),
                origin_area=self.back_area,
            ),
        )

    def _origin(self) -> Callable[[LedgerWorkspaceController], LedgerWorkspaceScreen]:
        doors, attached = self.doors, self.attached

        def build(controller: LedgerWorkspaceController) -> LedgerWorkspaceScreen:
            return LedgerEvidenceFilesAttachmentsScreen(controller, doors, attached=attached)

        return build

    @override
    def clear_private_view(self) -> None:
        self.pending.clear()
        self.attached.clear()
        for selector in ("#evidence-files-attach-ids", "#evidence-files-attach-evidence", "#evidence-files-detach-ids"):
            self.query_one(selector, Input).value = ""
        self._paint_pending()
        self._paint_linked()


__all__ = ["AttachedMemoryV1", "LedgerEvidenceFilesAttachmentsScreen", "attachment_outcome", "parse_identities"]

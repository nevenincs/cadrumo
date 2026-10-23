"""Evidence review: a read document's draft, as a summary or as the full review.

The summary carries the draft's figures, findings and blocking questions with
the document's own text left out; the full review is the person's projection
and carries that text. Both are reads; confirming a draft stays on the Evidence
area's own screen.
"""

from __future__ import annotations

from typing import Final, override

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Input, Static

from ....application.ledger.evidence_followup_contracts import (
    LedgerEvidenceReviewSummaryProjection,
    LedgerEvidenceReviewViewProjection,
    LedgerEvidenceReviewViewRequest,
)
from ....application.ledger.invoice_evidence_operation_dtos import ConfirmationBlockerProjectionV1
from ....application.operations.public_scalar import PublicDecimal
from ....core.confirmation_gate import ConfirmationBlockReason
from ....core.i18n.render import tr
from ....domain.iva.schema import InvoiceKind
from ..components.language import localized
from .controller import LedgerWorkspaceController
from .evidence_draft import draft_lines
from .evidence_files_common import EvidenceFilesToolScreen, blank_to_none, short_identity, shown
from .evidence_files_doors import LedgerEvidenceFilesDoorsV1
from .models import LedgerEvidenceDraftV1
from .workspace_presentation import ledger_workspace_page

_KIND_LOCALE_KEYS: Final[dict[InvoiceKind, str]] = {
    InvoiceKind.RECEIVED: "tui.ledger.invoice.kind.received",
    InvoiceKind.ISSUED: "tui.ledger.invoice.kind.issued",
}
_REASON_LOCALE_KEYS: Final[dict[ConfirmationBlockReason, str]] = {
    ConfirmationBlockReason.CLOSURE_DISCREPANCY: "tui.ledger.evidence_files.review.reason.closure_discrepancy",
    ConfirmationBlockReason.AMBIGUOUS_IDENTITY: "tui.ledger.evidence_files.review.reason.ambiguous_identity",
    ConfirmationBlockReason.UNRESOLVED_DIRECTION: "tui.ledger.evidence_files.review.reason.unresolved_direction",
    ConfirmationBlockReason.CONTRADICTED_REGIME: "tui.ledger.evidence_files.review.reason.contradicted_regime",
    ConfirmationBlockReason.UNDETERMINED_ESTABLISHMENT: (
        "tui.ledger.evidence_files.review.reason.undetermined_establishment"
    ),
    ConfirmationBlockReason.UNMODELLED_INVOICE_CLASS: (
        "tui.ledger.evidence_files.review.reason.unmodelled_invoice_class"
    ),
    ConfirmationBlockReason.CONTRADICTED_INVOICE_CLASS: (
        "tui.ledger.evidence_files.review.reason.contradicted_invoice_class"
    ),
}


def _amount(value: PublicDecimal | None) -> str:
    return shown(None if value is None else value.decimal)


def review_reason_label(reason: ConfirmationBlockReason) -> str:
    """Name, in the operator's language, why a read draft cannot be confirmed yet."""
    return tr(_REASON_LOCALE_KEYS[reason])


def _blocker_line(reason: ConfirmationBlockReason, field: str | None) -> str:
    return tr("tui.ledger.evidence_files.review.blocker", reason=review_reason_label(reason), field=shown(field))


def summary_lines(summary: LedgerEvidenceReviewSummaryProjection) -> tuple[str, ...]:
    """Word the review summary: figures, findings and blocking questions, never document text."""
    kind = (
        tr("tui.ledger.evidence.draft.unread")
        if summary.suggested_kind is None
        else tr(_KIND_LOCALE_KEYS[summary.suggested_kind])
    )
    lines = [
        tr(
            "tui.ledger.evidence_files.review.read_by",
            reference=short_identity(summary.evidence_reference),
            extractor=summary.extractor,
            date=summary.drafted_at.date().isoformat(),
        ),
        tr("tui.ledger.evidence_files.review.kind", kind=kind),
        tr(
            "tui.ledger.evidence_files.review.amounts",
            base=_amount(summary.taxable_base),
            rate=_amount(summary.iva_rate),
            iva=_amount(summary.iva_amount),
            total=_amount(summary.grand_total),
        ),
        tr("tui.ledger.evidence_files.review.findings", count=len(summary.discrepancies)),
        tr("tui.ledger.evidence_files.review.blockers", count=len(summary.blockers)),
        *(_blocker_line(blocker.reason, blocker.field) for blocker in summary.blockers),
    ]
    if summary.text_withheld:
        lines.append(tr("tui.ledger.evidence_files.review.text_withheld"))
    return tuple(lines)


def _view_blocker_lines(blockers: tuple[ConfirmationBlockerProjectionV1, ...]) -> tuple[str, ...]:
    return (
        tr("tui.ledger.evidence_files.review.blockers", count=len(blockers)),
        *(_blocker_line(blocker.reason, blocker.field) for blocker in blockers),
    )


def view_lines(view: LedgerEvidenceReviewViewProjection) -> tuple[str, ...]:
    """Word the full review through the Evidence area's own draft wording."""
    draft = view.draft
    reading = LedgerEvidenceDraftV1(
        evidence_id=view.evidence_reference,
        supplier_name=draft.supplier_name,
        supplier_tax_id=draft.supplier_tax_id,
        invoice_number=draft.invoice_number,
        invoice_date=draft.invoice_date,
        taxable_base=None if draft.taxable_base is None else draft.taxable_base.decimal,
        iva_rate=None if draft.iva_rate is None else draft.iva_rate.decimal,
        iva_amount=None if draft.iva_amount is None else draft.iva_amount.decimal,
        grand_total=None if draft.grand_total is None else draft.grand_total.decimal,
        currency=draft.currency,
        suggested_kind=draft.suggested_kind,
        discrepancies=len(draft.discrepancies),
        label_reading_fallback=None
        if view.label_reading_fallback is None
        else view.label_reading_fallback.to_fallback(),
        full_projection=draft,
    )
    return (
        tr(
            "tui.ledger.evidence_files.review.read_by",
            reference=short_identity(view.evidence_reference),
            extractor=view.extractor,
            date=view.drafted_at.date().isoformat(),
        ),
        *draft_lines(reading),
        *_view_blocker_lines(view.blockers),
    )


class LedgerEvidenceFilesReviewScreen(EvidenceFilesToolScreen):
    """Read one draft's review, as a summary or in full, by its evidence reference."""

    def __init__(
        self,
        controller: LedgerWorkspaceController,
        doors: LedgerEvidenceFilesDoorsV1,
        *,
        reference: str | None = None,
    ) -> None:
        """Open over the injected doors, with ``reference`` already entered when given."""
        super().__init__(controller, doors, id="ledger-evidence-files-review-screen")
        self._initial_reference = reference or ""
        self.shown_lines: tuple[str, ...] = ()
        self._shown: LedgerEvidenceReviewSummaryProjection | LedgerEvidenceReviewViewProjection | None = None

    @override
    def compose(self) -> ComposeResult:
        yield self.banner(tr("tui.ledger.evidence_files.review.title"), "tui.ledger.evidence_files.review.title")
        with ledger_workspace_page() as navigation:
            yield navigation
            yield localized(
                Static(tr("tui.ledger.evidence_files.review.prompt"), markup=False),
                "tui.ledger.evidence_files.review.prompt",
            )
            yield localized(
                Input(
                    value=self._initial_reference,
                    placeholder=tr("tui.ledger.evidence_files.review.reference"),
                    id="evidence-files-reference",
                ),
                "tui.ledger.evidence_files.review.reference",
            )
            with Horizontal(classes="evidence-files-actions"):
                yield localized(
                    Button(
                        tr("tui.ledger.evidence_files.review.summary"), id="evidence-files-summary", variant="primary"
                    ),
                    "tui.ledger.evidence_files.review.summary",
                )
                yield localized(
                    Button(tr("tui.ledger.evidence_files.review.full"), id="evidence-files-full"),
                    "tui.ledger.evidence_files.review.full",
                )
            yield Static("", id="ledger-flow-status", markup=False)
            yield Static("", id="ledger-refusal", classes="ledger-refusal", markup=False)
            yield Static("", id="evidence-files-review-body", classes="evidence-files-detail", markup=False)

    def on_mount(self) -> None:
        """Show the shell; a reference read from the records list is read at once."""
        self.populate_navigation()
        self.query_one("#evidence-files-reference", Input).focus()
        if self._initial_reference:
            self.start(self._read_summary)

    def _request(self) -> LedgerEvidenceReviewViewRequest | None:
        reference = blank_to_none(self.query_one("#evidence-files-reference", Input).value)
        if reference is None:
            self.refuse(tr("tui.ledger.evidence_files.review.reference_required"))
            return None
        return LedgerEvidenceReviewViewRequest(profile_id=self.doors.profile_id, evidence_reference=reference)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Read the summary or the full review of the entered reference."""
        match event.button.id:
            case "evidence-files-summary":
                self.start(self._read_summary)
            case "evidence-files-full":
                self.start(self._read_full)
            case _:
                return

    async def _read_summary(self) -> None:
        request = self._request()
        if request is None:
            return
        self.status(tr("tui.ledger.evidence_files.loading"))
        summary = await self.ask(self.doors.review_summary(request))
        if summary is not None:
            self._show(summary)

    async def _read_full(self) -> None:
        request = self._request()
        if request is None:
            return
        self.status(tr("tui.ledger.evidence_files.loading"))
        view = await self.ask(self.doors.review_view(request))
        if view is not None:
            self._show(view)

    def _show(self, review: LedgerEvidenceReviewSummaryProjection | LedgerEvidenceReviewViewProjection) -> None:
        self._shown = review
        self._paint_review()
        self.status("")

    def _paint_review(self) -> None:
        review = self._shown
        if review is None:
            self.shown_lines = ()
        elif isinstance(review, LedgerEvidenceReviewSummaryProjection):
            self.shown_lines = summary_lines(review)
        else:
            self.shown_lines = view_lines(review)
        self.query_one("#evidence-files-review-body", Static).update("\n".join(self.shown_lines))

    @override
    async def refresh_language(self) -> None:
        await super().refresh_language()
        self._paint_review()

    @override
    def clear_private_view(self) -> None:
        self._shown = None
        self._paint_review()


__all__ = ["LedgerEvidenceFilesReviewScreen", "review_reason_label", "summary_lines", "view_lines"]

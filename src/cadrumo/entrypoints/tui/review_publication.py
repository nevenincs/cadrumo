"""Shared review publication disclosure and receipt dialogs for Modelo and Ledger."""

from __future__ import annotations

from typing import ClassVar, override

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Link, Static

from ...application.export.publication_receipt import PublicationReceipt, ReadableExportAuthorization
from ...application.export.review_snapshot import ReviewSnapshot
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import output_language
from ..review_publication_labels import GoogleReviewLabels
from ..review_publication_presentation import (
    ReviewPublicationLabels,
    ReviewPublicationPresentation,
    review_publication_offer,
    review_publication_result,
)
from .components.theme import tokenised
from .components.widgets import ContentDataTable, NoticeBand

_REVIEW_CSS = tokenised("""
ReviewPublicationOfferScreen, ReviewPublicationResultScreen { align: center middle; }
.review-publication-dialog {
    border: $cadrumo-radius-overlay $accent;
    background: $surface;
    padding: $cadrumo-space-0 $cadrumo-space-1;
    width: $cadrumo-modal-width;
    height: $cadrumo-modal-height;
}
#review-publication-content { height: 1fr; }
#review-publication-title { text-style: bold; }
#review-publication-actions { height: auto; align-horizontal: right; margin-top: $cadrumo-stack; }
""")


class _ReviewPublicationScreen[ReturnT](ModalScreen[ReturnT]):
    """Render a pure presentation; every payload string remains literal text."""

    DEFAULT_CSS = _REVIEW_CSS
    BINDINGS: ClassVar = [Binding("escape", "close", "", show=False), Binding("t", "technical", "", show=False)]

    def __init__(self, presentation: ReviewPublicationPresentation, label: ReviewPublicationLabels) -> None:
        super().__init__()
        self._presentation = presentation
        self._label = label
        self._technical = False

    def _content(self, title: str) -> ComposeResult:
        with VerticalScroll(id="review-publication-content"):
            yield Static(self._label(title), id="review-publication-title", markup=False)
            yield NoticeBand(self._presentation.notices, id="review-publication-notices")
            yield ContentDataTable[str](id="review-publication-table", cursor_type="row", zebra_stripes=True)
            if self._presentation.spreadsheet_url is not None:
                yield Link(
                    self._label("google_review.open_document"),
                    url=self._presentation.spreadsheet_url,
                    id="review-publication-link",
                )

    def on_mount(self) -> None:
        """State the ordinary facts first; technical identities require an explicit action."""
        table = self.query_one("#review-publication-table", ContentDataTable)
        table.add_column(self._label("google_review.field"), key="field")
        table.add_column(self._label("google_review.value"), key="value")
        self._render_rows()
        self.query_one("#review-publication-close", Button).focus()

    def _render_rows(self) -> None:
        table = self.query_one("#review-publication-table", ContentDataTable)
        table.clear()
        rows = self._presentation.rows
        if self._technical:
            rows += self._presentation.technical_rows
        for row in rows:
            table.add_row(row.label, row.value, key=row.key)

    def action_technical(self) -> None:
        """Reveal or hide retained baseline and publication identities."""
        self._technical = not self._technical
        self._render_rows()


class ReviewPublicationOfferScreen(_ReviewPublicationScreen[bool]):
    """Disclose a saved review selection and managed remote destination before submission."""

    def __init__(
        self,
        snapshot: ReviewSnapshot,
        authorization: ReadableExportAuthorization,
        *,
        label: ReviewPublicationLabels | None = None,
    ) -> None:
        """Hold the correlated immutable offer; this dialog never performs publication."""
        labels = label if label is not None else GoogleReviewLabels(OutputLanguage(output_language()))
        super().__init__(review_publication_offer(snapshot, authorization, label=labels), labels)

    @override
    def compose(self) -> ComposeResult:
        with Vertical(classes="review-publication-dialog"):
            yield from self._content("google_review.offer.title")
            with Horizontal(id="review-publication-actions"):
                yield Button(self._label("google_review.technical"), id="review-publication-technical")
                yield Button(self._label("google_review.cancel"), id="review-publication-close")
                yield Button(self._label("google_review.publish"), id="review-publication-publish", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Return the explicit publish choice to the registered-operation caller."""
        if event.button.id == "review-publication-publish":
            self.dismiss(True)
        elif event.button.id == "review-publication-close":
            self.dismiss(False)
        elif event.button.id == "review-publication-technical":
            self.action_technical()

    def action_close(self) -> None:
        """Cancel the offer without submitting an operation."""
        self.dismiss(False)


class ReviewPublicationResultScreen(_ReviewPublicationScreen[None]):
    """State published, partial or uncertain receipt facts with the known document link."""

    def __init__(
        self,
        snapshot: ReviewSnapshot,
        publication: PublicationReceipt,
        *,
        label: ReviewPublicationLabels | None = None,
    ) -> None:
        """Hold the actual correlated receipt rather than treating an allocated ID as success."""
        labels = label if label is not None else GoogleReviewLabels(OutputLanguage(output_language()))
        super().__init__(review_publication_result(snapshot, publication, label=labels), labels)

    @override
    def compose(self) -> ComposeResult:
        with Vertical(classes="review-publication-dialog"):
            yield from self._content("google_review.result.title")
            with Horizontal(id="review-publication-actions"):
                yield Button(self._label("google_review.technical"), id="review-publication-technical")
                yield Button(self._label("google_review.close"), id="review-publication-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Close the statement or inspect its retained technical identities."""
        if event.button.id == "review-publication-close":
            self.dismiss(None)
        elif event.button.id == "review-publication-technical":
            self.action_technical()

    def action_close(self) -> None:
        """Close a result without replaying its publication."""
        self.dismiss(None)

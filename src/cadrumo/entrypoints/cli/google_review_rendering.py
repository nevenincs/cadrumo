"""Text projection for the registered calculation and standalone ledger review verbs."""

from __future__ import annotations

from ...application.export.publication_receipt import PublicationReceipt
from ...application.export.review_snapshot import ReviewSnapshot
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import output_language
from ..review_publication_labels import GoogleReviewLabels
from ..review_publication_presentation import ReviewPublicationLabels, review_publication_result


def google_review_receipt_lines(
    snapshot: ReviewSnapshot,
    publication: PublicationReceipt,
    *,
    command: str,
    label: ReviewPublicationLabels | None = None,
) -> tuple[str, ...]:
    """Keep publication state, exact selection and known link beside the review limitations."""
    labels = label if label is not None else GoogleReviewLabels(OutputLanguage(output_language()))
    view = review_publication_result(snapshot, publication, label=labels)
    lines = [f"operation\t{command}", f"published\t{view.published}"]
    lines.extend(f"{row.key}\t{row.value}" for row in (*view.rows, *view.technical_rows))
    if view.spreadsheet_url is not None:
        lines.append(f"spreadsheet_url\t{view.spreadsheet_url}")
    lines.extend(f"notice\t{notice.severity}\t{notice.message}" for notice in view.notices)
    return tuple(lines)

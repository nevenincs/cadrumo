"""Inert operator presentation of saved review baselines and publication receipts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import quote

from ..application.export.managed_artifact_ports import ManagedArtifactKind
from ..application.export.publication_receipt import (
    PublicationReceipt,
    PublicationState,
    ReadableExportAuthorization,
)
from ..application.export.review_snapshot import (
    CalculationReviewSelection,
    EvidenceDisposition,
    ReviewSnapshot,
    ReviewStatus,
)
from ..core.presentation import NoticePresentation

type ReviewPublicationLabels = Callable[[str], str]


@dataclass(frozen=True, slots=True)
class ReviewPresentationRow:
    """One already-resolved operator fact, with a stable presentation key."""

    key: str
    label: str
    value: str


@dataclass(frozen=True, slots=True)
class ReviewPublicationPresentation:
    """Display facts without granting admission or asserting current remote state."""

    rows: tuple[ReviewPresentationRow, ...]
    technical_rows: tuple[ReviewPresentationRow, ...]
    notices: tuple[NoticePresentation, ...]
    spreadsheet_url: str | None = None
    published: bool = False


def _row(key: str, value: str, label: ReviewPublicationLabels) -> ReviewPresentationRow:
    return ReviewPresentationRow(key, label(f"google_review.label.{key}"), value)


def _snapshot_rows(snapshot: ReviewSnapshot, label: ReviewPublicationLabels) -> tuple[ReviewPresentationRow, ...]:
    selection = snapshot.selection
    scope = (
        f"{selection.modelo} · {selection.filing_year} · {selection.period}"
        if isinstance(selection, CalculationReviewSelection)
        else label("google_review.selection.ledger")
    )
    return (
        _row("selection", scope, label),
        _row("review_status", label(f"google_review.status.{snapshot.status.value}"), label),
        _row("amount_count", str(len(snapshot.amounts)), label),
        _row("ledger_row_count", str(len(snapshot.ledger_rows)), label),
        _row("evidence_count", str(len(snapshot.evidence)), label),
        _row("finding_count", str(len(snapshot.findings)), label),
    )


def _snapshot_technical_rows(
    snapshot: ReviewSnapshot, label: ReviewPublicationLabels
) -> tuple[ReviewPresentationRow, ...]:
    selection = snapshot.selection
    rows = [_row("snapshot_digest", snapshot.snapshot_digest, label)]
    if isinstance(selection, CalculationReviewSelection):
        rows.extend(
            (
                _row("work_unit_id", selection.work_unit_id, label),
                _row("calculation_revision_id", selection.calculation_revision_id, label),
                _row("registry_digest", selection.registry_digest, label),
            )
        )
    else:
        rows.append(_row("ledger_snapshot_id", selection.ledger_snapshot_id, label))
    return tuple(rows)


def _snapshot_notices(snapshot: ReviewSnapshot, label: ReviewPublicationLabels) -> tuple[NoticePresentation, ...]:
    notices = [
        NoticePresentation("info", label("google_review.notice.external_copy")),
        NoticePresentation("info", label("google_review.notice.evidence_index")),
    ]
    if snapshot.status is not ReviewStatus.VERIFIED:
        notices.append(NoticePresentation("warning", label(f"google_review.notice.{snapshot.status.value}")))
    if any(
        item.disposition in {EvidenceDisposition.MISSING, EvidenceDisposition.UNAVAILABLE} for item in snapshot.evidence
    ):
        notices.append(NoticePresentation("warning", label("google_review.notice.missing_evidence")))
    notices.extend(NoticePresentation("warning", finding.detail) for finding in snapshot.findings)
    return tuple(notices)


def review_publication_offer(
    snapshot: ReviewSnapshot,
    authorization: ReadableExportAuthorization,
    *,
    label: ReviewPublicationLabels,
) -> ReviewPublicationPresentation:
    """Describe the exact baseline, remote destination and proposed readable disclosure."""
    if (
        authorization.profile_id != snapshot.selection.profile_id
        or authorization.snapshot_digest != snapshot.snapshot_digest
    ):
        raise ValueError("review disclosure does not match the selected baseline")
    categories = ", ".join(label(f"google_review.category.{item.value}") for item in authorization.payload_categories)
    return ReviewPublicationPresentation(
        rows=(
            *_snapshot_rows(snapshot, label),
            _row("destination", label("google_review.destination.managed_google_folder"), label),
            _row("payload_categories", categories, label),
        ),
        technical_rows=(
            *_snapshot_technical_rows(snapshot, label),
            _row("root_folder_id", authorization.root_folder_id, label),
            _row("publication_id", str(authorization.publication_id), label),
        ),
        notices=_snapshot_notices(snapshot, label),
    )


def review_publication_result(
    snapshot: ReviewSnapshot,
    publication: PublicationReceipt,
    *,
    label: ReviewPublicationLabels,
) -> ReviewPublicationPresentation:
    """Present only correlated receipt facts; a created ID alone cannot mean success."""
    if (
        publication.profile_id != snapshot.selection.profile_id
        or publication.snapshot_digest != snapshot.snapshot_digest
    ):
        raise ValueError("review publication does not match the selected baseline")
    sheets = tuple(item for item in publication.artifacts if item.kind is ManagedArtifactKind.REVIEW_SHEET)
    published = publication.state is PublicationState.PUBLISHED
    if published and len(sheets) != 1:
        raise ValueError("published workbook receipt must identify exactly one native review sheet")
    spreadsheet_url = (
        f"https://docs.google.com/spreadsheets/d/{quote(sheets[0].artifact_id, safe='')}/edit"
        if len(sheets) == 1
        else None
    )
    notices = list(_snapshot_notices(snapshot, label))
    if not published:
        notices.append(NoticePresentation("warning", label(f"google_review.publication.{publication.state.value}")))
    if publication.failure is not None:
        notices.append(NoticePresentation("warning", label(f"google_review.failure.{publication.failure.value}")))
    technical_rows = [
        *_snapshot_technical_rows(snapshot, label),
        _row("root_folder_id", publication.root.artifact_id, label),
        _row("publication_id", str(publication.publication_id), label),
    ]
    if publication.package_digest is not None:
        technical_rows.append(_row("package_digest", publication.package_digest, label))
    return ReviewPublicationPresentation(
        rows=(
            *_snapshot_rows(snapshot, label),
            _row("destination", label("google_review.destination.managed_google_folder"), label),
            _row("publication_state", label(f"google_review.publication.{publication.state.value}"), label),
        ),
        technical_rows=tuple(technical_rows),
        notices=tuple(notices),
        spreadsheet_url=spreadsheet_url,
        published=published,
    )

"""Validate identity, authority and attribution within sealed review content."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .review_snapshot import ReviewSnapshotContent


def validate_review_snapshot_content(content: ReviewSnapshotContent) -> None:
    """Require the complete review contract in its original validation order."""
    _validate_schema(content)
    _validate_saved_form(content)
    _validate_identities_and_references(content)
    _validate_completeness(content)


def _validate_schema(content: ReviewSnapshotContent) -> None:
    from .review_snapshot import CalculationReviewSelection

    calculation = isinstance(content.selection, CalculationReviewSelection)
    if content.schema_version == 1 and (
        content.calculation_lifecycle is not None or content.saved_form is not None or content.text_values
    ):
        raise ValueError("v1 review snapshots cannot carry unbound lifecycle metadata")
    if content.schema_version == 2 and calculation and content.calculation_lifecycle is None:
        raise ValueError("v2 calculation review requires captured lifecycle metadata")
    if not calculation and content.calculation_lifecycle is not None:
        raise ValueError("ledger review cannot claim a calculation lifecycle")


def _validate_saved_form(content: ReviewSnapshotContent) -> None:
    from .review_snapshot import CalculationReviewSelection

    if content.saved_form is not None:
        if not isinstance(content.selection, CalculationReviewSelection):
            raise ValueError("saved form requires a calculation selection")
        rendering = content.saved_form.rendering
        if (
            rendering.registry_snapshot.snapshot_ref != content.selection.registry_snapshot_ref
            or rendering.registry_digest != content.selection.registry_digest
            or rendering.authority_generation != content.selection.authority_generation
        ):
            raise ValueError("saved form authority does not match the review selection")
        _validate_saved_values(content)


def _validate_saved_values(content: ReviewSnapshotContent) -> None:
    if content.saved_form is None:
        return
    scalars = {value.id: value.value for value in content.saved_form.scalars}
    if any(amount.row_id is None and scalars.get(amount.casilla_id) != amount.value for amount in content.amounts):
        raise ValueError("saved form values do not match the baseline amounts")
    if any(scalars.get(item.casilla_id) != item.value for item in content.text_values):
        raise ValueError("saved form text values do not match the retained baseline")


def _validate_identities_and_references(content: ReviewSnapshotContent) -> None:
    from .review_snapshot import LedgerReviewSelection

    contribution_ids = {item.contribution_id for item in content.contributions}
    evidence_ids = {item.evidence_id for item in content.evidence}
    row_ids = {row.transaction_id for row in content.ledger_rows}
    _validate_unique_identities(content, contribution_ids, evidence_ids, row_ids)
    if isinstance(content.selection, LedgerReviewSelection) and (content.amounts or content.text_values):
        raise ValueError("ledger-only review cannot invent calculated casilla values")
    _validate_attribution(content, contribution_ids, evidence_ids, row_ids)


def _validate_attribution(
    content: ReviewSnapshotContent, contribution_ids: set[str], evidence_ids: set[str], row_ids: set[str]
) -> None:
    from .review_snapshot import ReviewSourceKind

    for amount in content.amounts:
        if not set(amount.contribution_ids) <= contribution_ids:
            raise ValueError("amount attribution refers to a missing contribution")
    for item in content.text_values:
        if not set(item.contribution_ids) <= contribution_ids:
            raise ValueError("text attribution refers to a missing contribution")
    for source in content.contributions:
        if not set(source.evidence_ids) <= evidence_ids:
            raise ValueError("source attribution refers to missing inventory entries")
        if source.kind is ReviewSourceKind.LEDGER_ROW and source.source_id not in row_ids:
            raise ValueError("ledger contribution lacks its captured row")


def _validate_unique_identities(
    content: ReviewSnapshotContent, contribution_ids: set[str], evidence_ids: set[str], row_ids: set[str]
) -> None:
    if (
        len(contribution_ids) != len(content.contributions)
        or len(evidence_ids) != len(content.evidence)
        or len(row_ids) != len(content.ledger_rows)
        or len({amount.amount_id for amount in content.amounts}) != len(content.amounts)
        or len({item.value_id for item in content.text_values}) != len(content.text_values)
    ):
        raise ValueError("snapshot identities must be unique within each record family")


def _validate_completeness(content: ReviewSnapshotContent) -> None:
    from .review_snapshot import EvidenceDisposition, ReviewSourceKind, ReviewStatus

    incomplete = any(
        item.disposition in {EvidenceDisposition.MISSING, EvidenceDisposition.UNAVAILABLE} for item in content.evidence
    ) or any(item.kind is ReviewSourceKind.UNAVAILABLE for item in content.contributions)
    if incomplete and content.status is ReviewStatus.VERIFIED:
        raise ValueError("unavailable evidence or provenance cannot be a verified complete review")

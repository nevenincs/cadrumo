"""CLI review text states the exact saved selection and incomplete effects."""

import pytest

from ....application.export.publication_receipt import PublicationFailure, PublicationState
from ...tests.review_publication_fixture import (
    frontend_created_publication,
    frontend_published_publication,
    frontend_review_label,
    frontend_review_snapshot,
)
from ..google_review_rendering import google_review_receipt_lines

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_published_draft_text_has_exact_saved_revision_link_and_evidence_limits() -> None:
    snapshot = frontend_review_snapshot()
    lines = google_review_receipt_lines(
        snapshot,
        frontend_published_publication(snapshot),
        command="modelo.spreadsheet.push",
        label=frontend_review_label,
    )
    assert lines[:2] == ("operation\tmodelo.spreadsheet.push", "published\tTrue")
    assert f"calculation_revision_id\t{'c' * 64}" in lines
    assert "spreadsheet_url\thttps://docs.google.com/spreadsheets/d/saved-review/edit" in lines
    assert "review_status\tgoogle_review.status.provisional" in lines
    assert "notice\twarning\tgoogle_review.notice.missing_evidence" in lines


def test_partial_standalone_ledger_text_never_claims_publication_or_modelo_support() -> None:
    snapshot = frontend_review_snapshot(ledger_only=True)
    receipt = frontend_created_publication(snapshot).advance(
        PublicationState.PARTIAL, failure=PublicationFailure.POPULATION
    )
    lines = google_review_receipt_lines(
        snapshot, receipt, command="ledger.spreadsheet.push", label=frontend_review_label
    )
    assert "published\tFalse" in lines
    assert "publication_state\tgoogle_review.publication.partial" in lines
    assert f"ledger_snapshot_id\t{'a' * 64}" in lines
    assert not any(line.startswith(("modelo\t", "calculation_revision_id\t", "output_path\t")) for line in lines)

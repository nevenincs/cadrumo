"""Frontend statements distinguish saved review quality from publication completion."""

from uuid import UUID

import pytest

from ...application.export.managed_artifact_ports import ManagedArtifactKind
from ...application.export.publication_receipt import PublicationFailure, PublicationReceipt, PublicationState
from ..review_publication_presentation import review_publication_offer, review_publication_result
from .review_publication_fixture import (
    frontend_authorization,
    frontend_created_publication,
    frontend_publication,
    frontend_published_publication,
    frontend_review_label,
    frontend_review_snapshot,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_offer_names_the_saved_draft_and_remote_destination() -> None:
    snapshot = frontend_review_snapshot()
    offer = review_publication_offer(
        snapshot, frontend_authorization(frontend_publication(snapshot)), label=frontend_review_label
    )
    values = {row.key: row.value for row in offer.rows}
    assert values["selection"] == "303 · 2026 · 1T"
    assert values["review_status"] == "google_review.status.provisional"
    assert values["destination"] == "google_review.destination.managed_google_folder"
    assert values["ledger_row_count"] == "1"
    assert values["payload_categories"] == "google_review.category.calculation, google_review.category.ledger"
    assert "output_path" not in values
    assert not offer.published and offer.spreadsheet_url is None
    assert {notice.message for notice in offer.notices} >= {
        "google_review.notice.provisional",
        "google_review.notice.external_copy",
        "google_review.notice.evidence_index",
        "google_review.notice.missing_evidence",
        "Historical payload unavailable",
    }


def test_standalone_ledger_does_not_acquire_a_modelo_or_calculation_identity() -> None:
    snapshot = frontend_review_snapshot(ledger_only=True)
    offer = review_publication_offer(
        snapshot, frontend_authorization(frontend_publication(snapshot)), label=frontend_review_label
    )
    values = {row.key: row.value for row in (*offer.rows, *offer.technical_rows)}
    assert values["selection"] == "google_review.selection.ledger"
    assert values["amount_count"] == "0"
    assert values["ledger_snapshot_id"] == "a" * 64
    assert not {"modelo", "work_unit_id", "calculation_revision_id", "registry_digest"} & values.keys()


@pytest.mark.parametrize("mismatch", ["profile", "digest"])
def test_an_uncorrelated_disclosure_is_refused(mismatch: str) -> None:
    snapshot = frontend_review_snapshot()
    authorization = frontend_authorization(frontend_publication(snapshot))
    values = authorization.model_dump()
    values.update(profile_id=UUID(int=9)) if mismatch == "profile" else values.update(snapshot_digest="f" * 64)
    with pytest.raises(ValueError, match="selected baseline"):
        review_publication_offer(snapshot, type(authorization).model_validate(values), label=frontend_review_label)


def test_creation_is_not_presented_as_published() -> None:
    snapshot = frontend_review_snapshot()
    result = review_publication_result(snapshot, frontend_created_publication(snapshot), label=frontend_review_label)
    assert not result.published
    assert result.spreadsheet_url == "https://docs.google.com/spreadsheets/d/saved-review/edit"
    assert "google_review.publication.remote-created" in {notice.message for notice in result.notices}


@pytest.mark.parametrize("state", [PublicationState.PARTIAL, PublicationState.UNCERTAIN])
def test_incomplete_receipts_retain_the_known_link_and_failure(state: PublicationState) -> None:
    snapshot = frontend_review_snapshot()
    receipt = frontend_created_publication(snapshot).advance(state, failure=PublicationFailure.POPULATION)
    result = review_publication_result(snapshot, receipt, label=frontend_review_label)
    assert not result.published
    assert result.spreadsheet_url == "https://docs.google.com/spreadsheets/d/saved-review/edit"
    assert {f"google_review.publication.{state.value}", "google_review.failure.population"} <= {
        notice.message for notice in result.notices
    }


def test_uncertain_creation_without_a_known_artifact_has_no_link() -> None:
    snapshot = frontend_review_snapshot()
    receipt = frontend_publication(snapshot).advance(
        PublicationState.UNCERTAIN, failure=PublicationFailure.CREATE_UNKNOWN
    )
    result = review_publication_result(snapshot, receipt, label=frontend_review_label)
    assert not result.published and result.spreadsheet_url is None


def test_only_a_complete_native_workbook_receipt_is_published() -> None:
    snapshot = frontend_review_snapshot()
    result = review_publication_result(snapshot, frontend_published_publication(snapshot), label=frontend_review_label)
    assert result.published
    assert result.spreadsheet_url == "https://docs.google.com/spreadsheets/d/saved-review/edit"
    assert {row.key: row.value for row in result.technical_rows}["calculation_revision_id"] == "c" * 64


def test_a_published_package_without_a_native_sheet_cannot_claim_workbook_success() -> None:
    snapshot = frontend_review_snapshot()
    receipt = frontend_published_publication(snapshot)
    artifact = receipt.artifacts[0].model_dump()
    artifact.update(kind=ManagedArtifactKind.EVIDENCE_PACKAGE)
    invalid_workbook = PublicationReceipt.model_validate(
        {**receipt.model_dump(), "artifacts": (type(receipt.artifacts[0]).model_validate(artifact),)}
    )
    with pytest.raises(ValueError, match="native review sheet"):
        review_publication_result(snapshot, invalid_workbook, label=frontend_review_label)


def test_uncorrelated_publication_result_is_refused() -> None:
    snapshot = frontend_review_snapshot()
    receipt = frontend_publication(snapshot)
    other = PublicationReceipt.model_validate({**receipt.model_dump(), "snapshot_digest": "f" * 64})
    with pytest.raises(ValueError, match="selected baseline"):
        review_publication_result(snapshot, other, label=frontend_review_label)


def test_document_link_encodes_the_receipt_identifier_as_one_path_segment() -> None:
    snapshot = frontend_review_snapshot()
    result = review_publication_result(
        snapshot, frontend_created_publication(snapshot, artifact_id="a/b?x=#fragment"), label=frontend_review_label
    )
    assert result.spreadsheet_url == "https://docs.google.com/spreadsheets/d/a%2Fb%3Fx%3D%23fragment/edit"

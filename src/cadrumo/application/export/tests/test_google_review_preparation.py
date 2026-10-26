"""Exact selection and disclosure correlation before a review can be published."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest

from ....core.errors.hierarchy import InternalInvariantError
from ...storage.calc_sheets.records import SheetExportPlan, SheetReviewMetadata
from ...storage.calc_sheets.tests.review_fixture import review_label, review_snapshot
from .. import google_operation
from ..google_operation import (
    GoogleSheetsExportActiveProfileRequiredError,
    GoogleSheetsExportSubjectMismatchError,
    prepare_google_review_plan,
    publish_google_review,
)
from ..managed_artifact_ports import ArtifactCreationReceipt, ManagedArtifactKind
from ..publication_receipt import (
    PublicationFailure,
    PublicationReceipt,
    PublicationState,
    ReadableExportAuthorization,
    ReadablePayloadCategory,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _publication(digest: str) -> PublicationReceipt:
    return PublicationReceipt(
        publication_id=UUID(int=2),
        profile_id=UUID(int=1),
        snapshot_digest=digest,
        root=ArtifactCreationReceipt(
            profile_id=UUID(int=1),
            root_folder_id="managed-root",
            artifact_id="managed-root",
            creation_id=UUID(int=3),
            kind=ManagedArtifactKind.ROOT,
        ),
    )


def _authorization(publication: PublicationReceipt) -> ReadableExportAuthorization:
    return ReadableExportAuthorization(
        profile_id=publication.profile_id,
        publication_id=publication.publication_id,
        root_folder_id=publication.root.artifact_id,
        snapshot_digest=publication.snapshot_digest,
        payload_categories=(ReadablePayloadCategory.CALCULATION, ReadablePayloadCategory.LEDGER),
        disclosure_digest="e" * 64,
    )


@pytest.fixture(autouse=True)
def active_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(google_operation, "require_active_bucket_id", lambda: str(UUID(int=1)))
    monkeypatch.setattr(google_operation, "resolve_active_capability", lambda _: SimpleNamespace(enabled=True))


def test_preparation_binds_sealed_baseline_and_publication() -> None:
    snapshot = review_snapshot()
    receipt = _publication(snapshot.snapshot_digest)
    plan = prepare_google_review_plan(
        snapshot,
        selection=snapshot.selection,
        publication=receipt,
        authorization=_authorization(receipt),
        exported_at=datetime(2026, 10, 5, tzinfo=UTC),
        label=review_label,
    )
    assert plan.metadata.snapshot_digest == snapshot.snapshot_digest
    assert plan.metadata.publication_id == receipt.publication_id


def test_stale_saved_revision_is_refused() -> None:
    snapshot = review_snapshot()
    other = review_snapshot(amount="99.75")
    receipt = _publication(other.snapshot_digest)
    with pytest.raises(GoogleSheetsExportSubjectMismatchError):
        prepare_google_review_plan(
            snapshot,
            selection=snapshot.selection,
            publication=receipt,
            authorization=_authorization(receipt),
            exported_at=datetime(2026, 10, 5, tzinfo=UTC),
            label=review_label,
        )


def test_exact_active_profile_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    snapshot = review_snapshot()
    receipt = _publication(snapshot.snapshot_digest)
    monkeypatch.setattr(google_operation, "require_active_bucket_id", lambda: str(UUID(int=9)))
    with pytest.raises(GoogleSheetsExportActiveProfileRequiredError):
        prepare_google_review_plan(
            snapshot,
            selection=snapshot.selection,
            publication=receipt,
            authorization=_authorization(receipt),
            exported_at=datetime(2026, 10, 5, tzinfo=UTC),
            label=review_label,
        )


def test_uncertain_create_is_not_reprepared_for_population() -> None:
    snapshot = review_snapshot()
    receipt = _publication(snapshot.snapshot_digest).advance(
        PublicationState.UNCERTAIN, failure=PublicationFailure.CREATE_UNKNOWN
    )
    with pytest.raises(GoogleSheetsExportSubjectMismatchError, match="reconciliation"):
        prepare_google_review_plan(
            snapshot,
            selection=snapshot.selection,
            publication=receipt,
            authorization=_authorization(receipt),
            exported_at=datetime(2026, 10, 5, tzinfo=UTC),
            label=review_label,
        )


def test_ledger_disclosure_is_required_for_supporting_rows() -> None:
    snapshot = review_snapshot()
    receipt = _publication(snapshot.snapshot_digest)
    authorization = ReadableExportAuthorization.model_validate(
        {**_authorization(receipt).model_dump(), "payload_categories": (ReadablePayloadCategory.CALCULATION,)}
    )
    with pytest.raises(GoogleSheetsExportSubjectMismatchError, match="disclosure"):
        prepare_google_review_plan(
            snapshot,
            selection=snapshot.selection,
            publication=receipt,
            authorization=authorization,
            exported_at=datetime(2026, 10, 5, tzinfo=UTC),
            label=review_label,
        )


def test_published_copy_cannot_be_reprepared_for_overwrite() -> None:
    snapshot = review_snapshot()
    receipt = _publication(snapshot.snapshot_digest)
    child = ArtifactCreationReceipt(
        profile_id=receipt.profile_id,
        root_folder_id=receipt.root.artifact_id,
        artifact_id="review-sheet",
        parent_id=receipt.root.artifact_id,
        creation_id=UUID(int=4),
        publication_id=receipt.publication_id,
        kind=ManagedArtifactKind.REVIEW_SHEET,
    )
    receipt = receipt.advance(PublicationState.REMOTE_CREATED, artifacts=(child,))
    for state in (PublicationState.POPULATED, PublicationState.VERIFIED, PublicationState.PUBLISHED):
        receipt = receipt.advance(state)
    with pytest.raises(GoogleSheetsExportSubjectMismatchError, match="reconciliation"):
        prepare_google_review_plan(
            snapshot,
            selection=snapshot.selection,
            publication=receipt,
            authorization=_authorization(receipt),
            exported_at=datetime(2026, 10, 5, tzinfo=UTC),
            label=review_label,
        )


def test_wrong_root_disclosure_is_refused() -> None:
    snapshot = review_snapshot()
    receipt = _publication(snapshot.snapshot_digest)
    authorization = ReadableExportAuthorization.model_validate(
        {**_authorization(receipt).model_dump(), "root_folder_id": "other-root"}
    )
    with pytest.raises(GoogleSheetsExportSubjectMismatchError):
        prepare_google_review_plan(
            snapshot,
            selection=snapshot.selection,
            publication=receipt,
            authorization=authorization,
            exported_at=datetime(2026, 10, 5, tzinfo=UTC),
            label=review_label,
        )


class _ReceiptPort:
    """Unit-test boundary: receipt validation is tested independently of Google."""

    def __init__(self, result: PublicationReceipt) -> None:
        self.result = result
        self.calls = 0

    def execute(
        self, plan: SheetExportPlan[SheetReviewMetadata], publication: PublicationReceipt
    ) -> PublicationReceipt:
        self.calls += 1
        assert plan.metadata.publication_id == publication.publication_id
        return self.result


def test_partial_transport_outcome_is_retained_as_partial() -> None:
    snapshot = review_snapshot()
    receipt = _publication(snapshot.snapshot_digest)
    uncertain = receipt.advance(PublicationState.UNCERTAIN, failure=PublicationFailure.CREATE_UNKNOWN)
    port = _ReceiptPort(uncertain)
    result = publish_google_review(
        snapshot,
        selection=snapshot.selection,
        publication=receipt,
        authorization=_authorization(receipt),
        prepared=port,
        exported_at=datetime(2026, 10, 5, tzinfo=UTC),
        label=review_label,
    )
    assert result == uncertain
    assert port.calls == 1


def test_unrelated_transport_receipt_cannot_be_settled_as_this_export() -> None:
    snapshot = review_snapshot()
    receipt = _publication(snapshot.snapshot_digest)
    port = _ReceiptPort(_publication("f" * 64))
    with pytest.raises(InternalInvariantError, match="unrelated"):
        publish_google_review(
            snapshot,
            selection=snapshot.selection,
            publication=receipt,
            authorization=_authorization(receipt),
            prepared=port,
            exported_at=datetime(2026, 10, 5, tzinfo=UTC),
            label=review_label,
        )


def test_allocated_id_alone_is_not_a_completed_publication() -> None:
    snapshot = review_snapshot()
    receipt = _publication(snapshot.snapshot_digest)
    child = ArtifactCreationReceipt(
        profile_id=receipt.profile_id,
        root_folder_id=receipt.root.artifact_id,
        artifact_id="empty-sheet",
        parent_id=receipt.root.artifact_id,
        creation_id=UUID(int=4),
        publication_id=receipt.publication_id,
        kind=ManagedArtifactKind.REVIEW_SHEET,
    )
    port = _ReceiptPort(receipt.advance(PublicationState.REMOTE_CREATED, artifacts=(child,)))
    with pytest.raises(InternalInvariantError, match="unfinished"):
        publish_google_review(
            snapshot,
            selection=snapshot.selection,
            publication=receipt,
            authorization=_authorization(receipt),
            prepared=port,
            exported_at=datetime(2026, 10, 5, tzinfo=UTC),
            label=review_label,
        )


def test_prepared_label_cannot_hide_existing_artifact_effects() -> None:
    snapshot = review_snapshot()
    receipt = _publication(snapshot.snapshot_digest)
    child = ArtifactCreationReceipt(
        profile_id=receipt.profile_id,
        root_folder_id=receipt.root.artifact_id,
        artifact_id="already-created-sheet",
        parent_id=receipt.root.artifact_id,
        creation_id=UUID(int=4),
        publication_id=receipt.publication_id,
        kind=ManagedArtifactKind.REVIEW_SHEET,
    )
    receipt = PublicationReceipt.model_validate({**receipt.model_dump(), "artifacts": (child,)})
    port = _ReceiptPort(receipt)
    with pytest.raises(GoogleSheetsExportSubjectMismatchError, match="reconciliation"):
        publish_google_review(
            snapshot,
            selection=snapshot.selection,
            publication=receipt,
            authorization=_authorization(receipt),
            prepared=port,
            exported_at=datetime(2026, 10, 5, tzinfo=UTC),
            label=review_label,
        )
    assert port.calls == 0

"""Synthetic review baseline and publication identities for frontend tests."""

from uuid import UUID

from ...application.export.managed_artifact_ports import ArtifactCreationReceipt, ManagedArtifactKind
from ...application.export.publication_receipt import (
    PublicationReceipt,
    PublicationState,
    ReadableExportAuthorization,
    ReadablePayloadCategory,
)
from ...application.export.review_snapshot import ReviewSnapshot
from ...application.storage.calc_sheets.tests.review_fixture import review_snapshot


def frontend_review_snapshot(*, ledger_only: bool = False) -> ReviewSnapshot:
    """Reuse the sealed saved-revision fixture; no local sources are loaded."""
    return review_snapshot(ledger_only=ledger_only)


def frontend_publication(snapshot: ReviewSnapshot) -> PublicationReceipt:
    """A prepared publication with a synthetic profile-managed root."""
    return PublicationReceipt(
        publication_id=UUID(int=2),
        profile_id=snapshot.selection.profile_id,
        snapshot_digest=snapshot.snapshot_digest,
        root=ArtifactCreationReceipt(
            profile_id=snapshot.selection.profile_id,
            root_folder_id="managed-root",
            artifact_id="managed-root",
            creation_id=UUID(int=3),
            kind=ManagedArtifactKind.ROOT,
        ),
    )


def frontend_authorization(publication: PublicationReceipt) -> ReadableExportAuthorization:
    """Disclosure coordinates used only for rendering the offer."""
    return ReadableExportAuthorization(
        profile_id=publication.profile_id,
        publication_id=publication.publication_id,
        root_folder_id=publication.root.artifact_id,
        snapshot_digest=publication.snapshot_digest,
        payload_categories=(ReadablePayloadCategory.CALCULATION, ReadablePayloadCategory.LEDGER),
        disclosure_digest="e" * 64,
    )


def frontend_created_publication(snapshot: ReviewSnapshot, *, artifact_id: str = "saved-review") -> PublicationReceipt:
    """Acknowledged creation alone deliberately stops before population and verification."""
    receipt = frontend_publication(snapshot)
    return receipt.advance(
        PublicationState.REMOTE_CREATED,
        artifacts=(
            ArtifactCreationReceipt(
                profile_id=receipt.profile_id,
                root_folder_id=receipt.root.artifact_id,
                artifact_id=artifact_id,
                parent_id=receipt.root.artifact_id,
                creation_id=UUID(int=4),
                kind=ManagedArtifactKind.REVIEW_SHEET,
                publication_id=receipt.publication_id,
            ),
        ),
    )


def frontend_published_publication(snapshot: ReviewSnapshot) -> PublicationReceipt:
    """One synthetic receipt advances through every required publication checkpoint."""
    return (
        frontend_created_publication(snapshot)
        .advance(PublicationState.POPULATED)
        .advance(PublicationState.VERIFIED)
        .advance(PublicationState.PUBLISHED)
    )


def frontend_review_label(key: str) -> str:
    """Expose semantic keys directly so assertions do not depend on pending locale enrollment."""
    return key

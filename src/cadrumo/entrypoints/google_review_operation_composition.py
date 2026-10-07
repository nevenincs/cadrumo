"""Compose saved-revision review publication with profile-owned Google custody."""

from __future__ import annotations

from uuid import UUID

from ..adapters.outbound.google.api import drive_v3_service, sheets_v4_service
from ..adapters.outbound.google.artifact_admission import GoogleArtifactAdmission
from ..adapters.outbound.google.artifact_receipt_store import GoogleArtifactReceiptStore
from ..adapters.outbound.google.calc_sheets_apply import publish_review_plan
from ..adapters.outbound.google.managed_artifacts import ManagedGoogleArtifacts
from ..adapters.outbound.storage.factory import build_google_credentials, resolve_drive_root_folder_id
from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ..application.export.google_operation import publish_google_review
from ..application.export.google_review_operation_contracts import GoogleReviewOperationPorts
from ..application.export.managed_artifact_ports import ArtifactCreationReceipt
from ..application.export.publication_receipt import PublicationReceipt, ReadableExportAuthorization
from ..application.export.review_snapshot import ReviewSnapshot
from ..application.storage.calc_sheets.records import SheetExportPlan, SheetReviewMetadata
from ..application.storage.calc_sheets.review_labels import ReviewWorkbookLabels
from ..application.user_profile.access_contracts import AccessDenialCode
from ..application.user_profile.access_errors import ProfileAccessRefusedError
from ..application.user_profile.google_configuration_operation_ports import (
    GoogleConfigurationAcknowledgement,
    GoogleConfigurationCommit,
    GoogleConfigurationHandoff,
)
from ..core.external_constants import OutputLanguage
from ..core.i18n.render import output_language
from ..core.identity.hex_ids import CalculationRevisionId
from ..core.time.clock import now
from ..domain.calculations.registry.authority import PinnedAuthorityOperation
from .calculation_review_snapshot_composition import load_calculation_review_snapshot


def build_google_review_ports(*, profile_id: UUID, operation: PinnedAuthorityOperation) -> GoogleReviewOperationPorts:
    """Load one retained revision and defer all network access until reviewed publication."""
    profile = str(profile_id)

    def load_snapshot(revision_id: CalculationRevisionId) -> ReviewSnapshot:
        return load_calculation_review_snapshot(revision_id, profile_id=profile_id, operation=operation)

    def load_root() -> ArtifactCreationReceipt:
        root_id = resolve_drive_root_folder_id(profile=profile)
        store = GoogleArtifactReceiptStore(secure_object_repository_for_bucket(profile), profile_id=profile_id)
        root = store.load(root_id)
        if root is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        return root

    def load_publication(publication_id: UUID) -> PublicationReceipt | None:
        store = GoogleArtifactReceiptStore(secure_object_repository_for_bucket(profile), profile_id=profile_id)
        return store.load_publication(publication_id)

    def publish(
        snapshot: ReviewSnapshot,
        publication: PublicationReceipt,
        authorization: ReadableExportAuthorization,
        *,
        commit: GoogleConfigurationCommit,
        before_handoff: GoogleConfigurationHandoff,
        acknowledged: GoogleConfigurationAcknowledgement,
    ) -> PublicationReceipt:
        credentials = build_google_credentials(profile=profile)
        drive = drive_v3_service(credentials, unavailable_condition_id="google.review.client_available")
        sheets = sheets_v4_service(credentials, unavailable_condition_id="google.review.client_available")
        store = GoogleArtifactReceiptStore(
            secure_object_repository_for_bucket(profile), profile_id=profile_id, commit=commit
        )
        artifacts = ManagedGoogleArtifacts(
            GoogleArtifactAdmission(
                drive,
                profile_id=profile_id,
                root=publication.root,
                receipts=store,
                before_handoff=before_handoff,
                acknowledged=acknowledged,
            ),
            receipts=store,
        )

        class Prepared:
            def execute(
                self, plan: SheetExportPlan[SheetReviewMetadata], publication: PublicationReceipt
            ) -> PublicationReceipt:
                return publish_review_plan(plan, publication=publication, artifacts=artifacts, sheets=sheets)

        return publish_google_review(
            snapshot,
            selection=snapshot.selection,
            publication=publication,
            authorization=authorization,
            prepared=Prepared(),
            exported_at=now(),
            label=ReviewWorkbookLabels(OutputLanguage(output_language())),
        )

    return GoogleReviewOperationPorts(
        profile_id=profile_id,
        operation=operation,
        load_snapshot=load_snapshot,
        load_filing_snapshot=lambda revision_id, filing_record_id: load_calculation_review_snapshot(
            revision_id, profile_id=profile_id, operation=operation, filing_record_id=filing_record_id
        ),
        load_root=load_root,
        load_publication=load_publication,
        publish=publish,
    )

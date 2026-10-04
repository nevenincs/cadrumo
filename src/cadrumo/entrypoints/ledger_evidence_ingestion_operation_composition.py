"""Compose canonical evidence ingestion under one immutable worker profile pin."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from ..adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ..adapters.persistence.profile.extraction_drafts import ExtractionDraftRepository
from ..adapters.persistence.profile.purchase_invoice_evidence import (
    LedgerEvidenceAttachmentIngestor,
    LedgerEvidenceRepositoryAdapter,
)
from ..adapters.persistence.storage.attachment import AttachmentStore
from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ..application.ledger.evidence_ingestion_operation_ports import LedgerEvidenceIngestionPorts
from ..application.ledger.evidence_ports import LedgerEvidencePorts
from ..application.ledger.extraction_draft_store import ExtractionDraftRepositoryProtocol
from ..application.user_profile.access_contracts import AccessDenialCode
from ..application.user_profile.access_errors import ProfileAccessRefusedError
from ..core.bucket_pointer import require_active_bucket_id
from ..core.config import Settings, load_settings
from ..domain.calculations.registry.authority import PinnedAuthorityOperation
from .ledger_evidence_extraction_composition import invoice_draft_extraction_ports


def build_ledger_evidence_ingestion_operation_ports(
    *,
    profile_id: UUID,
    operation: PinnedAuthorityOperation,
    mutation_writer: Callable[[Callable[[], None]], None],
    before_read: Callable[[], None],
) -> LedgerEvidenceIngestionPorts:
    """Require exact worker identity before composing repositories or lazy providers."""
    bucket_id = str(profile_id)
    if require_active_bucket_id() != bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    settings = load_settings()
    objects = secure_object_repository_for_bucket(bucket_id, settings)
    store = AttachmentStore(objects=objects, bucket_id=bucket_id, mutation_writer=mutation_writer)
    events = BucketEventHistoryRepository(objects=objects, mutation_writer=mutation_writer)
    evidence = LedgerEvidencePorts(
        evidence_repository=LedgerEvidenceRepositoryAdapter(objects=objects, mutation_writer=mutation_writer),
        attachment_ingestor=LedgerEvidenceAttachmentIngestor(store=store),
        bucket_event_repository=events,
    )

    def draft_factory(*, bucket_id: str, settings: Settings) -> ExtractionDraftRepositoryProtocol:
        if bucket_id != str(profile_id) or require_active_bucket_id() != bucket_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        return ExtractionDraftRepository(bucket_id=bucket_id, settings=settings, mutation_writer=mutation_writer)

    return LedgerEvidenceIngestionPorts(
        profile_id=profile_id,
        operation=operation,
        settings=settings,
        evidence=evidence,
        extraction=invoice_draft_extraction_ports(
            evidence_ports=evidence, operation=operation, before_read=before_read
        ),
        draft_factory=draft_factory,
    )

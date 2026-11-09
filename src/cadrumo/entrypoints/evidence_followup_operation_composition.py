"""Concrete encrypted readers for registered evidence follow-up operations."""

from __future__ import annotations

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ..adapters.outbound.llm.consent import off_host_evidence_read_askable
from ..adapters.persistence.llm.consent_ledger import EvidenceConsentLedger
from ..adapters.persistence.profile.extraction_drafts import ExtractionDraftRepository
from ..application.ledger.consent_withdrawal import ConsentedDispatch
from ..application.ledger.evidence_followup_contracts import (
    LedgerEvidenceFollowupOperationPorts,
    OffHostReadAskable,
)
from ..application.ledger.extraction_draft_repository import ExtractionDraftRepositoryProtocol
from ..application.user_profile.access_errors import ProfileAccessRefusedError
from ..application.user_profile.capabilities import cloud_evidence_upload_eligible_for_active_profile
from ..core.bucket_pointer import require_active_bucket_id
from ..core.config import Settings
from ..core.identity.bucket import canonical_bucket_id
from ..domain.attachments.protocols import AttachmentStoreProtocol
from .adapter_composition_ports import build_attachment_store


def _require_profile(bucket_id: str) -> str:
    normalized_bucket_id = canonical_bucket_id(bucket_id)
    if require_active_bucket_id() != normalized_bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return normalized_bucket_id


def _attachment_store(bucket_id: str, /) -> AttachmentStoreProtocol:
    return build_attachment_store(_require_profile(bucket_id))


def _extraction_drafts(*, bucket_id: str, settings: Settings) -> ExtractionDraftRepositoryProtocol:
    return ExtractionDraftRepository(bucket_id=_require_profile(bucket_id), settings=settings)


def _consent_entries(*, bucket_id: str) -> tuple[ConsentedDispatch, ...]:
    _require_profile(bucket_id)
    return tuple(
        ConsentedDispatch(
            profile_bucket_id=entry.profile_bucket_id,
            evidence_content_address=entry.evidence_content_address,
            provider=entry.provider,
            model=entry.model,
            surface=entry.surface,
            recorded_at=entry.recorded_at,
        )
        for entry in EvidenceConsentLedger().load_entries()
    )


def _off_host_read_askable(settings: Settings) -> OffHostReadAskable:
    def askable(*, bucket_id: str) -> bool:
        _require_profile(bucket_id)
        return off_host_evidence_read_askable(
            settings,
            profile_eligible=cloud_evidence_upload_eligible_for_active_profile(settings=settings),
        )

    return askable


def build_ledger_evidence_followup_operation_ports(*, settings: Settings) -> LedgerEvidenceFollowupOperationPorts:
    """Provide guarded factories; construction opens no profile stores."""
    return LedgerEvidenceFollowupOperationPorts(
        settings=settings,
        attachment_store_factory=_attachment_store,
        extraction_draft_repository_factory=_extraction_drafts,
        consent_entries_factory=_consent_entries,
        off_host_read_askable=_off_host_read_askable(settings),
    )


__all__ = ["build_ledger_evidence_followup_operation_ports"]

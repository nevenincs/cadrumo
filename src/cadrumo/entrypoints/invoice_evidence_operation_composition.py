"""Exact-profile invoice evidence readers and canonical confirmation writers."""

from __future__ import annotations

from collections.abc import Callable

from ..adapters.outbound.llm.consent import (
    OffHostEvidenceReadOutcome,
    classify_off_host_evidence_read,
    mint_evidence_consent_token,
)
from ..adapters.outbound.llm.errors import LLMConsentError
from ..adapters.persistence.llm.consent_ledger import EvidenceConsentLedger
from ..adapters.persistence.profile.catalogue_creation import build_catalogue_creation_ports
from ..adapters.persistence.profile.counterparty_establishment import build_counterparty_establishment_repository
from ..adapters.persistence.profile.invoice_confirmation import build_invoice_confirmation_ports
from ..application.ledger.invoice_draft_extraction_ports import EvidenceConsentProof
from ..application.ledger.invoice_evidence_operation import InvoiceEvidenceOperationPorts
from ..application.user_profile.access_contracts import AccessDenialCode
from ..application.user_profile.access_errors import ProfileAccessRefusedError
from ..application.user_profile.capabilities import cloud_evidence_upload_eligible_for_active_profile
from ..core.bucket_pointer import require_active_bucket_id
from ..core.config import load_settings
from ..core.config_support import LLMProvider
from ..core.identity.bucket import canonical_bucket_id
from .adapter_composition import build_ledger_evidence_ports
from .ledger_evidence_extraction_composition import invoice_draft_extraction_ports


def build_invoice_evidence_operation_ports(
    *,
    bucket_id: str,
    before_consent_save: Callable[[], None] | None = None,
    after_consent_save: Callable[[bool], None] | None = None,
) -> InvoiceEvidenceOperationPorts:
    """Bind encrypted source and write capabilities to the immutable worker profile."""
    normalized_bucket_id = canonical_bucket_id(bucket_id)
    if require_active_bucket_id() != normalized_bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    if (before_consent_save is None) != (after_consent_save is None):
        raise ValueError("invoice evidence consent custody requires paired save callbacks")
    settings = load_settings()
    evidence_ports = build_ledger_evidence_ports(bucket_id=normalized_bucket_id)
    consent_ledger = (
        EvidenceConsentLedger(before_save=before_consent_save, after_save=after_consent_save)
        if before_consent_save is not None
        else None
    )

    def mint_consent(
        provider: LLMProvider,
        acknowledged: bool,
        surface: str,
        raw_content_sha256: str,
    ) -> EvidenceConsentProof:
        if require_active_bucket_id() != normalized_bucket_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        outcome = classify_off_host_evidence_read(provider=provider, acknowledged=acknowledged)
        if outcome is not OffHostEvidenceReadOutcome.OFF_HOST_CONSENTED:
            raise LLMConsentError(context={"consent_outcome": outcome.value})
        return mint_evidence_consent_token(
            settings=settings,
            profile_eligible=cloud_evidence_upload_eligible_for_active_profile(settings=settings),
            acknowledged=acknowledged,
            surface=surface,
            evidence_content_address=raw_content_sha256,
        )

    return InvoiceEvidenceOperationPorts(
        bucket_id=normalized_bucket_id,
        settings=settings,
        evidence_ports=evidence_ports,
        extraction_ports=invoice_draft_extraction_ports(evidence_ports=evidence_ports, consent_ledger=consent_ledger),
        catalogue_creation_ports=build_catalogue_creation_ports(bucket_id=normalized_bucket_id),
        invoice_confirmation_ports=build_invoice_confirmation_ports(bucket_id=normalized_bucket_id),
        counterparty_establishment_repository=build_counterparty_establishment_repository(
            bucket_id=normalized_bucket_id
        ),
        mint_consent=mint_consent,
    )


__all__ = ["build_invoice_evidence_operation_ports"]

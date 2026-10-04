"""Closed request, result, and profile capability contracts for evidence follow-up reads."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, field_validator, model_validator

from ...core.config import Settings
from ...core.confirmation_gate import ConfirmationBlockReason, ReviewAdvisoryKind
from ...core.draft_discrepancy import DraftDiscrepancyKind
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.time.utc import validate_utc_aware
from ...domain.attachments.protocols import AttachmentStoreProtocol
from ...domain.iva.establishment import StatedCountryCodeStatus
from .attachment_review import AttachmentReviewItem
from .consent_withdrawal import CloudDerivedArtefact, ConsentedDispatch, ConsentWithdrawalSurvey
from .extraction_draft_store import ExtractionDraftRepositoryFactory
from .invoice_evidence_operation_dtos import (
    ConfirmationBlockerProjectionV1,
    InvoiceDraftProjectionV1,
    LabelReadingFallbackProjectionV1,
)

LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID = "ledger.evidence.attachment_queue"


LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID = "ledger.evidence.attachment_view"


LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID = "ledger.evidence.consent.list"


LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID = "ledger.evidence.review.list"


LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID = "ledger.evidence.review.view"


MAX_EVIDENCE_FOLLOWUP_READ_ROWS = 4_096


_Reference = Annotated[str, Field(min_length=1, max_length=64)]


_AttachmentId = Annotated[str, Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")]


_ShortText = Annotated[str, Field(min_length=1, max_length=2_048)]


_ReviewRows = Annotated[
    tuple["EvidenceReviewQueueRowProjection", ...], Field(max_length=MAX_EVIDENCE_FOLLOWUP_READ_ROWS)
]


_AttachmentRows = Annotated[tuple[AttachmentReviewItem, ...], Field(max_length=MAX_EVIDENCE_FOLLOWUP_READ_ROWS)]


_BlockerRows = Annotated[tuple[ConfirmationBlockerProjectionV1, ...], Field(max_length=128)]


_UTC_AFTER_VALIDATOR = pydantic_validation_boundary(validate_utc_aware)


class AttachmentStoreFactory(Protocol):
    """Compose the encrypted attachment capability for one active profile."""

    def __call__(self, bucket_id: str, /) -> AttachmentStoreProtocol:
        """Return the attachment store bound to ``bucket_id``."""
        ...


class EvidenceConsentEntriesFactory(Protocol):
    """Project adapter-side consent entries for the consent survey."""

    def __call__(self, *, bucket_id: str) -> tuple[ConsentedDispatch, ...]:
        """Load consent entries; the application survey scopes them to the profile."""
        ...


@dataclass(frozen=True, slots=True)
class LedgerEvidenceFollowupOperationPorts:
    """Explicit capabilities needed by the five evidence follow-up reads."""

    settings: Settings
    attachment_store_factory: AttachmentStoreFactory
    extraction_draft_repository_factory: ExtractionDraftRepositoryFactory
    consent_entries_factory: EvidenceConsentEntriesFactory


class LedgerEvidenceAttachmentQueueRequest(BaseModel):
    """Private request for all pending attachments in one profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID


class LedgerEvidenceAttachmentViewRequest(BaseModel):
    """Private request for one exact attachment manifest."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    attachment_id: _AttachmentId


class LedgerEvidenceConsentListRequest(BaseModel):
    """Private request for one profile's consent and derived-artifact survey."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID


class LedgerEvidenceReviewListRequest(BaseModel):
    """Private request for a typed, optionally narrowed pending-review queue."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    reason: ConfirmationBlockReason | None = None
    finding: DraftDiscrepancyKind | None = None
    advisory: ReviewAdvisoryKind | None = None
    blocking_only: bool = False


class LedgerEvidenceReviewViewRequest(BaseModel):
    """Private request for one pending extraction draft."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    evidence_reference: _Reference


class LedgerEvidenceAttachmentQueueProjection(BaseModel):
    """Complete bounded pending-attachment projection for one profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    count: NonNegativeInt
    rows: _AttachmentRows = ()

    @model_validator(mode="after")
    def _correlate_count_and_pending_rows(self) -> LedgerEvidenceAttachmentQueueProjection:
        if self.count != len(self.rows) or any(not row.pending_review for row in self.rows):
            raise ValueError("attachment queue count or pending status is inconsistent")
        attachment_ids = tuple(row.attachment_id for row in self.rows)
        if len(set(attachment_ids)) != len(self.rows) or attachment_ids != tuple(sorted(attachment_ids)):
            raise ValueError("attachment queue identities or order are inconsistent")
        return self


class LedgerEvidenceAttachmentViewProjection(BaseModel):
    """One review-safe attachment manifest for the exact profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    item: AttachmentReviewItem


class ConsentedDispatchProjection(BaseModel):
    """Closed consent-ledger row with a plain public UTC datetime schema."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_bucket_id: str
    evidence_content_address: str
    provider: str
    model: str
    surface: str
    recorded_at: datetime
    _recorded_at_is_utc = field_validator("recorded_at", mode="after")(_UTC_AFTER_VALIDATOR)

    @classmethod
    def from_dispatch(cls, value: ConsentedDispatch) -> ConsentedDispatchProjection:
        """Copy every canonical consent fact into the schema-safe DTO."""
        return cls(**value.model_dump())


class CloudDerivedArtefactProjection(BaseModel):
    """Closed draft-history row with a plain public UTC datetime schema."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    evidence_reference: str
    provenance_stamp: str
    transport: str | None = None
    drafted_at: datetime
    _drafted_at_is_utc = field_validator("drafted_at", mode="after")(_UTC_AFTER_VALIDATOR)

    @classmethod
    def from_artefact(cls, value: CloudDerivedArtefact) -> CloudDerivedArtefactProjection:
        """Copy every canonical derived-artifact fact into the schema-safe DTO."""
        return cls(**value.model_dump())


class ConsentWithdrawalSurveyProjection(BaseModel):
    """Complete consent survey copied into schema-safe public snapshots."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    consented_dispatches: Annotated[
        tuple[ConsentedDispatchProjection, ...], Field(max_length=MAX_EVIDENCE_FOLLOWUP_READ_ROWS)
    ] = ()
    cloud_derived_artefacts: Annotated[
        tuple[CloudDerivedArtefactProjection, ...], Field(max_length=MAX_EVIDENCE_FOLLOWUP_READ_ROWS)
    ] = ()
    transmitted_bytes_are_unrecallable: Literal[True] = True


def project_consent_withdrawal_survey(value: ConsentWithdrawalSurvey) -> ConsentWithdrawalSurveyProjection:
    """Copy every consent and derived-artifact row into the bounded public DTO."""
    if value.transmitted_bytes_are_unrecallable is not True:
        raise ValueError("consent survey must retain the canonical unrecallable-bytes statement")
    return ConsentWithdrawalSurveyProjection(
        consented_dispatches=tuple(
            ConsentedDispatchProjection.from_dispatch(row) for row in value.consented_dispatches
        ),
        cloud_derived_artefacts=tuple(
            CloudDerivedArtefactProjection.from_artefact(row) for row in value.cloud_derived_artefacts
        ),
        transmitted_bytes_are_unrecallable=True,
    )


class LedgerEvidenceConsentListProjection(BaseModel):
    """Consent history and cloud-derived artifacts for one exact profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    survey: ConsentWithdrawalSurveyProjection

    @model_validator(mode="after")
    def _correlate_consent_dispatches(self) -> LedgerEvidenceConsentListProjection:
        if any(row.profile_bucket_id != str(self.profile_id) for row in self.survey.consented_dispatches):
            raise ValueError("consent survey contains a dispatch from another profile")
        return self


class EvidenceReviewQueueRowProjection(BaseModel):
    """One pending draft with its complete blocker/advisory summary."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    evidence_reference: _Reference
    extractor: _ShortText
    drafted_at: datetime
    _drafted_at_is_utc = field_validator("drafted_at", mode="after")(_UTC_AFTER_VALIDATOR)
    blocking_count: NonNegativeInt
    reasons: Annotated[tuple[ConfirmationBlockReason, ...], Field(max_length=64)] = ()
    advisory_count: NonNegativeInt
    advisories: Annotated[tuple[ReviewAdvisoryKind, ...], Field(max_length=16)] = ()

    @model_validator(mode="after")
    def _correlate_counts_and_unique_summaries(self) -> EvidenceReviewQueueRowProjection:
        if self.advisory_count != len(self.advisories):
            raise ValueError("review queue advisory count does not match its kinds")
        if len(set(self.reasons)) != len(self.reasons) or len(set(self.advisories)) != len(self.advisories):
            raise ValueError("review queue row repeats a kind")
        if self.blocking_count < len(self.reasons):
            raise ValueError("review queue blocker summary exceeds its blocker count")
        return self


class PartyAttributionWarningProjection(BaseModel):
    """Public party warning with the canonical territory token as a string."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    role: _ShortText
    fields: Annotated[tuple[_ShortText, ...], Field(max_length=16)] = ()
    scope_if_attributed: _ShortText | None = None


class PartyAttributionAdvisoryProjection(BaseModel):
    """Closed public projection of all party attribution warnings."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    parties: Annotated[tuple[PartyAttributionWarningProjection, ...], Field(min_length=1, max_length=2)]

    @property
    def fields(self) -> tuple[str, ...]:
        """Return all unverified address fields in party order."""
        return tuple(field for party in self.parties for field in party.fields)


class CountryVocabularyWarningProjection(BaseModel):
    """Public country warning retaining its closed status and exact finding text."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    role: _ShortText
    field: _ShortText
    stated_code: _ShortText
    status: StatedCountryCodeStatus
    detail: _ShortText


class CountryVocabularyAdvisoryProjection(BaseModel):
    """Closed public projection of every country-vocabulary warning."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    parties: Annotated[tuple[CountryVocabularyWarningProjection, ...], Field(min_length=1, max_length=2)]

    def by_status(self, status: StatedCountryCodeStatus) -> tuple[CountryVocabularyWarningProjection, ...]:
        """Return the warnings for one exact canonical country-code status."""
        return tuple(party for party in self.parties if party.status is status)


class LedgerEvidenceReviewListProjection(BaseModel):
    """Complete bounded queue result and the request's displayed filters."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    filters: Annotated[tuple[str, ...], Field(max_length=4)] = ()
    rows: _ReviewRows = ()

    @model_validator(mode="after")
    def _ordered_unique_rows(self) -> LedgerEvidenceReviewListProjection:
        references = tuple(row.evidence_reference for row in self.rows)
        if references != tuple(sorted(set(references))):
            raise ValueError("review queue rows must have unique stable reference order")
        return self


class LedgerEvidenceReviewViewProjection(BaseModel):
    """Full canonical draft plus every finding and advisory needed for review.

    ``label_reading_fallback`` is read off the stored record, not the draft: the
    draft store moves it there when it writes, so the draft a review loads never
    carries it.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    evidence_reference: _Reference
    extractor: _ShortText
    drafted_at: datetime
    _drafted_at_is_utc = field_validator("drafted_at", mode="after")(_UTC_AFTER_VALIDATOR)
    draft: InvoiceDraftProjectionV1
    label_reading_fallback: LabelReadingFallbackProjectionV1 | None = None
    blockers: _BlockerRows = ()
    party_attribution_advisory: PartyAttributionAdvisoryProjection | None = None
    country_vocabulary_advisory: CountryVocabularyAdvisoryProjection | None = None

    @model_validator(mode="after")
    def _blocker_ids_are_unique(self) -> LedgerEvidenceReviewViewProjection:
        blocker_ids = tuple(blocker.blocker_id for blocker in self.blockers)
        if len(set(blocker_ids)) != len(blocker_ids):
            raise ValueError("review view repeats a blocker identity")
        return self


class LedgerEvidenceAttachmentQueueExecutionResult(BaseModel):
    """Encrypted result wrapper correlated to one profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    result: LedgerEvidenceAttachmentQueueProjection

    @model_validator(mode="after")
    def _profile_matches_result(self) -> LedgerEvidenceAttachmentQueueExecutionResult:
        if self.profile_id != self.result.profile_id:
            raise ValueError("attachment queue result belongs to another profile")
        return self


class LedgerEvidenceAttachmentViewExecutionResult(BaseModel):
    """Encrypted result wrapper correlated to one profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    result: LedgerEvidenceAttachmentViewProjection

    @model_validator(mode="after")
    def _profile_matches_result(self) -> LedgerEvidenceAttachmentViewExecutionResult:
        if self.profile_id != self.result.profile_id:
            raise ValueError("attachment view result belongs to another profile")
        return self


class LedgerEvidenceConsentListExecutionResult(BaseModel):
    """Encrypted result wrapper correlated to one profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    result: LedgerEvidenceConsentListProjection

    @model_validator(mode="after")
    def _profile_matches_result(self) -> LedgerEvidenceConsentListExecutionResult:
        if self.profile_id != self.result.profile_id:
            raise ValueError("consent list result belongs to another profile")
        return self


class LedgerEvidenceReviewListExecutionResult(BaseModel):
    """Encrypted result wrapper correlated to one profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    result: LedgerEvidenceReviewListProjection

    @model_validator(mode="after")
    def _profile_matches_result(self) -> LedgerEvidenceReviewListExecutionResult:
        if self.profile_id != self.result.profile_id:
            raise ValueError("review queue result belongs to another profile")
        return self


class LedgerEvidenceReviewViewExecutionResult(BaseModel):
    """Encrypted result wrapper correlated to one profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    result: LedgerEvidenceReviewViewProjection

    @model_validator(mode="after")
    def _profile_matches_result(self) -> LedgerEvidenceReviewViewExecutionResult:
        if self.profile_id != self.result.profile_id:
            raise ValueError("review view result belongs to another profile")
        return self


__all__ = [
    "LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID",
    "LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID",
    "LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID",
    "LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID",
    "LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID",
    "MAX_EVIDENCE_FOLLOWUP_READ_ROWS",
    "AttachmentStoreFactory",
    "CloudDerivedArtefactProjection",
    "ConsentWithdrawalSurveyProjection",
    "ConsentedDispatchProjection",
    "CountryVocabularyAdvisoryProjection",
    "CountryVocabularyWarningProjection",
    "EvidenceConsentEntriesFactory",
    "EvidenceReviewQueueRowProjection",
    "LedgerEvidenceAttachmentQueueExecutionResult",
    "LedgerEvidenceAttachmentQueueProjection",
    "LedgerEvidenceAttachmentQueueRequest",
    "LedgerEvidenceAttachmentViewExecutionResult",
    "LedgerEvidenceAttachmentViewProjection",
    "LedgerEvidenceAttachmentViewRequest",
    "LedgerEvidenceConsentListExecutionResult",
    "LedgerEvidenceConsentListProjection",
    "LedgerEvidenceConsentListRequest",
    "LedgerEvidenceFollowupOperationPorts",
    "LedgerEvidenceReviewListExecutionResult",
    "LedgerEvidenceReviewListProjection",
    "LedgerEvidenceReviewListRequest",
    "LedgerEvidenceReviewViewExecutionResult",
    "LedgerEvidenceReviewViewProjection",
    "LedgerEvidenceReviewViewRequest",
    "PartyAttributionAdvisoryProjection",
    "PartyAttributionWarningProjection",
    "project_consent_withdrawal_survey",
]

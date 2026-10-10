"""Closed request, result, and profile capability contracts for evidence follow-up reads.

The review view is a person's projection: it carries the draft's text as the
document prints it. The review summary serves the same review to an agent with
every finding, status and amount, and with that text left out.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Final, Literal, Protocol, Self
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, field_validator, model_validator

from ...core.config import Settings
from ...core.confirmation_gate import ConfirmationBlockReason, ReviewAdvisoryKind
from ...core.draft_discrepancy import DraftDiscrepancyKind
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.field_grounding import FieldGroundingOutcome
from ...core.field_origin import FieldOrigin
from ...core.hex import Hex64Str
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.time.utc import validate_utc_aware
from ...domain.attachments.protocols import AttachmentStoreProtocol
from ...domain.iva.classification import InvoiceKind
from ...domain.iva.establishment import StatedCountryCodeStatus
from ...domain.iva.supply_nature import SupplyNature
from ..operations.public_scalar import PublicDecimal
from .attachment_review import AttachmentReviewItem
from .consent_withdrawal import CloudDerivedArtefact, ConsentedDispatch, ConsentWithdrawalSurvey
from .extraction_draft_repository import ExtractionDraftRepositoryFactory
from .invoice_evidence_operation_dtos import (
    ConfirmationBlockerProjectionV1,
    DraftDiscrepancyProjectionV1,
    FieldProvenanceProjectionV1,
    InvoiceDraftLineProjectionV1,
    InvoiceDraftProjectionV1,
    InvoiceDraftRateBreakdownProjectionV1,
    LabelReadingFallbackProjectionV1,
)
from .structured_invoice_ports import StructuredInvoiceClassificationKind

LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID = "ledger.evidence.attachment_queue"


LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID = "ledger.evidence.attachment_view"


LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID = "ledger.evidence.consent.list"


LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID = "ledger.evidence.review.list"


LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID = "ledger.evidence.review.view"


LEDGER_EVIDENCE_REVIEW_SUMMARY_OPERATION_DEFINITION_ID = "ledger.evidence.review.summary"


MAX_EVIDENCE_FOLLOWUP_READ_ROWS = 4_096


_Reference = Annotated[str, Field(min_length=1, max_length=64)]


_AttachmentId = Annotated[str, Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")]


_ShortText = Annotated[str, Field(min_length=1, max_length=2_048)]


_ReviewRows = Annotated[
    tuple["EvidenceReviewQueueRowProjection", ...], Field(max_length=MAX_EVIDENCE_FOLLOWUP_READ_ROWS)
]


_AttachmentRows = Annotated[tuple[AttachmentReviewItem, ...], Field(max_length=MAX_EVIDENCE_FOLLOWUP_READ_ROWS)]


_BlockerRows = Annotated[tuple[ConfirmationBlockerProjectionV1, ...], Field(max_length=128)]


_FieldName = Annotated[str, Field(min_length=1, max_length=128)]


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

    @field_validator("recorded_at")
    @classmethod
    @pydantic_validation_boundary
    def _recorded_at_is_utc(cls, value: datetime) -> datetime:
        return validate_utc_aware(value)

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

    @field_validator("drafted_at")
    @classmethod
    @pydantic_validation_boundary
    def _drafted_at_is_utc(cls, value: datetime) -> datetime:
        return validate_utc_aware(value)

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
    blocking_count: NonNegativeInt
    reasons: Annotated[tuple[ConfirmationBlockReason, ...], Field(max_length=64)] = ()
    advisory_count: NonNegativeInt
    advisories: Annotated[tuple[ReviewAdvisoryKind, ...], Field(max_length=16)] = ()

    @field_validator("drafted_at")
    @classmethod
    @pydantic_validation_boundary
    def _drafted_at_is_utc(cls, value: datetime) -> datetime:
        return validate_utc_aware(value)

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
    draft: InvoiceDraftProjectionV1
    label_reading_fallback: LabelReadingFallbackProjectionV1 | None = None
    blockers: _BlockerRows = ()
    party_attribution_advisory: PartyAttributionAdvisoryProjection | None = None
    country_vocabulary_advisory: CountryVocabularyAdvisoryProjection | None = None

    @field_validator("drafted_at")
    @classmethod
    @pydantic_validation_boundary
    def _drafted_at_is_utc(cls, value: datetime) -> datetime:
        return validate_utc_aware(value)

    @model_validator(mode="after")
    def _blocker_ids_are_unique(self) -> LedgerEvidenceReviewViewProjection:
        blocker_ids = tuple(blocker.blocker_id for blocker in self.blockers)
        if len(set(blocker_ids)) != len(blocker_ids):
            raise ValueError("review view repeats a blocker identity")
        return self


DRAFT_TEXT_FIELDS_WITHHELD_FROM_AGENTS: Final[tuple[str, ...]] = (
    "supplier_tax_id",
    "supplier_name",
    "customer_tax_id",
    "customer_name",
    "supplier_postal_code",
    "customer_postal_code",
    "supplier_country",
    "customer_country",
    "supplier_country_code",
    "customer_country_code",
    "supplier_stated_country_code",
    "customer_stated_country_code",
    "invoice_number",
    "invoice_series",
    "rectifies_invoice_number",
    "invoice_date",
    "currency",
    "regime_legend",
    "iva_category",
)
"""The draft fields whose value is text a reader took from the document.

An unreviewed draft is third-party content. An agent is told which of these
fields hold a value and never what the value is; the person reads it in the
review view, and it becomes the person's own record on confirmation.
"""


class EvidenceReviewFieldSummary(BaseModel):
    """How one draft field was acquired and grounded, without the text that grounds it."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    field: _FieldName
    origin: FieldOrigin
    grounding: FieldGroundingOutcome
    anchor_self_reported: bool
    attribution_unverified: bool
    derived_from: Annotated[tuple[_FieldName, ...], Field(max_length=128)] = ()
    candidate_count: NonNegativeInt
    anchor_withheld: bool
    refused_anchor_withheld: bool
    role_evidence_withheld: bool
    note_withheld: bool

    @classmethod
    def from_provenance(cls, row: FieldProvenanceProjectionV1) -> Self:
        """Keep the typed axes of one provenance record and say which of its texts exist."""
        return cls(
            field=row.field,
            origin=row.origin,
            grounding=row.grounding,
            anchor_self_reported=row.anchor_self_reported,
            attribution_unverified=row.attribution_unverified,
            derived_from=row.derived_from,
            candidate_count=len(row.candidates),
            anchor_withheld=row.anchor is not None,
            refused_anchor_withheld=row.refused_anchor is not None,
            role_evidence_withheld=row.role_evidence is not None,
            note_withheld=bool(row.note),
        )


class EvidenceReviewDiscrepancySummary(BaseModel):
    """One extraction finding: its kind, the field it concerns and the figures compared."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: DraftDiscrepancyKind
    field: _FieldName | None = None
    expected: PublicDecimal | None = None
    observed: PublicDecimal | None = None
    detail_withheld: bool

    @classmethod
    def from_discrepancy(cls, row: DraftDiscrepancyProjectionV1) -> Self:
        """Keep the finding's typed facts; its explanation can quote the document."""
        return cls(
            kind=row.kind,
            field=row.field,
            expected=row.expected,
            observed=row.observed,
            detail_withheld=bool(row.detail),
        )


class EvidenceReviewBlockerSummary(BaseModel):
    """One question that blocks confirmation, addressed by the identity confirmation answers."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    blocker_id: Annotated[str, Field(min_length=16, max_length=16)]
    reason: ConfirmationBlockReason
    field: _FieldName | None = None
    candidate_count: NonNegativeInt
    detail_withheld: bool

    @classmethod
    def from_blocker(cls, row: ConfirmationBlockerProjectionV1) -> Self:
        """Keep the blocker's identity, reason and field; its candidates are document readings."""
        return cls(
            blocker_id=row.blocker_id,
            reason=row.reason,
            field=row.field,
            candidate_count=len(row.candidates),
            detail_withheld=bool(row.detail),
        )


class EvidenceReviewLineSummary(BaseModel):
    """One draft line's figures, without its description."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    quantity: PublicDecimal | None = None
    unit_price: PublicDecimal | None = None
    taxable_base: PublicDecimal | None = None
    iva_rate: PublicDecimal | None = None
    iva_amount: PublicDecimal | None = None
    recargo_rate: PublicDecimal | None = None
    recargo_amount: PublicDecimal | None = None
    description_withheld: bool

    @classmethod
    def from_line(cls, row: InvoiceDraftLineProjectionV1) -> Self:
        """Keep every amount and rate of one line and say whether a description exists."""
        return cls(
            quantity=row.quantity,
            unit_price=row.unit_price,
            taxable_base=row.taxable_base,
            iva_rate=row.iva_rate,
            iva_amount=row.iva_amount,
            recargo_rate=row.recargo_rate,
            recargo_amount=row.recargo_amount,
            description_withheld=row.description is not None,
        )


class EvidenceReviewCountryWarningSummary(BaseModel):
    """Which party's stated country code was not accepted, and how, without the code as printed."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    role: _ShortText
    field: _ShortText
    status: StatedCountryCodeStatus


class LedgerEvidenceReviewSummaryProjection(BaseModel):
    """One pending draft's review for an agent: findings, statuses and figures, no document text.

    Amounts, rates, closed classifications and the typed axes of every finding
    are released. Text a reader took from the document is not: the draft's
    text fields are named in ``withheld_text_fields`` when they hold a value,
    and each row says which of its own texts were left out.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    evidence_reference: _Reference
    extractor: _ShortText
    drafted_at: datetime
    suggested_kind: InvoiceKind | None = None
    proposed_supply_nature: SupplyNature | None = None
    structured_invoice_class: StructuredInvoiceClassificationKind | None = None
    taxable_base: PublicDecimal | None = None
    iva_rate: PublicDecimal | None = None
    iva_amount: PublicDecimal | None = None
    grand_total: PublicDecimal | None = None
    recargo_amount: PublicDecimal | None = None
    retencion_rate: PublicDecimal | None = None
    retencion_amount: PublicDecimal | None = None
    suplidos_amount: PublicDecimal | None = None
    lines: Annotated[tuple[EvidenceReviewLineSummary, ...], Field(max_length=2_048)] = ()
    iva_breakdown: Annotated[tuple[InvoiceDraftRateBreakdownProjectionV1, ...], Field(max_length=256)] = ()
    transcription_sha256: Hex64Str | None = None
    raw_text_length: NonNegativeInt = 0
    fields: Annotated[tuple[EvidenceReviewFieldSummary, ...], Field(max_length=128)] = ()
    discrepancies: Annotated[tuple[EvidenceReviewDiscrepancySummary, ...], Field(max_length=128)] = ()
    blockers: Annotated[tuple[EvidenceReviewBlockerSummary, ...], Field(max_length=128)] = ()
    label_reading_fallback: LabelReadingFallbackProjectionV1 | None = None
    party_attribution_advisory: PartyAttributionAdvisoryProjection | None = None
    country_vocabulary_warnings: Annotated[tuple[EvidenceReviewCountryWarningSummary, ...], Field(max_length=2)] = ()
    withheld_text_fields: Annotated[tuple[_FieldName, ...], Field(max_length=64)] = ()
    text_withheld: bool

    @field_validator("drafted_at")
    @classmethod
    @pydantic_validation_boundary
    def _drafted_at_is_utc(cls, value: datetime) -> datetime:
        return validate_utc_aware(value)

    @model_validator(mode="after")
    def _consistent_summary(self) -> Self:
        blocker_ids = tuple(blocker.blocker_id for blocker in self.blockers)
        if len(set(blocker_ids)) != len(blocker_ids):
            raise ValueError("review summary repeats a blocker identity")
        if any(name not in DRAFT_TEXT_FIELDS_WITHHELD_FROM_AGENTS for name in self.withheld_text_fields) or len(
            set(self.withheld_text_fields)
        ) != len(self.withheld_text_fields):
            raise ValueError("review summary names a withheld field the draft does not hold as text")
        return self

    @classmethod
    def from_review_view(cls, view: LedgerEvidenceReviewViewProjection) -> Self:
        """Reduce the person's complete review to what an agent may hold."""
        draft = view.draft
        withheld_fields = tuple(
            name for name in DRAFT_TEXT_FIELDS_WITHHELD_FROM_AGENTS if getattr(draft, name) is not None
        )
        fields = tuple(EvidenceReviewFieldSummary.from_provenance(row) for row in draft.provenance)
        discrepancies = tuple(EvidenceReviewDiscrepancySummary.from_discrepancy(row) for row in draft.discrepancies)
        blockers = tuple(EvidenceReviewBlockerSummary.from_blocker(row) for row in view.blockers)
        lines = tuple(EvidenceReviewLineSummary.from_line(row) for row in draft.lines)
        structured_class = draft.facturae_invoice_class
        country_advisory = view.country_vocabulary_advisory
        country_warnings = (
            ()
            if country_advisory is None
            else tuple(
                EvidenceReviewCountryWarningSummary(role=row.role, field=row.field, status=row.status)
                for row in country_advisory.parties
            )
        )
        return cls(
            profile_id=view.profile_id,
            evidence_reference=view.evidence_reference,
            extractor=view.extractor,
            drafted_at=view.drafted_at,
            suggested_kind=draft.suggested_kind,
            proposed_supply_nature=draft.proposed_supply_nature,
            structured_invoice_class=None if structured_class is None else structured_class.kind,
            taxable_base=draft.taxable_base,
            iva_rate=draft.iva_rate,
            iva_amount=draft.iva_amount,
            grand_total=draft.grand_total,
            recargo_amount=draft.recargo_amount,
            retencion_rate=draft.retencion_rate,
            retencion_amount=draft.retencion_amount,
            suplidos_amount=draft.suplidos_amount,
            lines=lines,
            iva_breakdown=draft.iva_breakdown,
            transcription_sha256=draft.transcription_sha256,
            raw_text_length=draft.raw_text_length,
            fields=fields,
            discrepancies=discrepancies,
            blockers=blockers,
            label_reading_fallback=view.label_reading_fallback,
            party_attribution_advisory=view.party_attribution_advisory,
            country_vocabulary_warnings=country_warnings,
            withheld_text_fields=withheld_fields,
            text_withheld=bool(
                withheld_fields
                or structured_class is not None
                or country_warnings
                or any(line.description_withheld for line in lines)
                or any(
                    row.candidate_count
                    or row.anchor_withheld
                    or row.refused_anchor_withheld
                    or row.role_evidence_withheld
                    or row.note_withheld
                    for row in fields
                )
                or any(row.detail_withheld for row in discrepancies)
                or any(row.detail_withheld or row.candidate_count for row in blockers)
            ),
        )


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


class LedgerEvidenceReviewSummaryExecutionResult(BaseModel):
    """Encrypted result wrapper correlated to one profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    result: LedgerEvidenceReviewSummaryProjection

    @model_validator(mode="after")
    def _profile_matches_result(self) -> LedgerEvidenceReviewSummaryExecutionResult:
        if self.profile_id != self.result.profile_id:
            raise ValueError("review summary result belongs to another profile")
        return self


__all__ = [
    "DRAFT_TEXT_FIELDS_WITHHELD_FROM_AGENTS",
    "LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID",
    "LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID",
    "LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID",
    "LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID",
    "LEDGER_EVIDENCE_REVIEW_SUMMARY_OPERATION_DEFINITION_ID",
    "LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID",
    "MAX_EVIDENCE_FOLLOWUP_READ_ROWS",
    "AttachmentStoreFactory",
    "CloudDerivedArtefactProjection",
    "ConsentWithdrawalSurveyProjection",
    "ConsentedDispatchProjection",
    "CountryVocabularyAdvisoryProjection",
    "CountryVocabularyWarningProjection",
    "EvidenceConsentEntriesFactory",
    "EvidenceReviewBlockerSummary",
    "EvidenceReviewCountryWarningSummary",
    "EvidenceReviewDiscrepancySummary",
    "EvidenceReviewFieldSummary",
    "EvidenceReviewLineSummary",
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
    "LedgerEvidenceReviewSummaryExecutionResult",
    "LedgerEvidenceReviewSummaryProjection",
    "LedgerEvidenceReviewViewExecutionResult",
    "LedgerEvidenceReviewViewProjection",
    "LedgerEvidenceReviewViewRequest",
    "PartyAttributionAdvisoryProjection",
    "PartyAttributionWarningProjection",
    "project_consent_withdrawal_survey",
]

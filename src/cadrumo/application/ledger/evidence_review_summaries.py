"""Keep evidence review findings and amounts while withholding source text."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Annotated, Final, Self
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, field_validator, model_validator

from ...core.confirmation_gate import ConfirmationBlockReason
from ...core.draft_discrepancy import DraftDiscrepancyKind
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.field_grounding import FieldGroundingOutcome
from ...core.field_origin import FieldOrigin
from ...core.hex import Hex16Str, Hex64Str
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.time.utc import validate_utc_aware
from ...domain.iva.establishment import StatedCountryCodeStatus
from ...domain.iva.schema import InvoiceKind
from ...domain.iva.supply_nature import SupplyNature
from ..operations.public_scalar import PublicDecimal
from .evidence_followup_types import EvidenceFollowupReference, EvidenceFollowupText, EvidenceReviewFieldName
from .evidence_review_advisories import (
    CountryVocabularyAdvisoryProjection,
    PartyAttributionAdvisoryProjection,
)
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

if TYPE_CHECKING:
    from .evidence_followup_contracts import LedgerEvidenceReviewViewProjection

DRAFT_TEXT_FIELDS_WITHHELD_FROM_AUTOMATION: Final[tuple[str, ...]] = (
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

An unreviewed draft is third-party content. An automation is told which of these
fields hold a value and never what the value is; the person reads it in the
review view, and it becomes the person's own record on confirmation.
"""


class EvidenceReviewFieldSummary(BaseModel):
    """How one draft field was acquired and grounded, without the text that grounds it."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    field: EvidenceReviewFieldName
    origin: FieldOrigin
    grounding: FieldGroundingOutcome
    anchor_self_reported: bool
    attribution_unverified: bool
    derived_from: Annotated[tuple[EvidenceReviewFieldName, ...], Field(max_length=128)] = ()
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
    field: EvidenceReviewFieldName | None = None
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
    blocker_id: Hex16Str
    reason: ConfirmationBlockReason
    field: EvidenceReviewFieldName | None = None
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
    role: EvidenceFollowupText
    field: EvidenceFollowupText
    status: StatedCountryCodeStatus


class LedgerEvidenceReviewSummaryProjection(BaseModel):
    """One pending draft's review for an automation: findings, statuses and figures, no document text.

    Amounts, rates, closed classifications and the typed axes of every finding
    are released. Text a reader took from the document is not: the draft's
    text fields are named in ``withheld_text_fields`` when they hold a value,
    and each row says which of its own texts were left out.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    evidence_reference: EvidenceFollowupReference
    extractor: EvidenceFollowupText
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
    country_vocabulary_warnings: Annotated[tuple[EvidenceReviewCountryWarningSummary, ...], Field(max_length=16)] = ()
    withheld_text_fields: Annotated[tuple[EvidenceReviewFieldName, ...], Field(max_length=64)] = ()
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
        if any(name not in DRAFT_TEXT_FIELDS_WITHHELD_FROM_AUTOMATION for name in self.withheld_text_fields) or len(
            set(self.withheld_text_fields)
        ) != len(self.withheld_text_fields):
            raise ValueError("review summary names a withheld field the draft does not hold as text")
        return self

    @classmethod
    def from_review_view(cls, view: LedgerEvidenceReviewViewProjection) -> Self:
        """Reduce the person's complete review to what an automation may hold."""
        draft = view.draft
        withheld_fields = _draft_withheld_text(draft)
        fields = tuple(EvidenceReviewFieldSummary.from_provenance(row) for row in draft.provenance)
        discrepancies = tuple(EvidenceReviewDiscrepancySummary.from_discrepancy(row) for row in draft.discrepancies)
        blockers = tuple(EvidenceReviewBlockerSummary.from_blocker(row) for row in view.blockers)
        lines = tuple(EvidenceReviewLineSummary.from_line(row) for row in draft.lines)
        structured_class = draft.facturae_invoice_class
        country_advisory = view.country_vocabulary_advisory
        country_warnings = _country_warning_summaries(country_advisory)
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
                or _summary_rows_withheld(lines, fields, discrepancies, blockers)
            ),
        )


def _draft_withheld_text(draft: InvoiceDraftProjectionV1) -> tuple[str, ...]:
    return tuple(name for name in DRAFT_TEXT_FIELDS_WITHHELD_FROM_AUTOMATION if getattr(draft, name) is not None)


def _country_warning_summaries(
    country_advisory: CountryVocabularyAdvisoryProjection | None,
) -> tuple[EvidenceReviewCountryWarningSummary, ...]:
    return (
        ()
        if country_advisory is None
        else tuple(
            EvidenceReviewCountryWarningSummary(role=row.role, field=row.field, status=row.status)
            for row in country_advisory.parties
        )
    )


def _field_text_withheld(row: EvidenceReviewFieldSummary) -> bool:
    return bool(
        row.candidate_count
        or row.anchor_withheld
        or row.refused_anchor_withheld
        or row.role_evidence_withheld
        or row.note_withheld
    )


def _summary_rows_withheld(
    lines: tuple[EvidenceReviewLineSummary, ...],
    fields: tuple[EvidenceReviewFieldSummary, ...],
    discrepancies: tuple[EvidenceReviewDiscrepancySummary, ...],
    blockers: tuple[EvidenceReviewBlockerSummary, ...],
) -> bool:
    return (
        any(line.description_withheld for line in lines)
        or any(_field_text_withheld(row) for row in fields)
        or any(row.detail_withheld for row in discrepancies)
        or any(row.detail_withheld or row.candidate_count for row in blockers)
    )

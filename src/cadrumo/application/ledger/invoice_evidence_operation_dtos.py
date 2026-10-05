"""Closed, lossless public DTOs for invoice evidence reading and confirmation.

The canonical evidence services return domain-rich drafts and confirmation
results. These projections keep every operator-relevant field while replacing
Decimals with :class:`PublicDecimal` and registry-projected tokens with bounded
strings. The latter values are already resolved under the caller's retained
authority pin; a frontend must not re-open the current registry to validate a
result that belongs to an earlier operation.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Self, TypeVar

from pydantic import BaseModel, Field, model_validator

from ...core.classifier_input_source import ClassifierInputSource
from ...core.confirmation_gate import ConfirmationBlockReason
from ...core.draft_discrepancy import DraftDiscrepancyKind
from ...core.field_grounding import FieldGroundingOutcome
from ...core.field_origin import FieldOrigin
from ...core.hex import Hex64Str
from ...core.iva_category_resolution import IvaCategoryOutcome
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.iva.classification import InvoiceKind, IvaInvoiceClassificationCriteria
from ...domain.iva.supply_nature import SupplyNature
from ..invoices.catalogue_read_projection import CatalogueInvoiceSnapshot
from ..ledger.classification_assembly import (
    ClassificationAssembly,
    DeclaredFact,
    DeclaredFacts,
    IvaCategoryResolution,
    MissingClassifierInput,
)
from ..ledger.confirm_establishment import ConfirmedEstablishment
from ..ledger.confirmation_gate import ConfirmationBlocker
from ..ledger.counterparty_establishment import CounterpartyEstablishmentContradiction
from ..ledger.establishment_ladder import (
    CounterpartyEstablishment,
    EstablishmentRung,
    RegistrationEstablishmentConflict,
)
from ..ledger.evidence_draft import PrintedTotalDiscrepancy
from ..ledger.invoice_confirmation import InvoiceConfirmationResult
from ..ledger.invoice_draft_records import (
    DraftDiscrepancyFinding,
    FieldAmbiguityCandidate,
    FieldProvenance,
    InvoiceDraft,
    InvoiceDraftLine,
    InvoiceDraftRateBreakdown,
    LabelReadingFallback,
    LabelReadingFallbackCause,
)
from ..ledger.structured_invoice_ports import (
    StructuredInvoiceClassificationKind,
)
from ..operations.public_scalar import PublicDecimal

_BoundedText = Annotated[str, Field(max_length=16_384)]
_ShortText = Annotated[str, Field(max_length=2_048)]
_FieldName = Annotated[str, Field(min_length=1, max_length=128)]
_RegistryToken = Annotated[str, Field(min_length=1, max_length=128)]
_MemberStateToken = Annotated[str, Field(min_length=2, max_length=2)]
_DeclaredValue = TypeVar("_DeclaredValue")


def _decimal(value: Decimal | None) -> PublicDecimal | None:
    """Preserve a decimal's canonical spelling on the public wire."""
    return None if value is None else PublicDecimal(decimal=str(value))


def _token(value: object | None) -> str | None:
    """Project one already-resolved opaque token without ambient revalidation."""
    return None if value is None else str(value)


class FieldAmbiguityCandidateProjectionV1(BaseModel):
    """Bounded candidate evidence carried by a field-provenance envelope."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    value: _ShortText
    anchor: _BoundedText | None = None
    note: _ShortText = ""

    @classmethod
    def from_candidate(cls, value: FieldAmbiguityCandidate) -> Self:
        """Copy one canonical ambiguity candidate without changing its facts."""
        return cls(value=value.value, anchor=value.anchor, note=value.note)


_Candidates = Annotated[tuple[FieldAmbiguityCandidateProjectionV1, ...], Field(max_length=16)]
_DerivedFields = Annotated[tuple[_FieldName, ...], Field(max_length=128)]


class FieldProvenanceProjectionV1(BaseModel):
    """Closed public form of one field's acquisition and grounding record."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    field: _FieldName
    origin: FieldOrigin
    grounding: FieldGroundingOutcome
    anchor: _BoundedText | None = None
    refused_anchor: _BoundedText | None = None
    candidates: _Candidates = ()
    anchor_self_reported: bool = False
    derived_from: _DerivedFields = ()
    role_evidence: _BoundedText | None = None
    attribution_unverified: bool = False
    note: _ShortText = ""

    @classmethod
    def from_provenance(cls, value: FieldProvenance) -> Self:
        """Copy all provenance axes, including ambiguity and party attribution."""
        return cls(
            field=value.field,
            origin=value.origin,
            grounding=value.grounding,
            anchor=value.anchor,
            refused_anchor=value.refused_anchor,
            candidates=tuple(FieldAmbiguityCandidateProjectionV1.from_candidate(row) for row in value.candidates),
            anchor_self_reported=value.anchor_self_reported,
            derived_from=value.derived_from,
            role_evidence=value.role_evidence,
            attribution_unverified=value.attribution_unverified,
            note=value.note,
        )


class DraftDiscrepancyProjectionV1(BaseModel):
    """One extraction finding with lossless decimal facts."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: DraftDiscrepancyKind
    field: _FieldName | None = None
    detail: _ShortText = ""
    expected: PublicDecimal | None = None
    observed: PublicDecimal | None = None

    @classmethod
    def from_finding(cls, value: DraftDiscrepancyFinding) -> Self:
        """Copy a finding while tagging its arithmetic values as decimals."""
        return cls(
            kind=value.kind,
            field=value.field,
            detail=value.detail,
            expected=_decimal(value.expected),
            observed=_decimal(value.observed),
        )


class LabelReadingFallbackProjectionV1(BaseModel):
    """Why a draft's label reading stood without its model fill.

    Kept beside a draft projection, never inside it: the fallback describes the
    reader, not the document, and a stored draft does not carry it, so folding
    it into the draft would change the digest a review is bound to.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    cause: LabelReadingFallbackCause
    unread_fields: Annotated[tuple[_FieldName, ...], Field(min_length=1, max_length=128)]
    reader_error_type: Annotated[str, Field(min_length=1, max_length=2_048)]
    failed_condition_id: _ShortText | None = None

    @classmethod
    def from_fallback(cls, value: LabelReadingFallback) -> Self:
        """Copy the machine facts of one fallback; it holds no document text."""
        return cls(
            cause=value.cause,
            unread_fields=value.unread_fields,
            reader_error_type=value.reader_error_type,
            failed_condition_id=value.failed_condition_id,
        )

    def to_fallback(self) -> LabelReadingFallback:
        """Restore the canonical record the frontend notice projectors read."""
        return LabelReadingFallback(
            cause=self.cause,
            unread_fields=self.unread_fields,
            reader_error_type=self.reader_error_type,
            failed_condition_id=self.failed_condition_id,
        )


class InvoiceDraftLineProjectionV1(BaseModel):
    """One structured line, preserving every optional amount and rate."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    description: _BoundedText | None = None
    quantity: PublicDecimal | None = None
    unit_price: PublicDecimal | None = None
    taxable_base: PublicDecimal | None = None
    iva_rate: PublicDecimal | None = None
    iva_amount: PublicDecimal | None = None
    recargo_rate: PublicDecimal | None = None
    recargo_amount: PublicDecimal | None = None

    @classmethod
    def from_line(cls, value: InvoiceDraftLine) -> Self:
        """Copy one structured draft line without deriving absent fields."""
        return cls(
            description=value.description,
            quantity=_decimal(value.quantity),
            unit_price=_decimal(value.unit_price),
            taxable_base=_decimal(value.taxable_base),
            iva_rate=_decimal(value.iva_rate),
            iva_amount=_decimal(value.iva_amount),
            recargo_rate=_decimal(value.recargo_rate),
            recargo_amount=_decimal(value.recargo_amount),
        )


class InvoiceDraftRateBreakdownProjectionV1(BaseModel):
    """One per-rate subtotal declared by a structured invoice."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    iva_rate: PublicDecimal | None = None
    taxable_base: PublicDecimal | None = None
    iva_amount: PublicDecimal | None = None
    recargo_rate: PublicDecimal | None = None
    recargo_amount: PublicDecimal | None = None

    @classmethod
    def from_breakdown(cls, value: InvoiceDraftRateBreakdown) -> Self:
        """Copy each per-rate amount, retaining distinctions between absent and zero."""
        return cls(
            iva_rate=_decimal(value.iva_rate),
            taxable_base=_decimal(value.taxable_base),
            iva_amount=_decimal(value.iva_amount),
            recargo_rate=_decimal(value.recargo_rate),
            recargo_amount=_decimal(value.recargo_amount),
        )


class StructuredInvoiceClassProjectionV1(BaseModel):
    """The structured reader's class fact, stored privately on ``InvoiceDraft``."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    source_code: _ShortText
    kind: StructuredInvoiceClassificationKind


_ProvenanceRows = Annotated[tuple[FieldProvenanceProjectionV1, ...], Field(max_length=128)]
_DraftLines = Annotated[tuple[InvoiceDraftLineProjectionV1, ...], Field(max_length=2_048)]
_RateBreakdowns = Annotated[tuple[InvoiceDraftRateBreakdownProjectionV1, ...], Field(max_length=256)]
_Discrepancies = Annotated[tuple[DraftDiscrepancyProjectionV1, ...], Field(max_length=128)]


class InvoiceDraftProjectionV1(BaseModel):
    """Closed public projection preserving the full canonical ``InvoiceDraft``."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    supplier_tax_id: _ShortText | None = None
    supplier_name: _BoundedText | None = None
    customer_tax_id: _ShortText | None = None
    customer_name: _BoundedText | None = None
    supplier_postal_code: _ShortText | None = None
    customer_postal_code: _ShortText | None = None
    supplier_country: _ShortText | None = None
    customer_country: _ShortText | None = None
    supplier_country_code: _ShortText | None = None
    customer_country_code: _ShortText | None = None
    supplier_stated_country_code: _ShortText | None = None
    customer_stated_country_code: _ShortText | None = None
    invoice_number: _ShortText | None = None
    invoice_series: _ShortText | None = None
    rectifies_invoice_number: _ShortText | None = None
    proposed_supply_nature: SupplyNature | None = None
    invoice_date: _ShortText | None = None
    taxable_base: PublicDecimal | None = None
    iva_rate: PublicDecimal | None = None
    iva_amount: PublicDecimal | None = None
    grand_total: PublicDecimal | None = None
    currency: _ShortText | None = None
    regime_legend: _BoundedText | None = None
    recargo_amount: PublicDecimal | None = None
    retencion_rate: PublicDecimal | None = None
    retencion_amount: PublicDecimal | None = None
    suplidos_amount: PublicDecimal | None = None
    lines: _DraftLines = ()
    iva_breakdown: _RateBreakdowns = ()
    iva_category: _RegistryToken | None = None
    suggested_kind: InvoiceKind | None = None
    transcription_sha256: Hex64Str | None = None
    provenance: _ProvenanceRows = ()
    discrepancies: _Discrepancies = ()
    raw_text_length: Annotated[int, Field(ge=0)] = 0
    facturae_invoice_class: StructuredInvoiceClassProjectionV1 | None = None

    @model_validator(mode="after")
    def _provenance_names_are_unique_draft_fields(self) -> Self:
        """Keep provenance attached to one declared field, as the source model does."""
        known = type(self).model_fields
        names = tuple(row.field for row in self.provenance)
        if len(set(names)) != len(names) or any(name not in known for name in names):
            raise ValueError("draft provenance must name unique fields present in the projection")
        return self

    @classmethod
    def from_draft(cls, draft: InvoiceDraft) -> Self:
        """Project every source field and the additional structured-class property."""
        structured_class = draft.facturae_invoice_class
        return cls(
            supplier_tax_id=_token(draft.supplier_tax_id),
            supplier_name=draft.supplier_name,
            customer_tax_id=_token(draft.customer_tax_id),
            customer_name=draft.customer_name,
            supplier_postal_code=draft.supplier_postal_code,
            customer_postal_code=draft.customer_postal_code,
            supplier_country=draft.supplier_country,
            customer_country=draft.customer_country,
            supplier_country_code=draft.supplier_country_code,
            customer_country_code=draft.customer_country_code,
            supplier_stated_country_code=draft.supplier_stated_country_code,
            customer_stated_country_code=draft.customer_stated_country_code,
            invoice_number=draft.invoice_number,
            invoice_series=draft.invoice_series,
            rectifies_invoice_number=draft.rectifies_invoice_number,
            proposed_supply_nature=draft.proposed_supply_nature,
            invoice_date=draft.invoice_date,
            taxable_base=_decimal(draft.taxable_base),
            iva_rate=_decimal(draft.iva_rate),
            iva_amount=_decimal(draft.iva_amount),
            grand_total=_decimal(draft.grand_total),
            currency=draft.currency,
            regime_legend=draft.regime_legend,
            recargo_amount=_decimal(draft.recargo_amount),
            retencion_rate=_decimal(draft.retencion_rate),
            retencion_amount=_decimal(draft.retencion_amount),
            suplidos_amount=_decimal(draft.suplidos_amount),
            lines=tuple(InvoiceDraftLineProjectionV1.from_line(row) for row in draft.lines),
            iva_breakdown=tuple(
                InvoiceDraftRateBreakdownProjectionV1.from_breakdown(row) for row in draft.iva_breakdown
            ),
            iva_category=draft.iva_category,
            suggested_kind=draft.suggested_kind,
            transcription_sha256=_token(draft.transcription_sha256),
            provenance=tuple(FieldProvenanceProjectionV1.from_provenance(row) for row in draft.provenance),
            discrepancies=tuple(DraftDiscrepancyProjectionV1.from_finding(row) for row in draft.discrepancies),
            raw_text_length=draft.raw_text_length,
            facturae_invoice_class=(
                None
                if structured_class is None
                else StructuredInvoiceClassProjectionV1(
                    source_code=structured_class.source_code,
                    kind=structured_class.kind,
                )
            ),
        )


class RegistryFactProjectionV1(BaseModel):
    """A value and source whose value vocabulary belongs to a retained registry pin."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    value: _RegistryToken
    source: ClassifierInputSource

    @classmethod
    def from_fact(cls, fact: DeclaredFact[_DeclaredValue] | None) -> Self | None:
        """Project the selected token and its attribution without re-resolving it."""
        return None if fact is None else cls(value=str(fact.value), source=fact.source)


class MissingClassifierInputProjectionV1(BaseModel):
    """One bounded input gap in the classification assembly."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    field: _FieldName
    reason: _ShortText
    settled_by: _ShortText

    @classmethod
    def from_missing(cls, value: MissingClassifierInput) -> Self:
        """Copy the named input gap and its resolution guidance."""
        return cls(field=value.field, reason=value.reason, settled_by=value.settled_by)


class ClassificationCriteriaProjectionV1(BaseModel):
    """Criteria sent to the IVA rule table, with governed tokens as plain values."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    transaction_date: date
    issuer_residency: _RegistryToken
    customer_residency: _RegistryToken
    customer_tax_status: _RegistryToken
    kind: _RegistryToken
    direction: InvoiceKind
    issuer_identification_state: _MemberStateToken | None = None
    customer_identification_state: _MemberStateToken | None = None
    art_69_dos_service: _RegistryToken | None = None
    rate_tier: _RegistryToken | None = None

    @classmethod
    def from_criteria(cls, value: IvaInvoiceClassificationCriteria) -> Self:
        """Project facts already selected by the caller-owned authority operation."""
        return cls(
            transaction_date=value.transaction_date,
            issuer_residency=str(value.issuer_residency),
            customer_residency=str(value.customer_residency),
            customer_tax_status=str(value.customer_tax_status),
            kind=str(value.kind),
            direction=value.direction,
            issuer_identification_state=_token(value.issuer_identification_state),
            customer_identification_state=_token(value.customer_identification_state),
            art_69_dos_service=_token(value.art_69_dos_service),
            rate_tier=_token(value.rate_tier),
        )


class ClassificationAssemblyProjectionV1(BaseModel):
    """Either the assembled criteria or the complete set of blocking gaps."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    criteria: ClassificationCriteriaProjectionV1 | None = None
    missing: Annotated[tuple[MissingClassifierInputProjectionV1, ...], Field(max_length=64)] = ()

    @classmethod
    def from_assembly(cls, value: ClassificationAssembly) -> Self:
        """Copy both the criteria, when complete, and every reported gap."""
        return cls(
            criteria=None
            if value.criteria is None
            else ClassificationCriteriaProjectionV1.from_criteria(value.criteria),
            missing=tuple(MissingClassifierInputProjectionV1.from_missing(row) for row in value.missing),
        )


class IvaCategoryResolutionProjectionV1(BaseModel):
    """Resolved, classified and document-declared IVA tokens with outcome."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: IvaCategoryOutcome
    category: _RegistryToken | None = None
    classified: _RegistryToken | None = None
    declared: RegistryFactProjectionV1 | None = None
    note: _ShortText = ""

    @classmethod
    def from_resolution(cls, value: IvaCategoryResolution) -> Self:
        """Copy each independent category answer and its outcome."""
        return cls(
            outcome=value.outcome,
            category=_token(value.category),
            classified=_token(value.classified),
            declared=RegistryFactProjectionV1.from_fact(value.declared),
            note=value.note,
        )


class CounterpartyEstablishmentContradictionProjectionV1(BaseModel):
    """Both incompatible territory claims, without registry-token revalidation."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    counterparty_key: Hex64Str
    canonical_tax_identifier: _ShortText
    confirmed_scope: _RegistryToken
    evidenced_scope: _RegistryToken
    detail: _ShortText

    @classmethod
    def from_contradiction(cls, value: CounterpartyEstablishmentContradiction) -> Self:
        """Copy both sides of the territory contradiction and its identity key."""
        return cls(
            counterparty_key=value.counterparty_key,
            canonical_tax_identifier=value.canonical_tax_identifier,
            confirmed_scope=str(value.confirmed_scope),
            evidenced_scope=str(value.evidenced_scope),
            detail=value.detail,
        )


class RegistrationEstablishmentConflictProjectionV1(BaseModel):
    """Foreign-registration evidence beside Spain-indicating document facts."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    identification_state: _MemberStateToken
    spain_indicating: Annotated[tuple[_ShortText, ...], Field(min_length=1, max_length=16)]
    detail: _ShortText

    @classmethod
    def from_conflict(cls, value: RegistrationEstablishmentConflict) -> Self:
        """Copy all facts in the registration conflict."""
        return cls(
            identification_state=str(value.identification_state),
            spain_indicating=value.spain_indicating,
            detail=value.detail,
        )


class CounterpartyEstablishmentProjectionV1(BaseModel):
    """Counterparty territory answer, including the exact rung and conflicts."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    scope: _RegistryToken | None = None
    rung: EstablishmentRung | None = None
    source: ClassifierInputSource | None = None
    contradiction: CounterpartyEstablishmentContradictionProjectionV1 | None = None
    identification_state: _MemberStateToken | None = None
    registration_conflict: RegistrationEstablishmentConflictProjectionV1 | None = None

    @classmethod
    def from_counterparty(cls, value: CounterpartyEstablishment) -> Self:
        """Copy the settled scope and any independent registration evidence."""
        return cls(
            scope=_token(value.scope),
            rung=value.rung,
            source=value.source,
            contradiction=(
                None
                if value.contradiction is None
                else CounterpartyEstablishmentContradictionProjectionV1.from_contradiction(value.contradiction)
            ),
            identification_state=_token(value.identification_state),
            registration_conflict=(
                None
                if value.registration_conflict is None
                else RegistrationEstablishmentConflictProjectionV1.from_conflict(value.registration_conflict)
            ),
        )


class ConfirmationBlockerProjectionV1(BaseModel):
    """One actionable review question retained on the confirmation result."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    blocker_id: Annotated[str, Field(min_length=16, max_length=16)]
    reason: ConfirmationBlockReason
    field: _FieldName | None = None
    detail: _ShortText = ""
    candidates: _Candidates = ()

    @classmethod
    def from_blocker(cls, value: ConfirmationBlocker) -> Self:
        """Copy the blocking question and its candidate evidence."""
        return cls(
            blocker_id=value.blocker_id,
            reason=value.reason,
            field=value.field,
            detail=value.detail,
            candidates=tuple(FieldAmbiguityCandidateProjectionV1.from_candidate(row) for row in value.candidates),
        )


class ConfirmedEstablishmentProjectionV1(BaseModel):
    """Full two-party territory, assembly, category and unresolved-review facts."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    counterparty: CounterpartyEstablishmentProjectionV1
    filer_scope: _RegistryToken | None = None
    declared: DeclaredFactsProjectionV1
    assembly: ClassificationAssemblyProjectionV1
    category: IvaCategoryResolutionProjectionV1
    review_items: Annotated[tuple[ConfirmationBlockerProjectionV1, ...], Field(max_length=64)] = ()
    resolved: bool

    @classmethod
    def from_establishment(cls, value: ConfirmedEstablishment) -> Self:
        """Copy every public field plus its derived established-state convenience."""
        return cls(
            counterparty=CounterpartyEstablishmentProjectionV1.from_counterparty(value.counterparty),
            filer_scope=_token(value.filer_scope),
            declared=DeclaredFactsProjectionV1.from_facts(value.declared),
            assembly=ClassificationAssemblyProjectionV1.from_assembly(value.assembly),
            category=IvaCategoryResolutionProjectionV1.from_resolution(value.category),
            review_items=tuple(ConfirmationBlockerProjectionV1.from_blocker(row) for row in value.review_items),
            resolved=value.resolved,
        )


class DeclaredFactsProjectionV1(BaseModel):
    """Every input fact consumed by classification, beside who established it."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    supply_nature: RegistryFactProjectionV1 | None = None
    customer_tax_status: RegistryFactProjectionV1 | None = None
    issuer_scope: RegistryFactProjectionV1 | None = None
    customer_scope: RegistryFactProjectionV1 | None = None
    issuer_identification_state: RegistryFactProjectionV1 | None = None
    customer_identification_state: RegistryFactProjectionV1 | None = None
    stated_category: RegistryFactProjectionV1 | None = None

    @classmethod
    def from_facts(cls, value: DeclaredFacts) -> Self:
        """Copy all seven independent facts without deriving absent answers."""
        return cls(
            supply_nature=RegistryFactProjectionV1.from_fact(value.supply_nature),
            customer_tax_status=RegistryFactProjectionV1.from_fact(value.customer_tax_status),
            issuer_scope=RegistryFactProjectionV1.from_fact(value.issuer_scope),
            customer_scope=RegistryFactProjectionV1.from_fact(value.customer_scope),
            issuer_identification_state=RegistryFactProjectionV1.from_fact(value.issuer_identification_state),
            customer_identification_state=RegistryFactProjectionV1.from_fact(value.customer_identification_state),
            stated_category=RegistryFactProjectionV1.from_fact(value.stated_category),
        )


class PrintedTotalDiscrepancyProjectionV1(BaseModel):
    """The printed, recorded and difference amounts returned by confirmation."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    printed_total: PublicDecimal
    recorded_total: PublicDecimal
    difference: PublicDecimal

    @classmethod
    def from_discrepancy(cls, value: PrintedTotalDiscrepancy) -> Self:
        """Copy all three totals without rounding or recomputing their difference."""
        return cls(
            printed_total=PublicDecimal(decimal=str(value.printed_total)),
            recorded_total=PublicDecimal(decimal=str(value.recorded_total)),
            difference=PublicDecimal(decimal=str(value.difference)),
        )


class InvoiceConfirmationProjectionV1(BaseModel):
    """Lossless public confirmation result with both draft and operator views."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    invoice: CatalogueInvoiceSnapshot
    draft: InvoiceDraftProjectionV1
    created: bool
    total_discrepancy: PrintedTotalDiscrepancyProjectionV1 | None = None
    confirmation_id: Annotated[str, Field(min_length=16, max_length=16)] | None = None
    confirmed_provenance: _ProvenanceRows = ()
    establishment: ConfirmedEstablishmentProjectionV1 | None = None
    label_reading_fallback: LabelReadingFallbackProjectionV1 | None = None

    @classmethod
    def from_result(cls, result: InvoiceConfirmationResult) -> Self:
        """Copy the canonical invoice, actual re-run draft and resolution facts."""
        return cls(
            invoice=CatalogueInvoiceSnapshot.from_invoice(result.invoice),
            draft=InvoiceDraftProjectionV1.from_draft(result.draft),
            created=result.created,
            total_discrepancy=(
                None
                if result.total_discrepancy is None
                else PrintedTotalDiscrepancyProjectionV1.from_discrepancy(result.total_discrepancy)
            ),
            confirmation_id=result.confirmation_id,
            confirmed_provenance=tuple(
                FieldProvenanceProjectionV1.from_provenance(row) for row in result.confirmed_provenance
            ),
            establishment=(
                None
                if result.establishment is None
                else ConfirmedEstablishmentProjectionV1.from_establishment(result.establishment)
            ),
            label_reading_fallback=(
                None
                if (fallback := result.draft.label_reading_fallback) is None
                else LabelReadingFallbackProjectionV1.from_fallback(fallback)
            ),
        )


__all__ = [
    "ClassificationAssemblyProjectionV1",
    "ClassificationCriteriaProjectionV1",
    "ConfirmationBlockerProjectionV1",
    "ConfirmedEstablishmentProjectionV1",
    "CounterpartyEstablishmentContradictionProjectionV1",
    "CounterpartyEstablishmentProjectionV1",
    "DeclaredFactsProjectionV1",
    "DraftDiscrepancyProjectionV1",
    "FieldAmbiguityCandidateProjectionV1",
    "FieldProvenanceProjectionV1",
    "InvoiceConfirmationProjectionV1",
    "InvoiceDraftLineProjectionV1",
    "InvoiceDraftProjectionV1",
    "InvoiceDraftRateBreakdownProjectionV1",
    "LabelReadingFallbackProjectionV1",
    "MissingClassifierInputProjectionV1",
    "PrintedTotalDiscrepancyProjectionV1",
    "RegistrationEstablishmentConflictProjectionV1",
    "RegistryFactProjectionV1",
    "StructuredInvoiceClassProjectionV1",
]

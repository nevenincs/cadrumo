"""Inventory ledgers for actividad economica stock valuation.

Defines strict pydantic v2 records for tracking opening stock,
period movements (purchases, COGS, counts), and closing stock per
activity / year, plus the FIFO and weighted-average (PMP / coste
medio) valuation engines required by LIS art. 17.1. LIFO is rejected
explicitly via :class:`LIFOForbiddenError`.

Public functions:
    :func:`parse_valuation_method` — coerce user input into a
    :class:`ValuationMethod`, refusing LIFO.
    :func:`compute_inventory_valuation` — value closing stock and
    COGS for one ledger.
    :func:`compute_inventory_anexo_d_projection` — project complete 2025
    acquisition cost and stock variation to ``0181``, ``0177``, and ``0182``.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import fields as dataclass_fields
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, ValidationInfo, field_validator, model_validator

from ....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN_CONFIG
from ....core import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ....core.errors import CadrumoError as _CadrumoError
from ....core.errors import CoreValidationError as _CoreValidationError
from ....core.external_constants import DEFAULT_IVA_GENERAL_RATE_PCT as _DEFAULT_IVA_GENERAL_RATE_PCT
from ....core.filing_year import FilingYear
from ....core.hashing import content_hash_hex as _content_hash_hex
from ....core.identity import ContentDigest
from ....core.money import round_to_cents as _quantize
from ....core.percentage import Percentage
from ....core.unit_proportion import UnitProportion
from ...filing_evidence import FilingEvidenceReference
from ...identifiers import canonical_decimal_string as _canonical_decimal_string


class AmortizacionLedgerError(_CadrumoError):
    """Raised when an amortizacion ledger operation is invalid."""


class InventoryLedgerError(_CadrumoError):
    """Raised when an inventory ledger operation is invalid."""


class InventoryValidationError(InventoryLedgerError, _CoreValidationError):
    """Raised when an inventory ledger fails Pydantic validation.

    Inherits from CoreValidationError (which itself inherits from CoreError
    and ValueError) to participate in the shared CoreValidationError catch
    surface and remain compatible with pydantic validators.
    """


class LIFOForbiddenError(InventoryLedgerError):
    """Raised when a caller attempts LIFO inventory valuation.

    LIS art. 17.1 does not admit LIFO for tax-purpose stock valuation
    in this regime; the message routes the operator to FIFO, PMP, or
    coste medio.
    """

    def __init__(self, method: str = "lifo") -> None:
        """Construct a refusal citing the LIS art. 17 valuation boundary.

        Args:
            method: User-supplied valuation method.
        """
        super().__init__(
            "LIFO valuation is not admitted for this tax ledger; use FIFO, PMP, or coste_medio per LIS art. 17.1.",
            context={"method": method, "legal_basis": "LIS art. 17.1"},
        )


class BasisCapExceededError(AmortizacionLedgerError):
    """Raised when cumulative amortization would exceed cost basis."""


INVENTORY_SCHEMA_VERSION = "3"
"""Forward-compatible schema version stamped onto every record in this module."""

_ZERO = Decimal("0.00")
_ONE = Decimal("1")
_HUNDRED = Decimal("100")


class MovementKind(StrEnum):
    """Supported inventory movement kinds.

    Attributes:
        OPENING: Stock present at the start of the period.
        PURCHASE: Inbound inventory acquisition.
        COGS: Cost-of-goods-sold consumption.
        COUNT: Adjustment to the physical count, modelled as a
            synthetic COGS movement against the discrepancy.
    """

    OPENING = "opening"
    PURCHASE = "purchase"
    COGS = "cogs"
    COUNT = "count"


class InventoryAcquisitionEvidenceKind(StrEnum):
    """Closed evidence authorities admitted for inventory acquisition facts."""

    PURCHASE_INVOICE = "purchase_invoice"
    TRANSPORT_DOCUMENT = "transport_document"
    INSURANCE_DOCUMENT = "insurance_document"
    CUSTOMS_DECLARATION = "customs_declaration"
    CONTRACT = "contract"
    OTHER_ACQUISITION_EVIDENCE = "other_acquisition_evidence"
    ATTRIBUTABLE_COST_REVIEW = "attributable_cost_review"
    IVA_RECOVERABILITY_REVIEW = "iva_recoverability_review"


class InventoryAttributableCostKind(StrEnum):
    """Closed directly-attributable cost vocabulary for inventory purchases."""

    FREIGHT = "freight"
    INSURANCE = "insurance"
    CUSTOMS_DUTY = "customs_duty"
    HANDLING = "handling"
    PROFESSIONAL_FEE = "professional_fee"
    OTHER_DIRECTLY_ATTRIBUTABLE = "other_directly_attributable"


def _require_cents(value: Decimal, *, field_name: str) -> Decimal:
    if value != _quantize(value):
        raise InventoryValidationError(f"{field_name} must be quantised to cents")
    return value


class InventoryAcquisitionEvidence(BaseModel):
    """Nominal evidence reference plus its immutable content digest."""

    model_config = _STRICT_FROZEN_CONFIG

    reference: FilingEvidenceReference
    evidence_kind: InventoryAcquisitionEvidenceKind
    content_digest: ContentDigest


class InventoryAttributableCostComponent(BaseModel):
    """One evidenced cost directly attributable to an inventory purchase."""

    model_config = _STRICT_FROZEN_CONFIG

    component_id: str = Field(min_length=1, max_length=128)
    kind: InventoryAttributableCostKind
    taxable_base: Decimal = Field(gt=_ZERO)
    iva_amount: Decimal = Field(ge=_ZERO)
    deductible_iva_ratio: Decimal = Field(ge=_ZERO, le=_ONE)
    evidence_references: tuple[FilingEvidenceReference, ...] = Field(min_length=1)

    @field_validator("component_id")
    @classmethod
    def _trim_component_id(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise InventoryValidationError("component_id must not be blank")
        return trimmed

    @field_validator("taxable_base", "iva_amount")
    @classmethod
    def _monetary_fields_are_cents(cls, value: Decimal, info: ValidationInfo) -> Decimal:
        return _require_cents(value, field_name=info.field_name or "amount")

    @field_validator("evidence_references")
    @classmethod
    def _evidence_references_are_distinct(
        cls,
        value: tuple[FilingEvidenceReference, ...],
    ) -> tuple[FilingEvidenceReference, ...]:
        identities = tuple(item.reference for item in value)
        if len(set(identities)) != len(identities):
            raise InventoryValidationError("component evidence references must be unique")
        return value

    @property
    def recoverable_iva(self) -> Decimal:
        """Return IVA excluded from inventory acquisition cost."""
        return _quantize(self.iva_amount * self.deductible_iva_ratio)

    @property
    def nonrecoverable_iva(self) -> Decimal:
        """Return IVA capitalized without independent rounding drift."""
        return self.iva_amount - self.recoverable_iva


class InventoryAcquisitionCompleteness(BaseModel):
    """Evidence-backed attestations that all three cost reviews occurred."""

    model_config = _STRICT_FROZEN_CONFIG

    consideration_evidence: FilingEvidenceReference
    attributable_cost_review_evidence: FilingEvidenceReference
    iva_recoverability_review_evidence: FilingEvidenceReference


class InventoryAcquisitionCost(BaseModel):
    """Complete, evidenced acquisition-cost decomposition for one purchase."""

    model_config = _STRICT_FROZEN_CONFIG

    consideration_excluding_iva: Decimal = Field(ge=_ZERO)
    consideration_iva_amount: Decimal = Field(ge=_ZERO)
    consideration_deductible_iva_ratio: Decimal = Field(ge=_ZERO, le=_ONE)
    attributable_cost_components: tuple[InventoryAttributableCostComponent, ...]
    evidence: tuple[InventoryAcquisitionEvidence, ...] = Field(min_length=1)
    completeness: InventoryAcquisitionCompleteness
    directly_attributable_cost_total: Decimal = Field(ge=_ZERO)
    nonrecoverable_iva_included: Decimal = Field(ge=_ZERO)
    recoverable_iva_excluded: Decimal = Field(ge=_ZERO)
    total_acquisition_cost: Decimal = Field(ge=_ZERO)

    @field_validator(
        "consideration_excluding_iva",
        "consideration_iva_amount",
        "directly_attributable_cost_total",
        "nonrecoverable_iva_included",
        "recoverable_iva_excluded",
        "total_acquisition_cost",
    )
    @classmethod
    def _monetary_fields_are_cents(cls, value: Decimal, info: ValidationInfo) -> Decimal:
        return _require_cents(value, field_name=info.field_name or "amount")

    @model_validator(mode="after")
    def _validate_complete_decomposition(self) -> InventoryAcquisitionCost:
        evidence_ids = tuple(item.reference.reference for item in self.evidence)
        if len(set(evidence_ids)) != len(evidence_ids):
            raise InventoryValidationError("inventory acquisition evidence references must be unique")
        component_ids = tuple(item.component_id for item in self.attributable_cost_components)
        if len(set(component_ids)) != len(component_ids):
            raise InventoryValidationError("inventory acquisition component identities must be unique")
        declared_refs = {
            self.completeness.consideration_evidence.reference,
            self.completeness.attributable_cost_review_evidence.reference,
            self.completeness.iva_recoverability_review_evidence.reference,
            *(
                reference.reference
                for component in self.attributable_cost_components
                for reference in component.evidence_references
            ),
        }
        missing = sorted(declared_refs - set(evidence_ids))
        if missing:
            raise InventoryValidationError(f"inventory acquisition evidence references are unresolved: {missing!r}")
        evidence_by_reference = {item.reference.reference: item.evidence_kind for item in self.evidence}
        if (
            evidence_by_reference[self.completeness.attributable_cost_review_evidence.reference]
            is not InventoryAcquisitionEvidenceKind.ATTRIBUTABLE_COST_REVIEW
        ):
            raise InventoryValidationError("attributable-cost completeness requires attributable-cost review evidence")
        if (
            evidence_by_reference[self.completeness.iva_recoverability_review_evidence.reference]
            is not InventoryAcquisitionEvidenceKind.IVA_RECOVERABILITY_REVIEW
        ):
            raise InventoryValidationError("IVA completeness requires IVA-recoverability review evidence")
        consideration_kind = evidence_by_reference[self.completeness.consideration_evidence.reference]
        if consideration_kind in {
            InventoryAcquisitionEvidenceKind.ATTRIBUTABLE_COST_REVIEW,
            InventoryAcquisitionEvidenceKind.IVA_RECOVERABILITY_REVIEW,
        }:
            raise InventoryValidationError("purchase consideration requires acquisition evidence, not review evidence")

        attributable = sum((item.taxable_base for item in self.attributable_cost_components), _ZERO)
        recoverable = _quantize(
            self.consideration_iva_amount * self.consideration_deductible_iva_ratio,
        ) + sum((item.recoverable_iva for item in self.attributable_cost_components), _ZERO)
        total_iva = self.consideration_iva_amount + sum(
            (item.iva_amount for item in self.attributable_cost_components),
            _ZERO,
        )
        nonrecoverable = total_iva - recoverable
        total = self.consideration_excluding_iva + attributable + nonrecoverable
        expected = {
            "directly_attributable_cost_total": _quantize(attributable),
            "recoverable_iva_excluded": _quantize(recoverable),
            "nonrecoverable_iva_included": _quantize(nonrecoverable),
            "total_acquisition_cost": _quantize(total),
        }
        for field_name, expected_value in expected.items():
            if getattr(self, field_name) != expected_value:
                raise InventoryValidationError(f"{field_name} does not match the acquisition decomposition")
        return self


class ValuationMethod(StrEnum):
    """Supported inventory valuation methods."""

    FIFO = "fifo"
    PMP = "pmp"
    COSTE_MEDIO = "coste_medio"


class InventoryClosingValuationBasis(StrEnum):
    """Grounded acquisition-price basis used by a physical year-end count."""

    FIFO_ACQUISITION_PRICE = "fifo_acquisition_price"
    PMP_ACQUISITION_PRICE = "pmp_acquisition_price"
    COSTE_MEDIO_ACQUISITION_PRICE = "coste_medio_acquisition_price"


class PhysicalClosingEvidenceRole(StrEnum):
    """Closed evidence roles required to ground a physical closing."""

    PHYSICAL_COUNT = "physical_count"
    ACQUISITION_PRICE_VALUATION = "acquisition_price_valuation"


class PhysicalClosingEvidence(BaseModel):
    """Digest-bound opaque evidence supporting a physical closing."""

    model_config = _STRICT_FROZEN_CONFIG

    reference: FilingEvidenceReference
    role: PhysicalClosingEvidenceRole
    content_digest: ContentDigest


class InventoryClosingAuthority(StrEnum):
    """Closed authority choices for inventory closing valuation."""

    MOVEMENT_DERIVED = "movement_derived"
    PHYSICAL_OBSERVATION = "physical_observation"


class InventoryClosingDecisionEvidenceRole(StrEnum):
    """Closed evidence role grounding an authority reconciliation decision."""

    AUTHORITY_RECONCILIATION = "authority_reconciliation"


class InventoryClosingDecisionEvidence(BaseModel):
    """Digest-bound reconciliation evidence used by one authority decision."""

    model_config = _STRICT_FROZEN_CONFIG

    reference: FilingEvidenceReference
    role: InventoryClosingDecisionEvidenceRole
    content_digest: ContentDigest


class PriorClosingContinuityEvidence(BaseModel):
    """Digest-bound evidence of the immediately prior authoritative closing."""

    model_config = _STRICT_FROZEN_CONFIG

    reference: FilingEvidenceReference
    content_digest: ContentDigest


def fingerprint_prior_authoritative_closing(
    *,
    actividad_id: str,
    filing_year: int,
    authoritative_closing_value: Decimal,
    authoritative_source_fingerprint: ContentDigest,
    evidence: tuple[PriorClosingContinuityEvidence, ...],
) -> ContentDigest:
    """Derive immutable identity for one prior authoritative closing fact."""
    return _content_hash_hex(
        {
            "fingerprint_schema_version": "1",
            "actividad_id": actividad_id,
            "filing_year": filing_year,
            "authoritative_closing_value": _canonical_decimal_string(authoritative_closing_value),
            "authoritative_source_fingerprint": authoritative_source_fingerprint,
            "evidence": [
                {
                    "reference": item.reference.reference,
                    "content_digest": item.content_digest,
                }
                for item in sorted(evidence, key=lambda item: item.reference.reference)
            ],
        },
    )


class PhysicalClosingObservation(BaseModel):
    """Immutable evidenced physical closing valuation for one activity and year."""

    model_config = _STRICT_FROZEN_CONFIG

    observation_id: str = Field(min_length=1, max_length=128)
    observed_on: date
    as_of_date: date
    actividad_id: str = Field(min_length=1)
    filing_year: FilingYear
    closing_value: Decimal = Field(ge=_ZERO)
    valuation_basis: InventoryClosingValuationBasis
    evidence: tuple[PhysicalClosingEvidence, ...] = Field(min_length=2)

    @field_validator("closing_value")
    @classmethod
    def _closing_value_is_cents(cls, value: Decimal) -> Decimal:
        return _require_cents(value, field_name="physical closing_value")

    @field_validator("evidence")
    @classmethod
    def _evidence_is_unique(
        cls,
        value: tuple[PhysicalClosingEvidence, ...],
    ) -> tuple[PhysicalClosingEvidence, ...]:
        identities = tuple(item.reference.reference for item in value)
        if len(set(identities)) != len(identities):
            raise InventoryValidationError("physical closing evidence references must be unique")
        roles = {item.role for item in value}
        required = {
            PhysicalClosingEvidenceRole.PHYSICAL_COUNT,
            PhysicalClosingEvidenceRole.ACQUISITION_PRICE_VALUATION,
        }
        if not required.issubset(roles):
            raise InventoryValidationError("physical closing requires count and acquisition-price valuation evidence")
        if len(roles) != len(value):
            raise InventoryValidationError("physical closing evidence roles must be unique")
        return value

    @model_validator(mode="after")
    def _observation_dates_match_year_end(self) -> PhysicalClosingObservation:
        expected_as_of = date(self.filing_year, 12, 31)
        if self.as_of_date != expected_as_of:
            raise InventoryValidationError("physical closing as_of_date must be filing-year end")
        if self.observed_on < self.as_of_date:
            raise InventoryValidationError("physical closing cannot be observed before its as-of date")
        return self

    @property
    def fingerprint(self) -> ContentDigest:
        """Return canonical economic/evidence identity for the observation."""
        return _content_hash_hex(
            {
                "fingerprint_schema_version": "1",
                "observation_id": self.observation_id,
                "observed_on": self.observed_on.isoformat(),
                "as_of_date": self.as_of_date.isoformat(),
                "actividad_id": self.actividad_id,
                "filing_year": self.filing_year,
                "closing_value": _canonical_decimal_string(self.closing_value),
                "valuation_basis": self.valuation_basis.value,
                "evidence": [
                    {
                        "reference": item.reference.reference,
                        "role": item.role.value,
                        "content_digest": item.content_digest,
                    }
                    for item in sorted(self.evidence, key=lambda evidence: evidence.reference.reference)
                ],
            },
        )


class InventoryClosingAuthorityDecision(BaseModel):
    """Explicit evidenced choice between movement and physical closing authority."""

    model_config = _STRICT_FROZEN_CONFIG

    decision_id: str = Field(min_length=1, max_length=128)
    actividad_id: str = Field(min_length=1)
    filing_year: FilingYear
    authority: InventoryClosingAuthority
    physical_observation_id: str | None = Field(default=None, min_length=1, max_length=128)
    physical_observation_fingerprint: ContentDigest | None = None
    reason: str = Field(min_length=1, max_length=512)
    actor: str = Field(min_length=1, max_length=64)
    source_command: str = Field(min_length=1, max_length=128)
    decided_at: datetime
    evidence: tuple[InventoryClosingDecisionEvidence, ...] = Field(min_length=1)

    @field_validator("evidence")
    @classmethod
    def _evidence_is_unique(
        cls,
        value: tuple[InventoryClosingDecisionEvidence, ...],
    ) -> tuple[InventoryClosingDecisionEvidence, ...]:
        identities = tuple(item.reference.reference for item in value)
        if len(set(identities)) != len(identities):
            raise InventoryValidationError("closing authority decision evidence references must be unique")
        return value

    @field_validator("decided_at")
    @classmethod
    def _decided_at_is_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise InventoryValidationError("closing authority decided_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def _authority_identity_is_closed(self) -> InventoryClosingAuthorityDecision:
        if self.authority is InventoryClosingAuthority.PHYSICAL_OBSERVATION:
            if self.physical_observation_id is None or self.physical_observation_fingerprint is None:
                raise InventoryValidationError(
                    "physical closing authority requires observation identity and fingerprint",
                )
        elif (self.physical_observation_id is None) != (self.physical_observation_fingerprint is None):
            raise InventoryValidationError(
                "competing physical observation identity and fingerprint must travel together",
            )
        return self

    @property
    def fingerprint(self) -> ContentDigest:
        """Return canonical tamper-sensitive decision identity."""
        return _content_hash_hex(
            {
                "fingerprint_schema_version": "1",
                "decision_id": self.decision_id,
                "actividad_id": self.actividad_id,
                "filing_year": self.filing_year,
                "authority": self.authority.value,
                "physical_observation_id": self.physical_observation_id,
                "physical_observation_fingerprint": self.physical_observation_fingerprint,
                "reason": self.reason,
                "actor": self.actor,
                "source_command": self.source_command,
                "decided_at": self.decided_at.isoformat(),
                "evidence": [
                    {
                        "reference": item.reference.reference,
                        "role": item.role.value,
                        "content_digest": item.content_digest,
                    }
                    for item in sorted(self.evidence, key=lambda evidence: evidence.reference.reference)
                ],
            },
        )


class PriorAuthoritativeClosingLink(BaseModel):
    """Continuity link from the immediately prior authoritative closing."""

    model_config = _STRICT_FROZEN_CONFIG

    actividad_id: str = Field(min_length=1)
    current_filing_year: int = Field(ge=1901)
    prior_filing_year: FilingYear
    prior_authoritative_closing_value: Decimal = Field(ge=_ZERO)
    current_opening_value: Decimal = Field(ge=_ZERO)
    prior_authoritative_source_fingerprint: ContentDigest
    prior_authoritative_closing_fingerprint: ContentDigest
    evidence: tuple[PriorClosingContinuityEvidence, ...] = Field(min_length=1)

    @field_validator("prior_authoritative_closing_value", "current_opening_value")
    @classmethod
    def _values_are_cents(cls, value: Decimal, info: ValidationInfo) -> Decimal:
        return _require_cents(value, field_name=info.field_name or "continuity value")

    @field_validator("evidence")
    @classmethod
    def _evidence_is_unique(
        cls,
        value: tuple[PriorClosingContinuityEvidence, ...],
    ) -> tuple[PriorClosingContinuityEvidence, ...]:
        identities = tuple(item.reference.reference for item in value)
        if len(set(identities)) != len(identities):
            raise InventoryValidationError("prior closing continuity evidence references must be unique")
        return value

    @model_validator(mode="after")
    def _continuity_is_immediate_and_value_equal(self) -> PriorAuthoritativeClosingLink:
        if self.prior_filing_year != self.current_filing_year - 1:
            raise InventoryValidationError("prior authoritative closing must be the immediate prior filing year")
        if self.prior_authoritative_closing_value != self.current_opening_value:
            raise InventoryValidationError("prior authoritative closing must equal current opening value")
        if self.prior_authoritative_closing_fingerprint != self.expected_prior_closing_fingerprint:
            raise InventoryValidationError("prior authoritative closing fingerprint does not bind the claimed source")
        return self

    @property
    def expected_prior_closing_fingerprint(self) -> ContentDigest:
        """Derive the fingerprint binding the claimed prior authoritative closing."""
        return fingerprint_prior_authoritative_closing(
            actividad_id=self.actividad_id,
            filing_year=self.prior_filing_year,
            authoritative_closing_value=self.prior_authoritative_closing_value,
            authoritative_source_fingerprint=self.prior_authoritative_source_fingerprint,
            evidence=self.evidence,
        )

    @property
    def fingerprint(self) -> ContentDigest:
        """Return current-link identity including the opening-side coordinate."""
        return _content_hash_hex(
            {
                "fingerprint_schema_version": "1",
                "prior_authoritative_closing_fingerprint": self.prior_authoritative_closing_fingerprint,
                "current_filing_year": self.current_filing_year,
                "current_opening_value": _canonical_decimal_string(self.current_opening_value),
            },
        )


class InventoryClosingConflictDiagnostic(BaseModel):
    """Retained conflict between movement-derived and physical closing values."""

    model_config = _STRICT_FROZEN_CONFIG

    actividad_id: str = Field(min_length=1)
    filing_year: FilingYear
    movement_derived_value: Decimal = Field(ge=_ZERO)
    physical_observed_value: Decimal = Field(ge=_ZERO)
    physical_observation_fingerprint: ContentDigest

    @field_validator("movement_derived_value", "physical_observed_value")
    @classmethod
    def _values_are_cents(cls, value: Decimal, info: ValidationInfo) -> Decimal:
        return _require_cents(value, field_name=info.field_name or "closing conflict value")


class InventoryClosingResolution(BaseModel):
    """Auditable authoritative closing resolution with retained conflict."""

    model_config = _STRICT_FROZEN_CONFIG

    actividad_id: str = Field(min_length=1)
    filing_year: FilingYear
    authority: InventoryClosingAuthority
    authoritative_value: Decimal = Field(ge=_ZERO)
    movement_derived_value: Decimal = Field(ge=_ZERO)
    physical_observed_value: Decimal | None = Field(default=None, ge=_ZERO)
    physical_observation_fingerprint: ContentDigest | None = None
    decision_id: str = Field(min_length=1, max_length=128)
    decision_fingerprint: ContentDigest
    physical_observation_id: str | None = Field(default=None, min_length=1, max_length=128)
    prior_closing_link_fingerprint: ContentDigest
    conflict: InventoryClosingConflictDiagnostic | None = None

    @field_validator("authoritative_value", "movement_derived_value", "physical_observed_value")
    @classmethod
    def _values_are_cents(cls, value: Decimal | None, info: ValidationInfo) -> Decimal | None:
        if value is None:
            return None
        return _require_cents(value, field_name=info.field_name or "closing resolution value")

    @model_validator(mode="after")
    def _conflict_is_retained(self) -> InventoryClosingResolution:
        has_physical = self.physical_observed_value is not None and self.physical_observation_fingerprint is not None
        if (self.physical_observed_value is None) != (self.physical_observation_fingerprint is None):
            raise InventoryValidationError("physical observed value and fingerprint must travel together")
        if has_physical != (self.physical_observation_id is not None):
            raise InventoryValidationError("physical observation identity must travel with physical resolution state")
        if self.authority is InventoryClosingAuthority.PHYSICAL_OBSERVATION:
            if not has_physical or self.authoritative_value != self.physical_observed_value:
                raise InventoryValidationError("physical authority value must equal the physical observation")
        elif self.authoritative_value != self.movement_derived_value:
            raise InventoryValidationError("movement-derived authority value must equal movement-derived closing")
        differs = has_physical and self.physical_observed_value != self.movement_derived_value
        if differs != (self.conflict is not None):
            raise InventoryValidationError("physical closing conflict diagnostic must exactly match value conflict")
        if self.conflict is not None and (
            self.conflict.actividad_id != self.actividad_id
            or self.conflict.filing_year != self.filing_year
            or self.conflict.movement_derived_value != self.movement_derived_value
            or self.conflict.physical_observed_value != self.physical_observed_value
            or self.conflict.physical_observation_fingerprint != self.physical_observation_fingerprint
        ):
            raise InventoryValidationError("physical closing conflict diagnostic does not match resolution state")
        return self


class InventoryClosingAuthorityRecord(BaseModel):
    """Ledger-owned immutable inputs for one closing-authority resolution."""

    model_config = _STRICT_FROZEN_CONFIG

    decision: InventoryClosingAuthorityDecision
    physical_observation: PhysicalClosingObservation | None = None
    prior_closing_link: PriorAuthoritativeClosingLink

    @model_validator(mode="after")
    def _coordinates_match(self) -> InventoryClosingAuthorityRecord:
        coordinate = (self.decision.actividad_id, self.decision.filing_year)
        if coordinate != (
            self.prior_closing_link.actividad_id,
            self.prior_closing_link.current_filing_year,
        ):
            raise InventoryValidationError("closing authority record inputs must share one activity/year coordinate")
        if self.physical_observation is not None and coordinate != (
            self.physical_observation.actividad_id,
            self.physical_observation.filing_year,
        ):
            raise InventoryValidationError("closing authority record observation must share the decision coordinate")
        return self

    @property
    def fingerprint(self) -> ContentDigest:
        """Return canonical identity for the complete persisted authority input set."""
        return _content_hash_hex(
            {
                "fingerprint_schema_version": "1",
                "decision_fingerprint": self.decision.fingerprint,
                "physical_observation_fingerprint": (
                    self.physical_observation.fingerprint if self.physical_observation is not None else None
                ),
                "prior_closing_link_fingerprint": self.prior_closing_link.fingerprint,
            },
        )


class MovementRecord(BaseModel):
    """One inventory movement for an activity/year.

    Attributes:
        movement_id: Stable natural key for the movement.
        movement_date: Date the movement applies on.
        kind: :class:`MovementKind`.
        sku: SKU / item identifier; defaults to ``"default"`` for
            single-SKU ledgers.
        quantity: Movement quantity (strictly positive).
        unit_cost: IVA-exclusive per-unit cost.
        taxable_base: Invoice taxable base (IVA-exclusive).
        iva_rate: IVA rate percentage (0-100).
        iva_amount: Optional explicit IVA amount; when set must equal
            ``taxable_base * iva_rate / 100``.
        deductible_iva_ratio: Fraction of input IVA the contribuyente
            may deduct (0-1).
        schema_version: Forward-compatible schema version. ``"3"``.
    """

    model_config = _STRICT_FROZEN_CONFIG

    movement_id: str = Field(min_length=1)
    movement_date: date
    kind: MovementKind = MovementKind.PURCHASE
    sku: str = Field(default="default", min_length=1)
    quantity: Decimal = Field(gt=Decimal("0"))
    unit_cost: Decimal | None = Field(default=None, ge=Decimal("0"))
    taxable_base: Decimal | None = Field(default=None, ge=Decimal("0"))
    iva_rate: Percentage = _DEFAULT_IVA_GENERAL_RATE_PCT
    iva_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    deductible_iva_ratio: UnitProportion = Decimal("1.00")
    acquisition_cost: InventoryAcquisitionCost | None = None
    schema_version: str = INVENTORY_SCHEMA_VERSION

    @classmethod
    def from_purchase_acquisition(
        cls,
        *,
        movement_id: str,
        movement_date: date,
        quantity: Decimal,
        acquisition_cost: InventoryAcquisitionCost,
        sku: str = "default",
    ) -> MovementRecord:
        """Project one complete acquisition into its canonical purchase movement."""
        consideration = acquisition_cost.consideration_excluding_iva
        iva_amount = acquisition_cost.consideration_iva_amount
        iva_rate = _ZERO if consideration == _ZERO else iva_amount * _HUNDRED / consideration
        return cls(
            movement_id=movement_id,
            movement_date=movement_date,
            kind=MovementKind.PURCHASE,
            sku=sku,
            quantity=quantity,
            taxable_base=consideration,
            iva_rate=iva_rate,
            iva_amount=iva_amount,
            deductible_iva_ratio=acquisition_cost.consideration_deductible_iva_ratio,
            acquisition_cost=acquisition_cost,
        )

    @property
    def value(self) -> Decimal:
        """Return the IVA-exclusive movement value."""
        if self.taxable_base is not None:
            return self.taxable_base
        if self.unit_cost is None:
            return _ZERO
        return self.quantity * self.unit_cost

    @property
    def capitalized_value(self) -> Decimal:
        """Return the sole value capitalized by inventory valuation."""
        if self.kind is MovementKind.PURCHASE:
            assert self.acquisition_cost is not None
            return self.acquisition_cost.total_acquisition_cost
        return self.value

    @property
    def resolved_unit_cost(self) -> Decimal:
        """Return capitalized unit cost, falling back to consideration for openings."""
        if self.kind is MovementKind.PURCHASE:
            return self.capitalized_value / self.quantity
        if self.unit_cost is not None:
            return self.unit_cost
        if self.taxable_base is None:
            return _ZERO
        return self.taxable_base / self.quantity

    @field_validator("schema_version")
    @classmethod
    def _schema_version_supported(cls, value: str) -> str:
        """Reject any schema_version other than the current :data:`INVENTORY_SCHEMA_VERSION`."""
        if value != INVENTORY_SCHEMA_VERSION:
            raise InventoryValidationError(f"unsupported MovementRecord schema_version {value!r}")
        return value

    @model_validator(mode="after")
    def _validate_movement_amounts(self) -> MovementRecord:
        """Enforce that opening / purchase movements carry a cost and IVA decomposes consistently."""
        needs_cost = self.kind in {MovementKind.OPENING, MovementKind.PURCHASE}
        if needs_cost and self.unit_cost is None and self.taxable_base is None:
            raise InventoryValidationError("opening and purchase movements require unit_cost or taxable_base")
        if self.taxable_base is not None:
            computed_iva = _quantize(self.taxable_base * self.iva_rate / _HUNDRED)
            if self.iva_amount is not None and self.iva_amount != computed_iva:
                raise InventoryValidationError("iva_amount must equal taxable_base * iva_rate")
        if (
            self.unit_cost is not None
            and self.taxable_base is not None
            and _quantize(self.quantity * self.unit_cost) != self.taxable_base
        ):
            raise InventoryValidationError("taxable_base must equal quantity * unit_cost")
        if self.kind is MovementKind.PURCHASE:
            if self.acquisition_cost is None:
                raise InventoryValidationError("purchase movements require complete acquisition_cost")
            if self.acquisition_cost.consideration_excluding_iva != _quantize(self.value):
                raise InventoryValidationError("acquisition consideration must equal the purchase consideration")
            expected_iva = self.iva_amount
            if expected_iva is None:
                expected_iva = _quantize(self.value * self.iva_rate / _HUNDRED)
            if self.acquisition_cost.consideration_iva_amount != expected_iva:
                raise InventoryValidationError("acquisition consideration IVA must equal the purchase IVA")
            if self.acquisition_cost.consideration_deductible_iva_ratio != self.deductible_iva_ratio:
                raise InventoryValidationError("acquisition IVA recoverability must equal the purchase ratio")
        elif self.acquisition_cost is not None:
            raise InventoryValidationError("acquisition_cost is permitted only for purchase movements")
        return self


class StockLayer(BaseModel):
    """Remaining inventory quantity at one IVA-exclusive unit cost.

    Attributes:
        sku: SKU / item identifier.
        quantity: Layer quantity (strictly positive).
        unit_cost: Per-unit cost the layer was acquired at.
        source_movement_id: Stable id of the originating
            :class:`MovementRecord` (or a synthetic id for opening
            stock and weighted-average pools).
    """

    model_config = _STRICT_FROZEN_CONFIG

    sku: str = Field(default="default", min_length=1)
    quantity: Decimal = Field(gt=Decimal("0"))
    unit_cost: Decimal = Field(ge=Decimal("0"))
    source_movement_id: str = Field(min_length=1)


class InventoryLedger(BaseModel):
    """Per-activity inventory ledger for one tax year.

    Attributes:
        actividad_id: Activity identifier the ledger is keyed by.
        year: Calendar year the ledger covers.
        valuation_method: FIFO, PMP, or coste medio; LIFO is forbidden.
        opening_stock: Aggregate IVA-exclusive opening valuation.
        opening_layers: Per-layer breakdown of opening stock; when
            non-empty must value-balance with ``opening_stock``.
        period_movements: Tuple of :class:`MovementRecord` rows
            covering the period.
        closing_authority_record: Required nullable persisted authority bundle;
            ``None`` states that no operator authority decision is recorded.
        schema_version: Forward-compatible schema version. ``"3"``.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    actividad_id: str = Field(min_length=1)
    year: int = Field(ge=1900)
    valuation_method: ValuationMethod
    opening_stock: Decimal = Field(ge=Decimal("0"))
    opening_layers: tuple[StockLayer, ...] = ()
    period_movements: tuple[MovementRecord, ...] = ()
    closing_authority_record: InventoryClosingAuthorityRecord | None
    schema_version: str = INVENTORY_SCHEMA_VERSION

    @field_validator("actividad_id")
    @classmethod
    def _actividad_id_is_canonical(cls, value: str) -> str:
        if value != value.strip() or any(ord(character) < 32 for character in value):
            raise InventoryValidationError("inventory actividad_id is not canonical")
        return value

    @field_validator("schema_version")
    @classmethod
    def _schema_version_supported(cls, value: str) -> str:
        """Reject any schema_version other than the current :data:`INVENTORY_SCHEMA_VERSION`."""
        if value != INVENTORY_SCHEMA_VERSION:
            raise InventoryValidationError(f"unsupported InventoryLedger schema_version {value!r}")
        return value

    @model_validator(mode="after")
    def _opening_stock_matches_layers(self) -> InventoryLedger:
        """Enforce that ``opening_layers`` value-balances with ``opening_stock``."""
        movement_ids = tuple(movement.movement_id for movement in self.period_movements)
        if len(set(movement_ids)) != len(movement_ids):
            raise InventoryValidationError("inventory ledger movement_id values must be unique")
        if self.opening_layers and _quantize(_layers_value(self.opening_layers)) != _quantize(self.opening_stock):
            raise InventoryValidationError("opening_stock must equal the value of opening_layers")
        if self.closing_authority_record is not None:
            record = self.closing_authority_record
            if (record.decision.actividad_id, record.decision.filing_year) != (self.actividad_id, self.year):
                raise InventoryValidationError("closing authority record must match the inventory ledger coordinate")
            resolve_inventory_authoritative_closing(
                self,
                decision=record.decision,
                physical_observation=record.physical_observation,
                prior_closing_link=record.prior_closing_link,
            )
        return self


class InventoryLedgerDocument(BaseModel):
    """JSON document containing inventory ledgers.

    ``(actividad_id, year)`` is the natural key: creation, movement recording,
    and lookup all assume one canonical ledger per activity per year. The
    uniqueness invariant lives here, on the document, because the repository
    had two competing versions of it -- ``create`` and the application service
    refused a second ledger for a pair, while the public
    ``save``/``save_inventory`` path accepted any document and wrote it without
    validating, so a replacement could persist two ledgers for one pair while
    every reader still assumed one.

    Attributes:
        schema_version: Forward-compatible schema version. ``"3"``.
        ledgers: Tuple of :class:`InventoryLedger` rows, each with a distinct
            ``(actividad_id, year)`` pair.
    """

    model_config = _STRICT_FROZEN_CONFIG

    schema_version: str = INVENTORY_SCHEMA_VERSION
    ledgers: tuple[InventoryLedger, ...] = ()

    @field_validator("schema_version")
    @classmethod
    def _schema_version_supported(cls, value: str) -> str:
        """Reject any schema_version other than the current :data:`INVENTORY_SCHEMA_VERSION`."""
        if value != INVENTORY_SCHEMA_VERSION:
            raise InventoryValidationError(f"unsupported InventoryLedgerDocument schema_version {value!r}")
        return value

    @model_validator(mode="after")
    def _reject_duplicate_actividad_year(self) -> InventoryLedgerDocument:
        """Refuse a document carrying two ledgers for one activity and year.

        Enforced on the document rather than at a write method so creation,
        bulk replacement, and the read boundary answer the same way. Applying
        at the read boundary is deliberate: a stored document that already
        holds a duplicate pair has no canonical ledger for it, and surfacing it
        silently is what the repository used to do.
        """
        keys = [(ledger.actividad_id, ledger.year) for ledger in self.ledgers]
        duplicates = sorted({key for key in keys if keys.count(key) > 1})
        if duplicates:
            rendered = ", ".join(f"{actividad_id}/{year}" for actividad_id, year in duplicates)
            raise InventoryValidationError(
                f"InventoryLedgerDocument carries duplicate actividad/year ledgers: {rendered}",
            )
        return self


def parse_valuation_method(raw: str) -> ValuationMethod:
    """Parse a user-supplied valuation method and refuse LIFO explicitly.

    Args:
        raw: User input (case- and separator-insensitive).

    Returns:
        The matching :class:`ValuationMethod` member.

    Raises:
        LIFOForbiddenError: When the input normalises to ``"lifo"``.
        InventoryLedgerError: When the input matches no known method.
    """
    normalized = raw.strip().lower().replace("-", "_")
    if normalized == "lifo":
        raise LIFOForbiddenError(raw)
    try:
        return ValuationMethod(normalized)
    except ValueError as exc:
        raise InventoryLedgerError(
            f"unknown valuation method {raw!r}; use fifo, pmp, or coste_medio",
            context={"method": raw},
        ) from exc


class InventoryValuationResult(BaseModel):
    """Computed valuation outcome for an inventory ledger.

    Attributes:
        closing_layers: Tuple of :class:`StockLayer` rows surviving
            after period movements were applied.
        closing_value: Aggregate closing valuation.
        cogs_value: Cost-of-goods-sold for the period.
        purchase_value: Aggregate value of PURCHASE movements during
            the period.
    """

    model_config = _STRICT_FROZEN_CONFIG

    closing_layers: tuple[StockLayer, ...]
    closing_value: Decimal
    cogs_value: Decimal
    purchase_value: Decimal


@dataclass(frozen=True, slots=True)
class _InventoryAnexoDDerivation:
    source_ledger: InventoryLedger
    source_ledger_fingerprint: ContentDigest
    actividad_id: str
    filing_year: int
    opening_value: Decimal
    movement_derived_closing_value: Decimal
    authoritative_closing_value: Decimal
    selected_authority: InventoryClosingAuthority
    authority_record_fingerprint: ContentDigest
    decision_id: str
    decision_fingerprint: ContentDigest
    physical_observation_id: str | None
    physical_observation_fingerprint: ContentDigest | None
    physical_observed_closing_value: Decimal | None
    prior_closing_link_fingerprint: ContentDigest
    complete_acquisition_total: Decimal
    acquisition_fingerprints: tuple[ContentDigest, ...]
    casilla_0177: Decimal
    casilla_0181: Decimal
    casilla_0182: Decimal
    closing_conflict: InventoryClosingConflictDiagnostic | None
    issues: tuple[Literal["physical_closing_conflict"], ...]


class InventoryAnexoDResult(BaseModel):
    """Complete source-owned 2025 inventory projection for one activity."""

    model_config = _STRICT_FROZEN_CONFIG

    source_ledger: InventoryLedger = Field(exclude=True, repr=False)
    source_ledger_fingerprint: ContentDigest
    actividad_id: str = Field(min_length=1)
    filing_year: Literal[2025]
    opening_value: Decimal = Field(ge=_ZERO)
    movement_derived_closing_value: Decimal = Field(ge=_ZERO)
    authoritative_closing_value: Decimal = Field(ge=_ZERO)
    selected_authority: InventoryClosingAuthority
    authority_record_fingerprint: ContentDigest
    decision_id: str = Field(min_length=1, max_length=128)
    decision_fingerprint: ContentDigest
    physical_observation_id: str | None = Field(default=None, min_length=1, max_length=128)
    physical_observation_fingerprint: ContentDigest | None = None
    physical_observed_closing_value: Decimal | None = Field(default=None, ge=_ZERO)
    prior_closing_link_fingerprint: ContentDigest
    complete_acquisition_total: Decimal = Field(ge=_ZERO)
    acquisition_fingerprints: tuple[ContentDigest, ...]
    casilla_0177: Decimal = Field(ge=_ZERO)
    casilla_0181: Decimal = Field(ge=_ZERO)
    casilla_0182: Decimal = Field(ge=_ZERO)
    closing_conflict: InventoryClosingConflictDiagnostic | None = None
    issues: tuple[Literal["physical_closing_conflict"], ...] = ()
    projection_fingerprint: ContentDigest

    @property
    def expected_projection_fingerprint(self) -> ContentDigest:
        """Derive the versioned identity of the complete projection envelope."""
        return _content_hash_hex(
            {
                "fingerprint_schema_version": "1",
                "projection": self.model_dump(mode="json", exclude={"projection_fingerprint"}),
            },
        )

    @model_validator(mode="after")
    def _variation_split_matches_audited_values(self) -> InventoryAnexoDResult:
        """Require an exact, mutually exclusive split of the audited basis."""
        monetary_values = (
            self.opening_value,
            self.movement_derived_closing_value,
            self.authoritative_closing_value,
            *(value for value in (self.physical_observed_closing_value,) if value is not None),
            self.complete_acquisition_total,
            self.casilla_0177,
            self.casilla_0181,
            self.casilla_0182,
        )
        if any(value != _quantize(value) for value in monetary_values):
            raise InventoryValidationError("inventory Anexo D values must be quantised to cents")
        signed_variation = _quantize(self.authoritative_closing_value - self.opening_value)
        expected_increase = max(signed_variation, _ZERO)
        expected_decrease = max(-signed_variation, _ZERO)
        if self.casilla_0177 != expected_increase or self.casilla_0182 != expected_decrease:
            raise InventoryValidationError(
                "inventory Anexo D outputs must be the mutually exclusive split of closing minus opening",
            )
        if self.casilla_0181 != self.complete_acquisition_total:
            raise InventoryValidationError("casilla 0181 must equal complete inventory acquisition cost")
        if self.complete_acquisition_total > _ZERO and not self.acquisition_fingerprints:
            raise InventoryValidationError("nonzero acquisition cost requires acquisition fingerprints")
        if len(set(self.acquisition_fingerprints)) != len(self.acquisition_fingerprints):
            raise InventoryValidationError("acquisition fingerprints must be unique")
        physical_state = (
            self.physical_observation_id,
            self.physical_observation_fingerprint,
            self.physical_observed_closing_value,
        )
        if any(value is None for value in physical_state) and any(value is not None for value in physical_state):
            raise InventoryValidationError("physical observation identity, fingerprint, and value must travel together")
        has_physical = self.physical_observation_id is not None
        physical_differs = has_physical and self.physical_observed_closing_value != self.movement_derived_closing_value
        if physical_differs != (self.closing_conflict is not None):
            raise InventoryValidationError("divergent physical closing requires its retained conflict diagnostic")
        if self.selected_authority is InventoryClosingAuthority.PHYSICAL_OBSERVATION:
            if not has_physical:
                raise InventoryValidationError("physical projection authority requires physical observation identity")
            if self.closing_conflict is None:
                if self.authoritative_closing_value != self.movement_derived_closing_value:
                    raise InventoryValidationError("physical authority without conflict must equal movement closing")
            elif self.authoritative_closing_value != self.closing_conflict.physical_observed_value:
                raise InventoryValidationError("physical authoritative closing must match retained observation")
        elif self.authoritative_closing_value != self.movement_derived_closing_value:
            raise InventoryValidationError("movement-derived authority must select movement-derived closing")
        if self.closing_conflict is not None:
            conflict = self.closing_conflict
            if not has_physical:
                raise InventoryValidationError("closing conflict requires physical observation identity")
            if (
                conflict.actividad_id != self.actividad_id
                or conflict.filing_year != self.filing_year
                or conflict.movement_derived_value != self.movement_derived_closing_value
                or conflict.physical_observed_value != self.physical_observed_closing_value
                or conflict.physical_observation_fingerprint != self.physical_observation_fingerprint
            ):
                raise InventoryValidationError("closing conflict must exactly match projection provenance")
        expected_issues = ("physical_closing_conflict",) if self.closing_conflict is not None else ()
        if self.issues != expected_issues:
            raise InventoryValidationError("inventory projection issues must exactly reflect retained conflicts")
        try:
            expected_source_values = _derive_inventory_anexo_d_values(self.source_ledger)
        except InventoryLedgerError as exc:
            raise InventoryValidationError("inventory projection retained source is invalid") from exc
        for field in dataclass_fields(expected_source_values):
            field_name = field.name
            expected_value = getattr(expected_source_values, field_name)
            if getattr(self, field_name) != expected_value:
                raise InventoryValidationError(
                    f"inventory projection field {field_name!r} does not match retained source authority"
                )
        if self.projection_fingerprint != self.expected_projection_fingerprint:
            raise InventoryValidationError("inventory projection fingerprint does not match projection state")
        return self


def resolve_inventory_authoritative_closing(
    ledger: InventoryLedger,
    *,
    decision: InventoryClosingAuthorityDecision,
    physical_observation: PhysicalClosingObservation | None,
    prior_closing_link: PriorAuthoritativeClosingLink | None,
) -> InventoryClosingResolution:
    """Resolve closing authority while retaining any physical/movement conflict."""
    if decision.actividad_id != ledger.actividad_id or decision.filing_year != ledger.year:
        raise InventoryValidationError("closing authority decision does not match the inventory ledger coordinate")
    derived = compute_inventory_valuation(ledger).closing_value
    if prior_closing_link is None:
        raise InventoryValidationError("closing authority requires complete prior-closing continuity")
    if (
        prior_closing_link.actividad_id != ledger.actividad_id
        or prior_closing_link.current_filing_year != ledger.year
        or prior_closing_link.current_opening_value != _quantize(ledger.opening_stock)
    ):
        raise InventoryValidationError(
            "prior closing continuity does not match the inventory ledger coordinate and opening",
        )

    decision_names_physical = decision.physical_observation_id is not None
    if decision_names_physical != (physical_observation is not None):
        raise InventoryValidationError("closing decision and competing physical observation must travel together")
    if physical_observation is None:
        return InventoryClosingResolution(
            actividad_id=ledger.actividad_id,
            filing_year=ledger.year,
            authority=decision.authority,
            authoritative_value=derived,
            movement_derived_value=derived,
            decision_id=decision.decision_id,
            decision_fingerprint=decision.fingerprint,
            prior_closing_link_fingerprint=prior_closing_link.fingerprint,
        )
    if decision.physical_observation_id != physical_observation.observation_id:
        raise InventoryValidationError("closing authority decision names a different physical observation")
    if decision.physical_observation_fingerprint != physical_observation.fingerprint:
        raise InventoryValidationError("closing authority decision fingerprint does not match physical observation")
    if decision.decided_at.date() < physical_observation.observed_on:
        raise InventoryValidationError("closing authority decision cannot predate the physical observation")
    if physical_observation.actividad_id != ledger.actividad_id or physical_observation.filing_year != ledger.year:
        raise InventoryValidationError("physical closing observation does not match the inventory ledger coordinate")
    expected_basis = {
        ValuationMethod.FIFO: InventoryClosingValuationBasis.FIFO_ACQUISITION_PRICE,
        ValuationMethod.PMP: InventoryClosingValuationBasis.PMP_ACQUISITION_PRICE,
        ValuationMethod.COSTE_MEDIO: InventoryClosingValuationBasis.COSTE_MEDIO_ACQUISITION_PRICE,
    }[ledger.valuation_method]
    if physical_observation.valuation_basis is not expected_basis:
        raise InventoryValidationError("physical closing valuation basis does not match the ledger valuation method")
    observed = physical_observation.closing_value
    conflict = None
    if observed != derived:
        conflict = InventoryClosingConflictDiagnostic(
            actividad_id=ledger.actividad_id,
            filing_year=ledger.year,
            movement_derived_value=derived,
            physical_observed_value=observed,
            physical_observation_fingerprint=physical_observation.fingerprint,
        )
    return InventoryClosingResolution(
        actividad_id=ledger.actividad_id,
        filing_year=ledger.year,
        authority=decision.authority,
        authoritative_value=(
            observed if decision.authority is InventoryClosingAuthority.PHYSICAL_OBSERVATION else derived
        ),
        movement_derived_value=derived,
        physical_observed_value=observed,
        physical_observation_fingerprint=physical_observation.fingerprint,
        decision_id=decision.decision_id,
        decision_fingerprint=decision.fingerprint,
        physical_observation_id=physical_observation.observation_id,
        prior_closing_link_fingerprint=prior_closing_link.fingerprint,
        conflict=conflict,
    )


def _inventory_projection_source_fingerprint(ledger: InventoryLedger) -> ContentDigest:
    """Hash canonical economic identities without exposing retained source facts."""
    return _content_hash_hex(
        {
            "fingerprint_schema_version": "1",
            "actividad_id": ledger.actividad_id,
            "filing_year": ledger.year,
            "valuation_method": ledger.valuation_method.value,
            "opening_stock": _canonical_decimal_string(ledger.opening_stock),
            "opening_layers": [
                {
                    "sku": layer.sku,
                    "quantity": _canonical_decimal_string(layer.quantity),
                    "unit_cost": _canonical_decimal_string(layer.unit_cost),
                    "source_movement_id": layer.source_movement_id,
                }
                for layer in sorted(
                    ledger.opening_layers,
                    key=lambda item: (item.sku, item.source_movement_id, item.quantity, item.unit_cost),
                )
            ],
            "movements": [
                {
                    "movement_id": movement.movement_id,
                    "movement_date": movement.movement_date.isoformat(),
                    "kind": movement.kind.value,
                    "sku": movement.sku,
                    "quantity": _canonical_decimal_string(movement.quantity),
                    "unit_cost": (
                        _canonical_decimal_string(movement.unit_cost) if movement.unit_cost is not None else None
                    ),
                    "taxable_base": (
                        _canonical_decimal_string(movement.taxable_base) if movement.taxable_base is not None else None
                    ),
                    "iva_rate": _canonical_decimal_string(movement.iva_rate),
                    "iva_amount": (
                        _canonical_decimal_string(movement.iva_amount) if movement.iva_amount is not None else None
                    ),
                    "deductible_iva_ratio": _canonical_decimal_string(movement.deductible_iva_ratio),
                    "schema_version": movement.schema_version,
                    "acquisition_fingerprint": (
                        inventory_acquisition_fingerprint(movement) if movement.kind is MovementKind.PURCHASE else None
                    ),
                }
                for movement in _sorted_movements(ledger)
            ],
            "closing_authority_record_fingerprint": (
                ledger.closing_authority_record.fingerprint if ledger.closing_authority_record is not None else None
            ),
        },
    )


def _derive_inventory_anexo_d_values(ledger: InventoryLedger) -> _InventoryAnexoDDerivation:
    """Derive every public projection field from one retained canonical source."""
    if ledger.year != 2025:
        raise InventoryLedgerError(
            "inventory Anexo D projection is grounded only for filing year 2025",
            context={"actividad_id": ledger.actividad_id, "filing_year": ledger.year},
        )
    out_of_period_movements = tuple(
        movement.movement_id for movement in ledger.period_movements if movement.movement_date.year != ledger.year
    )
    if out_of_period_movements:
        raise InventoryLedgerError(
            "inventory Anexo D projection contains movements outside its filing year",
            context={
                "actividad_id": ledger.actividad_id,
                "filing_year": ledger.year,
                "movement_ids": out_of_period_movements,
            },
        )
    try:
        validated = InventoryLedger.model_validate(ledger.model_dump())
    except ValidationError as exc:
        raise InventoryLedgerError("inventory projection source is incomplete or unreadable") from exc
    validated = validated.model_copy(update={"period_movements": _sorted_movements(validated)})
    record = validated.closing_authority_record
    if record is None:
        raise InventoryLedgerError("inventory projection requires a complete closing-authority record")
    resolution = resolve_inventory_authoritative_closing(
        validated,
        decision=record.decision,
        physical_observation=record.physical_observation,
        prior_closing_link=record.prior_closing_link,
    )
    purchases = tuple(movement for movement in _sorted_movements(validated) if movement.kind is MovementKind.PURCHASE)
    if any(movement.acquisition_cost is None for movement in purchases):
        raise InventoryLedgerError("inventory projection requires complete acquisition cost for every purchase")
    acquisition_total = _quantize(
        sum(
            (movement.acquisition_cost.total_acquisition_cost for movement in purchases if movement.acquisition_cost),
            _ZERO,
        ),
    )
    acquisition_fingerprints = tuple(inventory_acquisition_fingerprint(movement) for movement in purchases)
    valuation = compute_inventory_valuation(validated)
    if acquisition_total != valuation.purchase_value:
        raise InventoryLedgerError("complete acquisition totals do not match inventory valuation purchase authority")
    opening = _quantize(ledger.opening_stock)
    signed_variation = _quantize(resolution.authoritative_value - opening)
    return _InventoryAnexoDDerivation(
        source_ledger=validated,
        source_ledger_fingerprint=_inventory_projection_source_fingerprint(validated),
        actividad_id=validated.actividad_id,
        filing_year=2025,
        opening_value=opening,
        movement_derived_closing_value=resolution.movement_derived_value,
        authoritative_closing_value=resolution.authoritative_value,
        selected_authority=resolution.authority,
        authority_record_fingerprint=record.fingerprint,
        decision_id=resolution.decision_id,
        decision_fingerprint=resolution.decision_fingerprint,
        physical_observation_id=resolution.physical_observation_id,
        physical_observation_fingerprint=resolution.physical_observation_fingerprint,
        physical_observed_closing_value=resolution.physical_observed_value,
        prior_closing_link_fingerprint=resolution.prior_closing_link_fingerprint,
        complete_acquisition_total=acquisition_total,
        acquisition_fingerprints=acquisition_fingerprints,
        casilla_0177=max(signed_variation, _ZERO),
        casilla_0181=acquisition_total,
        casilla_0182=max(-signed_variation, _ZERO),
        closing_conflict=resolution.conflict,
        issues=("physical_closing_conflict",) if resolution.conflict is not None else (),
    )


def compute_inventory_anexo_d_projection(
    ledger: InventoryLedger,
) -> InventoryAnexoDResult:
    """Project one complete 2025 activity ledger to inventory casillas."""
    projection_values = _derive_inventory_anexo_d_values(ledger)
    payload = {field.name: getattr(projection_values, field.name) for field in dataclass_fields(projection_values)}
    projection = InventoryAnexoDResult.model_construct(
        None,
        **payload,
        projection_fingerprint="0" * 64,
    )
    return InventoryAnexoDResult(**payload, projection_fingerprint=projection.expected_projection_fingerprint)


def compute_inventory_valuation(ledger: InventoryLedger) -> InventoryValuationResult:
    """Value closing stock and COGS using the ledger's valuation method.

    Dispatches to the FIFO or weighted-average implementation per
    :attr:`InventoryLedger.valuation_method`.

    Args:
        ledger: Ledger to value.

    Returns:
        :class:`InventoryValuationResult` carrying the closing layers,
        closing valuation, COGS, and purchase totals.

    Raises:
        InventoryLedgerError: When ``valuation_method`` is not
            supported (defence-in-depth — should be unreachable as
            LIFO is rejected at parse time).
    """
    if ledger.valuation_method is ValuationMethod.FIFO:
        return _compute_fifo(ledger)
    if ledger.valuation_method in {ValuationMethod.PMP, ValuationMethod.COSTE_MEDIO}:
        return _compute_weighted_average(ledger)
    raise InventoryLedgerError(f"unsupported valuation method {ledger.valuation_method.value}")


def _compute_fifo(ledger: InventoryLedger) -> InventoryValuationResult:
    layers = list(_opening_layers(ledger))
    cogs_value = _ZERO
    purchase_value = _ZERO
    for movement in _sorted_movements(ledger):
        if movement.kind in {MovementKind.OPENING, MovementKind.PURCHASE}:
            unit_cost = movement.resolved_unit_cost
            layers.append(
                StockLayer(
                    sku=movement.sku,
                    quantity=movement.quantity,
                    unit_cost=unit_cost,
                    source_movement_id=movement.movement_id,
                ),
            )
            if movement.kind is MovementKind.PURCHASE:
                purchase_value += movement.quantity * unit_cost
            continue
        if movement.kind is MovementKind.COGS:
            consumed, layers = _consume_fifo(layers, movement)
            cogs_value += consumed
            continue
        if movement.kind is MovementKind.COUNT:
            layers = _apply_count(layers, movement)
    closing = _layers_value(layers)
    return InventoryValuationResult(
        closing_layers=tuple(layers),
        closing_value=_quantize(closing),
        cogs_value=_quantize(cogs_value),
        purchase_value=_quantize(purchase_value),
    )


def _compute_weighted_average(ledger: InventoryLedger) -> InventoryValuationResult:
    pools = _weighted_average_opening_pools(ledger)
    cogs_value = _ZERO
    purchase_value = _ZERO
    for movement in _sorted_movements(ledger):
        purchase_delta, cogs_delta = _apply_weighted_average_movement(ledger, movement, pools)
        purchase_value += purchase_delta
        cogs_value += cogs_delta
    layers = _weighted_average_layers(ledger, pools)
    return InventoryValuationResult(
        closing_layers=layers,
        closing_value=_quantize(sum((quantity_value[1] for quantity_value in pools.values()), _ZERO)),
        cogs_value=_quantize(cogs_value),
        purchase_value=_quantize(purchase_value),
    )


def _weighted_average_opening_pools(ledger: InventoryLedger) -> dict[str, tuple[Decimal, Decimal]]:
    pools: dict[str, tuple[Decimal, Decimal]] = {}
    for layer in _opening_layers(ledger):
        quantity, value = pools.get(layer.sku, (_ZERO, _ZERO))
        pools[layer.sku] = (quantity + layer.quantity, value + layer.quantity * layer.unit_cost)
    return pools


def _apply_weighted_average_movement(
    ledger: InventoryLedger,
    movement: MovementRecord,
    pools: dict[str, tuple[Decimal, Decimal]],
) -> tuple[Decimal, Decimal]:
    quantity, value = pools.get(movement.sku, (_ZERO, _ZERO))
    if movement.kind in {MovementKind.OPENING, MovementKind.PURCHASE}:
        unit_cost = movement.resolved_unit_cost
        movement_value = movement.quantity * unit_cost
        pools[movement.sku] = (quantity + movement.quantity, value + movement_value)
        purchase_delta = movement_value if movement.kind is MovementKind.PURCHASE else _ZERO
        return purchase_delta, _ZERO
    if movement.kind is MovementKind.COGS:
        return _apply_weighted_average_cogs(ledger, movement, quantity, value, pools)
    if movement.kind is MovementKind.COUNT:
        average = _ZERO if quantity == _ZERO else value / quantity
        pools[movement.sku] = (movement.quantity, movement.quantity * average)
    return _ZERO, _ZERO


def _apply_weighted_average_cogs(
    ledger: InventoryLedger,
    movement: MovementRecord,
    quantity: Decimal,
    value: Decimal,
    pools: dict[str, tuple[Decimal, Decimal]],
) -> tuple[Decimal, Decimal]:
    if movement.quantity > quantity:
        raise InventoryLedgerError(
            "inventory movement would consume more stock than available",
            context={
                "actividad_id": ledger.actividad_id,
                "movement_id": movement.movement_id,
                "available_quantity": str(quantity),
                "requested_quantity": str(movement.quantity),
            },
        )
    average = _ZERO if quantity == _ZERO else value / quantity
    consumed = movement.quantity * average
    pools[movement.sku] = (quantity - movement.quantity, value - consumed)
    return _ZERO, consumed


def _weighted_average_layers(
    ledger: InventoryLedger,
    pools: dict[str, tuple[Decimal, Decimal]],
) -> tuple[StockLayer, ...]:
    return tuple(
        StockLayer(
            sku=sku,
            quantity=quantity,
            unit_cost=_ZERO if quantity == _ZERO else value / quantity,
            source_movement_id=f"{ledger.actividad_id}-{ledger.year}-{sku}-weighted-average",
        )
        for sku, (quantity, value) in sorted(pools.items())
        if quantity > _ZERO
    )


def _consume_fifo(layers: list[StockLayer], movement: MovementRecord) -> tuple[Decimal, list[StockLayer]]:
    remaining = movement.quantity
    consumed = _ZERO
    updated: list[StockLayer] = []
    for layer in layers:
        if layer.sku != movement.sku or remaining <= _ZERO:
            updated.append(layer)
            continue
        take = min(layer.quantity, remaining)
        consumed += take * layer.unit_cost
        remaining -= take
        leftover = layer.quantity - take
        if leftover > _ZERO:
            updated.append(layer.model_copy(update={"quantity": leftover}))
    if remaining > _ZERO:
        raise InventoryLedgerError(
            "inventory movement would consume more stock than available",
            context={
                "movement_id": movement.movement_id,
                "sku": movement.sku,
                "missing_quantity": str(remaining),
            },
        )
    return consumed, updated


def _apply_count(layers: list[StockLayer], movement: MovementRecord) -> list[StockLayer]:
    current_quantity = sum((layer.quantity for layer in layers if layer.sku == movement.sku), _ZERO)
    if movement.quantity > current_quantity:
        raise InventoryLedgerError(
            "inventory count cannot increase stock without a purchase movement",
            context={
                "movement_id": movement.movement_id,
                "sku": movement.sku,
                "available_quantity": str(current_quantity),
                "counted_quantity": str(movement.quantity),
            },
        )
    to_remove = current_quantity - movement.quantity
    synthetic_cogs = movement.model_copy(update={"kind": MovementKind.COGS, "quantity": to_remove})
    _, updated = _consume_fifo(layers, synthetic_cogs)
    return updated


def _opening_layers(ledger: InventoryLedger) -> tuple[StockLayer, ...]:
    if ledger.opening_layers:
        return ledger.opening_layers
    if ledger.opening_stock == _ZERO:
        return ()
    return (
        StockLayer(
            sku="default",
            quantity=Decimal("1"),
            unit_cost=ledger.opening_stock,
            source_movement_id=f"{ledger.actividad_id}-{ledger.year}-opening",
        ),
    )


def _sorted_movements(ledger: InventoryLedger) -> tuple[MovementRecord, ...]:
    return tuple(sorted(ledger.period_movements, key=lambda item: (item.movement_date, item.movement_id)))


def _layers_value(layers: tuple[StockLayer, ...] | list[StockLayer]) -> Decimal:
    return sum((layer.quantity * layer.unit_cost for layer in layers), _ZERO)


def inventory_acquisition_fingerprint(movement: MovementRecord) -> ContentDigest:
    """Return a deterministic versioned economic/evidence purchase fingerprint."""
    if movement.kind is not MovementKind.PURCHASE or movement.acquisition_cost is None:
        raise InventoryValidationError("only a complete purchase acquisition can be fingerprinted")
    acquisition = movement.acquisition_cost
    payload = {
        "fingerprint_schema_version": "1",
        "movement_id": movement.movement_id,
        "movement_date": movement.movement_date.isoformat(),
        "kind": movement.kind.value,
        "sku": movement.sku,
        "quantity": _canonical_decimal_string(movement.quantity),
        "consideration_excluding_iva": _canonical_decimal_string(acquisition.consideration_excluding_iva),
        "consideration_iva_amount": _canonical_decimal_string(acquisition.consideration_iva_amount),
        "consideration_deductible_iva_ratio": _canonical_decimal_string(
            acquisition.consideration_deductible_iva_ratio,
        ),
        "components": [
            {
                "component_id": item.component_id,
                "kind": item.kind.value,
                "taxable_base": _canonical_decimal_string(item.taxable_base),
                "iva_amount": _canonical_decimal_string(item.iva_amount),
                "deductible_iva_ratio": _canonical_decimal_string(item.deductible_iva_ratio),
                "evidence_references": sorted(ref.reference for ref in item.evidence_references),
            }
            for item in sorted(acquisition.attributable_cost_components, key=lambda value: value.component_id)
        ],
        "evidence": [
            {
                "reference": item.reference.reference,
                "evidence_kind": item.evidence_kind.value,
                "content_digest": item.content_digest,
            }
            for item in sorted(acquisition.evidence, key=lambda value: value.reference.reference)
        ],
        "completeness": acquisition.completeness.model_dump(mode="json"),
        "totals": {
            "directly_attributable_cost_total": _canonical_decimal_string(
                acquisition.directly_attributable_cost_total,
            ),
            "nonrecoverable_iva_included": _canonical_decimal_string(acquisition.nonrecoverable_iva_included),
            "recoverable_iva_excluded": _canonical_decimal_string(acquisition.recoverable_iva_excluded),
            "total_acquisition_cost": _canonical_decimal_string(acquisition.total_acquisition_cost),
        },
    }
    return _content_hash_hex(payload)


__all__ = [
    "AmortizacionLedgerError",
    "BasisCapExceededError",
    "InventoryAcquisitionCompleteness",
    "InventoryAcquisitionCost",
    "InventoryAcquisitionEvidence",
    "InventoryAcquisitionEvidenceKind",
    "InventoryAnexoDResult",
    "InventoryAttributableCostComponent",
    "InventoryAttributableCostKind",
    "InventoryClosingAuthority",
    "InventoryClosingAuthorityDecision",
    "InventoryClosingAuthorityRecord",
    "InventoryClosingConflictDiagnostic",
    "InventoryClosingDecisionEvidence",
    "InventoryClosingDecisionEvidenceRole",
    "InventoryClosingResolution",
    "InventoryClosingValuationBasis",
    "InventoryLedger",
    "InventoryLedgerError",
    "InventoryValidationError",
    "LIFOForbiddenError",
    "MovementKind",
    "MovementRecord",
    "PhysicalClosingEvidence",
    "PhysicalClosingEvidenceRole",
    "PhysicalClosingObservation",
    "PriorAuthoritativeClosingLink",
    "PriorClosingContinuityEvidence",
    "StockLayer",
    "ValuationMethod",
    "compute_inventory_anexo_d_projection",
    "compute_inventory_valuation",
    "fingerprint_prior_authoritative_closing",
    "inventory_acquisition_fingerprint",
    "parse_valuation_method",
    "resolve_inventory_authoritative_closing",
]

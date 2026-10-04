"""Inventory closing observations, evidence, errors and shared validation kernels."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator

from ....core.decimal.constants import MONEY_ZERO
from ....core.errors.hierarchy import CadrumoError as _CadrumoError
from ....core.errors.hierarchy import CoreValidationError as _CoreValidationError
from ....core.errors.hierarchy import pydantic_validation_boundary
from ....core.filing_year import FilingYear
from ....core.hashing import content_hash_hex as _content_hash_hex
from ....core.identity.digest import ContentDigest
from ....core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN_CONFIG
from ....core.money.rounding import round_to_cents as _quantize
from ...filing_evidence import FilingEvidenceReference
from ...identifiers import canonical_decimal_string as _canonical_decimal_string


class InventoryLedgerError(_CadrumoError):
    """Raised when an inventory ledger operation is invalid."""


class InventoryValidationError(InventoryLedgerError, _CoreValidationError):
    """Raised when an inventory ledger fails Pydantic validation.

    Inherits from CoreValidationError (which itself inherits from CoreError
    and ValueError) to participate in the shared CoreValidationError catch
    surface and remain compatible with pydantic validators.
    """


def require_inventory_cents(value: Decimal, *, field_name: str) -> Decimal:
    """Refuse a monetary value that is not already quantised to cents."""
    if value != _quantize(value):
        raise InventoryValidationError(f"{field_name} must be quantised to cents")
    return value


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
                {"reference": item.reference.reference, "content_digest": item.content_digest}
                for item in sorted(evidence, key=lambda item: item.reference.reference)
            ],
        }
    )


class PhysicalClosingObservation(BaseModel):
    """Immutable evidenced physical closing valuation for one activity and year."""

    model_config = _STRICT_FROZEN_CONFIG
    observation_id: str = Field(min_length=1, max_length=128)
    observed_on: date
    as_of_date: date
    actividad_id: str = Field(min_length=1)
    filing_year: FilingYear
    closing_value: Decimal = Field(ge=MONEY_ZERO)
    valuation_basis: InventoryClosingValuationBasis
    evidence: tuple[PhysicalClosingEvidence, ...] = Field(min_length=2)

    @field_validator("closing_value")
    @classmethod
    @pydantic_validation_boundary
    def _closing_value_is_cents(cls, value: Decimal) -> Decimal:
        return require_inventory_cents(value, field_name="physical closing_value")

    @field_validator("evidence")
    @classmethod
    @pydantic_validation_boundary
    def _evidence_is_unique(cls, value: tuple[PhysicalClosingEvidence, ...]) -> tuple[PhysicalClosingEvidence, ...]:
        identities = tuple(item.reference.reference for item in value)
        if len(set(identities)) != len(identities):
            raise InventoryValidationError("physical closing evidence references must be unique")
        roles = {item.role for item in value}
        required = {PhysicalClosingEvidenceRole.PHYSICAL_COUNT, PhysicalClosingEvidenceRole.ACQUISITION_PRICE_VALUATION}
        if not required.issubset(roles):
            raise InventoryValidationError("physical closing requires count and acquisition-price valuation evidence")
        if len(roles) != len(value):
            raise InventoryValidationError("physical closing evidence roles must be unique")
        return value

    @model_validator(mode="after")
    @pydantic_validation_boundary
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
            }
        )

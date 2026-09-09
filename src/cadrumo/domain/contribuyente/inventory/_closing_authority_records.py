"""Canonical closing-authority records for inventory year-end resolution.

The public classes are loaded by the records facade after its foundational
closing observations and enums exist. The facade rebinds their module identity
to the historical public module.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator

from ....core.decimal.constants import MONEY_ZERO
from ....core.filing_year import FilingYear
from ....core.hashing import content_hash_hex as _content_hash_hex
from ....core.identity import ContentDigest
from ....core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN_CONFIG
from ....core.time.utc import UtcInstant
from ...identifiers import canonical_decimal_string as _canonical_decimal_string
from .records import (
    InventoryClosingAuthority,
    InventoryClosingDecisionEvidence,
    InventoryValidationError,
    PhysicalClosingObservation,
    PriorClosingContinuityEvidence,
    fingerprint_prior_authoritative_closing,
    require_inventory_cents,
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
    decided_at: UtcInstant
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
    prior_authoritative_closing_value: Decimal = Field(ge=MONEY_ZERO)
    current_opening_value: Decimal = Field(ge=MONEY_ZERO)
    prior_authoritative_source_fingerprint: ContentDigest
    prior_authoritative_closing_fingerprint: ContentDigest
    evidence: tuple[PriorClosingContinuityEvidence, ...] = Field(min_length=1)

    @field_validator("prior_authoritative_closing_value", "current_opening_value")
    @classmethod
    def _values_are_cents(cls, value: Decimal, info: ValidationInfo) -> Decimal:
        return require_inventory_cents(value, field_name=info.field_name or "continuity value")

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
    movement_derived_value: Decimal = Field(ge=MONEY_ZERO)
    physical_observed_value: Decimal = Field(ge=MONEY_ZERO)
    physical_observation_fingerprint: ContentDigest

    @field_validator("movement_derived_value", "physical_observed_value")
    @classmethod
    def _values_are_cents(cls, value: Decimal, info: ValidationInfo) -> Decimal:
        return require_inventory_cents(value, field_name=info.field_name or "closing conflict value")


class InventoryClosingResolution(BaseModel):
    """Auditable authoritative closing resolution with retained conflict."""

    model_config = _STRICT_FROZEN_CONFIG

    actividad_id: str = Field(min_length=1)
    filing_year: FilingYear
    authority: InventoryClosingAuthority
    authoritative_value: Decimal = Field(ge=MONEY_ZERO)
    movement_derived_value: Decimal = Field(ge=MONEY_ZERO)
    physical_observed_value: Decimal | None = Field(default=None, ge=MONEY_ZERO)
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
        return require_inventory_cents(value, field_name=info.field_name or "closing resolution value")

    @model_validator(mode="after")
    def _conflict_is_retained(self) -> InventoryClosingResolution:
        has_physical = _validate_resolution_physical_state(self)
        _validate_resolution_authority_value(self, has_physical)
        _validate_resolution_conflict(self, has_physical)
        return self


def _validate_resolution_physical_state(resolution: InventoryClosingResolution) -> bool:
    has_physical = (
        resolution.physical_observed_value is not None and resolution.physical_observation_fingerprint is not None
    )
    if (resolution.physical_observed_value is None) != (resolution.physical_observation_fingerprint is None):
        raise InventoryValidationError("physical observed value and fingerprint must travel together")
    if has_physical != (resolution.physical_observation_id is not None):
        raise InventoryValidationError("physical observation identity must travel with physical resolution state")
    return has_physical


def _validate_resolution_authority_value(
    resolution: InventoryClosingResolution,
    has_physical: bool,
) -> None:
    if resolution.authority is InventoryClosingAuthority.PHYSICAL_OBSERVATION:
        if not has_physical or resolution.authoritative_value != resolution.physical_observed_value:
            raise InventoryValidationError("physical authority value must equal the physical observation")
    elif resolution.authoritative_value != resolution.movement_derived_value:
        raise InventoryValidationError("movement-derived authority value must equal movement-derived closing")


def _validate_resolution_conflict(
    resolution: InventoryClosingResolution,
    has_physical: bool,
) -> None:
    differs = has_physical and resolution.physical_observed_value != resolution.movement_derived_value
    if differs != (resolution.conflict is not None):
        raise InventoryValidationError("physical closing conflict diagnostic must exactly match value conflict")
    if resolution.conflict is not None and (
        resolution.conflict.actividad_id != resolution.actividad_id
        or resolution.conflict.filing_year != resolution.filing_year
        or resolution.conflict.movement_derived_value != resolution.movement_derived_value
        or resolution.conflict.physical_observed_value != resolution.physical_observed_value
        or resolution.conflict.physical_observation_fingerprint != resolution.physical_observation_fingerprint
    ):
        raise InventoryValidationError("physical closing conflict diagnostic does not match resolution state")


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

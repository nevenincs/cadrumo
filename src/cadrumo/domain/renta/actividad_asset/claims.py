"""Append-only amortization claims and non-consuming filing projections."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator

from ....core.hashing import content_hash_hex
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.money.rounding import round_to_cents
from ....core.period import Period
from .errors import ActividadAssetClaimConflictError, ActividadAssetValidationError
from .lifecycle import AssetKind
from .schedule import ScheduledAmortizationCharge


class AmortizationClaim(BaseModel):
    """An immutable recorded charge, distinct from a recomputable forecast."""

    model_config = STRICT_FROZEN_CONFIG

    asset_id: str = Field(min_length=1, max_length=128)
    asset_revision_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    asset_kind: AssetKind
    tax_year: int = Field(ge=2025, le=2025)
    covered_from: date
    covered_until: date
    amount: Decimal
    schedule_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    authority_generation: str = Field(min_length=1, max_length=256)
    source_reference: str = Field(min_length=1, max_length=512)
    creating_operation: str = Field(min_length=1, max_length=256)
    supersedes_claim_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    calculation_revision_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    filing_revision_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @field_validator("amount")
    @classmethod
    def _require_cents_amount(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value < Decimal("0") or value != round_to_cents(value):
            raise ValueError("claim amount must be a non-negative Decimal rounded to euro cents")
        return value

    @model_validator(mode="after")
    def _validate_interval(self) -> AmortizationClaim:
        if self.covered_until <= self.covered_from:
            raise ValueError("claim covered interval must be half-open and non-empty")
        if not (date(self.tax_year, 1, 1) <= self.covered_from < self.covered_until <= date(self.tax_year + 1, 1, 1)):
            raise ValueError("claim covered interval must stay inside tax_year")
        return self

    @property
    def claim_id(self) -> str:
        """Return deterministic claim identity, including every replay discriminator."""
        return content_hash_hex(self.model_dump(mode="json"))

    @classmethod
    def from_schedule(
        cls,
        schedule: ScheduledAmortizationCharge,
        *,
        asset_kind: AssetKind,
        creating_operation: str,
        supersedes_claim_id: str | None = None,
    ) -> AmortizationClaim:
        """Materialise an explicit recorded claim from a schedule forecast."""
        return cls(
            asset_id=schedule.asset_id,
            asset_revision_id=schedule.asset_revision_id,
            asset_kind=asset_kind,
            tax_year=schedule.tax_year,
            covered_from=schedule.covered_from,
            covered_until=schedule.covered_until,
            amount=schedule.amount,
            schedule_fingerprint=schedule.schedule_fingerprint,
            authority_generation=schedule.authority_generation,
            source_reference=schedule.source_reference,
            creating_operation=creating_operation,
            supersedes_claim_id=supersedes_claim_id,
        )


class ClaimRecordResult(BaseModel):
    """Pure append result which tells an application whether storage must write."""

    model_config = STRICT_FROZEN_CONFIG

    claims: tuple[AmortizationClaim, ...]
    claim: AmortizationClaim
    reused_existing_claim: bool


class ClaimProjection(BaseModel):
    """A form projection which refers to claims and never creates deductions."""

    model_config = STRICT_FROZEN_CONFIG

    target_casilla_id: str = Field(pattern=r"^(?:\d{2}|0\d{3})$")
    tax_year: int = Field(ge=2025, le=2025)
    claim_ids: tuple[str, ...]
    amount: Decimal

    @field_validator("amount")
    @classmethod
    def _require_cents_amount(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value < Decimal("0") or value != round_to_cents(value):
            raise ValueError("projection amount must be a non-negative Decimal rounded to euro cents")
        return value


def record_claim(
    existing_claims: tuple[AmortizationClaim, ...],
    candidate: AmortizationClaim,
) -> ClaimRecordResult:
    """Apply exact-retry, overlap-conflict, and explicit-supersession rules."""
    for existing in existing_claims:
        if existing.claim_id == candidate.claim_id:
            return ClaimRecordResult(
                claims=existing_claims,
                claim=existing,
                reused_existing_claim=True,
            )
    matching_superseded: AmortizationClaim | None = None
    if candidate.supersedes_claim_id is not None:
        matching_superseded = next(
            (claim for claim in existing_claims if claim.claim_id == candidate.supersedes_claim_id),
            None,
        )
        if matching_superseded is None:
            raise ActividadAssetClaimConflictError("superseded claim is absent from history")
        if (
            matching_superseded.asset_id != candidate.asset_id
            or matching_superseded.covered_from != candidate.covered_from
            or matching_superseded.covered_until != candidate.covered_until
        ):
            raise ActividadAssetClaimConflictError(
                "superseding claim must preserve asset identity and covered interval",
            )
    for existing in effective_claims(existing_claims):
        if existing.asset_id != candidate.asset_id:
            continue
        exact_interval = (
            existing.covered_from == candidate.covered_from
            and existing.covered_until == candidate.covered_until
        )
        if exact_interval:
            if matching_superseded is existing:
                continue
            raise ActividadAssetClaimConflictError("same asset and covered interval already has a different claim")
        if _intervals_overlap(
            existing.covered_from,
            existing.covered_until,
            candidate.covered_from,
            candidate.covered_until,
        ):
            raise ActividadAssetClaimConflictError("activity-asset claims cannot cover overlapping intervals")
    return ClaimRecordResult(
        claims=(*existing_claims, candidate),
        claim=candidate,
        reused_existing_claim=False,
    )


def effective_claims(claims: tuple[AmortizationClaim, ...]) -> tuple[AmortizationClaim, ...]:
    """Return auditable-history claims that still consume lawful basis, in order."""
    superseded = {claim.supersedes_claim_id for claim in claims if claim.supersedes_claim_id is not None}
    return tuple(claim for claim in claims if claim.claim_id not in superseded)


def project_m100(claims: tuple[AmortizationClaim, ...], *, asset_kind: AssetKind, tax_year: int) -> ClaimProjection:
    """Project one effective claim set to its exclusive 2025 Modelo 100 destination."""
    selected = tuple(
        claim for claim in effective_claims(claims) if claim.tax_year == tax_year and claim.asset_kind is asset_kind
    )
    target_casilla_id = "0208" if asset_kind is AssetKind.MATERIAL else "0227"
    return _project(selected, tax_year=tax_year, target_casilla_id=target_casilla_id)


def project_m130(claims: tuple[AmortizationClaim, ...], *, period: Period, asset_kind: AssetKind) -> ClaimProjection:
    """Project the same effective claims cumulatively through a dated M130 period."""
    if period.filing_year != 2025 or not period.has_date_span():
        raise ActividadAssetValidationError("M130 asset projection requires a dated 2025 filing period")
    cutoff = period.end_date
    selected = tuple(
        claim
        for claim in effective_claims(claims)
        if claim.tax_year == period.filing_year
        and claim.asset_kind is asset_kind
        and claim.covered_until <= cutoff + timedelta(days=1)
    )
    return _project(selected, tax_year=period.filing_year, target_casilla_id="02")


def _project(claims: tuple[AmortizationClaim, ...], *, tax_year: int, target_casilla_id: str) -> ClaimProjection:
    return ClaimProjection(
        target_casilla_id=target_casilla_id,
        tax_year=tax_year,
        claim_ids=tuple(claim.claim_id for claim in claims),
        amount=round_to_cents(sum((claim.amount for claim in claims), Decimal("0"))),
    )


def _intervals_overlap(left_start: date, left_end: date, right_start: date, right_end: date) -> bool:
    return left_start < right_end and right_start < left_end


__all__ = [
    "AmortizationClaim",
    "ClaimProjection",
    "ClaimRecordResult",
    "effective_claims",
    "project_m100",
    "project_m130",
    "record_claim",
]

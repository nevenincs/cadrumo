"""Append-only amortization claims and non-consuming filing projections."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator

from ....core.filing_year import FilingYear
from ....core.hashing import content_hash_hex
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.money.rounding import round_to_cents
from ....core.period import Period
from .election import AmortizationMethod
from .errors import ActividadAssetClaimConflictError, ActividadAssetValidationError
from .lifecycle import ActivityAssetRevision, AssetKind
from .schedule import AssetScheduleHistory, ScheduledAmortizationCharge


class AmortizationClaim(BaseModel):
    """An immutable recorded charge, distinct from a recomputable forecast."""

    model_config = STRICT_FROZEN_CONFIG

    asset_id: str = Field(min_length=1, max_length=128)
    asset_revision_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    asset_kind: AssetKind
    tax_year: FilingYear
    covered_from: date
    covered_until: date
    amount: Decimal
    schedule_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    authority_generation: str = Field(min_length=1, max_length=256)
    source_reference: str = Field(min_length=1, max_length=2048)
    creating_operation: str = Field(min_length=1, max_length=256)
    supersedes_claim_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    calculation_revision_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    filing_revision_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    method: AmortizationMethod = AmortizationMethod.LINEAR
    free_depreciation_election_reference: str | None = Field(default=None, min_length=1, max_length=256)
    free_depreciation_new_material_evidence_reference: str | None = Field(default=None, min_length=1, max_length=512)
    free_depreciation_unit_acquisition_value: Decimal | None = None
    free_depreciation_annual_cap: Decimal | None = None

    @field_validator("amount")
    @classmethod
    def _require_cents_amount(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value < Decimal("0") or value != round_to_cents(value):
            raise ValueError("claim amount must be a non-negative Decimal rounded to euro cents")
        return value

    @field_validator("free_depreciation_unit_acquisition_value", "free_depreciation_annual_cap")
    @classmethod
    def _require_optional_positive_cents_amount(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and (not value.is_finite() or value <= Decimal("0") or value != round_to_cents(value)):
            raise ValueError("free-depreciation claim amounts must be positive Decimal amounts rounded to euro cents")
        return value

    @model_validator(mode="after")
    def _validate_interval(self) -> AmortizationClaim:
        if self.covered_until <= self.covered_from:
            raise ValueError("claim covered interval must be half-open and non-empty")
        if not (date(self.tax_year, 1, 1) <= self.covered_from < self.covered_until <= date(self.tax_year + 1, 1, 1)):
            raise ValueError("claim covered interval must stay inside tax_year")
        if self.method is AmortizationMethod.LOW_VALUE_FREE:
            if (
                self.free_depreciation_election_reference is None
                or self.free_depreciation_new_material_evidence_reference is None
                or self.free_depreciation_unit_acquisition_value is None
                or self.free_depreciation_annual_cap is None
            ):
                raise ValueError("free-depreciation claim requires election and annual-cap provenance")
        elif any(
            value is not None
            for value in (
                self.free_depreciation_election_reference,
                self.free_depreciation_new_material_evidence_reference,
                self.free_depreciation_unit_acquisition_value,
                self.free_depreciation_annual_cap,
            )
        ):
            raise ValueError("only a low-value claim carries free-depreciation election facts")
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
            method=schedule.method,
            free_depreciation_election_reference=schedule.free_depreciation_election_reference,
            free_depreciation_new_material_evidence_reference=schedule.free_depreciation_new_material_evidence_reference,
            free_depreciation_unit_acquisition_value=schedule.free_depreciation_unit_acquisition_value,
            free_depreciation_annual_cap=schedule.free_depreciation_annual_cap,
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
    tax_year: FilingYear
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
            existing.covered_from == candidate.covered_from and existing.covered_until == candidate.covered_until
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
    _require_free_depreciation_cap(existing_claims, candidate)
    return ClaimRecordResult(
        claims=(*existing_claims, candidate),
        claim=candidate,
        reused_existing_claim=False,
    )


def effective_claims(claims: tuple[AmortizationClaim, ...]) -> tuple[AmortizationClaim, ...]:
    """Return auditable-history claims that still consume lawful basis, in order."""
    superseded = {claim.supersedes_claim_id for claim in claims if claim.supersedes_claim_id is not None}
    return tuple(claim for claim in claims if claim.claim_id not in superseded)


def effective_free_depreciation_claims(
    claims: tuple[AmortizationClaim, ...],
    *,
    tax_year: int,
) -> tuple[AmortizationClaim, ...]:
    """Return effective low-value claims for the taxpayer's asset-history scope.

    One encrypted activity-asset history is bucket-bound to the taxpayer
    profile; summing its effective claims makes the statutory annual ceiling
    cover every enrolled asset and activity rather than the current asset or
    request order.
    """
    return tuple(
        claim
        for claim in effective_claims(claims)
        if claim.tax_year == tax_year and claim.method is AmortizationMethod.LOW_VALUE_FREE
    )


def _require_free_depreciation_cap(
    existing_claims: tuple[AmortizationClaim, ...],
    candidate: AmortizationClaim,
) -> None:
    """Enforce the elected annual ceiling against effective CAS-replayed history."""
    if candidate.method is not AmortizationMethod.LOW_VALUE_FREE:
        return
    annual_cap = candidate.free_depreciation_annual_cap
    if annual_cap is None:  # defensive: model validation proves unreachable
        raise ActividadAssetValidationError("free-depreciation claim lacks annual-cap provenance")
    effective = effective_free_depreciation_claims(
        (*existing_claims, candidate),
        tax_year=candidate.tax_year,
    )
    cap_values = {claim.free_depreciation_annual_cap for claim in effective}
    if cap_values != {annual_cap}:
        raise ActividadAssetClaimConflictError(
            "effective free-depreciation claims disagree on the annual-cap authority",
        )
    total = sum((claim.amount for claim in effective), Decimal("0"))
    if total > annual_cap:
        raise ActividadAssetClaimConflictError("free-depreciation effective claims exceed the annual cap")


def asset_schedule_history(
    claims: tuple[AmortizationClaim, ...],
    revisions: tuple[ActivityAssetRevision, ...],
    *,
    asset_id: str,
    tax_year: int,
    excluding_claim_id: str | None = None,
) -> AssetScheduleHistory:
    """Summarise effective history the schedule needs for one asset and tax year.

    Election fingerprints come from the revision each claim was recorded
    under.  A claim in a later tax year refuses, because the lawful charge of
    an earlier year cannot be recomputed after later basis was consumed.
    ``excluding_claim_id`` removes one effective claim after supersession is
    resolved, which is how a superseding claim is judged without its target.
    """
    elections = {revision.revision_id: revision.amortization.fingerprint for revision in revisions}
    effective = tuple(
        claim
        for claim in effective_claims(claims)
        if claim.asset_id == asset_id and claim.claim_id != excluding_claim_id
    )
    if any(claim.tax_year > tax_year for claim in effective):
        raise ActividadAssetValidationError("a later tax year already has recorded claims for this asset")
    before = tuple(claim for claim in effective if claim.tax_year < tax_year)
    within = tuple(claim for claim in effective if claim.tax_year == tax_year)
    missing = {claim.asset_revision_id for claim in effective} - elections.keys()
    if missing:
        raise ActividadAssetValidationError("an effective claim references a revision absent from history")
    return AssetScheduleHistory(
        accumulated_before_tax_year=sum((claim.amount for claim in before), Decimal("0")),
        accumulated_in_tax_year=sum((claim.amount for claim in within), Decimal("0")),
        taxpayer_low_value_claimed_in_tax_year=sum(
            (
                claim.amount
                for claim in effective_free_depreciation_claims(claims, tax_year=tax_year)
                if claim.claim_id != excluding_claim_id
            ),
            Decimal("0"),
        ),
        election_fingerprints_before_tax_year=tuple(
            sorted({elections[claim.asset_revision_id] for claim in before}),
        ),
        election_fingerprints_in_tax_year=tuple(sorted({elections[claim.asset_revision_id] for claim in within})),
    )


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
    "asset_schedule_history",
    "effective_claims",
    "effective_free_depreciation_claims",
    "project_m100",
    "project_m130",
    "record_claim",
]

"""Append-only amortization claims and non-consuming filing projections."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta
from decimal import Decimal
from typing import Final

from pydantic import BaseModel, Field, field_validator, model_validator

from ....core.filing_year import FilingYear
from ....core.hashing import content_hash_hex
from ....core.hex import Hex64Str
from ....core.identity.hex_ids import CalculationRevisionId
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.money.rounding import round_to_cents
from ....core.period import Period
from .election import (
    WORKFORCE_CONDITIONED_METHODS,
    AmortizationMethod,
    ElectionReference,
    EvidenceReference,
    require_euro_cents,
    require_free_depreciation_facts,
)
from .errors import ActividadAssetClaimConflictError, ActividadAssetValidationError
from .lifecycle import ActivityAssetRevision, AssetKind
from .schedule import AssetScheduleHistory, ScheduledAmortizationCharge

MATERIAL_M100_CASILLA_ID: Final[str] = "0208"
"""Modelo 100 destination the activity-asset source exclusively owns for material assets."""

INTANGIBLE_M100_CASILLA_ID: Final[str] = "0227"
"""Modelo 100 destination the activity-asset source exclusively owns for intangible assets."""

M100_AMORTIZATION_CASILLA_IDS: Final[frozenset[str]] = frozenset(
    {MATERIAL_M100_CASILLA_ID, INTANGIBLE_M100_CASILLA_ID},
)
"""The two Modelo 100 destinations that carry an activity amortization dotación.

A Renta expense observation reaching one of these casillas declares an
amortization-labelled deductible amount, whichever path produced it. Consumers
that must recognise such a declaration read this set rather than restating the
casilla numbers.
"""


def m100_casilla_id(asset_kind: AssetKind) -> str:
    """Return the Modelo 100 amortization destination for one asset kind."""
    return MATERIAL_M100_CASILLA_ID if asset_kind is AssetKind.MATERIAL else INTANGIBLE_M100_CASILLA_ID


class AmortizationClaim(BaseModel):
    """An immutable recorded charge, distinct from a recomputable forecast."""

    model_config = STRICT_FROZEN_CONFIG

    asset_id: str = Field(min_length=1, max_length=128)
    asset_revision_id: Hex64Str
    asset_kind: AssetKind
    tax_year: FilingYear
    covered_from: date
    covered_until: date
    amount: Decimal
    schedule_fingerprint: Hex64Str
    authority_generation: str = Field(min_length=1, max_length=256)
    source_reference: str = Field(min_length=1, max_length=2048)
    creating_operation: str = Field(min_length=1, max_length=256)
    supersedes_claim_id: Hex64Str | None = None
    calculation_revision_id: CalculationRevisionId | None = None
    filing_revision_id: Hex64Str | None = None
    method: AmortizationMethod = AmortizationMethod.LINEAR
    free_depreciation_election_reference: ElectionReference | None = None
    free_depreciation_new_material_evidence_reference: EvidenceReference | None = None
    free_depreciation_unit_acquisition_value: Decimal | None = None
    free_depreciation_annual_cap: Decimal | None = None

    @field_validator("amount")
    @classmethod
    def _require_cents_amount(cls, value: Decimal) -> Decimal:
        return require_euro_cents(value, allow_zero=True, label="claim amount")

    @field_validator("free_depreciation_unit_acquisition_value", "free_depreciation_annual_cap")
    @classmethod
    def _require_optional_positive_cents_amount(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return value
        return require_euro_cents(value, allow_zero=False, label="free-depreciation claim amount")

    @model_validator(mode="after")
    def _validate_interval(self) -> AmortizationClaim:
        if self.covered_until <= self.covered_from:
            raise ValueError("claim covered interval must be half-open and non-empty")
        if not (date(self.tax_year, 1, 1) <= self.covered_from < self.covered_until <= date(self.tax_year + 1, 1, 1)):
            raise ValueError("claim covered interval must stay inside tax_year")
        require_free_depreciation_facts(
            self.method,
            (
                self.free_depreciation_election_reference,
                self.free_depreciation_new_material_evidence_reference,
                self.free_depreciation_unit_acquisition_value,
                self.free_depreciation_annual_cap,
            ),
            subject="claim",
        )
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
        return require_euro_cents(value, allow_zero=True, label="projection amount")


def record_claim(
    existing_claims: tuple[AmortizationClaim, ...],
    candidate: AmortizationClaim,
) -> ClaimRecordResult:
    """Apply exact-retry, overlap-conflict, and explicit-supersession rules."""
    reused = _matching_claim_id(existing_claims, candidate.claim_id)
    if reused is not None:
        return ClaimRecordResult(claims=existing_claims, claim=reused, reused_existing_claim=True)
    matching_superseded = _superseded_claim(existing_claims, candidate)
    _validate_claim_interval(existing_claims, candidate, matching_superseded)
    _require_free_depreciation_cap(existing_claims, candidate)
    return ClaimRecordResult(claims=(*existing_claims, candidate), claim=candidate, reused_existing_claim=False)


def _matching_claim_id(claims: tuple[AmortizationClaim, ...], claim_id: str) -> AmortizationClaim | None:
    for claim in claims:
        if claim.claim_id == claim_id:
            return claim
    return None


def _superseded_claim(
    existing_claims: tuple[AmortizationClaim, ...],
    candidate: AmortizationClaim,
) -> AmortizationClaim | None:
    if candidate.supersedes_claim_id is None:
        return None
    matching = _matching_claim_id(existing_claims, candidate.supersedes_claim_id)
    if matching is None:
        raise ActividadAssetClaimConflictError("superseded claim is absent from history")
    _validate_supersession_identity(matching, candidate)
    return matching


def _validate_supersession_identity(
    superseded: AmortizationClaim,
    candidate: AmortizationClaim,
) -> None:
    if (
        superseded.asset_id != candidate.asset_id
        or superseded.covered_from != candidate.covered_from
        or superseded.covered_until != candidate.covered_until
    ):
        raise ActividadAssetClaimConflictError(
            "superseding claim must preserve asset identity and covered interval",
        )


def _validate_claim_interval(
    existing_claims: tuple[AmortizationClaim, ...],
    candidate: AmortizationClaim,
    matching_superseded: AmortizationClaim | None,
) -> None:
    for existing in effective_claims(existing_claims):
        if existing.asset_id != candidate.asset_id:
            continue
        if _has_same_interval(existing, candidate):
            if matching_superseded is existing:
                continue
            raise ActividadAssetClaimConflictError("same asset and covered interval already has a different claim")
        if _intervals_overlap(
            existing.covered_from, existing.covered_until, candidate.covered_from, candidate.covered_until
        ):
            raise ActividadAssetClaimConflictError("activity-asset claims cannot cover overlapping intervals")


def _has_same_interval(left: AmortizationClaim, right: AmortizationClaim) -> bool:
    return left.covered_from == right.covered_from and left.covered_until == right.covered_until


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
    effective = _asset_schedule_claims(
        claims,
        asset_id=asset_id,
        excluding_claim_id=excluding_claim_id,
    )
    _validate_asset_schedule_history(effective, elections, tax_year=tax_year)
    before, within = _split_claims_by_tax_year(effective, tax_year=tax_year)
    return AssetScheduleHistory(
        accumulated_before_tax_year=_amount_sum(before),
        accumulated_in_tax_year=_amount_sum(within),
        taxpayer_low_value_claimed_in_tax_year=_taxpayer_low_value_claim_amount(
            claims,
            tax_year=tax_year,
            excluding_claim_id=excluding_claim_id,
        ),
        election_fingerprints_before_tax_year=_election_fingerprints(before, elections),
        election_fingerprints_in_tax_year=_election_fingerprints(within, elections),
        same_incentive_investment_of_other_assets=_same_incentive_investment_of_other_assets(
            revisions,
            asset_id=asset_id,
        ),
    )


def _asset_schedule_claims(
    claims: tuple[AmortizationClaim, ...],
    *,
    asset_id: str,
    excluding_claim_id: str | None,
) -> tuple[AmortizationClaim, ...]:
    return tuple(
        claim
        for claim in effective_claims(claims)
        if claim.asset_id == asset_id and claim.claim_id != excluding_claim_id
    )


def _validate_asset_schedule_history(
    effective: tuple[AmortizationClaim, ...],
    elections: Mapping[str, str],
    *,
    tax_year: int,
) -> None:
    if any(claim.tax_year > tax_year for claim in effective):
        raise ActividadAssetValidationError("a later tax year already has recorded claims for this asset")
    missing = {claim.asset_revision_id for claim in effective} - elections.keys()
    if missing:
        raise ActividadAssetValidationError("an effective claim references a revision absent from history")


def _split_claims_by_tax_year(
    claims: tuple[AmortizationClaim, ...],
    *,
    tax_year: int,
) -> tuple[tuple[AmortizationClaim, ...], tuple[AmortizationClaim, ...]]:
    before = tuple(claim for claim in claims if claim.tax_year < tax_year)
    within = tuple(claim for claim in claims if claim.tax_year == tax_year)
    return before, within


def _amount_sum(claims: tuple[AmortizationClaim, ...]) -> Decimal:
    return sum((claim.amount for claim in claims), Decimal("0"))


def _taxpayer_low_value_claim_amount(
    claims: tuple[AmortizationClaim, ...],
    *,
    tax_year: int,
    excluding_claim_id: str | None,
) -> Decimal:
    included = (
        claim
        for claim in effective_free_depreciation_claims(claims, tax_year=tax_year)
        if claim.claim_id != excluding_claim_id
    )
    return sum((claim.amount for claim in included), Decimal("0"))


def _election_fingerprints(
    claims: tuple[AmortizationClaim, ...],
    elections: Mapping[str, str],
) -> tuple[str, ...]:
    return tuple(sorted({elections[claim.asset_revision_id] for claim in claims}))


def _same_incentive_investment_of_other_assets(
    revisions: tuple[ActivityAssetRevision, ...],
    *,
    asset_id: str,
) -> Decimal:
    """Sum the investment other assets place under this asset's workforce-conditioned incentive.

    Each asset counts through its current revision.  Assets share a cap only
    when they elect the same incentive and enter service in the same year,
    because each entry year has its own workforce test and its own cap.
    """
    current: dict[str, ActivityAssetRevision] = {}
    for revision in revisions:
        held = current.get(revision.asset_id)
        if held is None or revision.revision_number > held.revision_number:
            current[revision.asset_id] = revision
    this = current.get(asset_id)
    if this is None or this.amortization.method not in WORKFORCE_CONDITIONED_METHODS:
        return Decimal("0")
    return sum(
        (
            other.basis.deductible_basis()
            for other in current.values()
            if other.asset_id != asset_id
            and other.amortization.method is this.amortization.method
            and other.in_service_date.year == this.in_service_date.year
        ),
        Decimal("0"),
    )


def project_m100(claims: tuple[AmortizationClaim, ...], *, asset_kind: AssetKind, tax_year: int) -> ClaimProjection:
    """Project one effective claim set to its exclusive Modelo 100 destination."""
    selected = tuple(
        claim for claim in effective_claims(claims) if claim.tax_year == tax_year and claim.asset_kind is asset_kind
    )
    return _project(selected, tax_year=tax_year, target_casilla_id=m100_casilla_id(asset_kind))


def project_m130(claims: tuple[AmortizationClaim, ...], *, period: Period, asset_kind: AssetKind) -> ClaimProjection:
    """Project the same effective claims cumulatively through a dated M130 period."""
    if not period.has_date_span():
        raise ActividadAssetValidationError("M130 asset projection requires a dated filing period")
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
    "INTANGIBLE_M100_CASILLA_ID",
    "M100_AMORTIZATION_CASILLA_IDS",
    "MATERIAL_M100_CASILLA_ID",
    "AmortizationClaim",
    "ClaimProjection",
    "ClaimRecordResult",
    "asset_schedule_history",
    "effective_claims",
    "effective_free_depreciation_claims",
    "m100_casilla_id",
    "project_m100",
    "project_m130",
    "record_claim",
]

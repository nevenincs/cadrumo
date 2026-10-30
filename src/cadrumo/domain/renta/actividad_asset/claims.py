"""Append-only amortization claims and non-consuming filing projections."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta
from decimal import Decimal
from functools import cached_property

from pydantic import BaseModel, Field, field_validator, model_validator

from ....core.casilla_id import CasillaId
from ....core.filing_year import FilingYear
from ....core.hashing import content_hash_hex
from ....core.hex import Hex64Str
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.money.rounding import round_to_cents
from .election import (
    WORKFORCE_CONDITIONED_METHODS,
    AmortizationMethod,
    ElectionReference,
    EvidenceReference,
    require_euro_cents,
    require_free_depreciation_facts,
)
from .errors import ActividadAssetClaimConflictError, ActividadAssetValidationError
from .identity_cache import CachedIdentityModel
from .lifecycle import ActivityAssetRevision, AssetKind
from .schedule import AssetScheduleHistory, ScheduledAmortizationCharge


def last_day_covered(covered_until: date) -> date:
    """Return the last day a half-open claim interval covers, for display beside its exclusive boundary."""
    return covered_until - timedelta(days=1)


def covered_until_after(covered_through: date) -> date:
    """Return the exclusive boundary after a stated last covered day; the inverse of ``last_day_covered``."""
    return covered_through + timedelta(days=1)


class AmortizationClaim(CachedIdentityModel):
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
    method: AmortizationMethod = AmortizationMethod.LINEAR
    free_depreciation_election_reference: ElectionReference | None = None
    free_depreciation_new_material_evidence_reference: EvidenceReference | None = None
    free_depreciation_unit_acquisition_value: Decimal | None = None
    free_depreciation_annual_cap: Decimal | None = None
    disposal_revision_id: Hex64Str | None = None
    """The baja revision that wrote this claim; only such a claim may shorten or zero its predecessor."""

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

    @cached_property
    def claim_id(self) -> str:
        """Return deterministic claim identity, including every replay discriminator.

        A claim no baja wrote omits the reference, so its identity is unchanged by the field.
        """
        exclude = {"disposal_revision_id"} if self.disposal_revision_id is None else None
        return content_hash_hex(self.model_dump(mode="json", exclude=exclude))

    @classmethod
    def from_schedule(
        cls,
        schedule: ScheduledAmortizationCharge,
        *,
        asset_kind: AssetKind,
        creating_operation: str,
        supersedes_claim_id: str | None = None,
        disposal_revision_id: str | None = None,
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
            disposal_revision_id=disposal_revision_id,
        )

    def set_to_zero_by_baja(self, disposal_revision_id: str, *, creating_operation: str) -> AmortizationClaim:
        """Return the superseding claim that keeps this interval, wholly after a baja, at amount zero."""
        return self.model_copy(
            update={
                "asset_revision_id": disposal_revision_id,
                "amount": Decimal("0.00"),
                "creating_operation": creating_operation,
                "supersedes_claim_id": self.claim_id,
                "disposal_revision_id": disposal_revision_id,
            },
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

    target_casilla_id: CasillaId
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
        if any(claim.supersedes_claim_id == reused.claim_id for claim in existing_claims):
            raise ActividadAssetClaimConflictError(
                translated_message="ledger.actividad_asset.errors.claim_superseded_replay",
            )
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
        raise ActividadAssetClaimConflictError(
            translated_message="ledger.actividad_asset.errors.superseded_claim_absent"
        )
    _validate_supersession_identity(matching, candidate)
    return matching


def _validate_supersession_identity(
    superseded: AmortizationClaim,
    candidate: AmortizationClaim,
) -> None:
    shortened_by_baja = (
        candidate.disposal_revision_id is not None
        and superseded.covered_from == candidate.covered_from
        and candidate.covered_until < superseded.covered_until
    )
    if superseded.asset_id != candidate.asset_id or not (
        shortened_by_baja or _has_same_interval(superseded, candidate)
    ):
        raise ActividadAssetClaimConflictError(
            translated_message="ledger.actividad_asset.errors.superseding_claim_changes_interval"
        )


def _validate_claim_interval(
    existing_claims: tuple[AmortizationClaim, ...],
    candidate: AmortizationClaim,
    matching_superseded: AmortizationClaim | None,
) -> None:
    for existing in effective_claims(existing_claims):
        if existing.asset_id != candidate.asset_id or matching_superseded is existing:
            continue
        if _has_same_interval(existing, candidate):
            raise ActividadAssetClaimConflictError(
                translated_message="ledger.actividad_asset.errors.interval_has_different_claim"
            )
        if _intervals_overlap(
            existing.covered_from, existing.covered_until, candidate.covered_from, candidate.covered_until
        ):
            raise ActividadAssetClaimConflictError(translated_message="ledger.actividad_asset.errors.claims_overlap")


def _has_same_interval(left: AmortizationClaim, right: AmortizationClaim) -> bool:
    return left.covered_from == right.covered_from and left.covered_until == right.covered_until


def effective_claims(claims: tuple[AmortizationClaim, ...]) -> tuple[AmortizationClaim, ...]:
    """Return auditable-history claims that still consume lawful basis, in order."""
    superseded = {claim.supersedes_claim_id for claim in claims if claim.supersedes_claim_id is not None}
    return tuple(claim for claim in claims if claim.claim_id not in superseded)


def select_effective_claims(
    claims: tuple[AmortizationClaim, ...],
    *,
    tax_year: int,
    through: date | None = None,
) -> tuple[AmortizationClaim, ...]:
    """Return the effective claims of one tax year, optionally cut at an inclusive date.

    ``through`` is the last day a claim may cover: a claim is kept when its
    half-open interval ends no later than the day after ``through``.  This is
    the single selection every calculation and filing handoff projects from.
    """
    selected = tuple(claim for claim in effective_claims(claims) if claim.tax_year == tax_year)
    if through is None:
        return selected
    cutoff = through + timedelta(days=1)
    return tuple(claim for claim in selected if claim.covered_until <= cutoff)


class ClaimCoverageGap(BaseModel):
    """A half-open interval of an element's service window with no effective claim."""

    model_config = STRICT_FROZEN_CONFIG

    covered_from: date
    covered_until: date


def uncovered_claim_intervals(
    revision: ActivityAssetRevision,
    claims: tuple[AmortizationClaim, ...],
    *,
    start: date,
    end: date,
) -> tuple[ClaimCoverageGap, ...]:
    """Return the ordered, merged half-open intervals of ``[start, end)`` left uncovered.

    Only the element's service window counts: from its in-service date to its
    out-of-service date when set, clipped to the span.  Superseded claims and
    claims of other assets are ignored.  A zero claim covers its interval only once
    no lawful base remains, which is when the schedule charges zero there too;
    otherwise a deduction would vanish without a finding.  No amount is computed;
    callers call once per tax year.
    """
    if end <= start:
        raise ActividadAssetValidationError(translated_message="ledger.actividad_asset.errors.covered_interval_empty")
    window_start = max(start, revision.in_service_date)
    window_end = end if revision.out_of_service_date is None else min(end, revision.out_of_service_date)
    own = tuple(claim for claim in effective_claims(claims) if claim.asset_id == revision.asset_id)
    base_exhausted = _lawful_base_exhausted(revision, own)
    covering = sorted(
        (claim for claim in own if claim.amount > Decimal("0") or base_exhausted),
        key=lambda claim: claim.covered_from,
    )
    return _coverage_gaps(covering, window_start, window_end)


def _coverage_gaps(
    covering: list[AmortizationClaim], window_start: date, window_end: date
) -> tuple[ClaimCoverageGap, ...]:
    gaps: list[ClaimCoverageGap] = []
    cursor = window_start
    for claim in covering:
        if cursor >= window_end:
            break
        if claim.covered_until <= cursor:
            continue
        if claim.covered_from > cursor:
            gaps.append(ClaimCoverageGap(covered_from=cursor, covered_until=min(claim.covered_from, window_end)))
        cursor = max(cursor, claim.covered_until)
    if cursor < window_end:
        gaps.append(ClaimCoverageGap(covered_from=cursor, covered_until=window_end))
    return tuple(gaps)


def _lawful_base_exhausted(revision: ActivityAssetRevision, own: tuple[AmortizationClaim, ...]) -> bool:
    opening = revision.opening_history.accumulated_amount
    return opening is not None and opening + _amount_sum(own) >= revision.amortizable_ceiling()


def amount_before_baja_zeroed(claim: AmortizationClaim, claims: tuple[AmortizationClaim, ...]) -> Decimal:
    """Return the amount a zero claim a baja wrote replaced, following the chain of replacements."""
    by_id = {item.claim_id: item for item in claims}
    current = claim
    while current.amount == Decimal("0") and current.disposal_revision_id is not None:
        predecessor = by_id.get(current.supersedes_claim_id or "")
        if predecessor is None:
            break
        current = predecessor
    return current.amount


def claims_through_year(claims: tuple[AmortizationClaim, ...], tax_year: int) -> tuple[AmortizationClaim, ...]:
    """Return the claims a year's charge can rest on: nothing recorded for a later year moves it."""
    return tuple(claim for claim in claims if claim.tax_year <= tax_year)


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
        raise ActividadAssetValidationError(translated_message="ledger.actividad_asset.errors.authority_incomplete")
    effective = effective_free_depreciation_claims(
        (*existing_claims, candidate),
        tax_year=candidate.tax_year,
    )
    cap_values = {claim.free_depreciation_annual_cap for claim in effective}
    if cap_values != {annual_cap}:
        raise ActividadAssetClaimConflictError(
            translated_message="ledger.actividad_asset.errors.free_claims_disagree_on_cap"
        )
    total = sum((claim.amount for claim in effective), Decimal("0"))
    if total > annual_cap:
        raise ActividadAssetClaimConflictError(
            translated_message="ledger.actividad_asset.errors.free_claims_exceed_annual_cap"
        )


def current_revisions(revisions: tuple[ActivityAssetRevision, ...]) -> dict[str, ActivityAssetRevision]:
    """Return each asset's highest-numbered revision, the one that states its current facts."""
    current: dict[str, ActivityAssetRevision] = {}
    for revision in revisions:
        held = current.get(revision.asset_id)
        if held is None or revision.revision_number > held.revision_number:
            current[revision.asset_id] = revision
    return current


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
    under.  Claims of later tax years are summed apart: whether a method can
    still charge behind them is the schedule's rule, and they always count
    against the lawful basis.  ``excluding_claim_id`` removes one effective
    claim after supersession is resolved, which is how a superseding claim is
    judged without its target.
    """
    elections = {revision.revision_id: revision.amortization.fingerprint for revision in revisions}
    effective = _asset_schedule_claims(
        claims,
        asset_id=asset_id,
        excluding_claim_id=excluding_claim_id,
    )
    _require_known_revisions(effective, elections)
    before, within = _split_claims_by_tax_year(effective, tax_year=tax_year)
    after = tuple(claim for claim in effective if claim.tax_year > tax_year)
    return AssetScheduleHistory(
        accumulated_before_tax_year=_amount_sum(before),
        accumulated_in_tax_year=_amount_sum(within),
        accumulated_after_tax_year=_amount_sum(after),
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


def _require_known_revisions(
    effective: tuple[AmortizationClaim, ...],
    elections: Mapping[str, str],
) -> None:
    missing = {claim.asset_revision_id for claim in effective} - elections.keys()
    if missing:
        raise ActividadAssetValidationError(translated_message="ledger.actividad_asset.errors.claim_revision_absent")


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
    current = current_revisions(revisions)
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


def project_m100(
    claims: tuple[AmortizationClaim, ...],
    *,
    asset_kind: AssetKind,
    tax_year: int,
    target_casilla_id: CasillaId,
) -> ClaimProjection:
    """Project one effective claim set to the box the edition binds for its asset kind."""
    selected = tuple(
        claim for claim in select_effective_claims(claims, tax_year=tax_year) if claim.asset_kind is asset_kind
    )
    return _project(selected, tax_year=tax_year, target_casilla_id=target_casilla_id)


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
    "ClaimCoverageGap",
    "ClaimProjection",
    "ClaimRecordResult",
    "amount_before_baja_zeroed",
    "asset_schedule_history",
    "claims_through_year",
    "covered_until_after",
    "current_revisions",
    "effective_claims",
    "effective_free_depreciation_claims",
    "last_day_covered",
    "project_m100",
    "record_claim",
    "select_effective_claims",
    "uncovered_claim_intervals",
]

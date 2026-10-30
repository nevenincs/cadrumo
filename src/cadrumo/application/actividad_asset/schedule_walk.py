"""Walk an element's schedule year by year: the one route to accrued amortization.

The plan, the Modelo 130 calculation and the filing handoff all read this route.
The deductible value pending is the basis less the opening amount and the effective
claims.  A past year with no claim is a missing deduction: it shows its planned figure
and takes nothing from later years, which stay within their own maximum and stop at the
maximum period (DGT V3655-16).  The minimum amortization reduces cost at a baja under
RIRPF art. 40 and is a separate figure, never subtracted here.  Nothing here records a claim.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum

from ...core.tipos_actividad import TipoActividad
from ...domain.calculations.registry.errors import RegistryError
from ...domain.renta.actividad_asset.claims import (
    AmortizationClaim,
    ClaimCoverageGap,
    asset_schedule_history,
    claims_through_year,
    current_revisions,
    select_effective_claims,
    uncovered_claim_intervals,
)
from ...domain.renta.actividad_asset.election import FREE_AMOUNT_METHODS
from ...domain.renta.actividad_asset.errors import (
    ActividadAssetError,
    ActividadAssetIncompleteError,
    ActividadAssetPeriodElapsedError,
    ActividadAssetUnsupportedError,
)
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision, OpeningHistoryStatus
from ...domain.renta.actividad_asset.schedule import ScheduledAmortizationCharge
from .history import ActivityAssetHistory
from .ports import ActivityAssetForecastOperation


class PlanFigureAbsence(StrEnum):
    """Why a year has no planned figure."""

    FREE_ELECTION = "free_election"
    COVERED_BY_OPENING = "covered_by_opening"
    EDITION_UNAVAILABLE = "edition_unavailable"
    PERIOD_ELAPSED = "period_elapsed"
    BASIS_EXHAUSTED = "basis_exhausted"
    INCOMPLETE = "incomplete"
    UNSUPPORTED = "unsupported"
    CONFLICT = "conflict"


@dataclass(frozen=True, slots=True)
class WalkedYear:
    """One tax year of an element's schedule."""

    tax_year: int
    claims: tuple[AmortizationClaim, ...]
    gaps: tuple[ClaimCoverageGap, ...]
    charge: ScheduledAmortizationCharge | None
    absence: PlanFigureAbsence | None
    reason_key: str | None
    reason_facts: Mapping[str, str] = field(default_factory=dict[str, str])
    consumed_before: Decimal = Decimal("0")
    consumed_through: Decimal = Decimal("0")

    @property
    def claimed(self) -> Decimal:
        """Return what this year's effective claims charge."""
        return sum((claim.amount for claim in self.claims), Decimal("0"))


def walk_element(
    revision: ActivityAssetRevision,
    history: ActivityAssetHistory,
    *,
    forecast: ActivityAssetForecastOperation,
    through_year: int,
    settled_after: int | None = None,
) -> tuple[WalkedYear, ...]:
    """Work out each service year from entry to ``through_year`` under the current revision.

    Every year consumes its effective claims and nothing else.  A year the schedule
    cannot work out also carries the typed reason.  With ``settled_after``, the walk
    ends at the first such reason from that year on, which is where a plan stops
    having anything further to say.  From that year on an uncovered charge is a
    projection: it lowers the figures of the years after it, so the plan's remaining
    figures never exceed the value pending, and it is never counted as consumed.

    A non-zero opening amount states what was amortized through its last covered
    tax year.  Those years are the opening's: they neither charge nor consume, which
    keeps the same years from counting twice.  Later years without a claim are gaps.

    Returns:
        One row per year in order, stopping at the year of the element's baja.
    """
    disposal = revision.disposal
    last_year = through_year if disposal is None else min(through_year, disposal.disposal_date.year)
    rows: list[WalkedYear] = []
    consumed = Decimal("0")
    projected = Decimal("0")
    opening_covers_through = revision.opening_history.covered_through_tax_year
    for tax_year in range(revision.in_service_date.year, last_year + 1):
        claims = _claims_in_year(history, revision.asset_id, tax_year)
        gaps = uncovered_claim_intervals(
            revision,
            history.claims,
            start=date(tax_year, 1, 1),
            end=date(tax_year + 1, 1, 1),
        )
        if opening_covers_through is not None and tax_year <= opening_covers_through:
            rows.append(
                WalkedYear(
                    tax_year=tax_year,
                    claims=claims,
                    gaps=(),
                    charge=None,
                    absence=PlanFigureAbsence.COVERED_BY_OPENING,
                    reason_key=None,
                ),
            )
            continue
        row = _walk_year(
            revision,
            history,
            forecast=forecast,
            tax_year=tax_year,
            claims=claims,
            gaps=gaps,
            consumed_before=consumed,
            projected_before=projected,
        )
        rows.append(row)
        consumed = row.consumed_through
        settled = _is_settled_year(tax_year, settled_after)
        if settled and row.charge is not None and gaps:
            projected += max(row.charge.amount - row.claimed, Decimal("0"))
        if settled and row.absence is not None:
            break
    return tuple(rows)


def _is_settled_year(tax_year: int, settled_after: int | None) -> bool:
    return settled_after is not None and tax_year >= settled_after


def _claims_in_year(history: ActivityAssetHistory, asset_id: str, tax_year: int) -> tuple[AmortizationClaim, ...]:
    return tuple(
        claim for claim in select_effective_claims(history.claims, tax_year=tax_year) if claim.asset_id == asset_id
    )


def _walk_year(
    revision: ActivityAssetRevision,
    history: ActivityAssetHistory,
    *,
    forecast: ActivityAssetForecastOperation,
    tax_year: int,
    claims: tuple[AmortizationClaim, ...],
    gaps: tuple[ClaimCoverageGap, ...],
    consumed_before: Decimal,
    projected_before: Decimal,
) -> WalkedYear:
    claimed = sum((claim.amount for claim in claims), Decimal("0"))
    if revision.amortization.method in FREE_AMOUNT_METHODS:
        return WalkedYear(
            tax_year=tax_year,
            claims=claims,
            gaps=gaps,
            consumed_before=consumed_before,
            charge=None,
            absence=PlanFigureAbsence.FREE_ELECTION,
            reason_key=None,
            consumed_through=consumed_before + claimed,
        )
    try:
        charge = _span_charge(
            revision,
            history,
            forecast=forecast,
            tax_year=tax_year,
            until=date(tax_year + 1, 1, 1),
            projected_before=projected_before,
        )
    except (ActividadAssetError, RegistryError) as error:
        return WalkedYear(
            tax_year=tax_year,
            claims=claims,
            gaps=gaps,
            consumed_before=consumed_before,
            charge=None,
            absence=_absence_of(error),
            reason_key=_reason_key(error),
            reason_facts=_reason_facts(error),
            consumed_through=consumed_before + claimed,
        )
    return WalkedYear(
        tax_year=tax_year,
        claims=claims,
        gaps=gaps,
        consumed_before=consumed_before,
        charge=charge,
        absence=PlanFigureAbsence.BASIS_EXHAUSTED if charge.amount <= Decimal("0") else None,
        reason_key=None,
        consumed_through=consumed_before + claimed,
    )


def _span_charge(
    revision: ActivityAssetRevision,
    history: ActivityAssetHistory,
    *,
    forecast: ActivityAssetForecastOperation,
    tax_year: int,
    until: date,
    projected_before: Decimal = Decimal("0"),
) -> ScheduledAmortizationCharge:
    """Charge from 1 January to ``until`` as the schedule's own figure.

    Earlier years count through their effective claims, the same summary a forecast
    reads.  Claims inside the year do not reduce it and later years do not touch it.
    """
    summary = asset_schedule_history(
        claims_through_year(history.claims, tax_year),
        history.revisions,
        asset_id=revision.asset_id,
        tax_year=tax_year,
    )
    summary = summary.model_copy(
        update={
            "accumulated_before_tax_year": summary.accumulated_before_tax_year + projected_before,
            "accumulated_in_tax_year": Decimal("0"),
            "election_fingerprints_in_tax_year": (),
        },
    )
    return forecast(revision, covered_from=date(tax_year, 1, 1), covered_until=until, history=summary)


def _absence_of(error: Exception) -> PlanFigureAbsence:
    if isinstance(error, RegistryError):
        return PlanFigureAbsence.EDITION_UNAVAILABLE
    if isinstance(error, ActividadAssetPeriodElapsedError):
        return PlanFigureAbsence.PERIOD_ELAPSED
    if isinstance(error, ActividadAssetIncompleteError):
        return PlanFigureAbsence.INCOMPLETE
    if isinstance(error, ActividadAssetUnsupportedError):
        return PlanFigureAbsence.UNSUPPORTED
    return PlanFigureAbsence.CONFLICT


def _reason_key(error: Exception) -> str | None:
    return error.translated_message if isinstance(error, ActividadAssetError) else None


def _reason_facts(error: Exception) -> dict[str, str]:
    if not isinstance(error, ActividadAssetError):
        return {}
    return {name: str(value) for name, value in (error.context or {}).items()}


class M130ElementOutcome(StrEnum):
    """What one element says about one Modelo 130 period."""

    ACCRUED = "accrued"
    NOTHING = "nothing"
    FREE_GAP = "free_gap"
    UNAVAILABLE = "unavailable"
    AGRARIAN_EXCLUDED = "agrarian_excluded"


@dataclass(frozen=True, slots=True)
class M130Contribution:
    """One amount behind Modelo 130 casilla 02: a recorded claim or the element's schedule."""

    asset_id: str
    amount: Decimal
    claim_id: str | None = None
    schedule_fingerprint: str | None = None


@dataclass(frozen=True, slots=True)
class M130ElementAccrual:
    """One element's accrual from 1 January to the end of the period."""

    revision: ActivityAssetRevision
    outcome: M130ElementOutcome
    contributions: tuple[M130Contribution, ...] = ()
    error: ActividadAssetError | RegistryError | None = None
    activity_undeclared: bool = False


def m130_register_accruals(
    history: ActivityAssetHistory,
    *,
    forecast: ActivityAssetForecastOperation,
    period_end: date,
    activities: Mapping[str, TipoActividad | None],
    agrarian: frozenset[TipoActividad],
) -> tuple[M130ElementAccrual, ...]:
    """Work out what every element of the register accrued in the year through ``period_end``.

    An element belongs to the activity its acquisition row declares.  An agrarian
    activity pays a share of income whatever its expenses (RIRPF art. 110.1.c), so
    its elements stay out and others still count.  An element declaring no activity
    counts, because silence does not mean agrarian.

    Returns:
        One accrual per element, in asset order.
    """
    current = current_revisions(history.revisions)
    any_agrarian = any(activity in agrarian for activity in activities.values())
    accruals: list[M130ElementAccrual] = []
    for asset_id in sorted(current):
        revision = current[asset_id]
        activity = activities.get(asset_id)
        if activity in agrarian:
            accruals.append(M130ElementAccrual(revision=revision, outcome=M130ElementOutcome.AGRARIAN_EXCLUDED))
            continue
        accrual = _m130_element_accrual(revision, history, forecast=forecast, period_end=period_end)
        accruals.append(
            M130ElementAccrual(
                revision=revision,
                outcome=accrual.outcome,
                contributions=accrual.contributions,
                error=accrual.error,
                activity_undeclared=activity is None and any_agrarian,
            ),
        )
    return tuple(accruals)


def _m130_element_accrual(
    revision: ActivityAssetRevision,
    history: ActivityAssetHistory,
    *,
    forecast: ActivityAssetForecastOperation,
    period_end: date,
) -> M130ElementAccrual:
    tax_year = period_end.year
    until = period_end + timedelta(days=1)
    if revision.in_service_date >= until or (
        revision.disposal is not None and revision.disposal.disposal_date.year < tax_year
    ):
        return M130ElementAccrual(revision=revision, outcome=M130ElementOutcome.NOTHING)
    if revision.amortization.method in FREE_AMOUNT_METHODS:
        return _m130_free_accrual(revision, history, period_end=period_end)
    try:
        charge = _span_charge(
            revision,
            history,
            forecast=forecast,
            tax_year=tax_year,
            until=until,
        )
    except ActividadAssetPeriodElapsedError:
        return M130ElementAccrual(revision=revision, outcome=M130ElementOutcome.NOTHING)
    except (ActividadAssetError, RegistryError) as error:
        return M130ElementAccrual(revision=revision, outcome=M130ElementOutcome.UNAVAILABLE, error=error)
    if charge.amount <= Decimal("0"):
        return M130ElementAccrual(revision=revision, outcome=M130ElementOutcome.NOTHING)
    return M130ElementAccrual(
        revision=revision,
        outcome=M130ElementOutcome.ACCRUED,
        contributions=(
            M130Contribution(
                asset_id=revision.asset_id,
                amount=charge.amount,
                schedule_fingerprint=charge.schedule_fingerprint,
            ),
        ),
    )


def _m130_free_accrual(
    revision: ActivityAssetRevision,
    history: ActivityAssetHistory,
    *,
    period_end: date,
) -> M130ElementAccrual:
    """A free amount is the taxpayer's election, so only its recorded claims accrue."""
    claims = tuple(
        claim
        for claim in select_effective_claims(history.claims, tax_year=period_end.year, through=period_end)
        if claim.asset_id == revision.asset_id
    )
    accrued = tuple(claim for claim in claims if claim.amount > Decimal("0"))
    if accrued:
        return M130ElementAccrual(
            revision=revision,
            outcome=M130ElementOutcome.ACCRUED,
            contributions=tuple(
                M130Contribution(asset_id=revision.asset_id, amount=claim.amount, claim_id=claim.claim_id)
                for claim in accrued
            ),
        )
    if claims:
        return M130ElementAccrual(revision=revision, outcome=M130ElementOutcome.NOTHING)
    if free_base_remains(revision, history, tax_year=period_end.year):
        return M130ElementAccrual(revision=revision, outcome=M130ElementOutcome.FREE_GAP)
    return M130ElementAccrual(revision=revision, outcome=M130ElementOutcome.NOTHING)


def free_base_remains(revision: ActivityAssetRevision, history: ActivityAssetHistory, *, tax_year: int) -> bool:
    """Say whether a free-method element still has basis after opening history and claims up to ``tax_year``."""
    if revision.opening_history.status is OpeningHistoryStatus.MISSING:
        return True
    summary = asset_schedule_history(
        claims_through_year(history.claims, tax_year),
        history.revisions,
        asset_id=revision.asset_id,
        tax_year=tax_year,
    )
    opening = revision.opening_history.accumulated_amount or Decimal("0")
    consumed = opening + summary.accumulated_before_tax_year + summary.accumulated_in_tax_year
    return revision.amortizable_ceiling() > consumed


__all__ = [
    "M130Contribution",
    "M130ElementAccrual",
    "M130ElementOutcome",
    "PlanFigureAbsence",
    "WalkedYear",
    "free_base_remains",
    "m130_register_accruals",
    "walk_element",
]

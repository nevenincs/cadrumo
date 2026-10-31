"""Build the register's read models from history, the one schedule route and the ledger."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ...core.money.rounding import round_to_cents
from ...domain.calculations.registry.actividad_asset_form_options import ActivityAssetFormOptions
from ...domain.calculations.registry.errors import RegistryError
from ...domain.renta.actividad_asset.claims import (
    AmortizationClaim,
    ClaimCoverageGap,
    asset_schedule_history,
    current_revisions,
    effective_claims,
    last_day_covered,
)
from ...domain.renta.actividad_asset.disposal import ActivityAssetDisposalReason
from ...domain.renta.actividad_asset.election import FREE_AMOUNT_METHODS, AmortizationMethod, DirectEstimationRegime
from ...domain.renta.actividad_asset.election_facts import method_facts
from ...domain.renta.actividad_asset.errors import ActividadAssetError
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from ...domain.renta.actividad_asset.schedule import (
    AssetScheduleHistory,
    ScheduleAuthority,
    add_years,
    require_method_continuity,
)
from ..operations.public_scalar import PublicDecimal, project_scalar
from .activity_asset_read_models import (
    ActivityAssetClaimableInterval,
    ActivityAssetClaimStaleReason,
    ActivityAssetClaimState,
    ActivityAssetEdition,
    ActivityAssetElectionLimits,
    ActivityAssetFindingCounts,
    ActivityAssetListDisposal,
    ActivityAssetListRow,
    ActivityAssetMethodFact,
    ActivityAssetMethodFacts,
    ActivityAssetNotTableBoundReason,
    ActivityAssetPlanClaim,
    ActivityAssetPlanRow,
    ActivityAssetReasonFact,
    ActivityAssetRegisterState,
    activity_asset_label_key,
    project_reason_facts,
)
from .disposal_calculation import DisposalBoundsReader, year_minimum
from .fact_wording import token_family
from .history import ActivityAssetHistory
from .legal_citations import ResolvedLegalCitations
from .ports import ActivityAssetForecastOperation
from .schedule_walk import PlanFigureAbsence, WalkedYear, error_reason_facts, walk_element

_WALK_YEARS_LIMIT = 100
"""How far a plan looks ahead; every method settles long before this."""

_NOT_ACCRUING = frozenset({PlanFigureAbsence.PERIOD_ELAPSED, PlanFigureAbsence.BASIS_EXHAUSTED})
"""Absences meaning the element has nothing left, as distinct from a figure that cannot be worked out."""


def _amount(value: Decimal) -> PublicDecimal:
    return project_scalar(value)


def _optional_amount(value: Decimal | None) -> PublicDecimal | None:
    return None if value is None else _amount(value)


@dataclass(frozen=True, slots=True)
class RegisterReadContext:
    """What every read of one element needs."""

    history: ActivityAssetHistory
    forecast: ActivityAssetForecastOperation
    edition: Callable[[int], ActivityAssetEdition]
    admits_filing_year: Callable[[int], bool]
    last_admitted_year: int
    today: date
    minimum_bounds: DisposalBoundsReader
    class_labels: Callable[[DirectEstimationRegime, int], Mapping[str, str]]


def _walk_to_settlement(revision: ActivityAssetRevision, context: RegisterReadContext) -> tuple[WalkedYear, ...]:
    claim_years = [claim.tax_year for claim in context.history.claims if claim.asset_id == revision.asset_id]
    return walk_element(
        revision,
        context.history,
        forecast=context.forecast,
        through_year=revision.in_service_date.year + _WALK_YEARS_LIMIT,
        settled_after=max([context.today.year, *claim_years]),
    )


def _claimable(
    revision: ActivityAssetRevision,
    row: WalkedYear,
    history: ActivityAssetHistory,
) -> tuple[tuple[ActivityAssetClaimableInterval, ...], str | None, tuple[ActivityAssetReasonFact, ...]]:
    """Clip the year's gaps to what its charge covers, or say why nothing there can be claimed, and with which facts."""
    if row.absence in _NOT_ACCRUING or row.absence is PlanFigureAbsence.COVERED_BY_OPENING:
        return (), None, ()
    if row.absence is not None and row.absence is not PlanFigureAbsence.FREE_ELECTION:
        return (), row.reason_key, project_reason_facts(row.reason_facts)
    election = revision.amortization
    try:
        require_method_continuity(
            election.method,
            election.fingerprint,
            asset_schedule_history(
                history.claims,
                history.revisions,
                asset_id=revision.asset_id,
                tax_year=row.tax_year,
            ),
        )
    except ActividadAssetError as error:
        return (), error.translated_message, project_reason_facts(error_reason_facts(error))
    return _claimable_gaps(row), None, ()


def _claimable_gaps(row: WalkedYear) -> tuple[ActivityAssetClaimableInterval, ...]:
    start = row.charge.covered_from if row.charge is not None else date.min
    end = row.charge.covered_until if row.charge is not None else date.max
    intervals = tuple(
        _claimable_interval(max(gap.covered_from, start), min(gap.covered_until, end))
        for gap in row.gaps
        if max(gap.covered_from, start) < min(gap.covered_until, end) and not _gap_lies_on_a_claim(gap, row)
    )
    return intervals


def method_facts_view(method: AmortizationMethod) -> ActivityAssetMethodFacts:
    """Serve the facts an election of a method states, as the election model types them."""
    return ActivityAssetMethodFacts(
        method=method,
        facts=tuple(
            ActivityAssetMethodFact(
                path=fact.path,
                kind=fact.kind,
                required=fact.required,
                required_with_group=fact.required_with_group,
                token_family=None if fact.tokens is None else token_family(fact.tokens),
                tokens=() if fact.tokens is None else tuple(member.value for member in fact.tokens),
            )
            for fact in method_facts(method)
        ),
    )


def _claimable_interval(covered_from: date, covered_until: date) -> ActivityAssetClaimableInterval:
    return ActivityAssetClaimableInterval(
        covered_from=covered_from,
        covered_until=covered_until,
        covered_through=last_day_covered(covered_until),
    )


def _gap_lies_on_a_claim(gap: ClaimCoverageGap, row: WalkedYear) -> bool:
    """Say whether a gap is a zero claim's interval, which a correction supersedes and a new claim cannot take."""
    return any(
        claim.covered_from < gap.covered_until and gap.covered_from < claim.covered_until for claim in row.claims
    )


def _claim_state(
    row: WalkedYear,
    intervals: tuple[ActivityAssetClaimableInterval, ...],
    *,
    today: date,
) -> ActivityAssetClaimState:
    if not row.claims:
        return _unclaimed_state(row, today=today)
    if (
        intervals
        or any(_gap_lies_on_a_claim(gap, row) for gap in row.gaps)
        or (row.gaps and row.charge is None and row.absence is not PlanFigureAbsence.PERIOD_ELAPSED)
    ):
        return ActivityAssetClaimState.PARTIAL
    if any(claim.supersedes_claim_id is not None for claim in row.claims):
        return ActivityAssetClaimState.SUPERSEDED
    return ActivityAssetClaimState.CLAIMED


def _unclaimed_state(row: WalkedYear, *, today: date) -> ActivityAssetClaimState:
    if row.absence in _NOT_ACCRUING or row.absence is PlanFigureAbsence.COVERED_BY_OPENING:
        return ActivityAssetClaimState.NOT_DUE
    if row.tax_year > today.year:
        return ActivityAssetClaimState.NOT_DUE
    if row.absence is PlanFigureAbsence.EDITION_UNAVAILABLE:
        return ActivityAssetClaimState.EDITION_UNAVAILABLE
    return ActivityAssetClaimState.MISSING


def _plan_claims(
    revision: ActivityAssetRevision, tax_year: int, context: RegisterReadContext
) -> tuple[ActivityAssetPlanClaim, ...]:
    claims = context.history.claims
    superseded_by = {
        claim.supersedes_claim_id: claim.claim_id for claim in claims if claim.supersedes_claim_id is not None
    }
    return tuple(
        _plan_claim(claim, superseded_by, matches_current_schedule(claim, revision, context))
        for claim in claims
        if claim.asset_id == revision.asset_id and claim.tax_year == tax_year
    )


def _plan_claim(
    claim: AmortizationClaim, superseded_by: Mapping[str, str], stale: ActivityAssetClaimStaleReason | None
) -> ActivityAssetPlanClaim:
    return ActivityAssetPlanClaim(
        claim_id=claim.claim_id,
        amount=_amount(claim.amount),
        covered_from=claim.covered_from,
        covered_until=claim.covered_until,
        covered_through=last_day_covered(claim.covered_until),
        effective=claim.claim_id not in superseded_by,
        superseded_by=superseded_by.get(claim.claim_id),
        revision_id=claim.asset_revision_id,
        matches_current_schedule=stale is None,
        stale_reason=stale,
    )


def element_plan(revision: ActivityAssetRevision, context: RegisterReadContext) -> tuple[ActivityAssetPlanRow, ...]:
    """Work out one element's plan, one row per tax year until it settles.

    Returns:
        The rows in year order.  A year with no figure carries its typed reason.
    """
    rows: list[ActivityAssetPlanRow] = []
    boundary = date.max if revision.disposal is None else revision.disposal.boundary
    basis = revision.amortizable_ceiling()
    minimum = Decimal("0")
    minimum_complete = True
    for row in _walk_to_settlement(revision, context):
        intervals, refusal_key, refusal_facts = _claimable(revision, row, context.history)
        year = year_minimum(
            revision,
            tax_year=row.tax_year,
            boundary=boundary,
            bounds=context.minimum_bounds(revision, row.tax_year),
        )
        minimum_complete = minimum_complete and year is not None
        minimum += year or Decimal("0")
        rows.append(
            ActivityAssetPlanRow(
                tax_year=row.tax_year,
                method=revision.amortization.method,
                coefficient=_optional_amount(None if row.charge is None else row.charge.annual_rate),
                planned=_amount(row.charge.amount) if row.charge is not None and row.absence is None else None,
                absence=row.absence,
                absence_reason_key=row.reason_key,
                absence_reason_facts=project_reason_facts(row.reason_facts),
                claimed=_amount(row.claimed),
                claim_state=_claim_state(row, intervals, today=context.today),
                claimable_intervals=intervals,
                claimable_refusal_key=refusal_key,
                claimable_refusal_facts=refusal_facts,
                edition=_edition_or_none(context, row.tax_year),
                service_days=None if row.charge is None else row.charge.service_days,
                calendar_days=None if row.charge is None else row.charge.calendar_days,
                claims=_plan_claims(revision, row.tax_year, context),
                minimum_through=_amount(min(basis, round_to_cents(minimum))),
                minimum_complete=minimum_complete,
            ),
        )
    return tuple(rows)


_NOT_TABLE_BOUND = {
    AmortizationMethod.GOODWILL: ActivityAssetNotTableBoundReason.TWENTIETH_LIMIT,
    AmortizationMethod.INTANGIBLE_INDEFINITE_LIFE: ActivityAssetNotTableBoundReason.TWENTIETH_LIMIT,
    AmortizationMethod.INTANGIBLE_USEFUL_LIFE: ActivityAssetNotTableBoundReason.USEFUL_LIFE_EVIDENCE,
    AmortizationMethod.APPROVED_PLAN: ActivityAssetNotTableBoundReason.APPROVED_PLAN,
    AmortizationMethod.RESEARCH_DEVELOPMENT_BUILDING: ActivityAssetNotTableBoundReason.RESEARCH_DEVELOPMENT_PERIOD,
}
"""The methods whose limit is not the amortization table; every other non-table method elects its amount."""

_TABLE_METHODS = frozenset(
    {AmortizationMethod.LINEAR, AmortizationMethod.CONSTANT_PERCENTAGE, AmortizationMethod.SUM_OF_DIGITS},
)


def election_limits(
    revision: ActivityAssetRevision,
    authority: ScheduleAuthority,
    options: ActivityAssetFormOptions,
    citations: ResolvedLegalCitations,
) -> ActivityAssetElectionLimits:
    """State what the registry allows this election, from the authority its charges rest on.

    Returns:
        The class and corridor of a table method, else the limit that replaces them
        and the typed reason, with the citations resolved for the authority.
    """
    election = revision.amortization
    ends_on = authority.maximum_period_ends_on or authority.useful_life_ends_on
    if authority.sum_of_digits_period_years is not None:
        ends_on = add_years(revision.in_service_date, authority.sum_of_digits_period_years)
    if election.method not in _TABLE_METHODS:
        twentieth = _NOT_TABLE_BOUND.get(election.method) is ActivityAssetNotTableBoundReason.TWENTIETH_LIMIT
        return ActivityAssetElectionLimits(
            class_key=election.authority_class_key,
            class_label=(
                None if election.authority_class_key is None else options.class_labels.get(election.authority_class_key)
            ),
            maximum_coefficient=_optional_amount(authority.annual_rate if twentieth else None),
            maximum_period_ends_on=ends_on,
            legal_citations=citations.citations,
            legal_citations_complete=citations.complete,
            not_table_bound=_NOT_TABLE_BOUND.get(election.method, ActivityAssetNotTableBoundReason.FREE_ELECTION),
        )
    group = next(item for item in options.table_groups if item.class_key == election.authority_class_key)
    return ActivityAssetElectionLimits(
        class_key=group.class_key,
        class_label=group.class_label,
        maximum_coefficient=_amount(group.maximum_coefficient),
        minimum_coefficient=_amount(group.minimum_coefficient),
        maximum_period_years=_amount(group.maximum_period_years),
        maximum_period_ends_on=ends_on,
        legal_citations=citations.citations,
        legal_citations_complete=citations.complete,
    )


def _edition_or_none(context: RegisterReadContext, tax_year: int) -> ActivityAssetEdition | None:
    try:
        return context.edition(tax_year)
    except RegistryError:
        return None


def _history_before_claim(claim: AmortizationClaim, history: ActivityAssetHistory) -> AssetScheduleHistory:
    """Summarise what a claim's charge rested on: everything recorded for time before it."""
    return asset_schedule_history(
        tuple(
            item
            for item in history.claims
            if item.tax_year < claim.tax_year
            or (item.tax_year == claim.tax_year and item.covered_from < claim.covered_from)
        ),
        history.revisions,
        asset_id=claim.asset_id,
        tax_year=claim.tax_year,
    )


def matches_current_schedule(
    claim: AmortizationClaim,
    current: ActivityAssetRevision,
    context: RegisterReadContext,
) -> ActivityAssetClaimStaleReason | None:
    """Compare a claim's fingerprint with what the current revision and authority would stamp."""
    if claim.disposal_revision_id is not None and claim.amount == Decimal("0"):
        return None
    recorded_under = next(item for item in context.history.revisions if item.revision_id == claim.asset_revision_id)
    if not recorded_under.same_tax_facts(current):
        return ActivityAssetClaimStaleReason.REVISION_CHANGED
    try:
        charge = context.forecast(
            current,
            covered_from=claim.covered_from,
            covered_until=claim.covered_until,
            history=_history_before_claim(claim, context.history),
            requested_free_amount=claim.amount if current.amortization.method in FREE_AMOUNT_METHODS else None,
        )
    except (ActividadAssetError, RegistryError):
        return ActivityAssetClaimStaleReason.SCHEDULE_UNAVAILABLE
    if charge.schedule_fingerprint != claim.schedule_fingerprint:
        return ActivityAssetClaimStaleReason.AUTHORITY_CHANGED
    return None


def element_list(context: RegisterReadContext) -> tuple[ActivityAssetListRow, ...]:
    """Summarise every element of the register, in asset order.

    Returns:
        One row per element.  ``accumulated`` is the opening amount plus effective
        claims; ``pending`` is the basis less that, whatever the schedule's state, so
        an unclaimed year still shows in it.
    """
    current = current_revisions(context.history.revisions)
    return tuple(_list_row(current[asset_id], context) for asset_id in sorted(current))


def register_years(rows: Iterable[ActivityAssetListRow]) -> tuple[int, ...]:
    """Name every tax year some element can be read in, in ascending order."""
    return tuple(sorted({year for row in rows for year in row.years}))


def _list_row(revision: ActivityAssetRevision, context: RegisterReadContext) -> ActivityAssetListRow:
    plan = element_plan(revision, context)
    claims = _effective_asset_claims(context.history.claims, revision.asset_id)
    opening = revision.opening_history.accumulated_amount
    accumulated = None if opening is None else opening + sum((claim.amount for claim in claims), Decimal("0"))
    basis = revision.amortizable_ceiling()
    pending = None if accumulated is None else max(basis - accumulated, Decimal("0"))
    descriptor = context.history.current_descriptor(revision.asset_id)
    readable = _readable_years(plan, context)
    return ActivityAssetListRow(
        asset_id=revision.asset_id,
        name=None if descriptor is None else descriptor.facts.name,
        serial_number=None if descriptor is None else descriptor.facts.serial_number,
        asset_kind=revision.asset_kind,
        state=_register_state(revision, pending, plan, today=context.today),
        in_service_date=revision.in_service_date,
        method=revision.amortization.method,
        revision_number=revision.revision_number,
        basis=_amount(basis),
        accumulated=_optional_amount(accumulated),
        pending=_optional_amount(pending),
        findings=_finding_counts(plan, claims, revision, context),
        years=tuple(year for year in readable if year <= context.last_admitted_year),
        projected_years=tuple(year for year in readable if year > context.last_admitted_year),
        disposal=_list_disposal(revision),
    )


def _effective_asset_claims(claims: tuple[AmortizationClaim, ...], asset_id: str) -> tuple[AmortizationClaim, ...]:
    return tuple(claim for claim in effective_claims(claims) if claim.asset_id == asset_id)


def _readable_years(plan: tuple[ActivityAssetPlanRow, ...], context: RegisterReadContext) -> tuple[int, ...]:
    return tuple(row.tax_year for row in plan if context.admits_filing_year(row.tax_year))


def _list_disposal(revision: ActivityAssetRevision) -> ActivityAssetListDisposal | None:
    disposal = revision.disposal
    if disposal is None:
        return None
    return ActivityAssetListDisposal(
        disposal_date=disposal.disposal_date,
        reason=disposal.reason,
        reason_key=activity_asset_label_key(token_family(ActivityAssetDisposalReason), disposal.reason),
    )


def _finding_counts(
    plan: tuple[ActivityAssetPlanRow, ...],
    claims: tuple[AmortizationClaim, ...],
    revision: ActivityAssetRevision,
    context: RegisterReadContext,
) -> ActivityAssetFindingCounts:
    return ActivityAssetFindingCounts(
        missing=sum(
            row.claim_state in {ActivityAssetClaimState.MISSING, ActivityAssetClaimState.PARTIAL} for row in plan
        ),
        incomplete=sum(row.absence is PlanFigureAbsence.INCOMPLETE for row in plan),
        conflict=sum(row.absence in {PlanFigureAbsence.CONFLICT, PlanFigureAbsence.UNSUPPORTED} for row in plan),
        stale=sum(matches_current_schedule(claim, revision, context) is not None for claim in claims),
    )


def _register_state(
    revision: ActivityAssetRevision,
    pending: Decimal | None,
    plan: tuple[ActivityAssetPlanRow, ...],
    *,
    today: date,
) -> ActivityAssetRegisterState:
    """Name the element's standing; a schedule that ended over unclaimed years has not amortized it."""
    if _left_service(revision, today):
        return ActivityAssetRegisterState.OUT_OF_SERVICE
    if pending is not None and pending <= Decimal("0"):
        return ActivityAssetRegisterState.FULLY_AMORTIZED
    schedule_ended = any(row.absence in _NOT_ACCRUING and row.tax_year <= today.year for row in plan)
    unclaimed = any(
        row.claim_state in {ActivityAssetClaimState.MISSING, ActivityAssetClaimState.PARTIAL} for row in plan
    )
    return (
        ActivityAssetRegisterState.FULLY_AMORTIZED
        if schedule_ended and not unclaimed
        else ActivityAssetRegisterState.IN_SERVICE
    )


def _left_service(revision: ActivityAssetRevision, today: date) -> bool:
    return revision.disposal is not None and revision.disposal.boundary <= today


__all__ = [
    "RegisterReadContext",
    "election_limits",
    "element_list",
    "element_plan",
    "method_facts_view",
    "register_years",
]

"""Build the register's read models from history, the one schedule route and the ledger."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from ...core.external_constants import DEFAULT_CURRENCY
from ...core.money.rounding import round_to_cents
from ...domain.calculations.registry.errors import RegistryError
from ...domain.calculations.registry.prorrata_vocabulary import resolve_input_classification_definition
from ...domain.renta.actividad_asset.claims import (
    AmortizationClaim,
    asset_schedule_history,
    current_revisions,
    effective_claims,
)
from ...domain.renta.actividad_asset.election import FREE_AMOUNT_METHODS
from ...domain.renta.actividad_asset.errors import ActividadAssetError
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from ...domain.renta.actividad_asset.register_records import ActivityAssetEventKind
from ...domain.renta.actividad_asset.schedule import AssetScheduleHistory, require_method_continuity
from ...domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ...domain.transactions.models import Transaction, TransactionCatalogue
from ..operations.public_scalar import PublicDecimal, project_scalar
from .activity_asset_read_models import (
    ActivityAssetAcquisitionCandidate,
    ActivityAssetClaimableInterval,
    ActivityAssetClaimStaleReason,
    ActivityAssetClaimState,
    ActivityAssetEdition,
    ActivityAssetFindingCounts,
    ActivityAssetListRow,
    ActivityAssetNonDeductibleIvaState,
    ActivityAssetPlanClaim,
    ActivityAssetPlanRow,
    ActivityAssetRegisterState,
    ActivityAssetTimelineChange,
    ActivityAssetTimelineClaimUse,
    ActivityAssetTimelineEvent,
    project_reason_facts,
)
from .history import ActivityAssetHistory
from .ports import ActivityAssetForecastOperation
from .schedule_walk import PlanFigureAbsence, WalkedYear, walk_element

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
    today: date


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
) -> tuple[tuple[ActivityAssetClaimableInterval, ...], str | None]:
    """Clip the year's gaps to what its charge covers, or say why nothing there can be claimed."""
    if row.absence in _NOT_ACCRUING:
        return (), None
    if row.absence is not None and row.absence is not PlanFigureAbsence.FREE_ELECTION:
        return (), row.reason_key
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
        return (), error.translated_message
    start = row.charge.covered_from if row.charge is not None else date.min
    end = row.charge.covered_until if row.charge is not None else date.max
    intervals = tuple(
        ActivityAssetClaimableInterval(
            covered_from=max(gap.covered_from, start),
            covered_until=min(gap.covered_until, end),
        )
        for gap in row.gaps
        if max(gap.covered_from, start) < min(gap.covered_until, end)
    )
    return intervals, None


def _claim_state(
    row: WalkedYear,
    intervals: tuple[ActivityAssetClaimableInterval, ...],
    *,
    today: date,
) -> ActivityAssetClaimState:
    if not row.claims:
        if row.absence in _NOT_ACCRUING or row.tax_year > today.year:
            return ActivityAssetClaimState.NOT_DUE
        return ActivityAssetClaimState.MISSING
    if intervals or (row.gaps and row.charge is None and row.absence is not PlanFigureAbsence.PERIOD_ELAPSED):
        return ActivityAssetClaimState.PARTIAL
    if any(claim.supersedes_claim_id is not None for claim in row.claims):
        return ActivityAssetClaimState.SUPERSEDED
    return ActivityAssetClaimState.CLAIMED


def _plan_claims(
    asset_id: str, tax_year: int, claims: tuple[AmortizationClaim, ...]
) -> tuple[ActivityAssetPlanClaim, ...]:
    superseded_by = {
        claim.supersedes_claim_id: claim.claim_id for claim in claims if claim.supersedes_claim_id is not None
    }
    return tuple(
        ActivityAssetPlanClaim(
            claim_id=claim.claim_id,
            amount=_amount(claim.amount),
            covered_from=claim.covered_from,
            covered_until=claim.covered_until,
            effective=claim.claim_id not in superseded_by,
            superseded_by=superseded_by.get(claim.claim_id),
            revision_id=claim.asset_revision_id,
        )
        for claim in claims
        if claim.asset_id == asset_id and claim.tax_year == tax_year
    )


def element_plan(revision: ActivityAssetRevision, context: RegisterReadContext) -> tuple[ActivityAssetPlanRow, ...]:
    """Work out one element's plan, one row per tax year until it settles.

    Returns:
        The rows in year order.  A year with no figure carries its typed reason.
    """
    rows: list[ActivityAssetPlanRow] = []
    for row in _walk_to_settlement(revision, context):
        intervals, refusal_key = _claimable(revision, row, context.history)
        accruing = row.charge is not None and row.absence is None
        rows.append(
            ActivityAssetPlanRow(
                tax_year=row.tax_year,
                method=revision.amortization.method,
                coefficient=_optional_amount(None if row.charge is None else row.charge.annual_rate),
                planned=_amount(row.charge.amount) if accruing and row.charge is not None else None,
                absence=row.absence,
                absence_reason_key=row.reason_key,
                absence_reason_facts=project_reason_facts(row.reason_facts),
                claimed=_amount(row.claimed),
                claim_state=_claim_state(row, intervals, today=context.today),
                claimable_intervals=intervals,
                claimable_refusal_key=refusal_key,
                edition=_edition_or_none(context, row.tax_year),
                service_days=None if row.charge is None else row.charge.service_days,
                calendar_days=None if row.charge is None else row.charge.calendar_days,
                claims=_plan_claims(revision.asset_id, row.tax_year, context.history.claims),
            ),
        )
    return tuple(rows)


def _edition_or_none(context: RegisterReadContext, tax_year: int) -> ActivityAssetEdition | None:
    try:
        return context.edition(tax_year)
    except RegistryError:
        return None


def _matches_current_schedule(
    claim: AmortizationClaim,
    current: ActivityAssetRevision,
    context: RegisterReadContext,
) -> ActivityAssetClaimStaleReason | None:
    """Compare a claim's fingerprint with what the current revision and authority would stamp."""
    if claim.asset_revision_id != current.revision_id:
        return ActivityAssetClaimStaleReason.REVISION_CHANGED
    try:
        charge = context.forecast(
            current,
            covered_from=claim.covered_from,
            covered_until=claim.covered_until,
            history=AssetScheduleHistory(),
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
        claims; ``pending`` is the basis left, zero once the walk says nothing remains.
    """
    current = current_revisions(context.history.revisions)
    return tuple(_list_row(current[asset_id], context) for asset_id in sorted(current))


def _list_row(revision: ActivityAssetRevision, context: RegisterReadContext) -> ActivityAssetListRow:
    plan = element_plan(revision, context)
    claims = tuple(claim for claim in effective_claims(context.history.claims) if claim.asset_id == revision.asset_id)
    opening = revision.opening_history.accumulated_amount
    accumulated = None if opening is None else opening + sum((claim.amount for claim in claims), Decimal("0"))
    basis = round_to_cents(revision.amortizable_basis())
    settled = any(row.absence in _NOT_ACCRUING and row.tax_year <= context.today.year for row in plan)
    pending = None if accumulated is None else (Decimal("0.00") if settled else max(basis - accumulated, Decimal("0")))
    descriptor = context.history.current_descriptor(revision.asset_id)
    return ActivityAssetListRow(
        asset_id=revision.asset_id,
        name=None if descriptor is None else descriptor.facts.name,
        serial_number=None if descriptor is None else descriptor.facts.serial_number,
        asset_kind=revision.asset_kind,
        state=_register_state(revision, pending, today=context.today),
        in_service_date=revision.in_service_date,
        method=revision.amortization.method,
        revision_number=revision.revision_number,
        basis=_amount(basis),
        accumulated=_optional_amount(accumulated),
        pending=_optional_amount(pending),
        findings=ActivityAssetFindingCounts(
            missing=sum(
                row.claim_state in {ActivityAssetClaimState.MISSING, ActivityAssetClaimState.PARTIAL} for row in plan
            ),
            incomplete=sum(row.absence is PlanFigureAbsence.INCOMPLETE for row in plan),
            conflict=sum(row.absence in {PlanFigureAbsence.CONFLICT, PlanFigureAbsence.UNSUPPORTED} for row in plan),
            stale=sum(_matches_current_schedule(claim, revision, context) is not None for claim in claims),
        ),
    )


def _register_state(
    revision: ActivityAssetRevision,
    pending: Decimal | None,
    *,
    today: date,
) -> ActivityAssetRegisterState:
    if revision.out_of_service_date is not None and revision.out_of_service_date <= today:
        return ActivityAssetRegisterState.OUT_OF_SERVICE
    if pending is not None and pending <= Decimal("0"):
        return ActivityAssetRegisterState.FULLY_AMORTIZED
    return ActivityAssetRegisterState.IN_SERVICE


def _flatten(value: object, prefix: str = "") -> dict[str, str | None]:
    if isinstance(value, Mapping):
        flat: dict[str, str | None] = {}
        for name, item in value.items():
            flat.update(_flatten(item, f"{prefix}.{name}" if prefix else str(name)))
        return flat
    if isinstance(value, list | tuple):
        return {prefix: None if not value else ", ".join(str(item) for item in value)}
    return {prefix: None if value is None else str(value)}


def _changes(
    before: BaseModel | None,
    after: BaseModel,
    *,
    excluding: frozenset[str] = frozenset(),
) -> tuple[ActivityAssetTimelineChange, ...]:
    old = {} if before is None else _flatten(before.model_dump(mode="json", exclude=set(excluding)))
    new = _flatten(after.model_dump(mode="json", exclude=set(excluding)))
    return tuple(
        ActivityAssetTimelineChange(field=name, before=old.get(name), after=new.get(name))
        for name in sorted({*old, *new})
        if old.get(name) != new.get(name)
    )


_REVISION_LINK_FIELDS = frozenset({"asset_id", "revision_number", "supersedes_revision_id"})
"""A revision's place in its chain, which the timeline's order already states."""


def element_timeline(
    asset_id: str,
    context: RegisterReadContext,
    *,
    used_by: Mapping[str, tuple[str, ...]],
) -> tuple[ActivityAssetTimelineEvent, ...]:
    """List one element's records in history order, each with what it changed.

    Returns:
        One event per record.  A claim also says what consumed it and whether it
        still matches the current schedule.
    """
    history = context.history
    revisions = {item.revision_id: item for item in history.revisions}
    claims = {item.claim_id: item for item in history.claims}
    descriptors = {item.descriptor_id: item for item in history.descriptors}
    current = current_revisions(history.revisions)[asset_id]
    timeline: list[ActivityAssetTimelineEvent] = []
    for event in history.ordered_events():
        if event.asset_id != asset_id:
            continue
        effect_date: date | None = None
        changes: tuple[ActivityAssetTimelineChange, ...]
        claim_use: ActivityAssetTimelineClaimUse | None = None
        if event.kind is ActivityAssetEventKind.REVISION:
            revision = revisions[event.record_id]
            previous = revisions.get(revision.supersedes_revision_id or "")
            changes = _changes(previous, revision, excluding=_REVISION_LINK_FIELDS)
            effect_date = revision.in_service_date
        elif event.kind is ActivityAssetEventKind.CLAIM:
            claim = claims[event.record_id]
            replaced = claims.get(claim.supersedes_claim_id or "")
            changes = (
                ActivityAssetTimelineChange(
                    field="amount",
                    before=None if replaced is None else str(replaced.amount),
                    after=str(claim.amount),
                ),
            )
            effect_date = claim.covered_from
            stale = _matches_current_schedule(claim, current, context)
            claim_use = ActivityAssetTimelineClaimUse(
                used_by=used_by.get(claim.claim_id, ()),
                matches_current_schedule=stale is None,
                stale_reason=stale,
            )
        else:
            descriptor = descriptors[event.record_id]
            earlier = next(
                (
                    item
                    for item in history.descriptors
                    if item.asset_id == asset_id and item.descriptor_number == descriptor.descriptor_number - 1
                ),
                None,
            )
            changes = _changes(None if earlier is None else earlier.facts, descriptor.facts)
        timeline.append(
            ActivityAssetTimelineEvent(
                sequence=event.sequence,
                recorded_at=event.recorded_at,
                kind=event.kind,
                asset_id=asset_id,
                record_id=event.record_id,
                effect_date=effect_date,
                origin=event.origin,
                changes=changes,
                affects_calculation=event.kind is not ActivityAssetEventKind.DESCRIPTOR,
                claim=claim_use,
            ),
        )
    return tuple(timeline)


def acquisition_candidates(
    catalogue: TransactionCatalogue,
    history: ActivityAssetHistory,
) -> tuple[ActivityAssetAcquisitionCandidate, ...]:
    """List the business payments no element names as its acquisition yet, newest first.

    Returns:
        One candidate per row.  What the ledger does not know is null, never zero.
    """
    owned = {revision.acquisition.observed_transaction_id for revision in current_revisions(history.revisions).values()}
    rows = (
        row
        for row in catalogue.transactions.values()
        if row.direction is TransactionDirection.OUTGOING
        and row.lifecycle_state is TransactionLifecycleState.ACTIVE
        and row.business_classification in {BusinessClassification.BUSINESS, BusinessClassification.MIXED}
        and row.transaction_id not in owned
    )
    return tuple(
        _candidate(row)
        for row in sorted(rows, key=lambda item: (item.raw.booked_date, item.transaction_id), reverse=True)
    )


def _non_deductible_iva(row: Transaction) -> Decimal | None:
    """Read the row's non-deductible IVA from its classification; anything else stays unknown."""
    if row.iva_amount is None or row.input_classification is None or row.raw.currency != DEFAULT_CURRENCY:
        return None
    definition = resolve_input_classification_definition(row.input_classification)
    if definition.uses_general_percentage or definition.deductible_percentage is None:
        return None
    if definition.deductible_percentage == Decimal("100"):
        return Decimal("0.00")
    if definition.deductible_percentage == Decimal("0"):
        return row.iva_amount
    return None


def _candidate(row: Transaction) -> ActivityAssetAcquisitionCandidate:
    non_deductible = _non_deductible_iva(row)
    evidence_id = row.purchase_invoice_evidence_id
    paid = row.raw.amount if row.raw.currency == DEFAULT_CURRENCY else row.value_in_eur
    return ActivityAssetAcquisitionCandidate(
        transaction_id=row.transaction_id,
        booked_date=row.raw.booked_date,
        description=row.raw.description,
        amount=_amount(row.raw.amount),
        currency=row.raw.currency,
        paid_in_euro=_optional_amount(paid),
        taxable_base=_optional_amount(row.taxable_base),
        iva_amount=_optional_amount(row.iva_amount),
        non_deductible_iva_state=(
            ActivityAssetNonDeductibleIvaState.UNKNOWN
            if non_deductible is None
            else ActivityAssetNonDeductibleIvaState.KNOWN
        ),
        non_deductible_iva=_optional_amount(non_deductible),
        invoice_evidence_id=evidence_id,
        evidence_fingerprint=evidence_id if _is_digest(evidence_id) else None,
    )


def _is_digest(value: str | None) -> bool:
    return value is not None and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


__all__ = [
    "RegisterReadContext",
    "acquisition_candidates",
    "element_list",
    "element_plan",
    "element_timeline",
]

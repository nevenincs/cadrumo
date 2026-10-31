"""Timeline projections for activity-asset history."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date

from pydantic import BaseModel

from ...core.type_guards import is_object_list_or_tuple, is_object_mapping
from ...domain.calculations.registry.errors import RegistryError
from ...domain.renta.actividad_asset.claims import (
    AmortizationClaim,
    current_revisions,
    effective_claims,
)
from ...domain.renta.actividad_asset.election import DirectEstimationRegime
from ...domain.renta.actividad_asset.errors import ActividadAssetError
from ...domain.renta.actividad_asset.fact_leaves import FactKind, indexed_to_step_path
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from ...domain.renta.actividad_asset.register_records import ActivityAssetDescriptor, ActivityAssetEventKind
from ...domain.renta.actividad_asset.schedule import last_day_covered
from .activity_asset_read_models import (
    TIMELINE_INTERNAL_FIELDS,
    TIMELINE_LABELLED_FIELDS,
    ActivityAssetTimelineChange,
    ActivityAssetTimelineClaimUse,
    ActivityAssetTimelineEvent,
    ActivityAssetTimelineEventKind,
    timeline_field_key,
    timeline_token_key,
)
from .fact_wording import CLAIM_AMOUNT_PATH, ActivityAssetFlag, share_label
from .history import ActivityAssetHistory
from .register_reads import RegisterReadContext, matches_current_schedule


def _flatten(value: object, prefix: str = "") -> dict[str, str | None]:
    """Flatten a dumped record into dotted fields; a repeated row is named by its position."""
    if is_object_mapping(value):
        flat: dict[str, str | None] = {}
        for name, item in value.items():
            flat.update(_flatten(item, f"{prefix}.{name}" if prefix else str(name)))
        return flat
    if is_object_list_or_tuple(value):
        items = tuple(value)
        if not items:
            return {prefix: None}
        flat = {}
        for position, item in enumerate(items):
            flat.update(_flatten(item, f"{prefix}[{position}]"))
        return flat
    if isinstance(value, bool):
        return {prefix: ActivityAssetFlag(str(value).lower()).value}
    return {prefix: None if value is None else str(value)}


ClassNames = Callable[[BaseModel], Mapping[str, str]]
"""Reads the official names of the table classes a record's modality and year publish."""


def _changed_value_label(field: str, value: str | None, names: Mapping[str, str]) -> str | None:
    """Word a changed value that is a share or a table class, or return ``None`` for any other."""
    if value is None:
        return None
    kind = TIMELINE_LABELLED_FIELDS.get(indexed_to_step_path(field))
    if kind is FactKind.SHARE:
        return share_label(value)
    if kind is FactKind.CLASS:
        return names.get(value)
    return None


def _changes(
    before: BaseModel | None,
    after: BaseModel,
    *,
    class_names: ClassNames,
) -> tuple[ActivityAssetTimelineChange, ...]:
    old = {} if before is None else _flatten(before.model_dump(mode="json"))
    new = _flatten(after.model_dump(mode="json"))
    old_names: Mapping[str, str] = dict[str, str]() if before is None else class_names(before)
    new_names = class_names(after)
    return tuple(
        ActivityAssetTimelineChange(
            field=name,
            field_key=timeline_field_key(name),
            before=old.get(name),
            after=new.get(name),
            before_key=timeline_token_key(name, old.get(name)),
            after_key=timeline_token_key(name, new.get(name)),
            before_label=_changed_value_label(name, old.get(name), old_names),
            after_label=_changed_value_label(name, new.get(name), new_names),
        )
        for name in sorted({*old, *new})
        if old.get(name) != new.get(name) and indexed_to_step_path(name) not in TIMELINE_INTERNAL_FIELDS
    )


def _class_names_reader(context: RegisterReadContext) -> ClassNames:
    """Read the table class names of a revision's modality, under the year the plan limits read."""
    cache: dict[tuple[DirectEstimationRegime, int], Mapping[str, str]] = {}

    def names(record: BaseModel) -> Mapping[str, str]:
        if not isinstance(record, ActivityAssetRevision):
            return dict[str, str]()
        regime = record.amortization.regime
        tax_year = max(context.today.year, record.in_service_date.year)
        if (regime, tax_year) not in cache:
            try:
                cache[regime, tax_year] = context.class_labels(regime, tax_year)
            except (ActividadAssetError, RegistryError):
                cache[regime, tax_year] = {}
        return cache[regime, tax_year]

    return names


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
    class_names = _class_names_reader(context)
    effective = effective_claims(history.claims)
    timeline: list[ActivityAssetTimelineEvent] = []
    for event in history.ordered_events():
        if event.asset_id != asset_id:
            continue
        effect_date: date | None = None
        event_kind: ActivityAssetTimelineEventKind
        changes: tuple[ActivityAssetTimelineChange, ...]
        claim_use: ActivityAssetTimelineClaimUse | None = None
        if event.kind in {ActivityAssetEventKind.REVISION, ActivityAssetEventKind.BAJA}:
            revision = revisions[event.record_id]
            previous = revisions.get(revision.supersedes_revision_id or "")
            changes = _changes(previous, revision, class_names=class_names)
            event_kind, effect_date = _revision_event(revision, previous)
        elif event.kind is ActivityAssetEventKind.CLAIM:
            claim = claims[event.record_id]
            replaced = claims.get(claim.supersedes_claim_id or "")
            changes = _timeline_claim_changes(claim, replaced)
            effect_date = claim.covered_from
            event_kind = (
                ActivityAssetTimelineEventKind.CLAIM_REPLACED
                if replaced is not None
                else ActivityAssetTimelineEventKind.CLAIM_RECORDED
            )
            stale = matches_current_schedule(claim, current, context)
            claim_use = ActivityAssetTimelineClaimUse(
                used_by=used_by.get(claim.claim_id, ()),
                matches_current_schedule=stale is None,
                stale_reason=stale,
                in_effect=claim in effective,
                tax_year=claim.tax_year,
                covered_from=claim.covered_from,
                covered_through=last_day_covered(claim.covered_until),
            )
        else:
            event_kind = ActivityAssetTimelineEventKind.DESCRIBED
            descriptor = descriptors[event.record_id]
            changes = _descriptor_changes(descriptor, history, asset_id=asset_id, class_names=class_names)
        timeline.append(
            ActivityAssetTimelineEvent(
                sequence=event.sequence,
                recorded_at=event.recorded_at,
                kind=event.kind,
                event_kind=event_kind,
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


def _revision_event(
    revision: ActivityAssetRevision, previous: ActivityAssetRevision | None
) -> tuple[ActivityAssetTimelineEventKind, date]:
    """Say what a revision did and the day it takes effect.

    A baja takes effect on its date, and removing one on the date it had; any other revision on the
    day the element entered service.
    """
    if previous is None:
        return ActivityAssetTimelineEventKind.CREATED, revision.in_service_date
    if revision.disposal is not None and revision.disposal != previous.disposal:
        kind = (
            ActivityAssetTimelineEventKind.BAJA_RECORDED
            if previous.disposal is None
            else ActivityAssetTimelineEventKind.BAJA_CHANGED
        )
        return kind, revision.disposal.disposal_date
    if revision.disposal is None and previous.disposal is not None:
        return ActivityAssetTimelineEventKind.BAJA_REMOVED, previous.disposal.disposal_date
    return ActivityAssetTimelineEventKind.CORRECTED, revision.in_service_date


def _timeline_claim_changes(
    claim: AmortizationClaim, replaced: AmortizationClaim | None
) -> tuple[ActivityAssetTimelineChange, ...]:
    return (
        ActivityAssetTimelineChange(
            field=CLAIM_AMOUNT_PATH,
            field_key=timeline_field_key(CLAIM_AMOUNT_PATH),
            before=None if replaced is None else str(replaced.amount),
            after=str(claim.amount),
        ),
    )


def _descriptor_changes(
    descriptor: ActivityAssetDescriptor,
    history: ActivityAssetHistory,
    *,
    asset_id: str,
    class_names: ClassNames,
) -> tuple[ActivityAssetTimelineChange, ...]:
    earlier = next(
        (
            item
            for item in history.descriptors
            if item.asset_id == asset_id and item.descriptor_number == descriptor.descriptor_number - 1
        ),
        None,
    )
    return _changes(None if earlier is None else earlier.facts, descriptor.facts, class_names=class_names)

"""Collect the complete legal/source reference closure for one registry snapshot."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from .schema import ModeloDefinition, ModeloRevision
from .schema_surfaces import CasillaDefinition


class _GroundedRecord(Protocol):
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]


def _collect_grounded_record_refs(
    records: Iterable[_GroundedRecord],
    *,
    legal_ids: set[str],
    source_ids: set[str],
) -> None:
    for record in records:
        legal_ids.update(record.legal_refs)
        source_ids.update(record.source_refs)
        if not isinstance(record, CasillaDefinition):
            continue
        if record.constraints is not None:
            legal_ids.update(record.constraints.legal_refs)
            source_ids.update(record.constraints.source_refs)
        for alias in record.aliases:
            legal_ids.update(alias.legal_refs)
            source_ids.update(alias.source_refs)


def _collect_cross_reference_predicate_refs(
    revision: ModeloRevision,
    *,
    legal_ids: set[str],
    source_ids: set[str],
) -> None:
    for cross_reference in revision.live_cross_references:
        for predicate in cross_reference.applicability_predicates:
            legal_ids.update(predicate.legal_refs)
            source_ids.update(predicate.source_refs)


def _collect_export_layout_refs(
    revision: ModeloRevision,
    *,
    legal_ids: set[str],
    source_ids: set[str],
) -> None:
    for layout in revision.export_layouts:
        legal_ids.update(layout.legal_refs)
        source_ids.update(layout.source_refs)
        for export_record in layout.records:
            for field in export_record.fields:
                legal_ids.update(field.legal_refs)
                source_ids.update(field.source_refs)


def _collect_deadline_schedule_refs(
    revision: ModeloRevision,
    *,
    legal_ids: set[str],
    source_ids: set[str],
    include_deadline_windows: bool = True,
) -> None:
    if include_deadline_windows:
        for window in revision.deadline_windows:
            legal_ids.update(window.legal_refs)
            source_ids.update(window.source_refs)
            for condition in window.applicability_conditions:
                legal_ids.update(condition.legal_refs)
                source_ids.update(condition.source_refs)
    for schedule in revision.filing_schedules:
        legal_ids.update(schedule.legal_refs)
        source_ids.update(schedule.source_refs)
        for condition in schedule.profile_conditions:
            legal_ids.update(condition.legal_refs)
            source_ids.update(condition.source_refs)


def collect_snapshot_ref_ids(
    modelo: ModeloDefinition,
    revision: ModeloRevision,
    *,
    include_deadline_windows: bool = True,
    include_constructs: bool = True,
    include_parameters: bool = True,
    include_historical_continuity: bool = True,
) -> tuple[set[str], set[str]]:
    """Walk every record kind and return its (legal_ids, source_ids) pair.

    The snapshot's ``legal`` / ``sources`` mappings carry only the
    refs actually exercised by the slice — this helper aggregates the
    every-record-kind union the calculation-grounding rule mandates
    (legal_refs + source_refs preserved through every domain
    boundary). Flat records share one walk; nesting record
    kinds carry
    their own explicit blocks because they nest inner records that
    also carry refs.

    Takes ``modelo`` as a :class:`ModeloDefinition` and ``revision`` as a :class:`ModeloRevision`.
    """
    legal_ids = set(modelo.legal_refs).union(revision.legal_refs)
    source_ids = set(modelo.source_refs).union(revision.source_refs)
    if revision.completeness_manifest is not None:
        legal_ids.update(revision.completeness_manifest.legal_refs)
        source_ids.update(revision.completeness_manifest.source_refs)
    if include_historical_continuity:
        for evolution in revision.casilla_continuidad_evolutions:
            legal_ids.update(evolution.legal_refs)
            source_ids.update(evolution.source_refs)
        for relation in revision.casilla_structural_successions:
            legal_ids.update(relation.legal_refs)
            source_ids.update(relation.from_source_refs)
            source_ids.update(relation.to_source_refs)
    for predicate in revision.verification_predicates:
        legal_ids.update(predicate.legal_refs)
    # Applicability rules ground WHO the modelo applies to, and they were the one
    # grounded record kind this walk omitted. The snapshot still CARRIED the
    # rules, so `snapshot.legal` could not resolve the article a rule cites:
    # modelo 130's `m130-seed` names `trlirnr-rdleg-5-2004:art-2`, the provision
    # deciding whether a non-resident files at all, and a consumer resolving that
    # rule's grounding through the snapshot found a dangling id. Nineteen
    # revisions across eight modelos were affected.
    #
    # Legal-only, beside the verification predicates: an applicability rule
    # carries `legal_refs` and no `source_refs`, so it cannot join the flat
    # grounded-record walk below.
    for rule in revision.applicability:
        legal_ids.update(rule.legal_refs)
    flat_records = (
        revision.casillas,
        revision.formulas,
        *((revision.parameters,) if include_parameters else ()),
        revision.bindings,
        revision.projection_endpoints,
        revision.extraction_profiles,
        revision.live_cross_references,
        revision.workbook_parity_refs,
        revision.verification_expectations,
        revision.application_links,
        *((revision.constructs,) if include_constructs else ()),
        revision.dependency_classifications,
    )
    for kind_records in flat_records:
        _collect_grounded_record_refs(kind_records, legal_ids=legal_ids, source_ids=source_ids)
    _collect_cross_reference_predicate_refs(revision, legal_ids=legal_ids, source_ids=source_ids)
    _collect_export_layout_refs(revision, legal_ids=legal_ids, source_ids=source_ids)
    _collect_deadline_schedule_refs(
        revision,
        legal_ids=legal_ids,
        source_ids=source_ids,
        include_deadline_windows=include_deadline_windows,
    )
    return legal_ids, source_ids

"""Immutable snapshot creation for registry-backed calculations."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from ._export import derive_export_layouts_from_bindings
from ._schema import ModeloDefinition, ModeloRevision, RegistryCatalogues, RegistrySnapshot
from ._temporal import select_revision
from ._validate import RegistryValidator, _check_all_id_references

_SnapshotCacheKey = tuple[int, int, str, int, str, date | None, str | None]
_SnapshotCacheValue = tuple[ModeloDefinition, RegistryCatalogues, RegistrySnapshot]
_ValidationCacheKey = tuple[int, int, str]
_ValidationCacheValue = tuple[ModeloDefinition, RegistryCatalogues]

_SNAPSHOT_CACHE: dict[_SnapshotCacheKey, _SnapshotCacheValue] = {}
_VALIDATION_CACHE: dict[_ValidationCacheKey, _ValidationCacheValue] = {}


def build_snapshot(
    modelo: ModeloDefinition,
    catalogues: RegistryCatalogues,
    *,
    source_root: Path,
    filing_year: int,
    period: str,
    on: date | None = None,
    revision_id: str | None = None,
) -> RegistrySnapshot:
    """Validate ``modelo`` and return the selected immutable snapshot."""

    source_root_key = str(source_root.expanduser().resolve())
    key = (id(modelo), id(catalogues), source_root_key, filing_year, period, on, revision_id)
    cached = _SNAPSHOT_CACHE.get(key)
    if cached is not None and cached[0] is modelo and cached[1] is catalogues:
        return cached[2]

    _validate_modelo_once(modelo, catalogues, source_root_key)
    snapshot = _build_validated_snapshot(
        modelo,
        catalogues,
        filing_year=filing_year,
        period=period,
        on=on,
        revision_id=revision_id,
    )
    _SNAPSHOT_CACHE[key] = (modelo, catalogues, snapshot)
    return snapshot


def _validate_modelo_once(modelo: ModeloDefinition, catalogues: RegistryCatalogues, source_root_key: str) -> None:
    """Validate one immutable modelo/catalogue pair once per process."""

    key = (id(modelo), id(catalogues), source_root_key)
    cached = _VALIDATION_CACHE.get(key)
    if cached is not None and cached[0] is modelo and cached[1] is catalogues:
        return
    RegistryValidator(catalogues, source_root=Path(source_root_key)).validate_modelo(modelo)
    _VALIDATION_CACHE[key] = (modelo, catalogues)


def _build_validated_snapshot(
    modelo: ModeloDefinition,
    catalogues: RegistryCatalogues,
    *,
    filing_year: int,
    period: str,
    on: date | None = None,
    revision_id: str | None = None,
) -> RegistrySnapshot:
    """Return a selected snapshot after the caller has validated ``modelo``."""

    revision = select_revision(modelo, filing_year=filing_year, period=period, on=on, revision_id=revision_id)
    revision = revision.model_copy(update={"export_layouts": derive_export_layouts_from_bindings(revision)})
    legal_ids, source_ids = _collect_snapshot_ref_ids(modelo, revision)
    snapshot = RegistrySnapshot(
        modelo=modelo,
        revision=revision,
        filing_year=filing_year,
        period=period,
        legal={ref: catalogues.legal[ref] for ref in sorted(legal_ids)},
        sources={ref: catalogues.sources[ref] for ref in sorted(source_ids)},
        extraction_profiles={profile.id: profile for profile in revision.extraction_profiles},
        live_cross_references={
            cross_reference.id: cross_reference for cross_reference in revision.live_cross_references
        },
        workbook_parity_refs={workbook.id: workbook for workbook in revision.workbook_parity_refs},
        verification_expectations={expectation.id: expectation for expectation in revision.verification_expectations},
        application_links={link.id: link for link in revision.application_links},
        deadline_windows={window.id: window for window in revision.deadline_windows},
        filing_schedules={schedule.id: schedule for schedule in revision.filing_schedules},
        support_removal_decisions={decision.id: decision for decision in revision.support_removal_decisions},
        constructs={construct.id: construct for construct in revision.constructs},
        dependency_classifications={
            classification.id: classification for classification in revision.dependency_classifications
        },
    )
    _check_all_id_references(snapshot)
    return snapshot


def _collect_snapshot_ref_ids(
    modelo: ModeloDefinition,
    revision: ModeloRevision,
) -> tuple[set[str], set[str]]:
    """Walk every record kind and return its (legal_ids, source_ids) pair.

    The snapshot's ``legal`` / ``sources`` mappings carry only the
    refs actually exercised by the slice — this helper aggregates the
    every-record-kind union the calculation-grounding rule mandates
    (legal_refs + source_refs preserved through every domain
    boundary). Flat records share one walk; the three nesting record
    kinds (export_layouts, deadline_windows, filing_schedules) carry
    their own explicit blocks because they nest inner records that
    also carry refs.
    """
    legal_ids = set(modelo.legal_refs).union(revision.legal_refs)
    source_ids = set(modelo.source_refs).union(revision.source_refs)
    flat_records = (
        revision.casillas,
        revision.formulas,
        revision.parameters,
        revision.bindings,
        revision.relations,
        revision.algorithm_providers,
        revision.algorithm_bindings,
        revision.extraction_profiles,
        revision.live_cross_references,
        revision.workbook_parity_refs,
        revision.verification_expectations,
        revision.application_links,
        revision.support_removal_decisions,
        revision.constructs,
        revision.dependency_classifications,
    )
    for kind_records in flat_records:
        for record in kind_records:
            legal_ids.update(record.legal_refs)
            source_ids.update(record.source_refs)
    # Export layouts carry refs on the layout itself plus on every
    # field inside every record. Walk both axes explicitly so a future
    # binding-aware field gate still sees every nested ref.
    for layout in revision.export_layouts:
        legal_ids.update(layout.legal_refs)
        source_ids.update(layout.source_refs)
        for export_record in layout.records:
            for field in export_record.fields:
                legal_ids.update(field.legal_refs)
                source_ids.update(field.source_refs)
    # Deadline windows + filing schedules each nest applicability /
    # profile conditions that carry their own refs.
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
    return legal_ids, source_ids

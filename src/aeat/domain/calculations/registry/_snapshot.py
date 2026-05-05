"""Immutable snapshot creation for registry-backed calculations."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from ._schema import ModeloDefinition, RegistryCatalogues, RegistrySnapshot
from ._temporal import select_revision
from ._validate import RegistryValidator


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

    RegistryValidator(catalogues, source_root=source_root).validate_modelo(modelo)
    revision = select_revision(modelo, filing_year=filing_year, period=period, on=on, revision_id=revision_id)
    legal_ids = set(modelo.legal_refs).union(revision.legal_refs)
    source_ids = set(modelo.source_refs).union(revision.source_refs)
    for casilla in revision.casillas:
        legal_ids.update(casilla.legal_refs)
        source_ids.update(casilla.source_refs)
    for formula in revision.formulas:
        legal_ids.update(formula.legal_refs)
        source_ids.update(formula.source_refs)
    for parameter in revision.parameters:
        legal_ids.update(parameter.legal_refs)
        source_ids.update(parameter.source_refs)
    for binding in revision.bindings:
        legal_ids.update(binding.legal_refs)
        source_ids.update(binding.source_refs)
    for relation in revision.relations:
        legal_ids.update(relation.legal_refs)
        source_ids.update(relation.source_refs)
    for provider in revision.algorithm_providers:
        legal_ids.update(provider.legal_refs)
        source_ids.update(provider.source_refs)
    for algorithm_binding in revision.algorithm_bindings:
        legal_ids.update(algorithm_binding.legal_refs)
        source_ids.update(algorithm_binding.source_refs)
    for layout in revision.export_layouts:
        legal_ids.update(layout.legal_refs)
        source_ids.update(layout.source_refs)
        for record in layout.records:
            for field in record.fields:
                legal_ids.update(field.legal_refs)
                source_ids.update(field.source_refs)
    for profile in revision.extraction_profiles:
        legal_ids.update(profile.legal_refs)
        source_ids.update(profile.source_refs)
    for cross_reference in revision.live_cross_references:
        legal_ids.update(cross_reference.legal_refs)
        source_ids.update(cross_reference.source_refs)
    for workbook in revision.workbook_parity_refs:
        legal_ids.update(workbook.legal_refs)
        source_ids.update(workbook.source_refs)
    for expectation in revision.verification_expectations:
        legal_ids.update(expectation.legal_refs)
        source_ids.update(expectation.source_refs)
    for link in revision.application_links:
        legal_ids.update(link.legal_refs)
        source_ids.update(link.source_refs)
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
    for decision in revision.support_removal_decisions:
        legal_ids.update(decision.legal_refs)
        source_ids.update(decision.source_refs)
    for construct in revision.constructs:
        legal_ids.update(construct.legal_refs)
        source_ids.update(construct.source_refs)
    for classification in revision.dependency_classifications:
        legal_ids.update(classification.legal_refs)
        source_ids.update(classification.source_refs)
    return RegistrySnapshot(
        modelo=modelo,
        revision=revision,
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

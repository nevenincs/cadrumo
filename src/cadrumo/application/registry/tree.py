"""Registry-tree inspection and verification.

Loads the bundled ``registry/aeat`` tree through
:class:`~domain.calculations.registry.ValidatedRegistryAuthority` and reports
stable, read-only inventory counts. :func:`inspect_registry_tree` performs a
load-only pass; :func:`verify_registry_tree` additionally runs a full
fail-fast audit, including ``required_text`` corpus checks on every legal
reference.

This is one of three local registry read surfaces (the others are corpus/
manual projection in :mod:`application.registry.corpus` and filed-state
comparison in :mod:`application.registry.filed_state`); it does not read
captured AEAT observations or reconcile them against a local calculation --
that is filed-state comparison's distinct concern.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from pydantic import BaseModel, NonNegativeInt

from ...core.models import STRICT_FROZEN_CONFIG
from ...core.resources.bundled_data import bundled_path as _bundled_path
from ...domain.calculations.registry.authority import ValidatedRegistryAuthority as _ValidatedRegistryAuthority
from ...domain.calculations.registry.ids import ExportLayoutId as _ExportLayoutId
from ...domain.calculations.registry.ids import LegalRefId as _LegalRefId
from ...domain.calculations.registry.ids import RelationId as _RelationId
from ...domain.calculations.registry.ids import SourceRefId as _SourceRefId
from ...domain.calculations.registry.ids import WorkbookParityRefId as _WorkbookParityRefId
from ...domain.calculations.registry.legal import verify_legal_catalogue as _verify_legal_catalogue
from ...domain.calculations.registry.schema import ModeloDefinition as _ModeloDefinition


class RegistryTreeReport(BaseModel):
    """Read-only registry tree load or verification result.

    Every ``*_count`` is an inventory tally -- a ``len()`` over a collection the
    loaded authority already holds, or a sum of such tallies -- so none can be
    negative and each declares that bound. No count is authored in registry
    TOML; they are all derived at report assembly, which is what makes the
    bound a statement about this type rather than a hope about its input.
    """

    model_config = STRICT_FROZEN_CONFIG

    registry_root: str
    source_root: str | None = None
    modelo_count: NonNegativeInt
    revision_count: NonNegativeInt
    legal_reference_count: NonNegativeInt
    source_reference_count: NonNegativeInt
    casilla_count: NonNegativeInt
    formula_count: NonNegativeInt
    extraction_profile_count: NonNegativeInt
    cross_reference_count: NonNegativeInt
    workbook_parity_ref_count: NonNegativeInt
    verification_expectation_count: NonNegativeInt
    application_link_count: NonNegativeInt
    application_link_surfaces: tuple[str, ...]
    relation_count: NonNegativeInt
    relation_dependency_roles: tuple[str, ...]
    filing_schedule_count: NonNegativeInt
    modelos: tuple[str, ...]
    revision_details: tuple[RegistryRevisionDetailReport, ...]
    verified: bool
    verified_invariant_families: tuple[str, ...] = ()
    unverified_invariant_families: tuple[str, ...] = ()


class RegistryWorkbookParityDetailReport(BaseModel):
    """Workbook parity coverage declared by one registry revision."""

    model_config = STRICT_FROZEN_CONFIG

    id: _WorkbookParityRefId
    workbook_source: _SourceRefId
    formula_coverage: str
    runner_required: bool
    output_cell_count: NonNegativeInt


class RegistryRevisionDetailReport(BaseModel):
    """Read-only details for one modelo revision from the central registry."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: str
    revision: str
    legal_refs: tuple[_LegalRefId, ...]
    source_refs: tuple[_SourceRefId, ...]
    export_layout_ids: tuple[_ExportLayoutId, ...]
    export_layout_count: NonNegativeInt
    export_record_count: NonNegativeInt
    export_field_count: NonNegativeInt
    deadline_window_count: NonNegativeInt
    deadline_periods: tuple[str, ...]
    relation_ids: tuple[_RelationId, ...]
    relation_count: NonNegativeInt
    relation_dependency_roles: tuple[str, ...]
    filing_schedule_ids: tuple[str, ...]
    filing_schedule_count: NonNegativeInt
    portal_guard_policy_ids: tuple[str, ...]
    workbook_parity: tuple[RegistryWorkbookParityDetailReport, ...]


class RegistryRevisionInventory(NamedTuple):
    """Per-revision inventory tallies summed across every revision of a modelo set."""

    casilla_count: int
    formula_count: int
    extraction_profile_count: int
    cross_reference_count: int
    workbook_parity_ref_count: int
    verification_expectation_count: int
    application_link_count: int
    application_link_surfaces: tuple[str, ...]
    relation_count: int
    relation_dependency_roles: tuple[str, ...]
    filing_schedule_count: int


def _registry_tree_report(
    *,
    registry_root: Path,
    authority: _ValidatedRegistryAuthority,
    verified: bool,
    source_root: Path | None = None,
) -> RegistryTreeReport:
    """Assemble the read-only inventory :class:`RegistryTreeReport` from a loaded authority.

    The shared report-construction body of :func:`inspect_registry_tree` (which
    passes no ``source_root`` and ``verified=False``) and
    :func:`verify_registry_tree` (which records the ``source_root`` and
    ``verified=True``); each caller owns its own load and validation before
    calling this.
    """
    modelos = authority.modelos
    catalogues = authority.catalogues
    inventory = _revision_inventory(modelos)
    return RegistryTreeReport(
        registry_root=str(registry_root),
        source_root=None if source_root is None else str(source_root),
        modelo_count=len(modelos),
        revision_count=sum(len(modelo.revisions) for modelo in modelos),
        legal_reference_count=len(catalogues.legal),
        source_reference_count=len(catalogues.sources),
        casilla_count=inventory.casilla_count,
        formula_count=inventory.formula_count,
        extraction_profile_count=inventory.extraction_profile_count,
        cross_reference_count=inventory.cross_reference_count,
        workbook_parity_ref_count=inventory.workbook_parity_ref_count,
        verification_expectation_count=inventory.verification_expectation_count,
        application_link_count=inventory.application_link_count,
        application_link_surfaces=inventory.application_link_surfaces,
        relation_count=inventory.relation_count,
        relation_dependency_roles=inventory.relation_dependency_roles,
        filing_schedule_count=inventory.filing_schedule_count,
        modelos=tuple(sorted(modelo.id for modelo in modelos)),
        revision_details=_revision_details(modelos),
        verified=verified,
    )


def inspect_registry_tree(registry_root: Path) -> RegistryTreeReport:
    """Load the registry tree and return a :class:`RegistryTreeReport` with stable read-only inventory counts."""
    authority = _ValidatedRegistryAuthority.load(registry_root, source_root=_bundled_path())
    return _registry_tree_report(registry_root=registry_root, authority=authority, verified=False)


def verify_registry_tree(registry_root: Path, *, source_root: Path) -> RegistryTreeReport:
    """Load and fail-fast validate every registry modelo against shared catalogues.

    Returns a :class:`RegistryTreeReport`.

    Runs a full audit including ``required_text`` corpus checks on every
    legal reference.
    """
    authority = _ValidatedRegistryAuthority.load(registry_root, source_root=source_root)
    authority.validate_registry()
    _verify_legal_catalogue(authority.catalogues.legal, source_root=source_root)
    return _registry_tree_report(
        registry_root=registry_root,
        authority=authority,
        verified=True,
        source_root=source_root,
    ).model_copy(
        update={
            "verified_invariant_families": (
                "catalogue_and_corpus_integrity",
                "revision_section_contracts",
                "relation_source_coordinate_coverage",
            ),
            "unverified_invariant_families": (
                "export_layout_population",
                "published_design_span_attribution",
            ),
        },
    )


def _revision_inventory(modelos: tuple[_ModeloDefinition, ...]) -> RegistryRevisionInventory:
    revisions = tuple(revision for modelo in modelos for revision in modelo.revisions.values())
    application_surfaces = {link.surface for revision in revisions for link in revision.application_links}
    relation_roles = {relation.dependency_role for revision in revisions for relation in revision.relations}
    return RegistryRevisionInventory(
        casilla_count=sum(len(revision.casillas) for revision in revisions),
        formula_count=sum(len(revision.formulas) for revision in revisions),
        extraction_profile_count=sum(len(revision.extraction_profiles) for revision in revisions),
        cross_reference_count=sum(len(revision.live_cross_references) for revision in revisions),
        workbook_parity_ref_count=sum(len(revision.workbook_parity_refs) for revision in revisions),
        verification_expectation_count=sum(len(revision.verification_expectations) for revision in revisions),
        application_link_count=sum(len(revision.application_links) for revision in revisions),
        application_link_surfaces=tuple(sorted(application_surfaces)),
        relation_count=sum(len(revision.relations) for revision in revisions),
        relation_dependency_roles=tuple(sorted(relation_roles)),
        filing_schedule_count=sum(len(revision.filing_schedules) for revision in revisions),
    )


def _revision_details(modelos: tuple[_ModeloDefinition, ...]) -> tuple[RegistryRevisionDetailReport, ...]:
    reports: list[RegistryRevisionDetailReport] = []
    for modelo in sorted(modelos, key=lambda item: item.id):
        for revision_id, revision in sorted(modelo.revisions.items()):
            export_records = tuple(record for layout in revision.export_layouts for record in layout.records)
            export_fields = tuple(field for record in export_records for field in record.fields)
            workbook_parity = tuple(
                RegistryWorkbookParityDetailReport(
                    id=reference.id,
                    workbook_source=reference.workbook_source,
                    formula_coverage=reference.formula_coverage,
                    runner_required=reference.runner_required,
                    output_cell_count=len(reference.output_cells),
                )
                for reference in sorted(revision.workbook_parity_refs, key=lambda item: item.id)
            )
            reports.append(
                RegistryRevisionDetailReport(
                    modelo=str(modelo.id),
                    revision=str(revision_id),
                    legal_refs=tuple(revision.legal_refs),
                    source_refs=tuple(revision.source_refs),
                    export_layout_ids=tuple(layout.id for layout in revision.export_layouts),
                    export_layout_count=len(revision.export_layouts),
                    export_record_count=len(export_records),
                    export_field_count=len(export_fields),
                    deadline_window_count=len(revision.deadline_windows),
                    deadline_periods=tuple(
                        sorted(window.period.registry_token for window in revision.deadline_windows),
                    ),
                    relation_ids=tuple(relation.id for relation in revision.relations),
                    relation_count=len(revision.relations),
                    relation_dependency_roles=tuple(
                        sorted({relation.dependency_role for relation in revision.relations}),
                    ),
                    filing_schedule_ids=tuple(str(schedule.id) for schedule in revision.filing_schedules),
                    filing_schedule_count=len(revision.filing_schedules),
                    portal_guard_policy_ids=tuple(
                        sorted({decision.guard_policy_id for decision in revision.live_cross_references}),
                    ),
                    workbook_parity=workbook_parity,
                ),
            )
    return tuple(reports)


__all__ = [
    "RegistryRevisionDetailReport",
    "RegistryRevisionInventory",
    "RegistryTreeReport",
    "RegistryWorkbookParityDetailReport",
    "inspect_registry_tree",
    "verify_registry_tree",
]

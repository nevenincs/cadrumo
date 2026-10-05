"""Canonical inventory of export trees attested by the shipped registry."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import override

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision

from ..compiler.authority import compiled_bundled_authority
from ..maintenance_support import coverage_assessment_floor, coverage_assessment_horizon, revision_selection_coordinates
from .export_fragment_provenance import (
    export_fragment_provenance_path,
    load_export_fragment_provenance_manifest,
)
from .render_check import select_revision_record_design_source

__all__ = ["GeneratedExportTree", "generated_export_trees"]


@dataclass(frozen=True)
class GeneratedExportTree:
    """One committed generated export tree and its producing authority coordinates."""

    modelo: str
    revision: str
    source_ref: str
    epoch: str
    filing_year: int
    period: str
    historical_static: bool = False

    @property
    def layout_id(self) -> str:
        """Return the generated layout identity for this tree."""
        return f"generated-modelo-{self.modelo}-{self.revision}-fichero"

    @property
    def committed(self) -> Path:
        """Return the shipped export directory for this tree."""
        return bundled_path("registry", "aeat", "modelos", self.modelo, "revisions", self.revision, "export")

    @override
    def __str__(self) -> str:
        """Return the compact modelo/revision identity used by test reports."""
        return f"m{self.modelo}-{self.revision}"


def generated_export_trees() -> tuple[GeneratedExportTree, ...]:
    """Project every provenance-attested tree, including source-proven static history."""
    authority = compiled_bundled_authority()
    assessment_horizon = coverage_assessment_horizon(authority.catalogues)
    assessment_floor = coverage_assessment_floor(authority.catalogues)
    trees: list[GeneratedExportTree] = []
    for modelo in sorted(authority.modelos, key=lambda item: item.id):
        for revision in sorted(modelo.revisions.values(), key=lambda item: item.id):
            tree = _generated_export_tree_for_revision(
                modelo,
                revision,
                authority=authority,
                assessment_horizon=assessment_horizon,
                assessment_floor=assessment_floor,
            )
            if tree is not None:
                trees.append(tree)
    if not trees:
        raise AssertionError("validated registry declares no provenance-attested generated export tree")
    return tuple(trees)


def _generated_export_tree_for_revision(
    modelo: ModeloDefinition,
    revision: ModeloRevision,
    *,
    authority: ValidatedRegistryAuthority,
    assessment_horizon: int,
    assessment_floor: int,
) -> GeneratedExportTree | None:
    export_root = bundled_path(
        "registry",
        "aeat",
        "modelos",
        str(modelo.id),
        "revisions",
        str(revision.id),
        "export",
    )
    manifest_path = export_fragment_provenance_path(export_root)
    if not manifest_path.is_file():
        return None
    manifest = load_export_fragment_provenance_manifest(manifest_path.read_bytes())
    if manifest.modelo != modelo.id or manifest.revision_id != revision.id:
        raise AssertionError(
            f"generated export provenance identity conflicts with its declared registry revision: {manifest_path}",
        )
    coordinates = revision_selection_coordinates(
        revision,
        assessment_horizon=assessment_horizon,
        assessment_floor=assessment_floor,
    )
    historical_static = not coordinates
    if historical_static and max(revision.period_selector.years, default=assessment_floor) < assessment_floor:
        coordinates = revision_selection_coordinates(
            revision,
            assessment_horizon=min(assessment_horizon, assessment_floor - 1),
            assessment_floor=revision.valid_from.year,
        )
    if not coordinates:
        raise AssertionError(f"generated tree {modelo.id}/{revision.id} has no law-selectable coordinate")
    filing_year, period = coordinates[0]
    if historical_static:
        source_ref, epoch = select_revision_record_design_source(
            authority,
            modelo=str(modelo.id),
            revision=str(revision.id),
            filing_year=filing_year,
            period=period,
            source_ref=None,
        )
        if (
            source_ref != manifest.source_ref
            or epoch != manifest.design_epoch
            or authority.catalogues.sources[source_ref].sha256 != manifest.source_sha256
        ):
            raise AssertionError(
                f"historical generated tree {modelo.id}/{revision.id} differs from its "
                "uniquely selected official source"
            )
    return GeneratedExportTree(
        modelo=str(modelo.id),
        revision=str(revision.id),
        source_ref=str(manifest.source_ref),
        epoch=manifest.design_epoch,
        filing_year=filing_year,
        period=period,
        historical_static=historical_static,
    )

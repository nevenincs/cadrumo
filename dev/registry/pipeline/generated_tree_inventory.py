"""Canonical inventory of export trees attested by the shipped registry."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import override

from cadrumo.core.resources.bundled_data import bundled_path

from ..compiler.authority import compiled_bundled_authority
from ..maintenance_support import coverage_assessment_horizon, revision_selection_coordinates
from .export_fragment_provenance import (
    export_fragment_provenance_path,
    load_export_fragment_provenance_manifest,
)

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
    """Project every provenance-attested generated tree from validated authority."""
    authority = compiled_bundled_authority()
    assessment_horizon = coverage_assessment_horizon(authority.catalogues)
    trees: list[GeneratedExportTree] = []
    for modelo in sorted(authority.modelos, key=lambda item: item.id):
        for revision in sorted(modelo.revisions.values(), key=lambda item: item.id):
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
                continue
            manifest = load_export_fragment_provenance_manifest(manifest_path.read_bytes())
            if manifest.modelo != modelo.id or manifest.revision_id != revision.id:
                raise AssertionError(
                    "generated export provenance identity conflicts with its declared registry revision: "
                    f"{manifest_path}",
                )
            coordinates = revision_selection_coordinates(
                revision,
                assessment_horizon=assessment_horizon,
            )
            if not coordinates:
                raise AssertionError(f"generated tree {modelo.id}/{revision.id} has no law-selectable coordinate")
            filing_year, period = coordinates[0]
            trees.append(
                GeneratedExportTree(
                    modelo=str(modelo.id),
                    revision=str(revision.id),
                    source_ref=str(manifest.source_ref),
                    epoch=manifest.design_epoch,
                    filing_year=filing_year,
                    period=period,
                )
            )
    if not trees:
        raise AssertionError("validated registry declares no provenance-attested generated export tree")
    return tuple(trees)

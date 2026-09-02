"""Static filing-revision diagnostics after strict registry admission fails.

The classification capability deliberately exposes immutable inspection facts,
not a runtime registry authority.  It lets export conformance tooling explain a
strict-load refusal without gaining a path to calculate, render, or file.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.domain.calculations.registry._source_evidence_fingerprint import collect_source_evidence_fingerprints
from cadrumo.domain.calculations.registry.errors import RegistrySnapshotError, RegistryValidationError
from cadrumo.domain.calculations.registry.ids import ModeloId, RevisionId
from cadrumo.domain.calculations.registry.static_inspection import (
    RegistryRevisionInspection,
    StaticGeneratedArtifactInspection,
)
from cadrumo.domain.calculations.registry.temporal import coverage_assessment_horizon, revision_selection_coordinates

if TYPE_CHECKING:
    from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority


@dataclass(frozen=True, slots=True)
class RegistryDiagnosticFilingRevision:
    """Static filing-revision facts admitted for diagnostic classification.

    This projection carries no :class:`RegistrySnapshot` and no authority
    capability.  Its optional inspection is the existing static-only
    projection used by generated-artifact verification.
    """

    modelo: ModeloId
    revision: RevisionId
    selection_coordinates: tuple[tuple[int, str], ...]
    layout_ids: tuple[str, ...]
    layout_json: str | None
    inspection: StaticGeneratedArtifactInspection | None
    refusal_reason: str | None = None
    refusal_detail: str | None = None


@dataclass(frozen=True, slots=True)
class UnvalidatedRegistryClassification:
    """Narrow, read-only classification capability after strict loading fails.

    It intentionally exposes only static, per-revision classification facts.
    It cannot snapshot, calculate, render, or act as a runtime registry
    authority.
    """

    strict_validation_error: str
    filing_revisions: tuple[RegistryDiagnosticFilingRevision, ...]


def derive_filing_revision_classifications(
    authority: ValidatedRegistryAuthority,
) -> tuple[RegistryDiagnosticFilingRevision, ...]:
    """Copy every filing revision into static law-selection classification facts.

    The supplied authority is used only while this function runs.  Returned
    facts contain immutable coordinates, error text, and minimal static
    layout/inspection projections; they retain no authority, snapshot, or
    service object.
    """
    assessment_horizon = coverage_assessment_horizon(authority.catalogues)
    classified: list[RegistryDiagnosticFilingRevision] = []
    for modelo in sorted(authority.modelos, key=lambda item: item.id):
        for revision in sorted(modelo.revisions.values(), key=lambda item: item.id):
            if revision.authority_grade is not RegistryAuthorityGrade.FILING:
                continue
            try:
                selection_coordinates = revision_selection_coordinates(
                    revision,
                    assessment_horizon=assessment_horizon,
                )
            except ValueError as error:
                classified.append(
                    RegistryDiagnosticFilingRevision(
                        modelo=modelo.id,
                        revision=revision.id,
                        selection_coordinates=(),
                        layout_ids=(),
                        layout_json=None,
                        inspection=None,
                        refusal_reason="law_selection_failed",
                        refusal_detail=str(error),
                    )
                )
                continue
            try:
                inspection = RegistryRevisionInspection.from_revision(
                    modelo=modelo,
                    revision=revision,
                    source_root=authority.source_root,
                    sources=authority.catalogues.sources,
                    legal_ref_ids=frozenset(authority.catalogues.legal),
                )
                static_inspection = StaticGeneratedArtifactInspection.from_inspection(inspection)
            except ValueError as error:
                classified.append(
                    RegistryDiagnosticFilingRevision(
                        modelo=modelo.id,
                        revision=revision.id,
                        selection_coordinates=selection_coordinates,
                        layout_ids=tuple(str(layout.id) for layout in revision.export_layouts),
                        layout_json=None,
                        inspection=None,
                        refusal_reason="revision_validation_failed",
                        refusal_detail=str(error),
                    )
                )
                continue
            try:
                snapshots = tuple(
                    authority.snapshot(
                        modelo.id,
                        filing_year=filing_year,
                        period=period,
                        grade=RegistryAuthorityGrade.FILING,
                    )
                    for filing_year, period in selection_coordinates
                )
            except RegistryValidationError as error:
                layout = revision.export_layouts[0] if len(revision.export_layouts) == 1 else None
                classified.append(
                    RegistryDiagnosticFilingRevision(
                        modelo=modelo.id,
                        revision=revision.id,
                        selection_coordinates=selection_coordinates,
                        layout_ids=tuple(str(item.id) for item in revision.export_layouts),
                        layout_json=None if layout is None else layout.model_dump_json(),
                        inspection=static_inspection,
                        refusal_reason="revision_validation_failed",
                        refusal_detail=str(error),
                    )
                )
                continue
            except RegistrySnapshotError as error:
                classified.append(
                    RegistryDiagnosticFilingRevision(
                        modelo=modelo.id,
                        revision=revision.id,
                        selection_coordinates=selection_coordinates,
                        layout_ids=(),
                        layout_json=None,
                        inspection=static_inspection,
                        refusal_reason="law_selection_failed",
                        refusal_detail=str(error),
                    )
                )
                continue
            if any(snapshot.revision.id != revision.id for snapshot in snapshots):
                classified.append(
                    RegistryDiagnosticFilingRevision(
                        modelo=modelo.id,
                        revision=revision.id,
                        selection_coordinates=selection_coordinates,
                        layout_ids=(),
                        layout_json=None,
                        inspection=static_inspection,
                        refusal_reason="law_selection_failed",
                        refusal_detail="a filing-grade snapshot selected a different revision",
                    )
                )
                continue
            layout_ids = tuple(str(layout.id) for layout in snapshots[0].revision.export_layouts)
            if not layout_ids or any(
                tuple(str(layout.id) for layout in snapshot.revision.export_layouts) != layout_ids
                for snapshot in snapshots
            ):
                classified.append(
                    RegistryDiagnosticFilingRevision(
                        modelo=modelo.id,
                        revision=revision.id,
                        selection_coordinates=selection_coordinates,
                        layout_ids=layout_ids,
                        layout_json=None,
                        inspection=static_inspection,
                        refusal_reason="layout_unavailable",
                        refusal_detail=(
                            "the filing revision has no stable single layout across its selected coordinates"
                        ),
                    )
                )
                continue
            if len(layout_ids) != 1:
                classified.append(
                    RegistryDiagnosticFilingRevision(
                        modelo=modelo.id,
                        revision=revision.id,
                        selection_coordinates=selection_coordinates,
                        layout_ids=layout_ids,
                        layout_json=None,
                        inspection=static_inspection,
                        refusal_reason="layout_unavailable",
                        refusal_detail="conformance supports exactly one generated filing layout per revision",
                    )
                )
                continue
            classified.append(
                RegistryDiagnosticFilingRevision(
                    modelo=modelo.id,
                    revision=revision.id,
                    selection_coordinates=selection_coordinates,
                    layout_ids=layout_ids,
                    layout_json=snapshots[0].revision.export_layouts[0].model_dump_json(),
                    inspection=static_inspection,
                )
            )
    return tuple(classified)


def load_registry_diagnostic_classification(
    root: Path,
    *,
    source_root: Path,
    strict_validation_error: RegistryValidationError,
) -> UnvalidatedRegistryClassification:
    """Create the narrow static classifier after a recorded strict-load failure.

    The returned capability deliberately is not a registry authority.  It can
    only classify independently validated revision facts into diagnostic
    residue; filing, export, and calculation callers must load a validated
    authority through :meth:`ValidatedRegistryAuthority.load`.
    """
    from cadrumo.domain.calculations.registry.authority import (
        canonical_authority_root_pair,
        collect_registry_identity_fingerprints,
        construct_authority,
        fingerprint_key,
    )
    from cadrumo.domain.calculations.registry.identity import resolve_registry_identity

    identity_pair = canonical_authority_root_pair(root, source_root)
    resolved_root = identity_pair.root
    resolved_source_root = identity_pair.source_root
    identity = resolve_registry_identity(
        resolved_root,
        collect_fingerprints=collect_registry_identity_fingerprints,
    )
    source_evidence_key = fingerprint_key(collect_source_evidence_fingerprints(resolved_source_root))
    authority = construct_authority(
        resolved_root,
        resolved_source_root,
        source_evidence_key.fingerprints,
        identity=identity,
    )
    return UnvalidatedRegistryClassification(
        strict_validation_error=str(strict_validation_error),
        filing_revisions=derive_filing_revision_classifications(authority),
    )

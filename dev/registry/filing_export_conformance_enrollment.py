"""Classify static filing revisions into verified vector candidates or explicit residue."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.hashing import sha256_hex
from cadrumo.core.period import Period, PeriodError
from cadrumo.domain.calculations.registry.authority import (
    ValidatedRegistryAuthority,
)
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.ids import ModeloId, RevisionId
from cadrumo.domain.calculations.registry.schema_exports import ExportLayoutDefinition
from cadrumo.domain.calculations.registry.schema_references import RegistrySnapshotRef

from .compiler.export_fragment_grammar import EXPORT_FRAGMENT_PROVENANCE_FILENAME
from .diagnostic_classification import (
    RegistryDiagnosticFilingRevision,
    UnvalidatedRegistryClassification,
    derive_filing_revision_classifications,
)
from .filing_export_conformance import _CONFORMANCE_AUTHORITY_ID
from .filing_export_conformance_vectors import FilingExportConformanceVector
from .filing_export_generated_verification import _ConformanceGenerationEntry, _verify_generated_revision
from .filing_export_proof_contracts import (
    FilingExportConformanceVectorEvidence,
    FilingExportGeneratedOutput,
    FilingExportOfficialProbe,
    FilingExportProofCoordinate,
    FilingExportPublicProvenance,
)
from .maintenance_support import GeneratedArtifactInspection
from .pipeline.export_fragment_provenance import (
    ExportFragmentProvenanceManifest,
    load_export_fragment_provenance_manifest,
)

_GENERATOR_RESIDUE_OWNER = "aeat-export-fragment-generator-authority"


_PRODUCER_RESIDUE_OWNER = "source-casilla-integration"


_BUILDER_RESIDUE_OWNER = "filing-export-conformance"


_ConformanceResidueReason = Literal[
    "law_selection_failed",
    "revision_validation_failed",
    "layout_unavailable",
    "generated_provenance_missing",
    "generated_provenance_invalid",
    "official_probe_unavailable",
    "producer_binding_missing",
    "period_unrepresentable",
    "canonical_builder_missing",
    "canonical_builder_conflict",
    "registry_validation_incomplete",
]


@dataclass(frozen=True, slots=True)
class FilingExportConformanceProvenanceCandidate:
    """One live-generated public candidate that still needs a canonical builder."""

    evidence: FilingExportConformanceVectorEvidence


@dataclass(frozen=True, slots=True)
class FilingExportConformanceResidue:
    """One explicit reason a filing revision cannot receive conformance proof."""

    modelo: ModeloId
    revision: RevisionId
    layout_ids: tuple[str, ...]
    reason: _ConformanceResidueReason
    owner: str
    reconsideration_condition: str
    detail: str


@dataclass(frozen=True, slots=True)
class FilingExportConformanceEnrollmentReport:
    """Dynamic public-provenance enrollment and its non-success residue."""

    full_registry_validation_error: str | None
    provenance_candidates: tuple[FilingExportConformanceProvenanceCandidate, ...]
    materializable_vectors: tuple[FilingExportConformanceVector, ...]
    residues: tuple[FilingExportConformanceResidue, ...]

    def __post_init__(self) -> None:
        """Keep every successful or refused revision coordinate unique."""
        successful = tuple(
            (vector.evidence.coordinate.modelo, vector.evidence.coordinate.revision)
            for vector in self.materializable_vectors
        )
        refused = tuple((residue.modelo, residue.revision) for residue in self.residues)
        if len(successful) != len(set(successful)):
            raise ValueError("conformance enrollment materializes a revision more than once")
        if len(refused) != len(set(refused)):
            raise ValueError("conformance enrollment records a revision residue more than once")
        if set(successful).intersection(refused):
            raise ValueError("conformance enrollment cannot both materialize and refuse one revision")
        if self.full_registry_validation_error is not None and successful:
            raise ValueError("diagnostic conformance classification cannot materialize a vector")


def derive_filing_export_conformance_enrollment(
    *,
    workspace_root: Path,
    registry_root: Path,
    source_root: Path,
    authority: ValidatedRegistryAuthority,
    vectors: tuple[FilingExportConformanceVector, ...],
) -> FilingExportConformanceEnrollmentReport:
    """Classify validated filing revisions through the canonical static path."""
    return _derive_static_filing_export_conformance_enrollment(
        workspace_root=workspace_root,
        registry_root=registry_root,
        source_root=source_root,
        revisions=derive_filing_revision_classifications(authority),
        vectors=vectors,
        strict_validation_error=None,
        validated_authority=authority,
    )


def derive_diagnostic_filing_export_conformance_enrollment(
    *,
    workspace_root: Path,
    registry_root: Path,
    source_root: Path,
    classification: UnvalidatedRegistryClassification,
    vectors: tuple[FilingExportConformanceVector, ...],
) -> FilingExportConformanceEnrollmentReport:
    """Classify static diagnostic facts into residue only after strict failure."""
    return _derive_static_filing_export_conformance_enrollment(
        workspace_root=workspace_root,
        registry_root=registry_root,
        source_root=source_root,
        revisions=classification.filing_revisions,
        vectors=vectors,
        strict_validation_error=classification.strict_validation_error,
        validated_authority=None,
    )


def _derive_static_filing_export_conformance_enrollment(
    *,
    workspace_root: Path,
    registry_root: Path,
    source_root: Path,
    revisions: tuple[RegistryDiagnosticFilingRevision, ...],
    vectors: tuple[FilingExportConformanceVector, ...],
    strict_validation_error: str | None,
    validated_authority: ValidatedRegistryAuthority | None,
) -> FilingExportConformanceEnrollmentReport:
    """Classify one static filing projection with success gated by validation."""
    if validated_authority is not None and not isinstance(validated_authority, ValidatedRegistryAuthority):
        raise TypeError("conformance materialization requires a validated registry authority")
    if strict_validation_error is not None and validated_authority is not None:
        raise ValueError("unvalidated classification facts cannot authorize materialization")
    vector_by_revision = {
        (vector.evidence.coordinate.modelo, vector.evidence.coordinate.revision): vector for vector in vectors
    }
    if len(vector_by_revision) != len(vectors):
        raise ValueError("canonical conformance vectors must identify distinct revisions")
    candidates: list[FilingExportConformanceProvenanceCandidate] = []
    materializable_vectors: list[FilingExportConformanceVector] = []
    residues: list[FilingExportConformanceResidue] = []

    for selected in revisions:
        row = _classify_static_filing_revision(
            workspace_root=workspace_root,
            registry_root=registry_root,
            source_root=source_root,
            selected=selected,
            vector_by_revision=vector_by_revision,
            strict_validation_error=strict_validation_error,
            validated_authority=validated_authority,
        )
        _append_static_enrollment_row(
            row,
            candidates=candidates,
            materializable_vectors=materializable_vectors,
            residues=residues,
        )

    return FilingExportConformanceEnrollmentReport(
        full_registry_validation_error=strict_validation_error,
        provenance_candidates=tuple(candidates),
        materializable_vectors=tuple(materializable_vectors),
        residues=tuple(residues),
    )


def _append_static_enrollment_row(
    row: _StaticConformanceEnrollmentRow,
    *,
    candidates: list[FilingExportConformanceProvenanceCandidate],
    materializable_vectors: list[FilingExportConformanceVector],
    residues: list[FilingExportConformanceResidue],
) -> None:
    if row.candidate is not None:
        candidates.append(row.candidate)
    if row.materializable_vector is not None:
        materializable_vectors.append(row.materializable_vector)
    if row.residue is not None:
        residues.append(row.residue)


@dataclass(frozen=True, slots=True)
class _StaticConformanceEnrollmentRow:
    candidate: FilingExportConformanceProvenanceCandidate | None = None
    materializable_vector: FilingExportConformanceVector | None = None
    residue: FilingExportConformanceResidue | None = None


def _classify_static_filing_revision(
    *,
    workspace_root: Path,
    registry_root: Path,
    source_root: Path,
    selected: RegistryDiagnosticFilingRevision,
    vector_by_revision: Mapping[tuple[ModeloId, RevisionId], FilingExportConformanceVector],
    strict_validation_error: str | None,
    validated_authority: ValidatedRegistryAuthority | None,
) -> _StaticConformanceEnrollmentRow:
    if selected.refusal_reason is not None:
        return _StaticConformanceEnrollmentRow(
            residue=_static_revision_residue(
                workspace_root=workspace_root,
                registry_root=registry_root,
                source_root=source_root,
                selected=selected,
            )
        )
    try:
        layout, inspection = _static_verifier_inputs(selected)
    except ValueError as error:
        return _StaticConformanceEnrollmentRow(
            residue=_revision_validation_residue(selected=selected, detail=_residue_detail(error))
        )
    try:
        manifest_raw, manifest = _verify_static_generated_provenance(
            workspace_root=workspace_root,
            registry_root=registry_root,
            source_root=source_root,
            selected=selected,
            layout=layout,
            inspection=inspection,
            authority=validated_authority,
        )
    except (OSError, RegistryValidationError, ValueError) as error:
        return _StaticConformanceEnrollmentRow(residue=_generated_provenance_residue(selected=selected, error=error))
    candidate_or_residue = _static_candidate_from_provenance(
        selected=selected,
        layout=layout,
        manifest_raw=manifest_raw,
        manifest=manifest,
        validated_authority=validated_authority,
    )
    if isinstance(candidate_or_residue, FilingExportConformanceResidue):
        return _StaticConformanceEnrollmentRow(residue=candidate_or_residue)
    candidate = candidate_or_residue
    residue = _static_materialization_residue(
        selected=selected,
        layout=layout,
        candidate=candidate,
        vector_by_revision=vector_by_revision,
        strict_validation_error=strict_validation_error,
        validated_authority=validated_authority,
    )
    if residue is not None:
        return _StaticConformanceEnrollmentRow(candidate=candidate, residue=residue)
    vector = vector_by_revision[(selected.modelo, selected.revision)]
    return _StaticConformanceEnrollmentRow(candidate=candidate, materializable_vector=vector)


def _static_candidate_from_provenance(
    *,
    selected: RegistryDiagnosticFilingRevision,
    layout: ExportLayoutDefinition,
    manifest_raw: bytes,
    manifest: ExportFragmentProvenanceManifest,
    validated_authority: ValidatedRegistryAuthority | None,
) -> FilingExportConformanceProvenanceCandidate | FilingExportConformanceResidue:
    filing_year, period_code = selected.selection_coordinates[0]
    try:
        period = Period.from_year_and_code(filing_year, period_code)
    except (ValueError, PeriodError) as error:
        return _conformance_residue(
            modelo=selected.modelo,
            revision=selected.revision,
            layout_ids=selected.layout_ids,
            reason="period_unrepresentable",
            owner=_BUILDER_RESIDUE_OWNER,
            reconsideration_condition=(
                "Extend the public conformance contract for the exact law-selected filing period "
                "without substituting another period."
            ),
            detail=_residue_detail(error),
        )
    try:
        probes = _public_vector_probes(layout)
        snapshot_ref = _static_snapshot_ref(
            selected=selected,
            filing_year=filing_year,
            period_code=period_code,
            validated_authority=validated_authority,
        )
        evidence = _static_conformance_evidence(
            selected=selected,
            filing_year=filing_year,
            period=period,
            snapshot_ref=snapshot_ref,
            manifest_raw=manifest_raw,
            manifest=manifest,
            probes=probes,
        )
    except (RegistryValidationError, ValueError) as error:
        return _conformance_residue(
            modelo=selected.modelo,
            revision=selected.revision,
            layout_ids=selected.layout_ids,
            reason="official_probe_unavailable",
            owner=_GENERATOR_RESIDUE_OWNER,
            reconsideration_condition=(
                "Provide one distinct positioned literal probe in the first required non-repeating record."
            ),
            detail=_residue_detail(error),
        )
    return FilingExportConformanceProvenanceCandidate(evidence=evidence)


def _static_snapshot_ref(
    *,
    selected: RegistryDiagnosticFilingRevision,
    filing_year: int,
    period_code: str,
    validated_authority: ValidatedRegistryAuthority | None,
) -> RegistrySnapshotRef:
    if validated_authority is not None:
        return validated_authority.snapshot(
            selected.modelo,
            filing_year=filing_year,
            period=period_code,
            grade=RegistryAuthorityGrade.FILING,
        ).snapshot_ref
    return RegistrySnapshotRef(
        modelo=selected.modelo,
        revision_id=selected.revision,
        modelo_year=filing_year,
        period=period_code,
    )


def _static_conformance_evidence(
    *,
    selected: RegistryDiagnosticFilingRevision,
    filing_year: int,
    period: Period,
    snapshot_ref: RegistrySnapshotRef,
    manifest_raw: bytes,
    manifest: ExportFragmentProvenanceManifest,
    probes: tuple[FilingExportOfficialProbe, ...],
) -> FilingExportConformanceVectorEvidence:
    return FilingExportConformanceVectorEvidence(
        authority_id=_CONFORMANCE_AUTHORITY_ID,
        coordinate=FilingExportProofCoordinate(
            modelo=selected.modelo,
            revision=selected.revision,
            snapshot_ref=snapshot_ref,
            layout_ids=selected.layout_ids,
        ),
        filing_year=filing_year,
        period=period,
        mechanism_source_ref=f"generated-provenance/{selected.modelo}/{selected.revision}",
        mechanism_source_sha256=sha256_hex(manifest_raw),
        provenance=FilingExportPublicProvenance(
            official_source_ref=manifest.source_ref,
            official_source_sha256=manifest.source_sha256,
            design_epoch=manifest.design_epoch,
            generation_manifest_sha256=sha256_hex(manifest_raw),
            semantic_map_sha256=manifest.semantic_map_sha256,
            render_profile_sha256=manifest.render_profile_sha256,
            loader_semantic_sha256=manifest.loader_semantic_sha256,
            generated_outputs=tuple(
                FilingExportGeneratedOutput(relative_path=item.relative_path, sha256=item.sha256)
                for item in manifest.output_files
            ),
            probes=probes,
        ),
    )


def _static_materialization_residue(
    *,
    selected: RegistryDiagnosticFilingRevision,
    layout: ExportLayoutDefinition,
    candidate: FilingExportConformanceProvenanceCandidate,
    vector_by_revision: Mapping[tuple[ModeloId, RevisionId], FilingExportConformanceVector],
    strict_validation_error: str | None,
    validated_authority: ValidatedRegistryAuthority | None,
) -> FilingExportConformanceResidue | None:
    if not _layout_producer_keys(layout):
        return _conformance_residue(
            modelo=selected.modelo,
            revision=selected.revision,
            layout_ids=selected.layout_ids,
            reason="producer_binding_missing",
            owner=_PRODUCER_RESIDUE_OWNER,
            reconsideration_condition=(
                "Declare a resolved filing producer key before a canonical writer input can be materialized."
            ),
            detail="the selected layout declares no filing producer key",
        )
    vector = vector_by_revision.get((selected.modelo, selected.revision))
    if vector is None:
        return _conformance_residue(
            modelo=selected.modelo,
            revision=selected.revision,
            layout_ids=selected.layout_ids,
            reason="canonical_builder_missing",
            owner=_BUILDER_RESIDUE_OWNER,
            reconsideration_condition=(
                "Enroll a separately reviewed value-independent canonical builder for this public provenance candidate."
            ),
            detail="no canonical builder materializes non-sensitive conformance inputs for the selected revision",
        )
    if vector.evidence != candidate.evidence:
        return _conformance_residue(
            modelo=selected.modelo,
            revision=selected.revision,
            layout_ids=selected.layout_ids,
            reason="canonical_builder_conflict",
            owner=_BUILDER_RESIDUE_OWNER,
            reconsideration_condition=(
                "Align the canonical builder's public evidence with current generated provenance and selected layout."
            ),
            detail="canonical builder evidence conflicts with the reverified public provenance candidate",
        )
    if validated_authority is None:
        if strict_validation_error is None:
            raise AssertionError("refusal-only static classification requires a strict validation error")
        return _conformance_residue(
            modelo=selected.modelo,
            revision=selected.revision,
            layout_ids=selected.layout_ids,
            reason="registry_validation_incomplete",
            owner=_GENERATOR_RESIDUE_OWNER,
            reconsideration_condition=(
                "Resolve the recorded whole-registry validation failure, then re-run canonical conformance enrollment."
            ),
            detail=strict_validation_error,
        )
    return None


def _static_revision_residue(
    *,
    workspace_root: Path,
    registry_root: Path,
    source_root: Path,
    selected: RegistryDiagnosticFilingRevision,
) -> FilingExportConformanceResidue:
    """Map one static selection failure through the shared provenance verifier."""
    if selected.refusal_reason == "revision_validation_failed":
        try:
            layout, inspection = _static_verifier_inputs(selected)
            _verify_static_generated_provenance(
                workspace_root=workspace_root,
                registry_root=registry_root,
                source_root=source_root,
                selected=selected,
                layout=layout,
                inspection=inspection,
            )
        except (OSError, RegistryValidationError, ValueError) as error:
            return _generated_provenance_residue(selected=selected, error=error)
    if selected.refusal_reason == "law_selection_failed":
        return _conformance_residue(
            modelo=selected.modelo,
            revision=selected.revision,
            layout_ids=selected.layout_ids,
            reason="law_selection_failed",
            owner=_GENERATOR_RESIDUE_OWNER,
            reconsideration_condition="Restore a filing-grade law-selection coordinate for the registered revision.",
            detail=selected.refusal_detail or "static classification did not retain a law-selection failure detail",
        )
    if selected.refusal_reason == "layout_unavailable":
        return _conformance_residue(
            modelo=selected.modelo,
            revision=selected.revision,
            layout_ids=selected.layout_ids,
            reason="layout_unavailable",
            owner=_GENERATOR_RESIDUE_OWNER,
            reconsideration_condition=("Supply one stable generated filing layout for every law-selected coordinate."),
            detail=selected.refusal_detail or "static classification did not retain a layout failure detail",
        )
    return _revision_validation_residue(
        selected=selected,
        detail=selected.refusal_detail or "static classification did not retain a validation failure detail",
    )


def _static_verifier_inputs(
    selected: RegistryDiagnosticFilingRevision,
) -> tuple[ExportLayoutDefinition, GeneratedArtifactInspection]:
    """Return copied static verifier inputs without restoring a full inspection model."""
    if selected.layout_json is None or selected.inspection is None or not selected.selection_coordinates:
        raise ValueError("static filing revision has no complete verifier projection")
    return (
        ExportLayoutDefinition.model_validate_json(selected.layout_json),
        selected.inspection,
    )


def _verify_static_generated_provenance(
    *,
    workspace_root: Path,
    registry_root: Path,
    source_root: Path,
    selected: RegistryDiagnosticFilingRevision,
    layout: ExportLayoutDefinition,
    inspection: GeneratedArtifactInspection,
    authority: ValidatedRegistryAuthority | None = None,
) -> tuple[bytes, ExportFragmentProvenanceManifest]:
    """Load and verify provenance using only static revision projection facts."""
    manifest_path = (
        registry_root
        / "modelos"
        / str(selected.modelo)
        / "revisions"
        / str(selected.revision)
        / "export"
        / EXPORT_FRAGMENT_PROVENANCE_FILENAME
    )
    if not manifest_path.is_file():
        raise FileNotFoundError("the selected generated export tree has no canonical provenance manifest")
    manifest_raw = manifest_path.read_bytes()
    manifest = load_export_fragment_provenance_manifest(manifest_raw)
    if manifest.modelo != selected.modelo or manifest.revision_id != selected.revision:
        raise RegistryValidationError("generated provenance identity conflicts with the law-selected revision")
    _verify_generated_revision(
        workspace_root=workspace_root,
        registry_root=registry_root,
        source_root=source_root,
        authority=authority,
        inspection=inspection,
        entry=_ConformanceGenerationEntry(
            modelo=selected.modelo,
            revision=selected.revision,
            design_epoch=manifest.design_epoch,
            filing_year=selected.selection_coordinates[0][0],
        ),
        layout=layout,
    )
    return manifest_raw, manifest


def _generated_provenance_residue(
    *,
    selected: RegistryDiagnosticFilingRevision,
    error: Exception,
) -> FilingExportConformanceResidue:
    """Map every static generated-provenance failure in one place."""
    if isinstance(error, FileNotFoundError):
        return _conformance_residue(
            modelo=selected.modelo,
            revision=selected.revision,
            layout_ids=selected.layout_ids,
            reason="generated_provenance_missing",
            owner=_GENERATOR_RESIDUE_OWNER,
            reconsideration_condition=(
                "Publish canonical generated provenance for the exact selected layout and revision."
            ),
            detail=_residue_detail(error),
        )
    return _conformance_residue(
        modelo=selected.modelo,
        revision=selected.revision,
        layout_ids=selected.layout_ids,
        reason="generated_provenance_invalid",
        owner=_GENERATOR_RESIDUE_OWNER,
        reconsideration_condition=(
            "Regenerate and verify the exact canonical provenance, source bytes, semantic map, and render profile."
        ),
        detail=_residue_detail(error),
    )


def _revision_validation_residue(
    *,
    selected: RegistryDiagnosticFilingRevision,
    detail: str,
) -> FilingExportConformanceResidue:
    """Map copied static selection data that cannot pass validation."""
    return _conformance_residue(
        modelo=selected.modelo,
        revision=selected.revision,
        layout_ids=selected.layout_ids,
        reason="revision_validation_failed",
        owner=_GENERATOR_RESIDUE_OWNER,
        reconsideration_condition="Resolve the canonical revision validation failure before conformance enrollment.",
        detail=detail,
    )


def _conformance_residue(
    *,
    modelo: ModeloId,
    revision: RevisionId,
    layout_ids: tuple[str, ...],
    reason: _ConformanceResidueReason,
    owner: str,
    reconsideration_condition: str,
    detail: str,
) -> FilingExportConformanceResidue:
    """Build one non-success row without losing its owner or remedy condition."""
    return FilingExportConformanceResidue(
        modelo=modelo,
        revision=revision,
        layout_ids=layout_ids,
        reason=reason,
        owner=owner,
        reconsideration_condition=reconsideration_condition,
        detail=detail,
    )


def _residue_detail(error: Exception) -> str:
    """Keep a source failure bounded while retaining a truthful refusal cause."""
    return str(error).splitlines()[0][:500]


def _public_vector_probes(layout: ExportLayoutDefinition) -> tuple[FilingExportOfficialProbe, ...]:
    """Derive public literal probes from the selected official layout only."""
    records = tuple(sorted(layout.records, key=lambda record: record.order))
    if not records:
        raise RegistryValidationError("selected layout declares no records for an official conformance probe")
    first = records[0]
    if not first.required or first.repeat is not None:
        raise RegistryValidationError("first selected record cannot provide a stable official conformance probe")
    prefix_extent = layout.filing_envelope.prefix_extent if layout.filing_envelope is not None else 0
    probes = tuple(
        FilingExportOfficialProbe(
            record_id=str(first.id),
            field_id=str(field.id),
            emitted_offset=prefix_extent + field.offset - 1,
            length=field.length,
        )
        for field in first.fields
        if field.offset is not None and field.length is not None and field.literal is not None
    )
    if not probes:
        raise RegistryValidationError("first selected record declares no positioned literal field for conformance")
    return probes


def _layout_producer_keys(layout: ExportLayoutDefinition) -> frozenset[str]:
    """Return only the typed producer vocabulary actually declared by the selected layout."""
    return frozenset(
        field.producer_key for record in layout.records for field in record.fields if field.producer_key is not None
    )

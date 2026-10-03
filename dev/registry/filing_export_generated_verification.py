"""Verify the generated export tree backing a filing proof."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.ids import ModeloId, RevisionId
from cadrumo.domain.calculations.registry.schema_exports import ExportLayoutDefinition

from .compiler.export_fragment_grammar import EXPORT_FRAGMENT_PROVENANCE_FILENAME
from .maintenance_support import GeneratedArtifactInspection
from .pipeline.export_fragment_provenance import (
    ExportFragmentTarget,
    export_fragment_provenance_manifest_json_bytes,
    load_export_fragment_provenance_manifest,
    verify_export_fragment_provenance_manifest,
)
from .pipeline.joined_record_design import join_record_design_semantics
from .pipeline.record_design_intermediate import load_record_design_intermediate
from .pipeline.render_profile_evidence import RenderProfileSourceEvidence
from .pipeline.render_profile_loading import load_render_profile
from .pipeline.render_profile_source_reader import load_render_profile_source_evidence
from .pipeline.semantic_map import load_semantic_map


@dataclass(frozen=True, slots=True)
class _ConformanceGenerationEntry:
    modelo: ModeloId
    revision: RevisionId
    design_epoch: str
    filing_year: int


def _verify_generated_revision(
    *,
    workspace_root: Path,
    source_root: Path,
    inspection: GeneratedArtifactInspection,
    entry: _ConformanceGenerationEntry,
    layout: ExportLayoutDefinition,
):
    """Verify generated provenance from a static revision inspection."""
    export_root = (
        workspace_root
        / "src/cadrumo/_data/registry/aeat/modelos"
        / str(entry.modelo)
        / "revisions"
        / str(entry.revision)
        / "export"
    )
    manifest_path = export_root / EXPORT_FRAGMENT_PROVENANCE_FILENAME
    manifest = load_export_fragment_provenance_manifest(manifest_path.read_bytes())
    if (
        manifest.modelo != entry.modelo
        or manifest.revision_id != entry.revision
        or manifest.design_epoch != entry.design_epoch
    ):
        raise RegistryValidationError("canonical export manifest identity conflicts with the live proof entry")
    semantic_map = load_semantic_map(
        workspace_root / "dev/registry/mappings" / f"modelo_{entry.modelo}" / entry.design_epoch,
    )
    render_profile = load_render_profile(
        workspace_root / "dev/registry/render_profiles" / f"modelo_{entry.modelo}" / entry.design_epoch,
    )
    intermediate = load_record_design_intermediate(
        source_root,
        inspection.sources,
        source_ref=manifest.source_ref,
        filing_year=entry.filing_year,
        design_epoch=entry.design_epoch,
    )
    joined = join_record_design_semantics(semantic_map, intermediate, inspection)
    claims_official = any(
        rule.evidence.authority_kind != "reviewed_policy"
        for rule in (*render_profile.singleton_rules, *render_profile.width_17_rules)
    )
    source_evidence = (
        load_render_profile_source_evidence(
            source_root / inspection.sources[manifest.source_ref].corpus_path,
            render_profile,
        )
        if claims_official
        else RenderProfileSourceEvidence(design_identity=render_profile.design_identity, entries=())
    )
    verified = verify_export_fragment_provenance_manifest(
        export_root=export_root,
        joined=joined,
        semantic_map=semantic_map,
        target=ExportFragmentTarget(
            modelo=entry.modelo,
            revision_id=entry.revision,
            design_epoch=entry.design_epoch,
        ),
        loaded_layout=layout,
        field_derivations=manifest.field_derivations,
        render_profile=render_profile,
        render_profile_source_evidence=source_evidence,
    )
    if export_fragment_provenance_manifest_json_bytes(verified) != manifest_path.read_bytes():
        raise RegistryValidationError("canonical export manifest bytes changed during live verification")
    return verified, manifest_path

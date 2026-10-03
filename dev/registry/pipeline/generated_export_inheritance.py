"""Select only an exact, generated storage baseline for a child export delta."""

from __future__ import annotations

import tempfile
from hashlib import sha256
from pathlib import Path

from cadrumo.core.storage_environment import prepare_temporary_directory
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from .bootstrap_supersession import bootstrap_layout_supersession_fingerprint
from .export_fragment_provenance_projection import loader_semantic_digest
from .generated_export_inheritance_model import GeneratedExportInheritance, GeneratedExportInheritanceContext


def select_generated_export_inheritance(
    authority: ValidatedRegistryAuthority,
    registry_root: Path,
    *,
    modelo: str,
    revision: str,
    _visited: frozenset[str] = frozenset(),
) -> GeneratedExportInheritanceContext | None:
    """Return a baseline only when the child's entire effective layout is equal.

    This selects storage identity, never legal or review authority. The child
    still renders from its own source, semantic map and profile before equality
    with this baseline can be established by the renderer.
    """
    if revision in _visited:
        raise RegistryValidationError(f"generated export inheritance ancestor cycle at {modelo}/{revision}")
    visited = _visited | {revision}
    definition = authority.modelo(modelo)
    selected = definition.revisions[revision]
    baseline_id = selected.family_storage_baseline
    if baseline_id is None:
        return None
    if str(baseline_id) in visited:
        raise RegistryValidationError(f"generated export inheritance ancestor cycle at {modelo}/{baseline_id}")
    baseline = definition.revisions.get(str(baseline_id))
    if baseline is None:
        raise RegistryValidationError(f"generated export inheritance baseline {baseline_id!r} is absent")
    if len(selected.export_layouts) != 1 or len(baseline.export_layouts) != 1:
        return None
    if selected.export_layouts != baseline.export_layouts:
        return None
    for selected_id in (str(baseline_id), revision):
        evolution_root = (
            registry_root / "modelos" / modelo / "revisions" / selected_id / "casilla_continuidad_evolutions"
        )
        if evolution_root.exists():
            raise RegistryValidationError(
                "generated export inheritance cannot detach a revision with continuity evolutions: "
                f"{modelo}/{selected_id}",
            )
    # Artifact verification imports publication contracts, which refer to the
    # validator. Keep that dependency at the call boundary instead of creating
    # an import cycle while the validator is being defined.
    from .tree_publication_artifacts import verify_generated_export_package

    baseline_root = registry_root / "modelos" / modelo / "revisions" / str(baseline_id)
    export_root = baseline_root / "export"
    manifest = verify_generated_export_package(export_root)
    if str(manifest.modelo) != modelo or str(manifest.revision_id) != str(baseline_id):
        raise RegistryValidationError("generated export inheritance baseline package names another revision")
    source = authority.catalogues.sources.get(manifest.source_ref)
    if source is None or source.sha256 != manifest.source_sha256:
        raise RegistryValidationError("generated export inheritance baseline source pin is not current")
    baseline_layout = baseline.export_layouts[0]
    layout_sha256 = loader_semantic_digest(baseline_layout)
    if manifest.loader_semantic_sha256 != layout_sha256:
        raise RegistryValidationError("generated export inheritance baseline loader semantics changed")
    baseline_context = None
    if manifest.generated_export_inheritance is not None:
        baseline_context = select_generated_export_inheritance(
            authority,
            registry_root,
            modelo=modelo,
            revision=str(baseline_id),
            _visited=visited,
        )
        if baseline_context is None or baseline_context.attestation != manifest.generated_export_inheritance:
            raise RegistryValidationError("generated export inheritance baseline chain attestation changed")
    # A self-consistent old manifest is insufficient: each chain link must
    # reproduce its current official design, semantic map and profile.
    from ._export_tree import render_complete_export_tree
    from .render_check import compare_export_tree_roots, revision_render_inputs
    from .source_defects import source_defects_for

    baseline_inputs = revision_render_inputs(authority, modelo=modelo, revision=str(baseline_id))
    with tempfile.TemporaryDirectory(prefix="cadrumo-export-baseline-", dir=prepare_temporary_directory()) as scratch:
        fresh_root = Path(scratch) / "export"
        fresh = render_complete_export_tree(
            fresh_root,
            revision_id=baseline_inputs.revision_id,
            joined=baseline_inputs.joined,
            semantic_map=baseline_inputs.semantic_map,
            transport_profile=baseline_inputs.transport_profile,
            render_profile=baseline_inputs.render_profile,
            render_profile_source_evidence=baseline_inputs.render_profile_source_evidence,
            source_defects=source_defects_for(str(baseline_inputs.transport_profile.source_ref)),
            inheritance=baseline_context,
        )
        if (
            fresh.layout != baseline_layout
            or not compare_export_tree_roots(
                modelo=modelo,
                revision=str(baseline_id),
                layout_id=baseline_inputs.layout_id,
                committed_root=export_root,
                rendered_root=fresh_root,
            ).reproduced
        ):
            raise RegistryValidationError("generated export inheritance baseline source render is no longer current")
    manifest_path = export_root / "_generation.provenance.json"
    attestation = GeneratedExportInheritance(
        baseline_revision_id=baseline_id,
        baseline_revision_sha256=bootstrap_layout_supersession_fingerprint(baseline_root),
        baseline_manifest_sha256=sha256(manifest_path.read_bytes()).hexdigest(),
        baseline_layout_sha256=layout_sha256,
        baseline_source_ref=manifest.source_ref,
        baseline_source_sha256=manifest.source_sha256,
    )
    return GeneratedExportInheritanceContext(
        attestation=attestation,
        baseline_layout=baseline_layout,
        baseline_context=baseline_context,
    )


def require_generated_export_inheritance(
    expected: GeneratedExportInheritanceContext,
    authority: ValidatedRegistryAuthority,
    registry_root: Path,
    *,
    modelo: str,
    revision: str,
) -> None:
    """Refuse a removed, changed, or newly ambiguous storage baseline."""
    current = select_generated_export_inheritance(authority, registry_root, modelo=modelo, revision=revision)
    if current != expected:
        raise RegistryValidationError("generated export inheritance baseline or effective layout changed")

"""Select only an exact, generated storage baseline for a child export delta."""

from __future__ import annotations

import tempfile
from collections.abc import Mapping
from hashlib import sha256
from pathlib import Path

from cadrumo.core.directory_scan import iter_directory
from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.core.link_safety import is_link_like
from cadrumo.core.storage_environment import prepare_temporary_directory
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.errors import RegistryLoadError, RegistryValidationError
from cadrumo.domain.calculations.registry.ids import SourceRefId
from cadrumo.domain.calculations.registry.schema_exports import ExportLayoutDefinition
from cadrumo.domain.calculations.registry.static_inspection import GeneratedArtifactSource

from ..compiler.loader import load_modelo_directory
from ..compiler.validate_cross_revision import strict_cross_revision_casilla_continuity_failures
from .bootstrap_supersession import bootstrap_layout_supersession_fingerprint
from .export_fragment_provenance_projection import loader_semantic_digest
from .generated_export_inheritance_model import GeneratedExportInheritance, GeneratedExportInheritanceContext


def verify_generated_export_inheritance_storage(
    attestation: GeneratedExportInheritance,
    registry_root: Path,
    *,
    modelo: str,
    effective_layout: ExportLayoutDefinition,
    sources: Mapping[SourceRefId, GeneratedArtifactSource],
    _visited: frozenset[str] = frozenset(),
) -> None:
    """Verify static storage pins without granting baseline render or filing authority.

    Degraded diagnostics retain provenance candidates through this check. A successful
    proof still requires the full validated selector and fresh baseline source render.
    """
    baseline_id = str(attestation.baseline_revision_id)
    if baseline_id in _visited:
        raise RegistryValidationError("generated export inheritance storage has an ancestor cycle")
    from .tree_publication_artifacts import verify_generated_export_package

    baseline_root = registry_root / "modelos" / modelo / "revisions" / baseline_id
    export_root = baseline_root / "export"
    manifest = verify_generated_export_package(export_root)
    manifest_digest = sha256((export_root / "_generation.provenance.json").read_bytes()).hexdigest()
    if (
        str(manifest.modelo) != modelo
        or str(manifest.revision_id) != baseline_id
        or manifest_digest != attestation.baseline_manifest_sha256
        or bootstrap_layout_supersession_fingerprint(baseline_root) != attestation.baseline_revision_sha256
        or loader_semantic_digest(effective_layout) != attestation.baseline_layout_sha256
        or manifest.loader_semantic_sha256 != attestation.baseline_layout_sha256
        or manifest.source_ref != attestation.baseline_source_ref
        or manifest.source_sha256 != attestation.baseline_source_sha256
    ):
        raise RegistryValidationError("generated export inheritance storage differs from its baseline pins")
    source = sources.get(attestation.baseline_source_ref)
    if source is None or source.sha256 != attestation.baseline_source_sha256:
        raise RegistryValidationError("generated export inheritance storage source pin is not current")
    if manifest.generated_export_inheritance is not None:
        verify_generated_export_inheritance_storage(
            manifest.generated_export_inheritance,
            registry_root,
            modelo=modelo,
            effective_layout=effective_layout,
            sources=sources,
            _visited=_visited | {baseline_id},
        )


def select_generated_export_inheritance(
    authority: ValidatedRegistryAuthority,
    registry_root: Path,
    *,
    modelo: str,
    revision: str,
    source_root: Path | None = None,
    _visited: frozenset[str] = frozenset(),
    _require_eligible: bool = False,
    retain_source_chain: bool = False,
) -> GeneratedExportInheritanceContext | None:
    """Return a baseline only when the child's entire effective layout is equal.

    This selects storage identity, never legal or review authority. The child
    still renders from its own source, semantic map and profile before equality
    with this baseline can be established by the renderer. A detached candidate
    cannot retain evolution endpoints. Explicit source-chain staging may use
    the same compact storage only after its live complete continuity agrees
    with the validated authority; injected or stale evolution data still refuses.
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
        if evolution_root.exists() and (
            not retain_source_chain
            or not _validated_continuity_source_chain(authority, registry_root, modelo=modelo, revision=selected_id)
        ):
            if not _require_eligible:
                return None
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
            source_root=source_root,
            _visited=visited,
            _require_eligible=True,
            retain_source_chain=retain_source_chain,
        )
        if baseline_context is None or baseline_context.attestation != manifest.generated_export_inheritance:
            raise RegistryValidationError("generated export inheritance baseline chain attestation changed")
    # A self-consistent old manifest is insufficient: each chain link must
    # reproduce its current official design, semantic map and profile.
    from ._export_tree import render_complete_export_tree
    from .render_check import compare_export_tree_roots, revision_render_inputs
    from .source_defects import source_defects_for

    baseline_inputs = revision_render_inputs(
        authority, modelo=modelo, revision=str(baseline_id), source_root=source_root
    )
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
    retain_source_chain: bool = False,
    source_root: Path | None = None,
) -> None:
    """Refuse changed storage pins or an unvalidated retained continuity chain."""
    current = select_generated_export_inheritance(
        authority,
        registry_root,
        modelo=modelo,
        revision=revision,
        source_root=source_root,
        _require_eligible=True,
        retain_source_chain=retain_source_chain,
    )
    if current != expected:
        raise RegistryValidationError("generated export inheritance baseline or effective layout changed")


def _validated_continuity_source_chain(
    authority: ValidatedRegistryAuthority, registry_root: Path, *, modelo: str, revision: str
) -> bool:
    """Admit only real, nonempty evolution declarations in the unchanged full source."""
    expected = authority.modelo(modelo)
    if not expected.revisions[revision].casilla_continuidad_evolutions:
        return False
    try:
        current = load_modelo_directory(registry_root / "modelos" / modelo)
    except RegistryLoadError:
        return False
    return current == expected and not strict_cross_revision_casilla_continuity_failures((current,))


def generated_export_source_chain_fingerprint(
    registry_root: Path, *, modelo: str, revision: str, omit_target_export: bool = False
) -> str:
    """Pin every source member, omitting only the named export after approved cutover."""
    modelo_root = registry_root / "modelos" / modelo
    if is_link_like(modelo_root) or not modelo_root.is_dir():
        raise RegistryValidationError("generated source-chain origin is not a regular modelo directory")
    omitted = modelo_root / "revisions" / revision / "export"
    members: list[tuple[str, str, str]] = []

    def visit(directory: Path) -> None:
        for child in sorted(iter_directory(directory, require_root=True)):
            if is_link_like(child):
                raise RegistryValidationError("generated source-chain origin contains a linked member")
            if omit_target_export and child == omitted:
                continue
            relative = child.relative_to(modelo_root).as_posix()
            if child.is_dir():
                members.append((relative, "directory", ""))
                visit(child)
            elif child.is_file():
                members.append((relative, "file", sha256(child.read_bytes()).hexdigest()))
            else:
                raise RegistryValidationError("generated source-chain origin contains a non-regular member")

    visit(modelo_root)
    return sha256(canonical_json_bytes(members)).hexdigest()

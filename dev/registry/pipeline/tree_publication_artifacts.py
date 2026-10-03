"""Build, verify, and safely stage generated export package artifacts."""

from __future__ import annotations

import os
import shutil
from pathlib import Path, PurePosixPath

from cadrumo.core.directory_scan import DirectoryEntryKind, scan_directory
from cadrumo.core.fsync import fsync_parent_dir
from cadrumo.core.link_safety import is_link_like
from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ..compiler.export_fragment_grammar import EXPORT_FRAGMENT_PROVENANCE_FILENAME
from ..compiler.loader import load_modelo_directory
from ._export_tree import RenderedExportTree
from .export_fragment_provenance import (
    ExportFragmentProvenanceManifest,
    collect_export_fragment_output_digests,
    load_export_fragment_provenance_manifest,
    verify_export_fragment_provenance_manifest,
)
from .export_fragment_provenance_projection import loader_semantic_digest
from .joined_record_design import JoinedRecordDesign
from .render_profile_evidence import RenderProfileSourceEvidence
from .render_profile_model import RenderProfile
from .semantic_map import SemanticMap
from .tree_publication_contracts import (
    GeneratedExportTransactionPaths,
    GeneratedExportTreePublicationContext,
    export_provenance_file_sha256,
)


def _require_link_free_regular_members_allow_empty(path: Path, *, subject: str) -> None:
    """Admit an empty or partially deleted directory tree without following links."""
    if is_link_like(path) or not path.is_dir():
        raise RegistryValidationError(f"{subject} must be a non-linked directory: {path}")
    for member in scan_directory(path, recursive=True):
        if is_link_like(member):
            raise RegistryValidationError(f"{subject} contains a symbolic link or junction: {member}")
        if not member.is_dir() and not member.is_file():
            raise RegistryValidationError(f"{subject} contains a non-regular member: {member}")


def _verify_generated_export_companion(
    export_root: Path,
    *,
    expected_manifest_sha256: str,
    expected_manifest: ExportFragmentProvenanceManifest,
) -> None:
    """Verify a generated export tree nested inside a staged revision bundle."""
    manifest = verify_generated_export_package(export_root)
    if (
        manifest != expected_manifest
        or export_provenance_file_sha256(export_root / EXPORT_FRAGMENT_PROVENANCE_FILENAME) != expected_manifest_sha256
    ):
        raise RegistryValidationError("staged supersession export does not match the validated candidate")


def verify_generated_export_package(export_root: Path) -> ExportFragmentProvenanceManifest:
    """Return the package manifest after proving its files are exactly the attested outputs."""
    _require_complete_regular_tree(export_root, subject="generated export package")
    manifest_path = export_root / EXPORT_FRAGMENT_PROVENANCE_FILENAME
    if is_link_like(manifest_path) or not manifest_path.is_file():
        raise RegistryValidationError(
            f"generated export package lacks its internal provenance manifest: {manifest_path}",
        )
    manifest = load_export_fragment_provenance_manifest(manifest_path.read_bytes())
    actual_digests = collect_export_fragment_output_digests(export_root)
    if actual_digests != manifest.output_files:
        raise RegistryValidationError("generated export package file digests do not match its provenance manifest")
    actual_files = {
        PurePosixPath(*path.relative_to(export_root).parts)
        for path in scan_directory(export_root, recursive=True, select=DirectoryEntryKind.FILES)
    }
    expected_files = {PurePosixPath(item.relative_path) for item in manifest.output_files}
    expected_files.add(PurePosixPath(EXPORT_FRAGMENT_PROVENANCE_FILENAME))
    if actual_files != expected_files:
        raise RegistryValidationError(
            "generated export package has incomplete or extra files; "
            f"expected={sorted(path.as_posix() for path in expected_files)!r}, "
            f"actual={sorted(path.as_posix() for path in actual_files)!r}",
        )
    return manifest


def _verify_post_cutover_target(
    target_export_root: Path,
    *,
    expected_manifest_sha256: str,
    expected_manifest: ExportFragmentProvenanceManifest,
) -> None:
    if (
        export_provenance_file_sha256(target_export_root / EXPORT_FRAGMENT_PROVENANCE_FILENAME)
        != expected_manifest_sha256
    ):
        raise RegistryValidationError("published export provenance digest does not match the validated candidate")
    if verify_generated_export_package(target_export_root) != expected_manifest:
        raise RegistryValidationError("published export provenance does not match the validated candidate")
    modelo_root = target_export_root.parent.parent.parent
    loaded = load_modelo_directory(modelo_root)
    revision_id = target_export_root.parent.name
    revision = loaded.revisions.get(revision_id)
    if revision is None:
        raise RegistryValidationError(f"published export is not selectable from revision {revision_id!r}")
    matching_layouts = tuple(
        layout
        for layout in revision.export_layouts
        if loader_semantic_digest(layout) == expected_manifest.loader_semantic_sha256
    )
    if len(matching_layouts) != 1:
        raise RegistryValidationError(
            "published export tree does not have exactly one provenance-attested loader layout",
        )


def _verify_recovery_package_against_current_authorities(
    export_root: Path,
    *,
    context: GeneratedExportTreePublicationContext,
    modelo_root: Path,
    joined: JoinedRecordDesign,
    semantic_map: SemanticMap,
    rendered: RenderedExportTree,
    render_profile: RenderProfile,
    render_profile_source_evidence: RenderProfileSourceEvidence,
) -> ExportFragmentProvenanceManifest:
    package_manifest = verify_generated_export_package(export_root)
    loaded = load_modelo_directory(modelo_root)
    revision_id = str(context.validation.target.revision_id)
    revision = loaded.revisions.get(revision_id)
    if revision is None or len(revision.export_layouts) != 1:
        raise RegistryValidationError(
            f"recovered export is not exactly selectable from current revision {revision_id!r}",
        )
    loaded_layout = revision.export_layouts[0]
    if loaded_layout != rendered.layout:
        raise RegistryValidationError("recovered export loader semantics do not equal the current rendered layout")
    verified = verify_export_fragment_provenance_manifest(
        export_root=export_root,
        joined=joined,
        semantic_map=semantic_map,
        target=context.validation.target,
        loaded_layout=loaded_layout,
        field_derivations=rendered.field_derivations,
        render_profile=render_profile,
        render_profile_source_evidence=render_profile_source_evidence,
    )
    if verified != package_manifest:
        raise RegistryValidationError("recovered export package does not match current provenance authority")
    return verified


def stage_verified_candidate_package(
    *,
    candidate_export_root: Path,
    target_root: Path,
    modelo: str,
    revision_id: str,
    expected_manifest_sha256: str,
    expected_manifest: ExportFragmentProvenanceManifest,
) -> Path:
    """Copy exactly one verified package to the target revision's filesystem.

    The caller-owned candidate can live on a different filesystem (as it does
    when a system temporary directory is on ``C:`` and the registry is on
    ``Y:``).  Only this fresh, opaque sibling is ever the source of the final
    ``os.replace`` into ``export/``.
    """
    staging = GeneratedExportTransactionPaths(
        target_root=target_root,
        modelo=modelo,
        revision_id=revision_id,
    ).new_staging_sibling()
    try:
        staging.mkdir()
        for source in scan_directory(candidate_export_root, recursive=True, select=DirectoryEntryKind.FILES):
            if is_link_like(source) or not source.is_file():
                raise RegistryValidationError(f"generated candidate package changed while staging: {source}")
            relative = source.relative_to(candidate_export_root)
            destination = staging / relative
            destination_parent = destination.parent
            destination_parent.mkdir(parents=True, exist_ok=True)
            _copy_and_fsync_regular_file(source, destination)
            fsync_parent_dir(destination)
        fsync_parent_dir(staging / ".staging-complete")
        fsync_parent_dir(staging)
        staged_manifest = verify_generated_export_package(staging)
        if (
            export_provenance_file_sha256(staging / EXPORT_FRAGMENT_PROVENANCE_FILENAME) != expected_manifest_sha256
            or staged_manifest != expected_manifest
        ):
            raise RegistryValidationError("same-volume staged export does not match the validated candidate")
    except OSError as exc:
        _delete_verified_staged_candidate_if_present(staging)
        raise RegistryValidationError(f"cannot stage generated export package beside target: {exc}") from exc
    except RegistryValidationError:
        _delete_verified_staged_candidate_if_present(staging)
        raise
    return staging


def _copy_and_fsync_regular_file(source: Path, destination: Path) -> None:
    """Copy one already enumerated regular member without metadata inheritance."""
    with source.open("rb") as input_stream, destination.open("xb") as output_stream:
        shutil.copyfileobj(input_stream, output_stream)
        output_stream.flush()
        os.fsync(output_stream.fileno())


def _delete_verified_staged_candidate_if_present(staging: Path) -> None:
    if staging.exists():
        _require_complete_regular_tree(staging, subject="generated export staging directory")
        try:
            shutil.rmtree(staging)
        except OSError as exc:
            raise RegistryValidationError(f"cannot delete generated export staging directory {staging}: {exc}") from exc
        if staging.exists():
            raise RegistryValidationError(f"generated export staging residue remains: {staging}")


def _require_complete_regular_tree(path: Path, *, subject: str) -> None:
    if is_link_like(path) or not path.is_dir():
        raise RegistryValidationError(f"{subject} must be a non-linked directory: {path}")
    children = scan_directory(path)
    if not children:
        raise RegistryValidationError(f"{subject} must not be empty: {path}")
    for child in children:
        if is_link_like(child):
            raise RegistryValidationError(f"{subject} contains a symbolic link or junction: {child}")
        if child.is_dir():
            _require_complete_regular_tree(child, subject=subject)
        elif not child.is_file():
            raise RegistryValidationError(f"{subject} contains a non-regular member: {child}")

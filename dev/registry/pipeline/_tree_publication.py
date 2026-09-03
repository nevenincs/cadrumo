"""Recoverable hard-cutover publication for one validated generated export tree.

Generator-owned: ``revisions/<id>/export/`` in full, PLUS the ``export_refs``
field of exactly those casillas the generated layout addresses.  Everything else
in the revision -- casilla labels, legal and source refs, constraints, ordering,
formulae, bindings, parity and application records -- remains outside this
boundary, as do casillas the layout does not address.

``export_refs`` is inside the boundary because it is DERIVED, not authored: the
generator has just computed which casilla each export field addresses, and the
back-reference is that one fact written the other way.  Registry validation
requires both directions, so a generated layout cannot validate while the
casillas it addresses stay silent about it.  Hand-authoring it would mean
copying generated field ids into casilla files by hand -- dual maintenance of a
single fact, which rots on the next regeneration.  The write is textual and
touches only that line, so every other byte of a casilla file survives
unchanged.

The requirement is scoped to fixed-width layouts, and deliberately so: Modelo
100 documents that its revisions carry no per-casilla ``export_refs`` because
they export through an ``xml_dictionary`` layout.  That is correct and must not
be "fixed" by adding refs it should not have.

The internal JSON provenance member moves with the generated TOML tree, while
the production registry loader continues to consume only its TOML fragments.
"""

from __future__ import annotations

import os
import secrets
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from cadrumo.core.directory_scan import DirectoryEntryKind, scan_directory
from cadrumo.core.fsync import fsync_parent_dir
from cadrumo.core.hashing import canonical_json_bytes, hash_file
from cadrumo.core.link_safety import is_link_like
from cadrumo.core.locks import exclusive_file_lock
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.loader import load_modelo_directory

from ._casilla_export_refs import export_refs_by_casilla, write_generated_casilla_export_refs
from ._export_tree import RenderedExportTree
from ._provenance_manifest import (
    EXPORT_FRAGMENT_PROVENANCE_FILENAME,
    ExportFragmentOutputDigest,
    ExportFragmentProvenanceManifest,
    collect_export_fragment_output_digests,
    load_export_fragment_provenance_manifest,
    loader_semantic_digest,
    verify_export_fragment_provenance_manifest,
)
from ._render_profile import RenderProfile, RenderProfileSourceEvidence
from ._semantic_map import SemanticMap
from ._semantic_map_join import JoinedRecordDesign
from ._tree_paths import contains
from ._tree_validation import (
    GeneratedExportTreeValidationContext,
    ValidatedGeneratedExportTree,
    validate_generated_export_tree,
)

__all__ = [
    "GeneratedExportTreePublicationContext",
    "GeneratedExportTreeTargetStateReceipt",
    "PublishedGeneratedExportTree",
    "publish_validated_generated_export_tree",
]


_LEGACY_SIBLING_MANIFEST: Final[str] = "export.provenance.json"
_JOURNAL_SCHEMA_VERSION: Final[int] = 1
_SHA256_PATTERN: Final[str] = r"^[0-9a-f]{64}$"


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class _PublicationJournal(_StrictModel):
    """Crash-recovery facts for an opaque export-directory transaction."""

    schema_version: Literal[1]
    state: Literal["intent", "backup_staged", "candidate_live", "committed"]
    modelo: str = Field(min_length=1)
    revision_id: str = Field(min_length=1)
    candidate_export: str = Field(min_length=1)
    backup_export: str = Field(min_length=1)
    candidate_manifest_sha256: str = Field(pattern=_SHA256_PATTERN)


@dataclass(frozen=True, slots=True)
class GeneratedExportTreePublicationContext:
    """Explicit caller roots and the validated candidate for one export cutover."""

    validation: GeneratedExportTreeValidationContext
    temporary_root: Path
    target_root: Path
    target_export_root: Path
    expected_target_state: GeneratedExportTreeTargetStateReceipt | None = None


@dataclass(frozen=True, slots=True)
class GeneratedExportTreeTargetStateReceipt:
    """The target state a read-only check observed before publication."""

    manifest_sha256: str | None
    output_files: tuple[ExportFragmentOutputDigest, ...]

    @classmethod
    def observe(cls, export_root: Path) -> GeneratedExportTreeTargetStateReceipt:
        if not export_root.exists():
            return cls(manifest_sha256=None, output_files=())
        return cls(
            manifest_sha256=_sha256(export_root / EXPORT_FRAGMENT_PROVENANCE_FILENAME),
            output_files=collect_export_fragment_output_digests(export_root),
        )


@dataclass(frozen=True, slots=True)
class PublishedGeneratedExportTree:
    """The precise generated export tree selected through the loader boundary and cut over."""

    validated: ValidatedGeneratedExportTree | None
    export_root: Path
    provenance_manifest_path: Path


def publish_validated_generated_export_tree(
    *,
    context: GeneratedExportTreePublicationContext,
    joined: JoinedRecordDesign,
    semantic_map: SemanticMap,
    rendered: RenderedExportTree,
    render_profile: RenderProfile,
    render_profile_source_evidence: RenderProfileSourceEvidence,
) -> PublishedGeneratedExportTree:
    """Validate, journal, swap, verify, and finalize one generated export tree.

    No prior export content is parsed, copied, combined with the candidate, or
    exposed as a fallback.  An existing tree is an opaque rollback directory
    while the transaction is live, and is deleted after the candidate passes its
    post-cutover manifest, digest, and production-loader checks.
    """
    candidate_export_root, target_export_root = _prepare_publication_paths(context)
    revision_root = target_export_root.parent
    journal_path = _journal_path(context)
    lock_identity = _lock_identity(context)

    with exclusive_file_lock(lock_identity):
        _require_expected_target_state(context, target_export_root)
        recovery_completed = _recover_interrupted_publication(
            context=context,
            target_export_root=target_export_root,
            journal_path=journal_path,
            joined=joined,
            semantic_map=semantic_map,
            rendered=rendered,
            render_profile=render_profile,
            render_profile_source_evidence=render_profile_source_evidence,
        )
        if recovery_completed:
            return PublishedGeneratedExportTree(
                validated=None,
                export_root=target_export_root,
                provenance_manifest_path=target_export_root / EXPORT_FRAGMENT_PROVENANCE_FILENAME,
            )
        _require_no_stale_sibling_manifest(revision_root, subject="generated target revision")

        # This is the immediate pre-cutover proof.  The candidate's complete
        # authoritative registry is validated before the transaction journal or
        # either export directory can be changed.
        validated = validate_generated_export_tree(
            context=context.validation,
            joined=joined,
            semantic_map=semantic_map,
            rendered=rendered,
            render_profile=render_profile,
            render_profile_source_evidence=render_profile_source_evidence,
        )
        candidate_manifest = _verify_generated_export_package(candidate_export_root)
        candidate_manifest_sha256 = _sha256(candidate_export_root / EXPORT_FRAGMENT_PROVENANCE_FILENAME)
        staged_candidate_export_root = _stage_verified_candidate_package(
            candidate_export_root=candidate_export_root,
            target_export_root=target_export_root,
            expected_manifest_sha256=candidate_manifest_sha256,
            expected_manifest=candidate_manifest,
        )

        backup_export_root = _rollback_sibling(
            target_root=context.target_root.resolve(),
            modelo=str(context.validation.target.modelo),
            revision_id=str(context.validation.target.revision_id),
        )
        journal = _PublicationJournal(
            schema_version=_JOURNAL_SCHEMA_VERSION,
            state="intent",
            modelo=str(context.validation.target.modelo),
            revision_id=str(context.validation.target.revision_id),
            candidate_export=str(staged_candidate_export_root),
            backup_export=str(backup_export_root),
            candidate_manifest_sha256=candidate_manifest_sha256,
        )
        _write_journal(journal_path, journal)

        had_target = target_export_root.exists()
        if had_target:
            os.replace(target_export_root, backup_export_root)
            fsync_parent_dir(target_export_root)
            journal = journal.model_copy(update={"state": "backup_staged"})
            _write_journal(journal_path, journal)
        try:
            os.replace(staged_candidate_export_root, target_export_root)
        except OSError as publish_error:
            _restore_backup_or_raise(
                target_export_root=target_export_root,
                backup_export_root=backup_export_root,
                publish_error=publish_error,
            )
            _delete_verified_staged_candidate_if_present(staged_candidate_export_root)
            _delete_journal(journal_path)
            raise RegistryValidationError(
                f"generated export publication failed; the previous target was restored: {publish_error}",
            ) from publish_error
        fsync_parent_dir(target_export_root)
        journal = journal.model_copy(update={"state": "candidate_live"})
        _write_journal(journal_path, journal)

        _verify_post_cutover_target(
            target_export_root,
            expected_manifest_sha256=candidate_manifest_sha256,
            expected_manifest=candidate_manifest,
        )
        _write_export_refs(rendered, revision_root)
        journal = journal.model_copy(update={"state": "committed"})
        _write_journal(journal_path, journal)
        if had_target:
            _delete_opaque_rollback_tree(backup_export_root)
        _delete_journal(journal_path)

    return PublishedGeneratedExportTree(
        validated=validated,
        export_root=target_export_root,
        provenance_manifest_path=target_export_root / EXPORT_FRAGMENT_PROVENANCE_FILENAME,
    )


def _write_export_refs(rendered: RenderedExportTree, revision_root: Path) -> None:
    """Write the derived casilla back-references the docstring scopes this module to.

    Idempotent and reconciling, so recovery re-runs may call it again over a
    partially written revision.
    """
    write_generated_casilla_export_refs(
        revision_root,
        export_refs_by_casilla=export_refs_by_casilla(rendered),
    )


def _prepare_publication_paths(context: GeneratedExportTreePublicationContext) -> tuple[Path, Path]:
    temporary_root = _require_narrow_root(context.temporary_root, subject="generated temporary root")
    target_root = _require_narrow_root(context.target_root, subject="generated publication target root")
    _require_disjoint_roots(temporary_root, target_root)
    candidate_registry_root = _require_descendant_directory(
        context.validation.registry_root,
        root=temporary_root,
        subject="generated candidate registry root",
    )
    modelo_id = str(context.validation.target.modelo)
    revision_id = str(context.validation.target.revision_id)
    candidate_export_root = _require_descendant_directory(
        candidate_registry_root / "modelos" / modelo_id / "revisions" / revision_id / "export",
        root=temporary_root,
        subject="generated candidate export root",
    )
    _require_no_stale_sibling_manifest(candidate_export_root.parent, subject="generated candidate revision")
    _require_complete_regular_tree(candidate_export_root, subject="generated candidate export root")

    target_export_root = _require_target_export_root(
        context.target_export_root,
        target_root=target_root,
        modelo_id=modelo_id,
        revision_id=revision_id,
    )
    _require_no_stale_sibling_manifest(target_export_root.parent, subject="generated target revision")
    if target_export_root.exists():
        _require_complete_regular_tree(target_export_root, subject="generated target export root")
    return candidate_export_root, target_export_root


def _require_expected_target_state(context: GeneratedExportTreePublicationContext, target_export_root: Path) -> None:
    """Refuse a target that changed after the read-only preflight and before lock entry."""
    expected = context.expected_target_state
    if expected is None:
        return
    if expected.manifest_sha256 is None:
        if target_export_root.exists():
            raise RegistryValidationError("generated export target appeared after check and before publication lock")
        return
    if (
        not target_export_root.exists()
        or _sha256(target_export_root / EXPORT_FRAGMENT_PROVENANCE_FILENAME) != expected.manifest_sha256
        or collect_export_fragment_output_digests(target_export_root) != expected.output_files
    ):
        raise RegistryValidationError("generated export target changed after check and before publication lock")


def _require_narrow_root(path: Path, *, subject: str) -> Path:
    if is_link_like(path) or not path.is_dir():
        raise RegistryValidationError(f"{subject} must be an existing non-linked directory: {path}")
    resolved = path.resolve()
    workspace_root = Path.cwd().resolve()
    if resolved == resolved.parent or resolved == workspace_root or contains(resolved, workspace_root):
        raise RegistryValidationError(f"{subject} is too broad for generated publication: {path}")
    if (resolved / ".git").exists():
        raise RegistryValidationError(f"{subject} must not be a workspace root: {path}")
    return resolved


def _require_disjoint_roots(temporary_root: Path, target_root: Path) -> None:
    if contains(temporary_root, target_root) or contains(target_root, temporary_root):
        raise RegistryValidationError("generated temporary and publication target roots must be disjoint")


def _require_descendant_directory(path: Path, *, root: Path, subject: str) -> Path:
    resolved = _require_descendant(path, root=root, subject=subject)
    _require_existing_link_free_path(resolved, root=root, subject=subject)
    if not resolved.is_dir():
        raise RegistryValidationError(f"{subject} must be a directory: {path}")
    return resolved


def _require_target_export_root(
    path: Path,
    *,
    target_root: Path,
    modelo_id: str,
    revision_id: str,
) -> Path:
    resolved = _require_descendant(path, root=target_root, subject="generated target export root")
    expected = target_root / "modelos" / modelo_id / "revisions" / revision_id / "export"
    if resolved != expected:
        raise RegistryValidationError(
            f"generated target export root must be {expected}, got {resolved}",
        )
    _require_existing_link_free_path(resolved.parent, root=target_root, subject="generated target revision root")
    if not resolved.parent.is_dir():
        raise RegistryValidationError(f"generated target revision root must be a directory: {resolved.parent}")
    if resolved.exists() and (is_link_like(resolved) or not resolved.is_dir()):
        raise RegistryValidationError(f"generated target export root must be a non-linked directory: {resolved}")
    return resolved


def _require_descendant(path: Path, *, root: Path, subject: str) -> Path:
    if is_link_like(path):
        raise RegistryValidationError(f"{subject} must not be a symbolic link or junction: {path}")
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise RegistryValidationError(f"{subject} must resolve within its explicit caller root: {path}") from exc
    if not relative.parts:
        raise RegistryValidationError(f"{subject} must be a strict descendant of its explicit caller root: {path}")
    return resolved


def _require_existing_link_free_path(path: Path, *, root: Path, subject: str) -> None:
    cursor = root
    for part in path.relative_to(root).parts:
        cursor = cursor / part
        if not cursor.exists():
            raise RegistryValidationError(f"{subject} is missing: {cursor}")
        if is_link_like(cursor):
            raise RegistryValidationError(f"{subject} contains a symbolic link or junction: {cursor}")


def _require_no_stale_sibling_manifest(revision_root: Path, *, subject: str) -> None:
    stale = revision_root / _LEGACY_SIBLING_MANIFEST
    if stale.exists() or is_link_like(stale):
        raise RegistryValidationError(f"{subject} refuses stale sibling provenance manifest: {stale}")


def _verify_generated_export_package(export_root: Path) -> ExportFragmentProvenanceManifest:
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
    if _sha256(target_export_root / EXPORT_FRAGMENT_PROVENANCE_FILENAME) != expected_manifest_sha256:
        raise RegistryValidationError("published export provenance digest does not match the validated candidate")
    if _verify_generated_export_package(target_export_root) != expected_manifest:
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


def _recover_interrupted_publication(
    *,
    context: GeneratedExportTreePublicationContext,
    target_export_root: Path,
    journal_path: Path,
    joined: JoinedRecordDesign,
    semantic_map: SemanticMap,
    rendered: RenderedExportTree,
    render_profile: RenderProfile,
    render_profile_source_evidence: RenderProfileSourceEvidence,
) -> bool:
    if not journal_path.exists():
        return False
    journal = _load_journal(journal_path)
    if journal.modelo != str(context.validation.target.modelo) or journal.revision_id != str(
        context.validation.target.revision_id
    ):
        raise RegistryValidationError(f"generated publication journal does not belong to this target: {journal_path}")
    backup_export_root = _journal_backup_path(journal, target_export_root, context.target_root.resolve())
    if _retire_completed_legacy_orphan_journal(
        context=context,
        journal=journal,
        journal_path=journal_path,
        target_export_root=target_export_root,
        backup_export_root=backup_export_root,
    ):
        return False
    staged_candidate_export_root = _journal_staged_candidate_path(journal, target_export_root)
    candidate_is_verified = staged_candidate_export_root.exists() and _matches_journal_candidate(
        staged_candidate_export_root,
        journal,
    )
    target_is_verified = target_export_root.exists() and _matches_journal_candidate(target_export_root, journal)

    if target_is_verified:
        target_manifest = _verify_recovery_package_against_current_authorities(
            target_export_root,
            context=context,
            joined=joined,
            semantic_map=semantic_map,
            rendered=rendered,
            render_profile=render_profile,
            render_profile_source_evidence=render_profile_source_evidence,
        )
        _verify_post_cutover_target(
            target_export_root,
            expected_manifest_sha256=journal.candidate_manifest_sha256,
            expected_manifest=target_manifest,
        )
        _write_export_refs(rendered, target_export_root.parent)
        _delete_opaque_rollback_if_present(backup_export_root)
        _delete_journal(journal_path)
        return True
    if backup_export_root.exists():
        if candidate_is_verified:
            candidate_manifest = _verify_recovery_package_against_current_authorities(
                staged_candidate_export_root,
                context=context,
                joined=joined,
                semantic_map=semantic_map,
                rendered=rendered,
                render_profile=render_profile,
                render_profile_source_evidence=render_profile_source_evidence,
            )
            if target_export_root.exists():
                _move_failed_candidate_aside(target_export_root)
            os.replace(staged_candidate_export_root, target_export_root)
            fsync_parent_dir(target_export_root)
            _verify_post_cutover_target(
                target_export_root,
                expected_manifest_sha256=journal.candidate_manifest_sha256,
                expected_manifest=candidate_manifest,
            )
            _delete_opaque_rollback_tree(backup_export_root)
            _delete_journal(journal_path)
            return True
        if target_export_root.exists():
            _move_failed_candidate_aside(target_export_root)
        os.replace(backup_export_root, target_export_root)
        fsync_parent_dir(target_export_root)
        _delete_journal(journal_path)
        return False
    if candidate_is_verified and not target_export_root.exists():
        candidate_manifest = _verify_recovery_package_against_current_authorities(
            staged_candidate_export_root,
            context=context,
            joined=joined,
            semantic_map=semantic_map,
            rendered=rendered,
            render_profile=render_profile,
            render_profile_source_evidence=render_profile_source_evidence,
        )
        os.replace(staged_candidate_export_root, target_export_root)
        fsync_parent_dir(target_export_root)
        _verify_post_cutover_target(
            target_export_root,
            expected_manifest_sha256=journal.candidate_manifest_sha256,
            expected_manifest=candidate_manifest,
        )
        _write_export_refs(rendered, target_export_root.parent)
        _delete_journal(journal_path)
        return True
    if target_export_root.exists():
        _delete_journal(journal_path)
        return False
    raise RegistryValidationError(f"generated publication journal cannot recover a live export: {journal_path}")


def _verify_recovery_package_against_current_authorities(
    export_root: Path,
    *,
    context: GeneratedExportTreePublicationContext,
    joined: JoinedRecordDesign,
    semantic_map: SemanticMap,
    rendered: RenderedExportTree,
    render_profile: RenderProfile,
    render_profile_source_evidence: RenderProfileSourceEvidence,
) -> ExportFragmentProvenanceManifest:
    package_manifest = _verify_generated_export_package(export_root)
    modelo_root = export_root.parent.parent.parent
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


def _matches_journal_candidate(export_root: Path, journal: _PublicationJournal) -> bool:
    try:
        _verify_generated_export_package(export_root)
        return _sha256(export_root / EXPORT_FRAGMENT_PROVENANCE_FILENAME) == journal.candidate_manifest_sha256
    except (OSError, RegistryValidationError):
        return False


def _journal_backup_path(
    journal: _PublicationJournal,
    target_export_root: Path,
    target_root: Path,
) -> Path:
    backup = Path(journal.backup_export)
    if backup.parent != target_root:
        raise RegistryValidationError("generated publication journal backup escapes the target registry root")
    if not backup.name.startswith(
        f".generated-export-backup-{journal.modelo}-{journal.revision_id}-",
    ):
        raise RegistryValidationError("generated publication journal backup name is not transaction-scoped")
    return backup


def _retire_completed_legacy_orphan_journal(
    *,
    context: GeneratedExportTreePublicationContext,
    journal: _PublicationJournal,
    journal_path: Path,
    target_export_root: Path,
    backup_export_root: Path,
) -> bool:
    """Forget exactly one pre-staging transaction that provably changed nothing.

    Before same-volume staging, an ``intent`` journal could point at a system
    temporary candidate on another volume.  A failed replace may have already
    restored (or never displaced) the target and removed both temporary
    candidates before this process sees the journal.  This narrow shape has no
    remaining mutation to recover.  Every live candidate, backup, target, or
    different transaction state stays fail-closed for normal recovery.
    """
    expected = context.expected_target_state
    recorded_candidate = Path(journal.candidate_export)
    if not (
        journal.state == "intent"
        and expected is not None
        and expected.manifest_sha256 is None
        and expected.output_files == ()
        and not target_export_root.exists()
        and not backup_export_root.exists()
        and not recorded_candidate.exists()
        and not is_link_like(recorded_candidate)
    ):
        return False
    _delete_journal(journal_path)
    return True


def _rollback_sibling(
    *,
    target_root: Path,
    modelo: str,
    revision_id: str,
) -> Path:
    backup = target_root / (f".generated-export-backup-{modelo}-{revision_id}-{secrets.token_hex(16)}")
    if backup.exists() or is_link_like(backup):
        raise RegistryValidationError(f"generated export rollback sibling unexpectedly exists: {backup}")
    return backup


def _staging_sibling(target_export_root: Path) -> Path:
    """Return one opaque, same-volume candidate sibling for the final swap."""
    staging = target_export_root.with_name(
        f".{target_export_root.name}.generated-stage-{secrets.token_hex(16)}",
    )
    if staging.exists() or is_link_like(staging):
        raise RegistryValidationError(f"generated export staging sibling unexpectedly exists: {staging}")
    return staging


def _stage_verified_candidate_package(
    *,
    candidate_export_root: Path,
    target_export_root: Path,
    expected_manifest_sha256: str,
    expected_manifest: ExportFragmentProvenanceManifest,
) -> Path:
    """Copy exactly one verified package to the target revision's filesystem.

    The caller-owned candidate can live on a different filesystem (as it does
    when a system temporary directory is on ``C:`` and the registry is on
    ``Y:``).  Only this fresh, opaque sibling is ever the source of the final
    ``os.replace`` into ``export/``.
    """
    staging = _staging_sibling(target_export_root)
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
        staged_manifest = _verify_generated_export_package(staging)
        if (
            _sha256(staging / EXPORT_FRAGMENT_PROVENANCE_FILENAME) != expected_manifest_sha256
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


def _journal_staged_candidate_path(journal: _PublicationJournal, target_export_root: Path) -> Path:
    candidate = Path(journal.candidate_export)
    prefix = f".{target_export_root.name}.generated-stage-"
    if candidate.parent != target_export_root.parent or not candidate.name.startswith(prefix):
        raise RegistryValidationError(
            "generated publication journal candidate is not a target-revision staging sibling",
        )
    if is_link_like(candidate):
        raise RegistryValidationError("generated publication journal candidate must not be a symbolic link or junction")
    return candidate


def _delete_verified_staged_candidate_if_present(staging: Path) -> None:
    if staging.exists():
        _require_complete_regular_tree(staging, subject="generated export staging directory")
        try:
            shutil.rmtree(staging)
        except OSError as exc:
            raise RegistryValidationError(f"cannot delete generated export staging directory {staging}: {exc}") from exc
        if staging.exists():
            raise RegistryValidationError(f"generated export staging residue remains: {staging}")


def _journal_path(context: GeneratedExportTreePublicationContext) -> Path:
    return context.target_root.resolve() / f"{_transaction_stem(context)}.json"


def _lock_identity(context: GeneratedExportTreePublicationContext) -> Path:
    return context.target_root.resolve() / _transaction_stem(context)


def _transaction_stem(context: GeneratedExportTreePublicationContext) -> str:
    modelo = str(context.validation.target.modelo)
    revision_id = str(context.validation.target.revision_id)
    return f".generated-export-transaction-{modelo}-{revision_id}"


def _restore_backup_or_raise(
    *,
    target_export_root: Path,
    backup_export_root: Path,
    publish_error: OSError,
) -> None:
    if not backup_export_root.exists():
        raise RegistryValidationError(f"generated export publication failed: {publish_error}") from publish_error
    try:
        os.replace(backup_export_root, target_export_root)
        fsync_parent_dir(target_export_root)
    except OSError as restore_error:
        raise RegistryValidationError(
            "generated export publication failed and the previous export could not be restored; "
            f"publication_error={publish_error}; restoration_error={restore_error}",
        ) from restore_error
    return None


def _delete_opaque_rollback_if_present(backup_export_root: Path) -> None:
    if backup_export_root.exists():
        _delete_opaque_rollback_tree(backup_export_root)


def _delete_opaque_rollback_tree(backup_export_root: Path) -> None:
    _require_complete_regular_tree(backup_export_root, subject="generated export rollback directory")
    try:
        shutil.rmtree(backup_export_root)
    except OSError as exc:
        raise RegistryValidationError(
            f"cannot delete generated export rollback directory {backup_export_root}: {exc}",
        ) from exc
    if backup_export_root.exists():
        raise RegistryValidationError(f"generated export rollback residue remains: {backup_export_root}")


def _move_failed_candidate_aside(target_export_root: Path) -> None:
    failed = target_export_root.with_name(f".{target_export_root.name}.generator-invalid-{secrets.token_hex(16)}")
    os.replace(target_export_root, failed)
    try:
        _delete_opaque_rollback_tree(failed)
    except BaseException:
        if not target_export_root.exists() and failed.exists():
            os.replace(failed, target_export_root)
        raise


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


def _write_journal(path: Path, journal: _PublicationJournal) -> None:
    payload = canonical_json_bytes(journal.model_dump(mode="json"))
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
        fsync_parent_dir(path)
    except OSError as exc:
        raise RegistryValidationError(f"cannot persist generated export publication journal {path}: {exc}") from exc
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def _load_journal(path: Path) -> _PublicationJournal:
    if is_link_like(path) or not path.is_file():
        raise RegistryValidationError(f"generated publication journal must be a regular file: {path}")
    raw = path.read_bytes()
    try:
        journal = _PublicationJournal.model_validate_json(raw)
    except ValidationError as exc:
        raise RegistryValidationError(f"generated publication journal is invalid: {path}") from exc
    if raw != canonical_json_bytes(journal.model_dump(mode="json")):
        raise RegistryValidationError(f"generated publication journal is not canonical JSON: {path}")
    return journal


def _delete_journal(path: Path) -> None:
    if path.exists():
        path.unlink()
        fsync_parent_dir(path)


def _sha256(path: Path) -> str:
    if is_link_like(path) or not path.is_file():
        raise RegistryValidationError(f"generated export provenance path must be a regular file: {path}")
    digest, _byte_count = hash_file(path)
    return digest



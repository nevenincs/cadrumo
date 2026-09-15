"""Recoverable hard-cutover publication for one validated generated export tree.

Generator-owned: ``revisions/<id>/export/`` in full and nothing else.  Every
other member of the revision -- casilla declarations, labels, legal and source
refs, constraints, ordering, formulae, bindings, parity and application records
-- remains outside this boundary.  A casilla's ``export_refs`` is not written
here or anywhere: the registry loader derives it from the layout this module
publishes, so the swapped-in tree is the whole of the change.

The internal JSON provenance member moves with the generated TOML tree, while
the production registry loader continues to consume only its TOML fragments.
"""

from __future__ import annotations

import os
import secrets
import shutil
import tempfile
from collections.abc import Callable
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

from ..compiler.loader import load_modelo_directory
from ..conformance.manager import reset_conformance_cache
from ._export_tree import RenderedExportTree
from ._tree_validation import (
    GeneratedExportTreeValidationContext,
    ValidatedGeneratedExportTree,
    validate_generated_export_tree,
)
from .export_fragment_provenance import (
    EXPORT_FRAGMENT_PROVENANCE_FILENAME,
    LEGACY_EXPORT_FRAGMENT_PROVENANCE_FILENAME,
    SHA256_PATTERN,
    ExportFragmentOutputDigest,
    ExportFragmentProvenanceManifest,
    collect_export_fragment_output_digests,
    load_export_fragment_provenance_manifest,
    loader_semantic_digest,
    verify_export_fragment_provenance_manifest,
)
from .joined_record_design import JoinedRecordDesign
from .render_profile import RenderProfile, RenderProfileSourceEvidence
from .semantic_map import SemanticMap
from .tree_paths import contains

__all__ = [
    "GeneratedExportPublicationJournal",
    "GeneratedExportTransactionPaths",
    "GeneratedExportTreePublicationContext",
    "GeneratedExportTreeTargetStateReceipt",
    "PublishedGeneratedExportTree",
    "export_provenance_file_sha256",
    "load_generated_export_publication_journal",
    "publish_validated_generated_export_tree",
    "recover_interrupted_publication",
    "require_expected_target_state",
    "stage_verified_candidate_package",
    "verify_generated_export_package",
    "write_generated_export_publication_journal",
]


_JOURNAL_SCHEMA_VERSION: Final[Literal[1]] = 1


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class GeneratedExportPublicationJournal(_StrictModel):
    """Crash-recovery facts for an opaque export-directory transaction."""

    schema_version: Literal[1]
    state: Literal["intent", "backup_staged", "candidate_live", "committed"]
    modelo: str = Field(min_length=1)
    revision_id: str = Field(min_length=1)
    candidate_export: str = Field(min_length=1)
    backup_export: str = Field(min_length=1)
    candidate_manifest_sha256: str = Field(pattern=SHA256_PATTERN)


@dataclass(frozen=True, slots=True)
class GeneratedExportTreePublicationContext:
    """Explicit caller roots and the validated candidate for one export cutover."""

    validation: GeneratedExportTreeValidationContext
    temporary_root: Path
    target_root: Path
    target_export_root: Path
    expected_target_state: GeneratedExportTreeTargetStateReceipt | None = None
    #: Replaces one export directory with another for cutover, rollback and
    #: recovery. A caller proving the rollback path supplies a replacement that
    #: refuses one specific swap; publication itself always uses ``os.replace``.
    replace_export_directory: Callable[[Path, Path], None] = os.replace


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
            manifest_sha256=export_provenance_file_sha256(export_root / EXPORT_FRAGMENT_PROVENANCE_FILENAME),
            output_files=collect_export_fragment_output_digests(export_root),
        )


@dataclass(frozen=True, slots=True)
class PublishedGeneratedExportTree:
    """The precise generated export tree selected through the loader boundary and cut over."""

    validated: ValidatedGeneratedExportTree | None
    export_root: Path
    provenance_manifest_path: Path


@dataclass(frozen=True, slots=True)
class GeneratedExportTransactionPaths:
    """The registry-root siblings one modelo/revision export transaction owns.

    The journal and lock identity are fixed per target. Each rollback backup and
    staging sibling is a fresh, opaque name under a transaction-scoped prefix, so
    recovery recognises exactly the siblings this transaction may own.
    """

    target_root: Path
    modelo: str
    revision_id: str

    @classmethod
    def for_context(cls, context: GeneratedExportTreePublicationContext) -> GeneratedExportTransactionPaths:
        """The transaction paths under a publication context's resolved target root."""
        return cls(
            target_root=context.target_root.resolve(),
            modelo=str(context.validation.target.modelo),
            revision_id=str(context.validation.target.revision_id),
        )

    @property
    def lock_identity(self) -> Path:
        """The identity whose ``.lock`` sidecar serialises this transaction."""
        return self.target_root / f".generated-export-transaction-{self.modelo}-{self.revision_id}"

    @property
    def journal(self) -> Path:
        """The crash-recovery journal beside the lock identity."""
        return self.target_root / f"{self.lock_identity.name}.json"

    @property
    def backup_prefix(self) -> str:
        """The name prefix every rollback backup sibling of this transaction carries."""
        return f".generated-export-backup-{self.modelo}-{self.revision_id}-"

    @property
    def staging_prefix(self) -> str:
        """The name prefix every same-volume staging sibling of this transaction carries."""
        return f".generated-export-stage-{self.modelo}-{self.revision_id}-"

    def new_backup_sibling(self) -> Path:
        """Return a fresh rollback backup sibling that does not exist yet."""
        backup = self.target_root / f"{self.backup_prefix}{secrets.token_hex(16)}"
        if backup.exists() or is_link_like(backup):
            raise RegistryValidationError(f"generated export rollback sibling unexpectedly exists: {backup}")
        return backup

    def new_staging_sibling(self) -> Path:
        """Return a fresh same-volume staging sibling that does not exist yet.

        It lives beside ``modelos/`` at the registry root, never inside the revision
        directory: ``load_modelo_directory`` recursively validates every file under
        a revision directory and refuses a staging sibling parked next to ``export/``.
        """
        staging = self.target_root / f"{self.staging_prefix}{secrets.token_hex(16)}"
        if staging.exists() or is_link_like(staging):
            raise RegistryValidationError(f"generated export staging sibling unexpectedly exists: {staging}")
        return staging


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
    candidate_export_root = _prepare_candidate_publication_path(context)
    transaction_paths = GeneratedExportTransactionPaths.for_context(context)
    journal_path = transaction_paths.journal
    lock_identity = transaction_paths.lock_identity

    with exclusive_file_lock(lock_identity):
        target_export_root = _admit_target_publication_path(context)
        revision_root = target_export_root.parent
        require_expected_target_state(context, target_export_root)
        recovery_completed = recover_interrupted_publication(
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
            # Recovery finalized (or re-finalized) a candidate as live, which
            # is outside anything the conformance snapshot cache's key covers.
            # See reset_conformance_cache.
            reset_conformance_cache()
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
        candidate_manifest = verify_generated_export_package(candidate_export_root)
        candidate_manifest_sha256 = export_provenance_file_sha256(
            candidate_export_root / EXPORT_FRAGMENT_PROVENANCE_FILENAME
        )
        publication_target_root = context.target_root.resolve()
        publication_modelo = str(context.validation.target.modelo)
        publication_revision_id = str(context.validation.target.revision_id)
        staged_candidate_export_root = stage_verified_candidate_package(
            candidate_export_root=candidate_export_root,
            target_root=publication_target_root,
            modelo=publication_modelo,
            revision_id=publication_revision_id,
            expected_manifest_sha256=candidate_manifest_sha256,
            expected_manifest=candidate_manifest,
        )

        backup_export_root = transaction_paths.new_backup_sibling()
        journal = GeneratedExportPublicationJournal(
            schema_version=_JOURNAL_SCHEMA_VERSION,
            state="intent",
            modelo=str(context.validation.target.modelo),
            revision_id=str(context.validation.target.revision_id),
            candidate_export=str(staged_candidate_export_root),
            backup_export=str(backup_export_root),
            candidate_manifest_sha256=candidate_manifest_sha256,
        )
        write_generated_export_publication_journal(journal_path, journal)

        had_target = target_export_root.exists()
        if had_target:
            context.replace_export_directory(target_export_root, backup_export_root)
            fsync_parent_dir(target_export_root)
            journal = journal.model_copy(update={"state": "backup_staged"})
            write_generated_export_publication_journal(journal_path, journal)
        try:
            context.replace_export_directory(staged_candidate_export_root, target_export_root)
        except OSError as publish_error:
            _restore_backup_or_raise(
                target_export_root=target_export_root,
                backup_export_root=backup_export_root,
                publish_error=publish_error,
                replace_export_directory=context.replace_export_directory,
            )
            _delete_verified_staged_candidate_if_present(staged_candidate_export_root)
            _delete_journal(journal_path)
            raise RegistryValidationError(
                f"generated export publication failed; the previous target was restored: {publish_error}",
            ) from publish_error
        fsync_parent_dir(target_export_root)
        journal = journal.model_copy(update={"state": "candidate_live"})
        write_generated_export_publication_journal(journal_path, journal)

        _verify_post_cutover_target(
            target_export_root,
            expected_manifest_sha256=candidate_manifest_sha256,
            expected_manifest=candidate_manifest,
        )
        journal = journal.model_copy(update={"state": "committed"})
        write_generated_export_publication_journal(journal_path, journal)
        if had_target:
            _delete_opaque_rollback_tree(backup_export_root)
        _delete_journal(journal_path)
        reset_conformance_cache()

    return PublishedGeneratedExportTree(
        validated=validated,
        export_root=target_export_root,
        provenance_manifest_path=target_export_root / EXPORT_FRAGMENT_PROVENANCE_FILENAME,
    )


def _prepare_candidate_publication_path(context: GeneratedExportTreePublicationContext) -> Path:
    """Admit only caller-owned candidate state before destination lock acquisition."""
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
    return candidate_export_root


def _admit_target_publication_path(context: GeneratedExportTreePublicationContext) -> Path:
    """Admit destination-owned state while holding its publication lock."""
    target_root = _require_narrow_root(context.target_root, subject="generated publication target root")
    modelo_id = str(context.validation.target.modelo)
    revision_id = str(context.validation.target.revision_id)
    target_export_root = _require_target_export_root(
        context.target_export_root,
        target_root=target_root,
        modelo_id=modelo_id,
        revision_id=revision_id,
    )
    _require_no_stale_sibling_manifest(target_export_root.parent, subject="generated target revision")
    if target_export_root.exists():
        _require_complete_regular_tree(target_export_root, subject="generated target export root")
    return target_export_root


def require_expected_target_state(context: GeneratedExportTreePublicationContext, target_export_root: Path) -> None:
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
        or export_provenance_file_sha256(target_export_root / EXPORT_FRAGMENT_PROVENANCE_FILENAME)
        != expected.manifest_sha256
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
    stale = revision_root / LEGACY_EXPORT_FRAGMENT_PROVENANCE_FILENAME
    if stale.exists() or is_link_like(stale):
        raise RegistryValidationError(f"{subject} refuses stale sibling provenance manifest: {stale}")


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


def recover_interrupted_publication(
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
    """Complete, roll back, or retire an interrupted transaction; report whether a candidate went live."""
    if not journal_path.exists():
        return False
    journal = load_generated_export_publication_journal(journal_path)
    if journal.modelo != str(context.validation.target.modelo) or journal.revision_id != str(
        context.validation.target.revision_id
    ):
        raise RegistryValidationError(f"generated publication journal does not belong to this target: {journal_path}")
    publication_target_root = context.target_root.resolve()
    backup_export_root = _journal_backup_path(journal, target_export_root, publication_target_root)
    if _retire_completed_legacy_orphan_journal(
        context=context,
        journal=journal,
        journal_path=journal_path,
        target_export_root=target_export_root,
        backup_export_root=backup_export_root,
    ):
        return False
    staged_candidate_export_root = _journal_staged_candidate_path(journal, publication_target_root)
    candidate_is_verified = staged_candidate_export_root.exists() and _matches_journal_candidate(
        staged_candidate_export_root,
        journal,
    )
    target_is_verified = target_export_root.exists() and _matches_journal_candidate(target_export_root, journal)

    if target_is_verified:
        target_manifest = _verify_recovery_package_against_current_authorities(
            target_export_root,
            context=context,
            modelo_root=target_export_root.parent.parent.parent,
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
        _delete_opaque_rollback_if_present(backup_export_root)
        _delete_journal(journal_path)
        return True
    if backup_export_root.exists():
        if candidate_is_verified:
            if target_export_root.exists():
                _move_failed_candidate_aside(
                    target_export_root,
                    replace_export_directory=context.replace_export_directory,
                )
            context.replace_export_directory(staged_candidate_export_root, target_export_root)
            fsync_parent_dir(target_export_root)
            # The authority check reads `revision.export_layouts` off the disk
            # tree, which only exists once the candidate is at the canonical
            # `export/` location -- it cannot see content still sitting at the
            # staging path, so this runs after the swap, mirroring the primary
            # publish path's own swap-then-verify order.
            candidate_manifest = _verify_recovery_package_against_current_authorities(
                target_export_root,
                context=context,
                modelo_root=target_export_root.parent.parent.parent,
                joined=joined,
                semantic_map=semantic_map,
                rendered=rendered,
                render_profile=render_profile,
                render_profile_source_evidence=render_profile_source_evidence,
            )
            _verify_post_cutover_target(
                target_export_root,
                expected_manifest_sha256=journal.candidate_manifest_sha256,
                expected_manifest=candidate_manifest,
            )
            _delete_opaque_rollback_tree(backup_export_root)
            _delete_journal(journal_path)
            return True
        if target_export_root.exists():
            _move_failed_candidate_aside(
                target_export_root,
                replace_export_directory=context.replace_export_directory,
            )
        context.replace_export_directory(backup_export_root, target_export_root)
        fsync_parent_dir(target_export_root)
        _delete_journal(journal_path)
        return False
    if candidate_is_verified and not target_export_root.exists():
        context.replace_export_directory(staged_candidate_export_root, target_export_root)
        fsync_parent_dir(target_export_root)
        candidate_manifest = _verify_recovery_package_against_current_authorities(
            target_export_root,
            context=context,
            modelo_root=target_export_root.parent.parent.parent,
            joined=joined,
            semantic_map=semantic_map,
            rendered=rendered,
            render_profile=render_profile,
            render_profile_source_evidence=render_profile_source_evidence,
        )
        _verify_post_cutover_target(
            target_export_root,
            expected_manifest_sha256=journal.candidate_manifest_sha256,
            expected_manifest=candidate_manifest,
        )
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


def _matches_journal_candidate(export_root: Path, journal: GeneratedExportPublicationJournal) -> bool:
    try:
        verify_generated_export_package(export_root)
        return (
            export_provenance_file_sha256(export_root / EXPORT_FRAGMENT_PROVENANCE_FILENAME)
            == journal.candidate_manifest_sha256
        )
    except (OSError, RegistryValidationError):
        return False


def _journal_backup_path(
    journal: GeneratedExportPublicationJournal,
    target_export_root: Path,
    target_root: Path,
) -> Path:
    backup = Path(journal.backup_export)
    if backup.parent != target_root:
        raise RegistryValidationError("generated publication journal backup escapes the target registry root")
    backup_prefix = GeneratedExportTransactionPaths(
        target_root=target_root,
        modelo=journal.modelo,
        revision_id=journal.revision_id,
    ).backup_prefix
    if not backup.name.startswith(backup_prefix):
        raise RegistryValidationError("generated publication journal backup name is not transaction-scoped")
    return backup


def _retire_completed_legacy_orphan_journal(
    *,
    context: GeneratedExportTreePublicationContext,
    journal: GeneratedExportPublicationJournal,
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


def _journal_staged_candidate_path(journal: GeneratedExportPublicationJournal, target_root: Path) -> Path:
    candidate = Path(journal.candidate_export)
    prefix = GeneratedExportTransactionPaths(
        target_root=target_root,
        modelo=journal.modelo,
        revision_id=journal.revision_id,
    ).staging_prefix
    if candidate.parent != target_root or not candidate.name.startswith(prefix):
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


def _restore_backup_or_raise(
    *,
    target_export_root: Path,
    backup_export_root: Path,
    publish_error: OSError,
    replace_export_directory: Callable[[Path, Path], None],
) -> None:
    if not backup_export_root.exists():
        raise RegistryValidationError(f"generated export publication failed: {publish_error}") from publish_error
    try:
        replace_export_directory(backup_export_root, target_export_root)
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


def _move_failed_candidate_aside(
    target_export_root: Path,
    *,
    replace_export_directory: Callable[[Path, Path], None],
) -> None:
    failed = target_export_root.with_name(f".{target_export_root.name}.generator-invalid-{secrets.token_hex(16)}")
    replace_export_directory(target_export_root, failed)
    try:
        _delete_opaque_rollback_tree(failed)
    except BaseException:
        if not target_export_root.exists() and failed.exists():
            replace_export_directory(failed, target_export_root)
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


def write_generated_export_publication_journal(path: Path, journal: GeneratedExportPublicationJournal) -> None:
    """Durably replace the journal at ``path`` with the canonical JSON of ``journal``."""
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


def load_generated_export_publication_journal(path: Path) -> GeneratedExportPublicationJournal:
    """Load a journal, refusing a linked, invalid, or non-canonical file."""
    if is_link_like(path) or not path.is_file():
        raise RegistryValidationError(f"generated publication journal must be a regular file: {path}")
    raw = path.read_bytes()
    try:
        journal = GeneratedExportPublicationJournal.model_validate_json(raw)
    except ValidationError as exc:
        raise RegistryValidationError(f"generated publication journal is invalid: {path}") from exc
    if raw != canonical_json_bytes(journal.model_dump(mode="json")):
        raise RegistryValidationError(f"generated publication journal is not canonical JSON: {path}")
    return journal


def _delete_journal(path: Path) -> None:
    if path.exists():
        path.unlink()
        fsync_parent_dir(path)


def export_provenance_file_sha256(path: Path) -> str:
    """Return the SHA-256 of one regular, non-linked export provenance file."""
    if is_link_like(path) or not path.is_file():
        raise RegistryValidationError(f"generated export provenance path must be a regular file: {path}")
    digest, _byte_count = hash_file(path)
    return digest

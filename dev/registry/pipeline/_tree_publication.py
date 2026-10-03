"""Orchestrate validated generated export tree publication."""

from __future__ import annotations

from pathlib import Path

from cadrumo.core.fsync import fsync_parent_dir
from cadrumo.core.locks import exclusive_file_lock
from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ..compiler.export_fragment_grammar import EXPORT_FRAGMENT_PROVENANCE_FILENAME
from ..conformance.manager import reset_conformance_cache
from ._export_tree import RenderedExportTree
from ._tree_validation import (
    ValidatedGeneratedExportTree,
    validate_generated_export_tree,
)
from .export_fragment_provenance import ExportFragmentProvenanceManifest
from .joined_record_design import JoinedRecordDesign
from .render_profile_evidence import RenderProfileSourceEvidence
from .render_profile_model import RenderProfile
from .semantic_map import SemanticMap
from .tree_publication_artifacts import (
    _delete_verified_staged_candidate_if_present,
    _verify_post_cutover_target,
    stage_verified_candidate_package,
    verify_generated_export_package,
)
from .tree_publication_contracts import (
    _JOURNAL_SCHEMA_VERSION,
    GeneratedExportPublicationJournal,
    GeneratedExportTransactionPaths,
    GeneratedExportTreePublicationContext,
    PublishedGeneratedExportTree,
    _require_no_legacy_transaction,
    export_provenance_file_sha256,
)
from .tree_publication_journal import (
    _delete_journal,
    load_generated_export_publication_journal,
    write_generated_export_publication_journal,
)
from .tree_publication_paths import (
    _admit_target_publication_path,
    _prepare_candidate_publication_path,
    _require_no_stale_sibling_manifest,
    require_expected_target_state,
)
from .tree_publication_recovery import (
    _delete_opaque_rollback_tree,
    _restore_backup_or_raise,
    _restore_failed_export_cutover,
    recover_interrupted_publication,
)
from .tree_publication_supersession import _publish_superseding_revision_bundle
from .tree_publication_supersession_recovery import _recover_interrupted_supersession_bundle_locked

__all__ = ["publish_validated_generated_export_tree"]


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
    exposed as a fallback. An existing tree is an opaque rollback directory
    while the transaction is live, and is deleted after the candidate passes its
    post-cutover manifest, digest, and production-loader checks.
    """
    candidate_export_root = _prepare_candidate_publication_path(context)
    transaction_paths = GeneratedExportTransactionPaths.for_context(context)
    journal_path = transaction_paths.journal
    with exclusive_file_lock(transaction_paths.lock_identity):
        target_export_root, recovered = _recover_or_admit_publication_target(
            context=context,
            transaction_paths=transaction_paths,
            journal_path=journal_path,
            joined=joined,
            semantic_map=semantic_map,
            rendered=rendered,
            render_profile=render_profile,
            render_profile_source_evidence=render_profile_source_evidence,
        )
        if recovered:
            return _already_published(target_export_root)
        validated, candidate_manifest, candidate_manifest_sha256, staged_candidate_export_root = (
            _validate_and_stage_candidate(
                context=context,
                candidate_export_root=candidate_export_root,
                joined=joined,
                semantic_map=semantic_map,
                rendered=rendered,
                render_profile=render_profile,
                render_profile_source_evidence=render_profile_source_evidence,
            )
        )
        if context.supersession is not None:
            return _publish_superseding_revision_bundle(
                context=context,
                target_export_root=target_export_root,
                candidate_export_root=candidate_export_root,
                staged_candidate_export_root=staged_candidate_export_root,
                validated=validated,
                candidate_manifest=candidate_manifest,
                candidate_manifest_sha256=candidate_manifest_sha256,
                joined=joined,
                semantic_map=semantic_map,
                rendered=rendered,
                render_profile=render_profile,
                render_profile_source_evidence=render_profile_source_evidence,
                transaction_paths=transaction_paths,
                journal_path=journal_path,
            )
        published = _publish_ordinary_candidate(
            context=context,
            target_export_root=target_export_root,
            transaction_paths=transaction_paths,
            journal_path=journal_path,
            validated=validated,
            candidate_manifest=candidate_manifest,
            candidate_manifest_sha256=candidate_manifest_sha256,
            staged_candidate_export_root=staged_candidate_export_root,
        )
    reset_conformance_cache()
    return published


def _recover_or_admit_publication_target(
    *,
    context: GeneratedExportTreePublicationContext,
    transaction_paths: GeneratedExportTransactionPaths,
    journal_path: Path,
    joined: JoinedRecordDesign,
    semantic_map: SemanticMap,
    rendered: RenderedExportTree,
    render_profile: RenderProfile,
    render_profile_source_evidence: RenderProfileSourceEvidence,
) -> tuple[Path, bool]:
    _require_no_legacy_transaction(transaction_paths)
    if journal_path.exists():
        interrupted_journal = load_generated_export_publication_journal(journal_path)
        if interrupted_journal.is_supersession and _recover_interrupted_supersession_bundle_locked(
            journal=interrupted_journal,
            journal_path=journal_path,
            transaction_paths=transaction_paths,
        ):
            target_export_root = _admit_target_publication_path(context)
            reset_conformance_cache()
            return target_export_root, True
    target_export_root = _admit_target_publication_path(context)
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
        # Recovery finalized a candidate as live, outside the conformance cache key.
        reset_conformance_cache()
        return target_export_root, True
    _require_no_stale_sibling_manifest(target_export_root.parent, subject="generated target revision")
    return target_export_root, False


def _already_published(target_export_root: Path) -> PublishedGeneratedExportTree:
    return PublishedGeneratedExportTree(
        validated=None,
        export_root=target_export_root,
        provenance_manifest_path=target_export_root / EXPORT_FRAGMENT_PROVENANCE_FILENAME,
    )


def _validate_and_stage_candidate(
    *,
    context: GeneratedExportTreePublicationContext,
    candidate_export_root: Path,
    joined: JoinedRecordDesign,
    semantic_map: SemanticMap,
    rendered: RenderedExportTree,
    render_profile: RenderProfile,
    render_profile_source_evidence: RenderProfileSourceEvidence,
) -> tuple[ValidatedGeneratedExportTree, ExportFragmentProvenanceManifest, str, Path]:
    # This is the immediate pre-cutover proof, before any journal or export tree changes.
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
    staged_candidate_export_root = stage_verified_candidate_package(
        candidate_export_root=candidate_export_root,
        target_root=context.target_root.resolve(),
        modelo=str(context.validation.target.modelo),
        revision_id=str(context.validation.target.revision_id),
        expected_manifest_sha256=candidate_manifest_sha256,
        expected_manifest=candidate_manifest,
    )
    return validated, candidate_manifest, candidate_manifest_sha256, staged_candidate_export_root


def _publish_ordinary_candidate(
    *,
    context: GeneratedExportTreePublicationContext,
    target_export_root: Path,
    transaction_paths: GeneratedExportTransactionPaths,
    journal_path: Path,
    validated: ValidatedGeneratedExportTree,
    candidate_manifest: ExportFragmentProvenanceManifest,
    candidate_manifest_sha256: str,
    staged_candidate_export_root: Path,
) -> PublishedGeneratedExportTree:
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
    _install_ordinary_candidate(
        context=context,
        target_export_root=target_export_root,
        backup_export_root=backup_export_root,
        staged_candidate_export_root=staged_candidate_export_root,
        journal_path=journal_path,
    )
    fsync_parent_dir(target_export_root)
    journal = journal.model_copy(update={"state": "candidate_live"})
    write_generated_export_publication_journal(journal_path, journal)
    _verify_live_ordinary_candidate(
        context=context,
        target_export_root=target_export_root,
        backup_export_root=backup_export_root,
        had_target=had_target,
        transaction_paths=transaction_paths,
        journal_path=journal_path,
        candidate_manifest=candidate_manifest,
        candidate_manifest_sha256=candidate_manifest_sha256,
    )
    journal = journal.model_copy(update={"state": "committed"})
    write_generated_export_publication_journal(journal_path, journal)
    if had_target:
        _delete_opaque_rollback_tree(backup_export_root)
    _delete_journal(journal_path)
    return PublishedGeneratedExportTree(
        validated=validated,
        export_root=target_export_root,
        provenance_manifest_path=target_export_root / EXPORT_FRAGMENT_PROVENANCE_FILENAME,
    )


def _install_ordinary_candidate(
    *,
    context: GeneratedExportTreePublicationContext,
    target_export_root: Path,
    backup_export_root: Path,
    staged_candidate_export_root: Path,
    journal_path: Path,
) -> None:
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


def _verify_live_ordinary_candidate(
    *,
    context: GeneratedExportTreePublicationContext,
    target_export_root: Path,
    backup_export_root: Path,
    had_target: bool,
    transaction_paths: GeneratedExportTransactionPaths,
    journal_path: Path,
    candidate_manifest: ExportFragmentProvenanceManifest,
    candidate_manifest_sha256: str,
) -> None:
    try:
        _verify_post_cutover_target(
            target_export_root,
            expected_manifest_sha256=candidate_manifest_sha256,
            expected_manifest=candidate_manifest,
        )
        if context.final_live_validator is not None:
            context.final_live_validator()
    except BaseException as error:
        try:
            _restore_failed_export_cutover(
                context=context,
                target_export_root=target_export_root,
                backup_export_root=backup_export_root,
                had_target=had_target,
                transaction_paths=transaction_paths,
            )
            _delete_journal(journal_path)
        except BaseException as restore_error:
            raise RegistryValidationError(
                "generated export publication failed and the previous target could not be restored; "
                f"publication_error={error}; restoration_error={restore_error}",
            ) from restore_error
        raise RegistryValidationError(
            f"generated export publication failed; the previous target was restored: {error}",
        ) from error

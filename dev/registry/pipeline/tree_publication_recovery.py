"""Recover interrupted generated export directory transactions."""

from __future__ import annotations

import secrets
import shutil
from collections.abc import Callable
from pathlib import Path

from cadrumo.core.fsync import fsync_parent_dir
from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from .export_fragment_provenance import ExportFragmentProvenanceManifest
from .export_tree_models import RenderedExportTree
from .joined_record_design import JoinedRecordDesign
from .render_profile_evidence import RenderProfileSourceEvidence
from .render_profile_model import RenderProfile
from .semantic_map import SemanticMap
from .tree_publication_artifacts import (
    _require_complete_regular_tree,
    _verify_post_cutover_target,
    _verify_recovery_package_against_current_authorities,
)
from .tree_publication_contracts import (
    GeneratedExportPublicationJournal,
    GeneratedExportTransactionPaths,
    GeneratedExportTreePublicationContext,
)
from .tree_publication_journal import (
    _delete_journal,
    _journal_backup_path,
    _journal_staged_candidate_path,
    _matches_journal_candidate,
    _retire_completed_legacy_orphan_journal,
    load_generated_export_publication_journal,
)
from .tree_publication_supersession import _delete_opaque_transaction_tree
from .tree_publication_supersession_recovery import _recover_interrupted_supersession_bundle_locked


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
    _require_recovery_journal_target(journal, context, journal_path)
    publication_target_root = context.target_root.resolve()
    if journal.is_supersession:
        return _recover_interrupted_supersession_bundle_locked(
            journal=journal,
            journal_path=journal_path,
            transaction_paths=GeneratedExportTransactionPaths(
                target_root=publication_target_root,
                modelo=journal.modelo,
                revision_id=journal.revision_id,
            ),
        )

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
        _finalize_verified_live_candidate(
            context=context,
            journal=journal,
            journal_path=journal_path,
            target_export_root=target_export_root,
            backup_export_root=backup_export_root,
            joined=joined,
            semantic_map=semantic_map,
            rendered=rendered,
            render_profile=render_profile,
            render_profile_source_evidence=render_profile_source_evidence,
        )
        return True
    if backup_export_root.exists():
        return _recover_with_existing_backup(
            context=context,
            journal=journal,
            journal_path=journal_path,
            target_export_root=target_export_root,
            backup_export_root=backup_export_root,
            staged_candidate_export_root=staged_candidate_export_root,
            candidate_is_verified=candidate_is_verified,
            joined=joined,
            semantic_map=semantic_map,
            rendered=rendered,
            render_profile=render_profile,
            render_profile_source_evidence=render_profile_source_evidence,
        )
    return _recover_without_backup(
        context=context,
        journal=journal,
        journal_path=journal_path,
        target_export_root=target_export_root,
        staged_candidate_export_root=staged_candidate_export_root,
        candidate_is_verified=candidate_is_verified,
        joined=joined,
        semantic_map=semantic_map,
        rendered=rendered,
        render_profile=render_profile,
        render_profile_source_evidence=render_profile_source_evidence,
    )


def _require_recovery_journal_target(
    journal: GeneratedExportPublicationJournal,
    context: GeneratedExportTreePublicationContext,
    journal_path: Path,
) -> None:
    if journal.modelo != str(context.validation.target.modelo) or journal.revision_id != str(
        context.validation.target.revision_id
    ):
        raise RegistryValidationError(f"generated publication journal does not belong to this target: {journal_path}")


def _finalize_verified_live_candidate(
    *,
    context: GeneratedExportTreePublicationContext,
    journal: GeneratedExportPublicationJournal,
    journal_path: Path,
    target_export_root: Path,
    backup_export_root: Path,
    joined: JoinedRecordDesign,
    semantic_map: SemanticMap,
    rendered: RenderedExportTree,
    render_profile: RenderProfile,
    render_profile_source_evidence: RenderProfileSourceEvidence,
) -> None:
    target_manifest = _verify_recovered_candidate(
        context=context,
        target_export_root=target_export_root,
        journal=journal,
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


def _recover_with_existing_backup(
    *,
    context: GeneratedExportTreePublicationContext,
    journal: GeneratedExportPublicationJournal,
    journal_path: Path,
    target_export_root: Path,
    backup_export_root: Path,
    staged_candidate_export_root: Path,
    candidate_is_verified: bool,
    joined: JoinedRecordDesign,
    semantic_map: SemanticMap,
    rendered: RenderedExportTree,
    render_profile: RenderProfile,
    render_profile_source_evidence: RenderProfileSourceEvidence,
) -> bool:
    if candidate_is_verified:
        _install_recovered_candidate(
            context=context,
            journal=journal,
            journal_path=journal_path,
            target_export_root=target_export_root,
            backup_export_root=backup_export_root,
            staged_candidate_export_root=staged_candidate_export_root,
            joined=joined,
            semantic_map=semantic_map,
            rendered=rendered,
            render_profile=render_profile,
            render_profile_source_evidence=render_profile_source_evidence,
        )
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


def _install_recovered_candidate(
    *,
    context: GeneratedExportTreePublicationContext,
    journal: GeneratedExportPublicationJournal,
    journal_path: Path,
    target_export_root: Path,
    backup_export_root: Path,
    staged_candidate_export_root: Path,
    joined: JoinedRecordDesign,
    semantic_map: SemanticMap,
    rendered: RenderedExportTree,
    render_profile: RenderProfile,
    render_profile_source_evidence: RenderProfileSourceEvidence,
) -> None:
    if target_export_root.exists():
        _move_failed_candidate_aside(
            target_export_root,
            replace_export_directory=context.replace_export_directory,
        )
    context.replace_export_directory(staged_candidate_export_root, target_export_root)
    fsync_parent_dir(target_export_root)
    candidate_manifest = _verify_recovered_candidate(
        context=context,
        target_export_root=target_export_root,
        journal=journal,
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


def _recover_without_backup(
    *,
    context: GeneratedExportTreePublicationContext,
    journal: GeneratedExportPublicationJournal,
    journal_path: Path,
    target_export_root: Path,
    staged_candidate_export_root: Path,
    candidate_is_verified: bool,
    joined: JoinedRecordDesign,
    semantic_map: SemanticMap,
    rendered: RenderedExportTree,
    render_profile: RenderProfile,
    render_profile_source_evidence: RenderProfileSourceEvidence,
) -> bool:
    if candidate_is_verified and not target_export_root.exists():
        context.replace_export_directory(staged_candidate_export_root, target_export_root)
        fsync_parent_dir(target_export_root)
        candidate_manifest = _verify_recovered_candidate(
            context=context,
            target_export_root=target_export_root,
            journal=journal,
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


def _verify_recovered_candidate(
    *,
    context: GeneratedExportTreePublicationContext,
    target_export_root: Path,
    journal: GeneratedExportPublicationJournal,
    joined: JoinedRecordDesign,
    semantic_map: SemanticMap,
    rendered: RenderedExportTree,
    render_profile: RenderProfile,
    render_profile_source_evidence: RenderProfileSourceEvidence,
) -> ExportFragmentProvenanceManifest:
    # The authority check needs `revision.export_layouts` from the canonical
    # `export/` path, so staged content is admitted only after its cutover.
    return _verify_recovery_package_against_current_authorities(
        target_export_root,
        context=context,
        modelo_root=target_export_root.parent.parent.parent,
        joined=joined,
        semantic_map=semantic_map,
        rendered=rendered,
        render_profile=render_profile,
        render_profile_source_evidence=render_profile_source_evidence,
    )


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


def _restore_failed_export_cutover(
    *,
    context: GeneratedExportTreePublicationContext,
    target_export_root: Path,
    backup_export_root: Path,
    had_target: bool,
    transaction_paths: GeneratedExportTransactionPaths,
) -> None:
    """Undo a candidate that failed post-cutover checks while its journal is live."""
    failed_candidate: Path | None = None
    if target_export_root.exists():
        failed_candidate = transaction_paths.new_staging_sibling()
        context.replace_export_directory(target_export_root, failed_candidate)
        fsync_parent_dir(target_export_root)
    if had_target:
        if not backup_export_root.exists():
            raise RegistryValidationError("generated export rollback backup disappeared before restoration")
        context.replace_export_directory(backup_export_root, target_export_root)
        fsync_parent_dir(target_export_root)
    if failed_candidate is not None:
        _delete_opaque_transaction_tree(
            failed_candidate,
            target_root=transaction_paths.target_root,
            prefix=transaction_paths.staging_prefix,
            subject="failed generated export candidate",
        )


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

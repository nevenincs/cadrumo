"""Recover interrupted reviewed whole-revision export supersessions."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import ValidationError

from cadrumo.core.fsync import fsync_parent_dir
from cadrumo.core.locks import exclusive_file_lock
from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ..compiler.export_fragment_grammar import EXPORT_FRAGMENT_PROVENANCE_FILENAME
from .candidate_staging import (
    bootstrap_layout_supersession_fingerprint,
)
from .tree_publication_artifacts import (
    _require_complete_regular_tree,
    verify_generated_export_package,
)
from .tree_publication_contracts import (
    _MODELO_ID_ADAPTER,
    _REVISION_ID_ADAPTER,
    GeneratedExportPublicationJournal,
    GeneratedExportTransactionPaths,
    _require_no_legacy_transaction,
    _require_single_path_component,
    export_provenance_file_sha256,
)
from .tree_publication_journal import (
    _delete_journal,
    _journal_supersession_backup_revision_path,
    _journal_supersession_candidate_revision_path,
    load_generated_export_publication_journal,
)
from .tree_publication_paths import _require_narrow_root
from .tree_publication_supersession import (
    _delete_opaque_transaction_tree,
    _delete_opaque_transaction_tree_allow_partial,
)


def recover_interrupted_supersession_bundle(*, target_root: Path, modelo: str, revision: str) -> bool:
    """Recover a journaled whole-revision bootstrap supersession before registry compilation.

    A bundle cutover briefly removes the revision directory while its old version
    sits in a transaction-owned sibling. This entry point runs before the normal
    registry compiler so it can restore or finalize that exact transaction even
    when the canonical revision path is temporarily absent.
    """
    try:
        validated_modelo = _MODELO_ID_ADAPTER.validate_python(modelo, strict=True)
        validated_revision = _REVISION_ID_ADAPTER.validate_python(revision, strict=True)
        _require_single_path_component(validated_modelo, subject="modelo")
        _require_single_path_component(validated_revision, subject="revision")
    except (ValidationError, ValueError) as exc:
        raise RegistryValidationError(
            "generated supersession recovery requires valid ModeloId and path-safe RevisionId values",
        ) from exc
    resolved_target_root = _require_narrow_root(target_root, subject="generated publication target root")
    paths = GeneratedExportTransactionPaths(
        target_root=resolved_target_root,
        modelo=validated_modelo,
        revision_id=validated_revision,
    )
    _require_no_legacy_transaction(paths)
    with exclusive_file_lock(paths.lock_identity):
        _require_no_legacy_transaction(paths)
        if not paths.journal.exists():
            return False
        journal = load_generated_export_publication_journal(paths.journal)
        if journal.modelo != validated_modelo or journal.revision_id != validated_revision:
            raise RegistryValidationError(
                f"generated publication journal does not belong to this target: {paths.journal}",
            )
        if not journal.is_supersession:
            return False
        return _recover_interrupted_supersession_bundle_locked(
            journal=journal,
            journal_path=paths.journal,
            transaction_paths=paths,
        )


def _recover_interrupted_supersession_bundle_locked(
    *,
    journal: GeneratedExportPublicationJournal,
    journal_path: Path,
    transaction_paths: GeneratedExportTransactionPaths,
) -> bool:
    """Finalize committed cleanup or safely restore the pinned pre-cutover revision."""
    if not journal.is_supersession:
        raise RegistryValidationError("supersession recovery requires a supersession journal")
    source_sha256 = journal.supersession_source_sha256
    candidate_sha256 = journal.candidate_revision_sha256
    if source_sha256 is None or candidate_sha256 is None:
        raise RegistryValidationError("generated supersession journal lacks a complete revision pin")

    target_revision_root = (
        transaction_paths.target_root / "modelos" / journal.modelo / "revisions" / journal.revision_id
    )
    target_export_root = target_revision_root / "export"
    candidate_revision_root = _journal_supersession_candidate_revision_path(journal, transaction_paths)
    backup_revision_root = _journal_supersession_backup_revision_path(journal, transaction_paths)
    if journal.state == "committed":
        return _recover_committed_supersession_bundle(
            journal=journal,
            journal_path=journal_path,
            transaction_paths=transaction_paths,
            target_revision_root=target_revision_root,
            target_export_root=target_export_root,
            candidate_revision_root=candidate_revision_root,
            backup_revision_root=backup_revision_root,
            source_sha256=source_sha256,
            candidate_sha256=candidate_sha256,
        )
    return _recover_uncommitted_supersession_bundle(
        journal_path=journal_path,
        transaction_paths=transaction_paths,
        target_revision_root=target_revision_root,
        candidate_revision_root=candidate_revision_root,
        backup_revision_root=backup_revision_root,
        source_sha256=source_sha256,
        candidate_sha256=candidate_sha256,
    )


def _recover_committed_supersession_bundle(
    *,
    journal: GeneratedExportPublicationJournal,
    journal_path: Path,
    transaction_paths: GeneratedExportTransactionPaths,
    target_revision_root: Path,
    target_export_root: Path,
    candidate_revision_root: Path,
    backup_revision_root: Path,
    source_sha256: str,
    candidate_sha256: str,
) -> bool:
    if not target_revision_root.exists():
        raise RegistryValidationError("committed supersession revision is missing; preserving its journal and backup")
    if bootstrap_layout_supersession_fingerprint(target_revision_root) != candidate_sha256:
        raise RegistryValidationError("committed supersession live revision changed; preserving it, backup and journal")
    verify_generated_export_package(target_export_root)
    if export_provenance_file_sha256(target_export_root / EXPORT_FRAGMENT_PROVENANCE_FILENAME) != (
        journal.candidate_manifest_sha256
    ):
        raise RegistryValidationError("committed supersession export changed; preserving backup and journal")
    _remove_candidate_revision(
        candidate_revision_root,
        transaction_paths=transaction_paths,
        expected_sha256=candidate_sha256,
        changed_error="committed supersession staging revision changed; preserving it and the journal",
        subject="committed generated supersession staging revision",
    )
    _remove_committed_supersession_backup(
        backup_revision_root,
        transaction_paths=transaction_paths,
        journal=journal,
        source_sha256=source_sha256,
    )
    _delete_journal(journal_path)
    return True


def _remove_committed_supersession_backup(
    backup_revision_root: Path,
    *,
    transaction_paths: GeneratedExportTransactionPaths,
    journal: GeneratedExportPublicationJournal,
    source_sha256: str,
) -> None:
    if not backup_revision_root.exists():
        return
    if journal.cleanup_started is not True:
        _require_complete_regular_tree(
            backup_revision_root,
            subject="committed generated supersession rollback revision",
        )
        if bootstrap_layout_supersession_fingerprint(backup_revision_root) != source_sha256:
            raise RegistryValidationError(
                "committed supersession rollback revision changed before cleanup; preserving it and the journal",
            )
    _delete_opaque_transaction_tree_allow_partial(
        backup_revision_root,
        target_root=transaction_paths.transaction_root,
        prefix=transaction_paths.bundle_backup_prefix,
        subject="committed generated supersession rollback revision",
    )


def _recover_uncommitted_supersession_bundle(
    *,
    journal_path: Path,
    transaction_paths: GeneratedExportTransactionPaths,
    target_revision_root: Path,
    candidate_revision_root: Path,
    backup_revision_root: Path,
    source_sha256: str,
    candidate_sha256: str,
) -> bool:
    if target_revision_root.exists():
        return _recover_uncommitted_supersession_with_live_target(
            journal_path=journal_path,
            transaction_paths=transaction_paths,
            target_revision_root=target_revision_root,
            candidate_revision_root=candidate_revision_root,
            backup_revision_root=backup_revision_root,
            source_sha256=source_sha256,
            candidate_sha256=candidate_sha256,
        )
    return _restore_uncommitted_supersession_without_live_target(
        journal_path=journal_path,
        transaction_paths=transaction_paths,
        target_revision_root=target_revision_root,
        candidate_revision_root=candidate_revision_root,
        backup_revision_root=backup_revision_root,
        candidate_sha256=candidate_sha256,
    )


def _recover_uncommitted_supersession_with_live_target(
    *,
    journal_path: Path,
    transaction_paths: GeneratedExportTransactionPaths,
    target_revision_root: Path,
    candidate_revision_root: Path,
    backup_revision_root: Path,
    source_sha256: str,
    candidate_sha256: str,
) -> bool:
    live_sha256 = bootstrap_layout_supersession_fingerprint(target_revision_root)
    if live_sha256 == candidate_sha256:
        return _restore_supersession_source_after_candidate_cutover(
            journal_path=journal_path,
            transaction_paths=transaction_paths,
            target_revision_root=target_revision_root,
            candidate_revision_root=candidate_revision_root,
            backup_revision_root=backup_revision_root,
            source_sha256=source_sha256,
        )
    if backup_revision_root.exists():
        raise RegistryValidationError(
            "uncommitted supersession live revision changed; preserving it, backup and journal"
        )
    if live_sha256 != source_sha256:
        raise RegistryValidationError("uncommitted supersession source revision changed; preserving it and the journal")
    _remove_candidate_revision(
        candidate_revision_root,
        transaction_paths=transaction_paths,
        expected_sha256=candidate_sha256,
        changed_error="uncommitted supersession staging revision changed; preserving it and the journal",
        subject="abandoned generated supersession candidate revision",
    )
    _delete_journal(journal_path)
    return False


def _restore_supersession_source_after_candidate_cutover(
    *,
    journal_path: Path,
    transaction_paths: GeneratedExportTransactionPaths,
    target_revision_root: Path,
    candidate_revision_root: Path,
    backup_revision_root: Path,
    source_sha256: str,
) -> bool:
    if not backup_revision_root.exists():
        raise RegistryValidationError(
            "uncommitted supersession candidate is live without its rollback revision; preserving it and journal",
        )
    _require_complete_regular_tree(backup_revision_root, subject="generated supersession rollback revision")
    if bootstrap_layout_supersession_fingerprint(backup_revision_root) != source_sha256:
        raise RegistryValidationError(
            "uncommitted supersession rollback revision changed; preserving candidate, backup and journal",
        )
    if candidate_revision_root.exists():
        raise RegistryValidationError("uncommitted supersession staging path is occupied; preserving all state")
    os.replace(target_revision_root, candidate_revision_root)
    fsync_parent_dir(target_revision_root)
    os.replace(backup_revision_root, target_revision_root)
    fsync_parent_dir(target_revision_root)
    if bootstrap_layout_supersession_fingerprint(target_revision_root) != source_sha256:
        raise RegistryValidationError("supersession rollback did not restore the pinned source revision")
    _delete_opaque_transaction_tree(
        candidate_revision_root,
        target_root=transaction_paths.transaction_root,
        prefix=transaction_paths.bundle_staging_prefix,
        subject="failed generated supersession candidate revision",
    )
    _delete_journal(journal_path)
    return False


def _restore_uncommitted_supersession_without_live_target(
    *,
    journal_path: Path,
    transaction_paths: GeneratedExportTransactionPaths,
    target_revision_root: Path,
    candidate_revision_root: Path,
    backup_revision_root: Path,
    candidate_sha256: str,
) -> bool:
    if not backup_revision_root.exists():
        raise RegistryValidationError(
            "uncommitted supersession lost both the live and rollback revision; preserving journal"
        )
    _require_complete_regular_tree(backup_revision_root, subject="generated supersession rollback revision")
    # A vacant canonical path permits restoration without overwriting a writer's
    # tree. Preserve the captured bytes even if a race changed them after pinning.
    os.replace(backup_revision_root, target_revision_root)
    fsync_parent_dir(target_revision_root)
    _remove_candidate_revision(
        candidate_revision_root,
        transaction_paths=transaction_paths,
        expected_sha256=candidate_sha256,
        changed_error="restored supersession source, but staging candidate changed; preserving candidate and journal",
        subject="failed generated supersession candidate revision",
    )
    _delete_journal(journal_path)
    return False


def _remove_candidate_revision(
    candidate_revision_root: Path,
    *,
    transaction_paths: GeneratedExportTransactionPaths,
    expected_sha256: str,
    changed_error: str,
    subject: str,
) -> None:
    if not candidate_revision_root.exists():
        return
    if bootstrap_layout_supersession_fingerprint(candidate_revision_root) != expected_sha256:
        raise RegistryValidationError(changed_error)
    _delete_opaque_transaction_tree(
        candidate_revision_root,
        target_root=transaction_paths.transaction_root,
        prefix=transaction_paths.bundle_staging_prefix,
        subject=subject,
    )

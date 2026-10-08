"""Publish reviewed whole-revision generated export supersessions."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.fsync import fsync_parent_dir
from cadrumo.core.link_safety import is_link_like
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema_form_layouts import FormLayoutReviewState

from ..compiler.export_fragment_grammar import EXPORT_FRAGMENT_PROVENANCE_FILENAME
from ..compiler.loader import load_modelo_directory
from ..conformance.manager import reset_conformance_cache
from ..form_layout.serialization import FORM_LAYOUT_DIRECTORY, FORM_LAYOUT_FRAGMENT
from ._tree_validation import (
    ValidatedGeneratedExportTree,
    ValidatedHistoricalStaticGeneratedExportTree,
)
from .bootstrap_construct_retarget import retarget_bootstrap_constructs_in_revision
from .bootstrap_supersession import (
    bootstrap_layout_supersession_fingerprint,
    retire_bootstrap_manual_export_layout,
    validate_bootstrap_manual_export_layout_supersession,
)
from .export_fragment_provenance import (
    ExportFragmentProvenanceManifest,
)
from .export_tree_models import RenderedExportTree
from .joined_record_design import JoinedRecordDesign
from .render_profile_evidence import RenderProfileSourceEvidence
from .render_profile_model import RenderProfile
from .semantic_map import SemanticMap
from .tree_publication_artifacts import (
    _delete_verified_staged_candidate_if_present,
    _require_complete_regular_tree,
    _require_link_free_regular_members_allow_empty,
    _verify_generated_export_companion,
    _verify_post_cutover_target,
    _verify_recovery_package_against_current_authorities,
)
from .tree_publication_contracts import (
    _JOURNAL_SCHEMA_VERSION,
    GeneratedExportPublicationJournal,
    GeneratedExportSupersession,
    GeneratedExportTransactionPaths,
    GeneratedExportTreePublicationContext,
    PublishedGeneratedExportTree,
)
from .tree_publication_journal import (
    _delete_journal,
    write_generated_export_publication_journal,
)


def _publish_superseding_revision_bundle(
    *,
    context: GeneratedExportTreePublicationContext,
    target_export_root: Path,
    candidate_export_root: Path,
    staged_candidate_export_root: Path,
    validated: ValidatedGeneratedExportTree | ValidatedHistoricalStaticGeneratedExportTree,
    candidate_manifest: ExportFragmentProvenanceManifest,
    candidate_manifest_sha256: str,
    joined: JoinedRecordDesign,
    semantic_map: SemanticMap,
    rendered: RenderedExportTree,
    render_profile: RenderProfile,
    render_profile_source_evidence: RenderProfileSourceEvidence,
    transaction_paths: GeneratedExportTransactionPaths,
    journal_path: Path,
) -> PublishedGeneratedExportTree:
    """Cut over one generated tree and its pinned manual/form/construct companions together."""
    supersession, revision_id, modelo_id, target_revision_root, source_modelo_root = _require_reviewed_supersession(
        context=context,
        target_export_root=target_export_root,
        staged_candidate_export_root=staged_candidate_export_root,
        rendered=rendered,
    )
    staged_revision_root, backup_revision_root, candidate_revision_sha256 = _stage_supersession_revision(
        context=context,
        target_revision_root=target_revision_root,
        source_modelo_root=source_modelo_root,
        revision_id=revision_id,
        supersession=supersession,
        staged_candidate_export_root=staged_candidate_export_root,
        candidate_manifest=candidate_manifest,
        candidate_manifest_sha256=candidate_manifest_sha256,
        transaction_paths=transaction_paths,
    )
    journal = _write_supersession_intent_journal(
        modelo_id=modelo_id,
        revision_id=revision_id,
        supersession=supersession,
        staged_revision_root=staged_revision_root,
        backup_revision_root=backup_revision_root,
        candidate_manifest_sha256=candidate_manifest_sha256,
        candidate_revision_sha256=candidate_revision_sha256,
        journal_path=journal_path,
    )
    try:
        _require_supersession_source_at_cutover(
            source_modelo_root=source_modelo_root,
            target_revision_root=target_revision_root,
            staged_revision_root=staged_revision_root,
            revision_id=revision_id,
            supersession=supersession,
            candidate_revision_sha256=candidate_revision_sha256,
        )
        journal = _cut_over_supersession_revision(
            context=context,
            target_revision_root=target_revision_root,
            staged_revision_root=staged_revision_root,
            backup_revision_root=backup_revision_root,
            journal_path=journal_path,
            journal=journal,
            source_sha256=supersession.source_state_sha256,
            candidate_revision_sha256=candidate_revision_sha256,
        )
        _verify_supersession_cutover(
            context=context,
            target_export_root=target_export_root,
            candidate_manifest_sha256=candidate_manifest_sha256,
            candidate_manifest=candidate_manifest,
            joined=joined,
            semantic_map=semantic_map,
            rendered=rendered,
            render_profile=render_profile,
            render_profile_source_evidence=render_profile_source_evidence,
        )
        if context.final_live_validator is not None:
            context.final_live_validator()
    except BaseException as error:
        try:
            _rollback_supersession_bundle(
                context=context,
                target_revision_root=target_revision_root,
                backup_revision_root=backup_revision_root,
                staged_revision_root=staged_revision_root,
                journal=journal,
                journal_path=journal_path,
                transaction_paths=transaction_paths,
            )
        except BaseException as restore_error:
            raise RegistryValidationError(
                "generated export supersession failed and its transaction state was preserved for recovery; "
                f"publication_error={error}; restoration_error={restore_error}",
            ) from restore_error
        raise RegistryValidationError(
            f"generated export supersession failed; the previous revision was restored: {error}",
        ) from error

    journal = _commit_supersession_revision(
        journal=journal,
        journal_path=journal_path,
        backup_revision_root=backup_revision_root,
        transaction_paths=transaction_paths,
        source_sha256=supersession.source_state_sha256,
    )
    return PublishedGeneratedExportTree(
        validated=validated,
        export_root=target_export_root,
        provenance_manifest_path=target_export_root / EXPORT_FRAGMENT_PROVENANCE_FILENAME,
    )


def _require_reviewed_supersession(
    *,
    context: GeneratedExportTreePublicationContext,
    target_export_root: Path,
    staged_candidate_export_root: Path,
    rendered: RenderedExportTree,
) -> tuple[GeneratedExportSupersession, str, str, Path, Path]:
    supersession = context.supersession
    if supersession is None:
        raise AssertionError("supersession bundle requires its explicit source pin")
    revision_id = str(context.validation.target.revision_id)
    modelo_id = str(context.validation.target.modelo)
    if str(rendered.layout.id) != supersession.generated_layout_id:
        raise RegistryValidationError(
            "generated export layout does not equal the bootstrap target's reviewed replacement id",
        )
    target_revision_root = target_export_root.parent
    source_modelo_root = target_revision_root.parent.parent
    try:
        source_state_sha256 = validate_bootstrap_manual_export_layout_supersession(
            source_modelo_root,
            revision=revision_id,
            superseded_layout_id=supersession.superseded_layout_id,
            expected_references=supersession.expected_construct_references,
            source_ref=supersession.source_ref,
            source_sha256=supersession.source_sha256,
            manual_source_sha256=supersession.manual_source_sha256,
            manual_origin_revision=supersession.manual_origin_revision,
        )
    except (OSError, ValueError) as exc:
        _delete_verified_staged_candidate_if_present(staged_candidate_export_root)
        raise RegistryValidationError(f"generated export supersession source is no longer admissible: {exc}") from exc
    if source_state_sha256 != supersession.source_state_sha256:
        _delete_verified_staged_candidate_if_present(staged_candidate_export_root)
        raise RegistryValidationError("generated export supersession source changed before candidate cutover")
    return supersession, revision_id, modelo_id, target_revision_root, source_modelo_root


def _stage_supersession_revision(
    *,
    context: GeneratedExportTreePublicationContext,
    target_revision_root: Path,
    source_modelo_root: Path,
    revision_id: str,
    supersession: GeneratedExportSupersession,
    staged_candidate_export_root: Path,
    candidate_manifest: ExportFragmentProvenanceManifest,
    candidate_manifest_sha256: str,
    transaction_paths: GeneratedExportTransactionPaths,
) -> tuple[Path, Path, str]:
    staged_revision_root = transaction_paths.new_bundle_staging_sibling()
    backup_revision_root = transaction_paths.new_bundle_backup_sibling()
    try:
        candidate_revision_sha256 = _build_supersession_candidate_revision(
            context=context,
            target_revision_root=target_revision_root,
            source_modelo_root=source_modelo_root,
            revision_id=revision_id,
            supersession=supersession,
            staged_revision_root=staged_revision_root,
            staged_candidate_export_root=staged_candidate_export_root,
            candidate_manifest=candidate_manifest,
            candidate_manifest_sha256=candidate_manifest_sha256,
        )
    except BaseException:
        _delete_verified_staged_candidate_if_present(staged_candidate_export_root)
        if staged_revision_root.exists():
            _delete_opaque_transaction_tree(
                staged_revision_root,
                target_root=transaction_paths.transaction_root,
                prefix=transaction_paths.bundle_staging_prefix,
                subject="generated supersession staging revision",
            )
        raise
    return staged_revision_root, backup_revision_root, candidate_revision_sha256


def _build_supersession_candidate_revision(
    *,
    context: GeneratedExportTreePublicationContext,
    target_revision_root: Path,
    source_modelo_root: Path,
    revision_id: str,
    supersession: GeneratedExportSupersession,
    staged_revision_root: Path,
    staged_candidate_export_root: Path,
    candidate_manifest: ExportFragmentProvenanceManifest,
    candidate_manifest_sha256: str,
) -> str:
    _require_complete_regular_tree(target_revision_root, subject="generated target revision bundle")
    if bootstrap_layout_supersession_fingerprint(target_revision_root) != supersession.source_state_sha256:
        raise RegistryValidationError("generated export supersession source changed before candidate copy")
    shutil.copytree(target_revision_root, staged_revision_root)
    if bootstrap_layout_supersession_fingerprint(staged_revision_root) != supersession.source_state_sha256:
        raise RegistryValidationError("generated export supersession source changed while copying the revision")
    if (staged_revision_root / "export").exists():
        raise RegistryValidationError("bootstrap supersession target unexpectedly acquired a generated tree")
    if (staged_revision_root / "export_layouts").is_dir():
        retire_bootstrap_manual_export_layout(
            staged_revision_root,
            revision=revision_id,
            superseded_layout_id=supersession.superseded_layout_id,
        )
    _retarget_reviewed_constructs(staged_revision_root, revision_id=revision_id, supersession=supersession)
    _install_generated_form_companion(
        context=context,
        staged_revision_root=staged_revision_root,
        source_modelo_root=source_modelo_root,
        revision_id=revision_id,
    )
    os.replace(staged_candidate_export_root, staged_revision_root / "export")
    fsync_parent_dir(staged_revision_root / "export")
    _verify_generated_export_companion(
        staged_revision_root / "export",
        expected_manifest_sha256=candidate_manifest_sha256,
        expected_manifest=candidate_manifest,
    )
    _require_complete_regular_tree(staged_revision_root, subject="generated supersession candidate revision")
    return bootstrap_layout_supersession_fingerprint(staged_revision_root)


def _retarget_reviewed_constructs(
    staged_revision_root: Path, *, revision_id: str, supersession: GeneratedExportSupersession
) -> None:
    """Keep stable references as stored; require a local keyed delta for any changed inherited id."""
    if supersession.superseded_layout_id == supersession.generated_layout_id:
        return
    if supersession.expected_construct_references and not (staged_revision_root / "constructs").is_dir():
        raise RegistryValidationError(
            "generated export supersession cannot retarget an inherited construct without a keyed local delta"
        )
    retarget_bootstrap_constructs_in_revision(
        staged_revision_root,
        revision=revision_id,
        superseded_layout_id=supersession.superseded_layout_id,
        generated_layout_id=supersession.generated_layout_id,
        expected_references=supersession.expected_construct_references,
    )


def _write_supersession_intent_journal(
    *,
    modelo_id: str,
    revision_id: str,
    supersession: GeneratedExportSupersession,
    staged_revision_root: Path,
    backup_revision_root: Path,
    candidate_manifest_sha256: str,
    candidate_revision_sha256: str,
    journal_path: Path,
) -> GeneratedExportPublicationJournal:
    journal = GeneratedExportPublicationJournal(
        schema_version=_JOURNAL_SCHEMA_VERSION,
        state="intent",
        modelo=modelo_id,
        revision_id=revision_id,
        candidate_export=str(staged_revision_root),
        backup_export=str(backup_revision_root),
        candidate_manifest_sha256=candidate_manifest_sha256,
        candidate_revision_sha256=candidate_revision_sha256,
        superseded_layout_id=supersession.superseded_layout_id,
        generated_layout_id=supersession.generated_layout_id,
        superseded_construct_references=supersession.expected_construct_references,
        supersession_source_sha256=supersession.source_state_sha256,
    )
    write_generated_export_publication_journal(journal_path, journal)
    return journal


def _require_supersession_source_at_cutover(
    *,
    source_modelo_root: Path,
    target_revision_root: Path,
    staged_revision_root: Path,
    revision_id: str,
    supersession: GeneratedExportSupersession,
    candidate_revision_sha256: str,
) -> None:
    # Pin the whole source once more at the actual cutover boundary. This
    # includes casillas, revision metadata, formulas and form layouts that
    # are not owned by the generator but move with this atomic bundle.
    if bootstrap_layout_supersession_fingerprint(target_revision_root) != supersession.source_state_sha256:
        raise RegistryValidationError("generated export supersession source changed immediately before cutover")
    source_state_sha256 = validate_bootstrap_manual_export_layout_supersession(
        source_modelo_root,
        revision=revision_id,
        superseded_layout_id=supersession.superseded_layout_id,
        expected_references=supersession.expected_construct_references,
        source_ref=supersession.source_ref,
        source_sha256=supersession.source_sha256,
        manual_source_sha256=supersession.manual_source_sha256,
        manual_origin_revision=supersession.manual_origin_revision,
    )
    if source_state_sha256 != supersession.source_state_sha256:
        raise RegistryValidationError("generated export supersession source changed immediately before cutover")
    if bootstrap_layout_supersession_fingerprint(staged_revision_root) != candidate_revision_sha256:
        raise RegistryValidationError("generated supersession candidate revision changed before cutover")


def _cut_over_supersession_revision(
    *,
    context: GeneratedExportTreePublicationContext,
    target_revision_root: Path,
    staged_revision_root: Path,
    backup_revision_root: Path,
    journal_path: Path,
    journal: GeneratedExportPublicationJournal,
    source_sha256: str,
    candidate_revision_sha256: str,
) -> GeneratedExportPublicationJournal:
    context.replace_export_directory(target_revision_root, backup_revision_root)
    fsync_parent_dir(target_revision_root)
    journal = journal.model_copy(update={"state": "backup_staged"})
    write_generated_export_publication_journal(journal_path, journal)
    # Verify the atomic rename captured exactly the pinned source. This closes
    # the last race between the pre-cutover hash and rename.
    if bootstrap_layout_supersession_fingerprint(backup_revision_root) != source_sha256:
        raise RegistryValidationError("generated export supersession source changed during cutover")
    if bootstrap_layout_supersession_fingerprint(staged_revision_root) != candidate_revision_sha256:
        raise RegistryValidationError("generated supersession candidate revision changed before cutover")
    context.replace_export_directory(staged_revision_root, target_revision_root)
    fsync_parent_dir(target_revision_root)
    journal = journal.model_copy(update={"state": "candidate_live"})
    write_generated_export_publication_journal(journal_path, journal)
    if bootstrap_layout_supersession_fingerprint(target_revision_root) != candidate_revision_sha256:
        raise RegistryValidationError("generated supersession live revision changed after cutover")
    return journal


def _commit_supersession_revision(
    *,
    journal: GeneratedExportPublicationJournal,
    journal_path: Path,
    backup_revision_root: Path,
    transaction_paths: GeneratedExportTransactionPaths,
    source_sha256: str,
) -> GeneratedExportPublicationJournal:
    # The commit record is the point of no rollback. A failure writing it is
    # ambiguous, so leave the live candidate, backup and journal for recovery.
    journal = journal.model_copy(update={"state": "committed"})
    try:
        write_generated_export_publication_journal(journal_path, journal)
    except BaseException as error:
        reset_conformance_cache()
        raise RegistryValidationError(
            "generated export supersession passed live validation but commit persistence failed; "
            f"candidate, backup and journal were retained for recovery: {error}",
        ) from error
    reset_conformance_cache()
    if backup_revision_root.exists():
        _require_complete_regular_tree(backup_revision_root, subject="generated supersession rollback revision")
        if bootstrap_layout_supersession_fingerprint(backup_revision_root) != source_sha256:
            raise RegistryValidationError(
                "generated supersession committed, but its rollback revision changed; the journal was retained",
            )
        journal = journal.model_copy(update={"cleanup_started": True})
        write_generated_export_publication_journal(journal_path, journal)
        _delete_opaque_transaction_tree_allow_partial(
            backup_revision_root,
            target_root=transaction_paths.transaction_root,
            prefix=transaction_paths.bundle_backup_prefix,
            subject="generated supersession rollback revision",
        )
    _delete_journal(journal_path)
    return journal


def _install_generated_form_companion(
    *,
    context: GeneratedExportTreePublicationContext,
    staged_revision_root: Path,
    source_modelo_root: Path,
    revision_id: str,
) -> None:
    """Install only the unreviewed companion produced in the validated candidate."""
    source_loaded = load_modelo_directory(source_modelo_root)
    source_revision = source_loaded.revisions[revision_id]
    if not source_revision.form_layouts:
        return
    candidate_revision_root = (
        context.validation.registry_root / "modelos" / str(context.validation.target.modelo) / "revisions" / revision_id
    )
    candidate_form_root = candidate_revision_root / FORM_LAYOUT_DIRECTORY
    if not candidate_form_root.is_dir():
        return
    candidate_fragments = tuple(scan_directory(candidate_form_root, pattern="*.toml", recursive=True))
    if (
        len(candidate_fragments) != 1
        or candidate_fragments[0].parent != candidate_form_root
        or candidate_fragments[0].name not in (FORM_LAYOUT_FRAGMENT, "0001-complete-edition.toml")
    ):
        raise RegistryValidationError("generated form companion candidate has unknown fragment ownership")
    if source_revision.form_layouts[0].review.state is FormLayoutReviewState.REVIEWED:
        return
    source_form_root = staged_revision_root / FORM_LAYOUT_DIRECTORY
    if source_form_root.exists():
        _remove_staged_section_directory(source_form_root)
    source_form_root.mkdir()
    # Isolated validation materialises an inherited edition under the generic
    # complete-edition filename. The live child remains a keyed delta, and the
    # owning form generator writes its local artifact under FORM_LAYOUT_FRAGMENT.
    # Keep the validated bytes while restoring that stable generated filename.
    shutil.copyfile(candidate_fragments[0], source_form_root / FORM_LAYOUT_FRAGMENT)


def _remove_staged_section_directory(path: Path) -> None:
    """Remove one known section directory from a staging tree after checking its location."""
    if is_link_like(path) or not path.is_dir():
        raise RegistryValidationError(f"generated staging section must be a non-linked directory: {path}")
    shutil.rmtree(path)
    if path.exists():
        raise RegistryValidationError(f"generated staging section remains after replacement: {path}")


def _verify_supersession_cutover(
    *,
    context: GeneratedExportTreePublicationContext,
    target_export_root: Path,
    candidate_manifest_sha256: str,
    candidate_manifest: ExportFragmentProvenanceManifest,
    joined: JoinedRecordDesign,
    semantic_map: SemanticMap,
    rendered: RenderedExportTree,
    render_profile: RenderProfile,
    render_profile_source_evidence: RenderProfileSourceEvidence,
) -> None:
    """Verify the live bundle through current generation authority and the production loader."""
    _verify_recovery_package_against_current_authorities(
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
        expected_manifest_sha256=candidate_manifest_sha256,
        expected_manifest=candidate_manifest,
    )


def _rollback_supersession_bundle(
    *,
    context: GeneratedExportTreePublicationContext,
    target_revision_root: Path,
    backup_revision_root: Path,
    staged_revision_root: Path,
    journal: GeneratedExportPublicationJournal,
    journal_path: Path,
    transaction_paths: GeneratedExportTransactionPaths,
) -> None:
    """Restore the prior revision only when every tree is still transaction-pinned."""
    source_sha256 = journal.supersession_source_sha256
    candidate_sha256 = journal.candidate_revision_sha256
    if source_sha256 is None or candidate_sha256 is None:
        raise RegistryValidationError("generated supersession journal has no complete revision pin")
    _require_pinned_supersession_stage(staged_revision_root, candidate_sha256)
    candidate_was_moved = _rollback_live_supersession_revision(
        context=context,
        target_revision_root=target_revision_root,
        backup_revision_root=backup_revision_root,
        staged_revision_root=staged_revision_root,
        journal_path=journal_path,
        transaction_paths=transaction_paths,
        source_sha256=source_sha256,
        candidate_sha256=candidate_sha256,
    )
    if candidate_was_moved is None:
        return
    _restore_supersession_backup_if_vacant(
        context=context,
        target_revision_root=target_revision_root,
        backup_revision_root=backup_revision_root,
    )
    if (
        candidate_was_moved
        and target_revision_root.exists()
        and bootstrap_layout_supersession_fingerprint(target_revision_root) != source_sha256
    ):
        raise RegistryValidationError(
            "restored supersession revision differs from its source pin; preserving the journal",
        )
    if staged_revision_root.exists():
        _delete_opaque_transaction_tree(
            staged_revision_root,
            target_root=transaction_paths.transaction_root,
            prefix=transaction_paths.bundle_staging_prefix,
            subject="failed generated supersession candidate revision",
        )
    _delete_journal(journal_path)


def _require_pinned_supersession_stage(staged_revision_root: Path, candidate_sha256: str) -> None:
    if (
        staged_revision_root.exists()
        and bootstrap_layout_supersession_fingerprint(staged_revision_root) != candidate_sha256
    ):
        raise RegistryValidationError("generated supersession staging revision changed; preserving it and the journal")


def _rollback_live_supersession_revision(
    *,
    context: GeneratedExportTreePublicationContext,
    target_revision_root: Path,
    backup_revision_root: Path,
    staged_revision_root: Path,
    journal_path: Path,
    transaction_paths: GeneratedExportTransactionPaths,
    source_sha256: str,
    candidate_sha256: str,
) -> bool | None:
    if not target_revision_root.exists():
        return False
    target_sha256 = bootstrap_layout_supersession_fingerprint(target_revision_root)
    if target_sha256 == source_sha256 and not backup_revision_root.exists():
        if staged_revision_root.exists():
            _delete_opaque_transaction_tree(
                staged_revision_root,
                target_root=transaction_paths.transaction_root,
                prefix=transaction_paths.bundle_staging_prefix,
                subject="generated supersession staging revision",
            )
        _delete_journal(journal_path)
        return None
    if target_sha256 != candidate_sha256:
        raise RegistryValidationError(
            "generated supersession live revision changed after cutover; preserving it, backup and journal",
        )
    if not backup_revision_root.exists():
        raise RegistryValidationError(
            "generated supersession rollback backup disappeared; preserving live candidate",
        )
    if bootstrap_layout_supersession_fingerprint(backup_revision_root) != source_sha256:
        raise RegistryValidationError(
            "generated supersession rollback revision changed; preserving live candidate, backup and journal",
        )
    if staged_revision_root.exists():
        raise RegistryValidationError(
            "generated supersession staging path is occupied; preserving all transaction state"
        )
    context.replace_export_directory(target_revision_root, staged_revision_root)
    fsync_parent_dir(target_revision_root)
    return True


def _restore_supersession_backup_if_vacant(
    *,
    context: GeneratedExportTreePublicationContext,
    target_revision_root: Path,
    backup_revision_root: Path,
) -> None:
    if not target_revision_root.exists() and backup_revision_root.exists():
        # A vacant destination preserves captured bytes without overwriting a writer's tree.
        _require_complete_regular_tree(backup_revision_root, subject="generated supersession rollback revision")
        context.replace_export_directory(backup_revision_root, target_revision_root)
        fsync_parent_dir(target_revision_root)
    elif not target_revision_root.exists():
        raise RegistryValidationError("generated supersession lost both the live and rollback revision")


def _delete_opaque_transaction_tree(path: Path, *, target_root: Path, prefix: str, subject: str) -> None:
    """Delete a transaction-owned tree only after proving its exact registry-root sibling identity."""
    resolved_target_root = target_root.resolve()
    resolved = path.resolve()
    if resolved.parent != resolved_target_root or not resolved.name.startswith(prefix) or is_link_like(path):
        raise RegistryValidationError(f"{subject} is not an owned sibling of the target registry root: {path}")
    _require_complete_regular_tree(resolved, subject=subject)
    try:
        shutil.rmtree(resolved)
    except OSError as exc:
        raise RegistryValidationError(f"cannot remove {subject}: {exc}") from exc
    if resolved.exists():
        raise RegistryValidationError(f"{subject} remains after deletion: {resolved}")


def _delete_opaque_transaction_tree_allow_partial(
    path: Path,
    *,
    target_root: Path,
    prefix: str,
    subject: str,
) -> None:
    """Finish committed cleanup of a transaction sibling after an interrupted delete."""
    resolved_target_root = target_root.resolve()
    resolved = path.resolve()
    if resolved.parent != resolved_target_root or not resolved.name.startswith(prefix) or is_link_like(path):
        raise RegistryValidationError(f"{subject} is not an owned sibling of the target registry root: {path}")
    if not resolved.exists():
        return
    _require_link_free_regular_members_allow_empty(resolved, subject=subject)
    try:
        shutil.rmtree(resolved)
    except OSError as exc:
        raise RegistryValidationError(f"cannot finish removing {subject}: {exc}") from exc
    if resolved.exists():
        raise RegistryValidationError(f"{subject} remains after cleanup: {resolved}")

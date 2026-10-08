"""Retire a completed ordinary publication at its original legacy journal location."""

from __future__ import annotations

from cadrumo.core.link_safety import is_link_like
from cadrumo.core.locks import exclusive_file_lock
from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ._tree_validation import validate_generated_export_tree
from .export_tree_models import RenderedExportTree
from .joined_record_design import JoinedRecordDesign
from .render_check import compare_export_tree_roots
from .render_profile_evidence import RenderProfileSourceEvidence
from .render_profile_model import RenderProfile
from .semantic_map import SemanticMap
from .tree_publication_artifacts import _verify_post_cutover_target, verify_generated_export_package
from .tree_publication_contracts import GeneratedExportTransactionPaths, GeneratedExportTreePublicationContext
from .tree_publication_journal import (
    _delete_journal,
    _journal_backup_path,
    _journal_staged_candidate_path,
    load_generated_export_publication_journal,
)
from .tree_publication_paths import _admit_target_publication_path, require_expected_target_state


def retire_completed_legacy_publication(
    *,
    context: GeneratedExportTreePublicationContext,
    joined: JoinedRecordDesign,
    semantic_map: SemanticMap,
    rendered: RenderedExportTree,
    render_profile: RenderProfile,
    render_profile_source_evidence: RenderProfileSourceEvidence,
) -> None:
    """Retire only a digest-pinned live candidate whose rollback cleanup already finished.

    A fresh independently validated render must reproduce the live record semantics.
    Stale provenance remains stale and requires a separate canonical republication.
    Every unfinished or conflicting transaction stays preserved for ordinary recovery.
    """
    paths = GeneratedExportTransactionPaths.for_context(context)
    with exclusive_file_lock(paths.lock_identity), exclusive_file_lock(paths.legacy_lock_identity, timeout=0):
        if paths.journal.exists() or is_link_like(paths.journal):
            raise RegistryValidationError("legacy recovery refuses a concurrent current-location journal")
        journal = load_generated_export_publication_journal(paths.legacy_journal)
        expected = context.expected_target_state
        if (
            journal.is_supersession
            or journal.state != "candidate_live"
            or journal.modelo != context.validation.target.modelo
            or journal.revision_id != context.validation.target.revision_id
            or expected is None
            or expected.manifest_sha256 != journal.candidate_manifest_sha256
        ):
            raise RegistryValidationError("legacy cleanup requires the exact completed ordinary target receipt")
        target = _admit_target_publication_path(context)
        require_expected_target_state(context, target)
        backup = _journal_backup_path(journal, target, paths.target_root)
        staged = _journal_staged_candidate_path(journal, paths.target_root)
        if any(path.exists() or is_link_like(path) for path in (backup, staged)):
            raise RegistryValidationError("legacy cleanup refuses a transaction with remaining recovery trees")
        manifest = verify_generated_export_package(target)
        _verify_post_cutover_target(
            target,
            expected_manifest_sha256=journal.candidate_manifest_sha256,
            expected_manifest=manifest,
        )
        validated = validate_generated_export_tree(
            context=context.validation,
            joined=joined,
            semantic_map=semantic_map,
            rendered=rendered,
            render_profile=render_profile,
            render_profile_source_evidence=render_profile_source_evidence,
        )
        if (manifest.source_ref, manifest.source_sha256) != (
            validated.provenance_manifest.source_ref,
            validated.provenance_manifest.source_sha256,
        ):
            raise RegistryValidationError("legacy cleanup refuses changed official source authority")
        candidate = (
            context.validation.registry_root / "modelos" / journal.modelo / "revisions" / journal.revision_id / "export"
        )
        comparison = compare_export_tree_roots(
            modelo=journal.modelo,
            revision=journal.revision_id,
            layout_id=str(rendered.layout.id),
            committed_root=target,
            rendered_root=candidate,
        )
        if comparison.record_differing or comparison.only_committed or comparison.only_rendered:
            raise RegistryValidationError(
                "legacy cleanup refuses live records that differ from current validated generation"
            )
        # Recheck the exact observed target after validation, before retiring its journal.
        require_expected_target_state(context, target)
        _delete_journal(paths.legacy_journal)

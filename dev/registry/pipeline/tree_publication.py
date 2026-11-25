"""Orchestrate validated generated export tree publication.

A single target publishes its ``export/`` directory alone; its generated form
companion stays with the separate form owner. A reviewed repair set is the one
exception: its set transaction installs every member's ``export/`` and its
generated ``form_layouts/0001-form-layout.toml`` together, runs one live
validation over the whole result, and restores every member's previous bytes
on any failure. The form bytes it installs are the form owner's generator
output, validated with the set before publication.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path

from cadrumo.core.atomic_write import atomic_write_bytes
from cadrumo.core.fsync import fsync_parent_dir
from cadrumo.core.locks import exclusive_file_lock
from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ..compiler.export_fragment_grammar import EXPORT_FRAGMENT_PROVENANCE_FILENAME
from ..conformance.manager import reset_conformance_cache
from ..form_layout.serialization import form_layout_fragment_path
from .export_fragment_provenance import ExportFragmentProvenanceManifest
from .export_tree_models import RenderedExportTree
from .generated_export_inheritance import generated_export_source_chain_fingerprint
from .joined_record_design import JoinedRecordDesign
from .render_profile_evidence import RenderProfileSourceEvidence
from .render_profile_model import RenderProfile
from .semantic_map import SemanticMap
from .tree_clearance_publication import has_export_clearance, publish_export_clearance_bundle
from .tree_publication_artifacts import (
    delete_verified_staged_candidate_if_present,
    stage_verified_candidate_package,
    verify_generated_export_package,
    verify_post_cutover_target,
)
from .tree_publication_contracts import (
    JOURNAL_SCHEMA_VERSION,
    GeneratedExportPublicationJournal,
    GeneratedExportTransactionPaths,
    GeneratedExportTreePublicationContext,
    PublishedGeneratedExportTree,
    export_provenance_file_sha256,
)
from .tree_publication_journal import (
    delete_journal,
    load_generated_export_publication_journal,
    write_generated_export_publication_journal,
)
from .tree_publication_paths import (
    admit_target_publication_path,
    prepare_candidate_publication_path,
    require_expected_target_state,
    require_no_stale_sibling_manifest,
)
from .tree_publication_recovery import (
    delete_opaque_rollback_tree,
    recover_interrupted_publication,
    restore_backup_or_raise,
    restore_failed_export_cutover,
)
from .tree_publication_supersession import publish_superseding_revision_bundle
from .tree_publication_supersession_recovery import recover_interrupted_supersession_bundle_locked
from .tree_validation import (
    ValidatedGeneratedExportTree,
    ValidatedHistoricalStaticGeneratedExportTree,
    validate_generated_export_tree,
)

__all__ = [
    "GeneratedExportSetMember",
    "publish_validated_generated_export_tree",
    "publish_validated_generated_export_tree_set",
]


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
    candidate_export_root = prepare_candidate_publication_path(context)
    transaction_paths = GeneratedExportTransactionPaths.for_context(context)
    journal_path = transaction_paths.journal
    with exclusive_file_lock(transaction_paths.lock_identity):
        _require_retained_publication_mode(context)
        _require_retained_source_after_cutover(context)
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
        _require_retained_source_after_cutover(context)
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
        _require_retained_publication_mode(context)
        _require_retained_source_after_cutover(context)
        if context.supersession is not None:
            return publish_superseding_revision_bundle(
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
        publisher = (
            publish_export_clearance_bundle
            if (
                not (context.validation.inheritance is not None and context.validation.source_chain_revisions)
                and has_export_clearance(target_export_root.parent, str(context.validation.target.revision_id))
            )
            else _publish_ordinary_candidate
        )
        published = publisher(
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
    if journal_path.exists():
        interrupted_journal = load_generated_export_publication_journal(journal_path)
        if (
            interrupted_journal.is_revision_bundle
            and context.validation.inheritance is not None
            and context.validation.source_chain_revisions
        ):
            raise RegistryValidationError(
                "compact retained source publication cannot recover a revision-bundle transaction",
            )
        if interrupted_journal.is_revision_bundle and recover_interrupted_supersession_bundle_locked(
            journal=interrupted_journal,
            journal_path=journal_path,
            transaction_paths=transaction_paths,
        ):
            target_export_root = admit_target_publication_path(context)
            reset_conformance_cache()
            return target_export_root, True
    target_export_root = admit_target_publication_path(context)
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
    require_no_stale_sibling_manifest(target_export_root.parent, subject="generated target revision")
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
) -> tuple[
    ValidatedGeneratedExportTree | ValidatedHistoricalStaticGeneratedExportTree,
    ExportFragmentProvenanceManifest,
    str,
    Path,
]:
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
    validated: ValidatedGeneratedExportTree | ValidatedHistoricalStaticGeneratedExportTree,
    candidate_manifest: ExportFragmentProvenanceManifest,
    candidate_manifest_sha256: str,
    staged_candidate_export_root: Path,
) -> PublishedGeneratedExportTree:
    backup_export_root = transaction_paths.new_backup_sibling()
    journal = GeneratedExportPublicationJournal(
        schema_version=JOURNAL_SCHEMA_VERSION,
        state="intent",
        modelo=str(context.validation.target.modelo),
        revision_id=str(context.validation.target.revision_id),
        candidate_export=staged_candidate_export_root.name,
        backup_export=backup_export_root.name,
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
        delete_opaque_rollback_tree(backup_export_root)
    delete_journal(journal_path)
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
        restore_backup_or_raise(
            target_export_root=target_export_root,
            backup_export_root=backup_export_root,
            publish_error=publish_error,
            replace_export_directory=context.replace_export_directory,
        )
        delete_verified_staged_candidate_if_present(staged_candidate_export_root)
        delete_journal(journal_path)
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
        _require_retained_source_after_cutover(context)
        verify_post_cutover_target(
            target_export_root,
            expected_manifest_sha256=candidate_manifest_sha256,
            expected_manifest=candidate_manifest,
        )
        if context.final_live_validator is not None:
            context.final_live_validator()
        _require_retained_source_after_cutover(context)
    except BaseException as error:
        try:
            restore_failed_export_cutover(
                context=context,
                target_export_root=target_export_root,
                backup_export_root=backup_export_root,
                had_target=had_target,
                transaction_paths=transaction_paths,
            )
            delete_journal(journal_path)
        except BaseException as restore_error:
            raise RegistryValidationError(
                "generated export publication failed and the previous target could not be restored; "
                f"publication_error={error}; restoration_error={restore_error}",
            ) from restore_error
        raise RegistryValidationError(
            f"generated export publication failed; the previous target was restored: {error}",
        ) from error


def _require_retained_source_after_cutover(context: GeneratedExportTreePublicationContext) -> None:
    """Keep compact target cutover from changing any captured non-export source byte."""
    expected = context.validation.source_chain_non_export_sha256
    if expected is None:
        return
    if context.validation.source_chain_registry_root != context.target_root.resolve():
        raise RegistryValidationError("generated source-chain origin differs from the publication root")
    current = generated_export_source_chain_fingerprint(
        context.target_root,
        modelo=str(context.validation.target.modelo),
        revision=str(context.validation.target.revision_id),
        omit_target_export=True,
    )
    if current != expected:
        raise RegistryValidationError("generated source-chain facts changed during export cutover")


def _require_retained_publication_mode(context: GeneratedExportTreePublicationContext) -> None:
    """Keep compact retained source publication inside its export-only transaction."""
    if context.validation.inheritance is None or not context.validation.source_chain_revisions:
        return
    revision_root = (
        context.target_root.resolve()
        / "modelos"
        / str(context.validation.target.modelo)
        / "revisions"
        / str(context.validation.target.revision_id)
    )
    if context.supersession is not None or has_export_clearance(
        revision_root, str(context.validation.target.revision_id)
    ):
        raise RegistryValidationError(
            "compact retained source publication does not support supersession or export clearance",
        )


@dataclass(frozen=True, slots=True)
class GeneratedExportSetMember:
    """One member of a reviewed set transaction: its validated export candidate and its generated form."""

    context: GeneratedExportTreePublicationContext
    joined: JoinedRecordDesign
    semantic_map: SemanticMap
    rendered: RenderedExportTree
    render_profile: RenderProfile
    render_profile_source_evidence: RenderProfileSourceEvidence
    form_fragment: bytes


@dataclass(slots=True)
class _SetMemberCutover:
    """The rollback state of one set member, advanced as each step of its cutover lands."""

    context: GeneratedExportTreePublicationContext
    target_export_root: Path
    transaction_paths: GeneratedExportTransactionPaths
    validated: ValidatedGeneratedExportTree | ValidatedHistoricalStaticGeneratedExportTree
    candidate_manifest: ExportFragmentProvenanceManifest
    candidate_manifest_sha256: str
    staged_candidate_export_root: Path
    form_path: Path
    old_form: bytes
    new_form: bytes
    backup_export_root: Path | None = None
    journal: GeneratedExportPublicationJournal | None = None
    had_target: bool = False
    export_installed: bool = False
    form_written: bool = False


def publish_validated_generated_export_tree_set(
    *,
    members: Sequence[GeneratedExportSetMember],
    final_live_validator: Callable[[], None],
) -> tuple[PublishedGeneratedExportTree, ...]:
    """Publish a reviewed set of one modelo's targets as one transaction.

    Every member is validated and staged under its own lock before any live
    change. Every member's export and generated form are then installed, and one
    live validation runs over the whole result. Any failure restores every
    member's previous export and form bytes; only a passing set commits.
    """
    _require_publishable_set(members)
    with ExitStack() as locks:
        for member in members:
            locks.enter_context(
                exclusive_file_lock(GeneratedExportTransactionPaths.for_context(member.context).lock_identity)
            )
        cutovers = [_admit_and_stage_set_member(member) for member in members]
        try:
            for cutover in cutovers:
                _install_set_member(cutover)
            for cutover in cutovers:
                verify_post_cutover_target(
                    cutover.target_export_root,
                    expected_manifest_sha256=cutover.candidate_manifest_sha256,
                    expected_manifest=cutover.candidate_manifest,
                )
                if cutover.form_path.read_bytes() != cutover.new_form:
                    raise RegistryValidationError("generated set form fragment differs from its validated bytes")
            final_live_validator()
            for cutover in cutovers:
                _require_retained_source_after_cutover(cutover.context)
        except BaseException as error:
            _restore_set_cutovers(cutovers, error)
            raise RegistryValidationError(
                f"generated export set publication failed; every member's previous tree was restored: {error}",
            ) from error
        published = tuple(_commit_set_member(cutover) for cutover in cutovers)
    reset_conformance_cache()
    return published


def _require_publishable_set(members: Sequence[GeneratedExportSetMember]) -> None:
    if not members:
        raise RegistryValidationError("generated export set publication requires at least one member")
    first = members[0].context
    identities = [
        (str(member.context.validation.target.modelo), str(member.context.validation.target.revision_id))
        for member in members
    ]
    if len(set(identities)) != len(identities) or len({modelo for modelo, _revision in identities}) != 1:
        raise RegistryValidationError("generated export set publication requires distinct revisions of one modelo")
    for member in members:
        _require_publishable_set_member(member.context, first)


def _require_publishable_set_member(
    context: GeneratedExportTreePublicationContext, first: GeneratedExportTreePublicationContext
) -> None:
    if context.target_root.resolve() != first.target_root.resolve():
        raise RegistryValidationError("generated export set members must share one publication root")
    if context.supersession is not None or context.final_live_validator is not None:
        raise RegistryValidationError(
            "generated export set publication refuses supersession and member-level live validators",
        )
    if context.validation.inheritance is not None:
        raise RegistryValidationError("generated export set publication refuses inherited export targets")


def _admit_and_stage_set_member(member: GeneratedExportSetMember) -> _SetMemberCutover:
    context = member.context
    candidate_export_root = prepare_candidate_publication_path(context)
    transaction_paths = GeneratedExportTransactionPaths.for_context(context)
    if transaction_paths.journal.exists():
        raise RegistryValidationError(
            "generated export set publication refuses a target with an interrupted single-target transaction",
        )
    target_export_root = admit_target_publication_path(context)
    require_expected_target_state(context, target_export_root)
    require_no_stale_sibling_manifest(target_export_root.parent, subject="generated set target revision")
    if has_export_clearance(target_export_root.parent, str(context.validation.target.revision_id)):
        raise RegistryValidationError("generated export set publication refuses export clearance")
    form_path = form_layout_fragment_path(target_export_root.parent)
    if not form_path.is_file():
        raise RegistryValidationError("generated export set member has no generated form fragment to replace")
    validated, candidate_manifest, candidate_manifest_sha256, staged_candidate_export_root = (
        _validate_and_stage_candidate(
            context=context,
            candidate_export_root=candidate_export_root,
            joined=member.joined,
            semantic_map=member.semantic_map,
            rendered=member.rendered,
            render_profile=member.render_profile,
            render_profile_source_evidence=member.render_profile_source_evidence,
        )
    )
    return _SetMemberCutover(
        context=context,
        target_export_root=target_export_root,
        transaction_paths=transaction_paths,
        validated=validated,
        candidate_manifest=candidate_manifest,
        candidate_manifest_sha256=candidate_manifest_sha256,
        staged_candidate_export_root=staged_candidate_export_root,
        form_path=form_path,
        old_form=form_path.read_bytes(),
        new_form=member.form_fragment,
    )


def _install_set_member(cutover: _SetMemberCutover) -> None:
    context = cutover.context
    backup_export_root = cutover.transaction_paths.new_backup_sibling()
    journal = GeneratedExportPublicationJournal(
        schema_version=JOURNAL_SCHEMA_VERSION,
        state="intent",
        modelo=str(context.validation.target.modelo),
        revision_id=str(context.validation.target.revision_id),
        candidate_export=cutover.staged_candidate_export_root.name,
        backup_export=backup_export_root.name,
        candidate_manifest_sha256=cutover.candidate_manifest_sha256,
    )
    write_generated_export_publication_journal(cutover.transaction_paths.journal, journal)
    cutover.journal = journal
    cutover.backup_export_root = backup_export_root
    if cutover.target_export_root.exists():
        context.replace_export_directory(cutover.target_export_root, backup_export_root)
        cutover.had_target = True
        fsync_parent_dir(cutover.target_export_root)
        cutover.journal = journal.model_copy(update={"state": "backup_staged"})
        write_generated_export_publication_journal(cutover.transaction_paths.journal, cutover.journal)
    context.replace_export_directory(cutover.staged_candidate_export_root, cutover.target_export_root)
    cutover.export_installed = True
    fsync_parent_dir(cutover.target_export_root)
    cutover.journal = cutover.journal.model_copy(update={"state": "candidate_live"})
    write_generated_export_publication_journal(cutover.transaction_paths.journal, cutover.journal)
    cutover.form_written = True
    atomic_write_bytes(cutover.form_path, cutover.new_form)


def _restore_set_cutovers(cutovers: Sequence[_SetMemberCutover], error: BaseException) -> None:
    """Restore every member's previous export and form, newest first."""
    failures: list[str] = []
    for cutover in reversed(cutovers):
        try:
            if cutover.form_written:
                atomic_write_bytes(cutover.form_path, cutover.old_form)
            if cutover.backup_export_root is not None:
                restore_failed_export_cutover(
                    context=cutover.context,
                    target_export_root=cutover.target_export_root,
                    backup_export_root=cutover.backup_export_root,
                    had_target=cutover.had_target,
                    transaction_paths=cutover.transaction_paths,
                )
            if not cutover.export_installed:
                delete_verified_staged_candidate_if_present(cutover.staged_candidate_export_root)
            if cutover.journal is not None:
                delete_journal(cutover.transaction_paths.journal)
        except BaseException as restore_error:
            failures.append(
                f"{cutover.context.validation.target.revision_id}: {restore_error}",
            )
    if failures:
        raise RegistryValidationError(
            "generated export set publication failed and some previous trees could not be restored; "
            f"publication_error={error}; restoration_errors={failures}",
        ) from error


def _commit_set_member(cutover: _SetMemberCutover) -> PublishedGeneratedExportTree:
    if cutover.journal is None:
        raise RegistryValidationError("generated export set member reached commit without its journal")
    write_generated_export_publication_journal(
        cutover.transaction_paths.journal, cutover.journal.model_copy(update={"state": "committed"})
    )
    if cutover.had_target and cutover.backup_export_root is not None:
        delete_opaque_rollback_tree(cutover.backup_export_root)
    delete_journal(cutover.transaction_paths.journal)
    return PublishedGeneratedExportTree(
        validated=cutover.validated,
        export_root=cutover.target_export_root,
        provenance_manifest_path=cutover.target_export_root / EXPORT_FRAGMENT_PROVENANCE_FILENAME,
    )

"""Publish an absent delta export and retire its obsolete family clearance.

The export and its revision metadata travel in one digest-pinned transaction.
The existing revision-bundle rollback and recovery own every interruption.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from cadrumo.core.fsync import fsync_parent_dir
from cadrumo.core.toml import parse_toml
from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ..compiler.export_fragment_grammar import EXPORT_FRAGMENT_PROVENANCE_FILENAME
from ._tree_validation import ValidatedGeneratedExportTree, ValidatedHistoricalStaticGeneratedExportTree
from .bootstrap_supersession import bootstrap_layout_supersession_fingerprint
from .export_fragment_provenance import ExportFragmentProvenanceManifest
from .export_tree_serialization import render_toml_bytes
from .tree_publication_artifacts import _require_complete_regular_tree, _verify_post_cutover_target
from .tree_publication_contracts import (
    _JOURNAL_SCHEMA_VERSION,
    GeneratedExportPublicationJournal,
    GeneratedExportTransactionPaths,
    GeneratedExportTreePublicationContext,
    PublishedGeneratedExportTree,
)
from .tree_publication_journal import write_generated_export_publication_journal
from .tree_publication_supersession import (
    _commit_supersession_revision,
    _cut_over_supersession_revision,
    _rollback_supersession_bundle,
)


def _has_export_clearance(revision_root: Path, revision_id: str) -> bool:
    metadata = revision_root / "revision.toml"
    if not metadata.is_file():
        return False
    payload = parse_toml(metadata.read_text(encoding="utf-8"))
    table = payload.get("revisions", {}).get(revision_id, {})
    return any(row.get("family") == "export_layouts" for row in table.get("cleared_families", ()))


def _publish_export_clearance_bundle(
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
    revision_root = target_export_root.parent
    revision_id = str(context.validation.target.revision_id)
    if target_export_root.exists():
        raise RegistryValidationError("export clearance retirement requires an absent generated tree")
    _require_complete_regular_tree(revision_root, subject="export clearance source revision")
    source_digest = bootstrap_layout_supersession_fingerprint(revision_root)
    if context.expected_target_state is None or context.expected_target_state.clearance_source_sha256 != source_digest:
        raise RegistryValidationError("export clearance source changed after check")
    admitted = parse_toml((revision_root / "revision.toml").read_text(encoding="utf-8"))["revisions"][revision_id]
    withdrawn = [row for row in admitted.get("cleared_families", ()) if row["family"] == "export_layouts"]
    if len(withdrawn) != 1 or withdrawn[0]["cause"] != "not_authored_for_this_edition":
        raise RegistryValidationError("export publication cannot retire an ambiguous or differently grounded clearance")
    staged = transaction_paths.new_bundle_staging_sibling()
    backup = transaction_paths.new_bundle_backup_sibling()
    shutil.copytree(revision_root, staged)
    if bootstrap_layout_supersession_fingerprint(staged) != source_digest:
        raise RegistryValidationError("export clearance source changed during candidate copy")
    metadata = staged / "revision.toml"
    payload = parse_toml(metadata.read_text(encoding="utf-8"))
    table = payload["revisions"][revision_id]
    clearances = table["cleared_families"]
    withdrawn = [row for row in clearances if row["family"] == "export_layouts"]
    if len(withdrawn) != 1 or withdrawn[0]["cause"] != "not_authored_for_this_edition":
        raise RegistryValidationError("export publication cannot retire an ambiguous or differently grounded clearance")
    remaining = [row for row in clearances if row["family"] != "export_layouts"]
    if remaining:
        table["cleared_families"] = remaining
    else:
        del table["cleared_families"]
    metadata.write_bytes(render_toml_bytes(metadata.name, payload))
    os.replace(staged_candidate_export_root, staged / "export")
    fsync_parent_dir(staged / "export")
    candidate_digest = bootstrap_layout_supersession_fingerprint(staged)
    journal = GeneratedExportPublicationJournal(
        schema_version=_JOURNAL_SCHEMA_VERSION,
        state="intent",
        modelo=str(context.validation.target.modelo),
        revision_id=revision_id,
        candidate_export=str(staged),
        backup_export=str(backup),
        candidate_manifest_sha256=candidate_manifest_sha256,
        candidate_revision_sha256=candidate_digest,
        supersession_source_sha256=source_digest,
        retires_export_clearance=True,
    )
    write_generated_export_publication_journal(journal_path, journal)
    try:
        if bootstrap_layout_supersession_fingerprint(revision_root) != source_digest:
            raise RegistryValidationError("export clearance source changed before cutover")
        journal = _cut_over_supersession_revision(
            context=context,
            target_revision_root=revision_root,
            staged_revision_root=staged,
            backup_revision_root=backup,
            journal_path=journal_path,
            journal=journal,
            source_sha256=source_digest,
            candidate_revision_sha256=candidate_digest,
        )
        _verify_post_cutover_target(
            target_export_root,
            expected_manifest_sha256=candidate_manifest_sha256,
            expected_manifest=candidate_manifest,
        )
        if context.final_live_validator is not None:
            context.final_live_validator()
    except BaseException as error:
        _rollback_supersession_bundle(
            context=context,
            target_revision_root=revision_root,
            backup_revision_root=backup,
            staged_revision_root=staged,
            journal=journal,
            journal_path=journal_path,
            transaction_paths=transaction_paths,
        )
        raise RegistryValidationError(
            f"generated clearance publication failed; the previous revision was restored: {error}"
        ) from error
    _commit_supersession_revision(
        journal=journal,
        journal_path=journal_path,
        backup_revision_root=backup,
        transaction_paths=transaction_paths,
        source_sha256=source_digest,
    )
    return PublishedGeneratedExportTree(
        validated=validated,
        export_root=target_export_root,
        provenance_manifest_path=target_export_root / EXPORT_FRAGMENT_PROVENANCE_FILENAME,
    )

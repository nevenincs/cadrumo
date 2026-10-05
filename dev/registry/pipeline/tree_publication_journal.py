"""Persist and validate generated export publication recovery journals."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from pydantic import ValidationError

from cadrumo.core.fsync import fsync_parent_dir
from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.core.link_safety import is_link_like
from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ..compiler.export_fragment_grammar import EXPORT_FRAGMENT_PROVENANCE_FILENAME
from .tree_publication_artifacts import verify_generated_export_package
from .tree_publication_contracts import (
    GeneratedExportPublicationJournal,
    GeneratedExportTransactionPaths,
    GeneratedExportTreePublicationContext,
    export_provenance_file_sha256,
)


def _journal_supersession_candidate_revision_path(
    journal: GeneratedExportPublicationJournal,
    transaction_paths: GeneratedExportTransactionPaths,
) -> Path:
    candidate = Path(journal.candidate_export)
    if candidate.parent != transaction_paths.transaction_root or not candidate.name.startswith(
        transaction_paths.bundle_staging_prefix,
    ):
        raise RegistryValidationError("generated supersession candidate is not a transaction-root staging sibling")
    if is_link_like(candidate):
        raise RegistryValidationError("generated supersession candidate must not be a symbolic link or junction")
    return candidate


def _journal_supersession_backup_revision_path(
    journal: GeneratedExportPublicationJournal,
    transaction_paths: GeneratedExportTransactionPaths,
) -> Path:
    backup = Path(journal.backup_export)
    if backup.parent != transaction_paths.transaction_root or not backup.name.startswith(
        transaction_paths.bundle_backup_prefix,
    ):
        raise RegistryValidationError("generated supersession backup is not a transaction-root backup sibling")
    if is_link_like(backup):
        raise RegistryValidationError("generated supersession backup must not be a symbolic link or junction")
    return backup


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


def write_generated_export_publication_journal(path: Path, journal: GeneratedExportPublicationJournal) -> None:
    """Durably replace the journal at ``path`` with the canonical JSON of ``journal``."""
    _require_journal_supersession_shape(journal)
    payload = canonical_json_bytes(journal.model_dump(mode="json", exclude_none=True))
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
    _require_journal_supersession_shape(journal)
    if raw != canonical_json_bytes(journal.model_dump(mode="json", exclude_none=True)):
        raise RegistryValidationError(f"generated publication journal is not canonical JSON: {path}")
    return journal


def _require_journal_supersession_shape(journal: GeneratedExportPublicationJournal) -> None:
    """Keep normal export journals distinct from complete supersession bundles."""
    supersession_values = (
        journal.generated_layout_id,
        journal.superseded_construct_references,
        journal.supersession_source_sha256,
        journal.candidate_revision_sha256,
    )
    if journal.superseded_layout_id is None:
        if any(value is not None for value in supersession_values) or journal.cleanup_started is not None:
            raise RegistryValidationError("generated publication journal has an incomplete supersession pin")
        return
    if any(value is None for value in supersession_values):
        raise RegistryValidationError("generated publication journal has an incomplete supersession pin")
    if journal.cleanup_started is not None and journal.state != "committed":
        raise RegistryValidationError("generated supersession cleanup cannot begin before commit")


def _delete_journal(path: Path) -> None:
    if path.exists():
        path.unlink()
        fsync_parent_dir(path)

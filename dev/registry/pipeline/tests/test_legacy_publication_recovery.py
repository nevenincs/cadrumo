"""Real legacy cleanup keeps unfinished transactions and target conflicts intact."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from cadrumo.core.locks import exclusive_file_lock
from cadrumo.core.locks_errors import LockAcquisitionError
from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ..legacy_publication_recovery import retire_completed_legacy_publication
from ..tree_publication_contracts import (
    GeneratedExportPublicationJournal,
    GeneratedExportTransactionPaths,
    GeneratedExportTreeTargetStateReceipt,
)
from ..tree_publication_journal import write_generated_export_publication_journal
from ._generated_tree_test_support import isolated_render_profile
from .test_generated_tree_publication import _publication_inputs, _tree_bytes

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize("conflict", (None, "intent", "wrong-digest", "remaining-backup", "active-legacy-writer"))
def test_completed_legacy_cleanup_requires_an_exact_finished_transaction(tmp_path: Path, conflict: str | None) -> None:
    context, joined, semantic_map, rendered, _candidate = _publication_inputs(tmp_path, existing_export=True)
    receipt = GeneratedExportTreeTargetStateReceipt.observe(context.target_export_root)
    assert receipt.manifest_sha256 is not None
    context = dataclasses.replace(context, expected_target_state=receipt)
    paths = GeneratedExportTransactionPaths.for_context(context)
    backup = paths.new_backup_sibling()
    if conflict == "remaining-backup":
        backup.mkdir()
        (backup / "preserve.txt").write_text("unfinished recovery", encoding="utf-8")
    journal = GeneratedExportPublicationJournal(
        schema_version=1,
        state="intent" if conflict == "intent" else "candidate_live",
        modelo=context.validation.target.modelo,
        revision_id=context.validation.target.revision_id,
        candidate_export=str(paths.new_staging_sibling()),
        backup_export=str(backup),
        candidate_manifest_sha256="a" * 64 if conflict == "wrong-digest" else receipt.manifest_sha256,
    )
    write_generated_export_publication_journal(paths.legacy_journal, journal)
    before_target = _tree_bytes(context.target_export_root)
    before_journal = paths.legacy_journal.read_bytes()
    profile, evidence = isolated_render_profile()

    def recover() -> None:
        retire_completed_legacy_publication(
            context=context,
            joined=joined,
            semantic_map=semantic_map,
            rendered=rendered,
            render_profile=profile,
            render_profile_source_evidence=evidence,
        )

    if conflict == "active-legacy-writer":
        with exclusive_file_lock(paths.legacy_lock_identity), pytest.raises(LockAcquisitionError):
            recover()
        assert paths.legacy_journal.read_bytes() == before_journal
    elif conflict is None:
        recover()
        assert not paths.legacy_journal.exists()
    else:
        with pytest.raises(RegistryValidationError, match="legacy cleanup"):
            recover()
        assert paths.legacy_journal.read_bytes() == before_journal
        if conflict == "remaining-backup":
            assert (backup / "preserve.txt").read_text(encoding="utf-8") == "unfinished recovery"
    assert _tree_bytes(context.target_export_root) == before_target

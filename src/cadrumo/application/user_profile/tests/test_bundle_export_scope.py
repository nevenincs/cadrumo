"""Scoped export recovery touches only the caller's known profile journals."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from ....core.hashing import sha256_hex
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.user_profile.errors import ProfileExportError
from ..bundle_export import reconcile_prepared_exports
from ..bundle_export_contracts import (
    ProfileBundleExportPurpose,
    ProfileBundleExportTarget,
    ProfileBundleExportTransport,
)
from ..bundle_export_operation import (
    ProfileBundleExportJournalRepository,
    ProfileBundleExportOperation,
    ProfileBundleExportOperationStatus,
    derive_export_operation_id,
    profile_export_staged_path,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_WHEN = datetime(2026, 9, 27, tzinfo=UTC)


def _prepared(
    repository: ProfileBundleExportJournalRepository, root: Path, profile_id: str, label: str
) -> tuple[ProfileBundleExportOperation, Path]:
    destination = root / f"{label}.json"
    staged = profile_export_staged_path(destination, process_id=os.getpid(), nonce="a" * 8)
    staged.write_bytes(f"private bundle for {label}".encode())
    purpose = ProfileBundleExportPurpose.PORTABLE_TRANSFER
    target = ProfileBundleExportTarget(destination=destination)
    operation = ProfileBundleExportOperation(
        operation_id=derive_export_operation_id(
            profile_id=profile_id, target_identity=target.identity, purpose=purpose
        ),
        status=ProfileBundleExportOperationStatus.PREPARED,
        profile_id=profile_id,
        display_name=label,
        target_identity=target.identity,
        destination=str(destination),
        staged_path=str(staged),
        content_sha256=sha256_hex(staged.read_bytes()),
        purpose=purpose,
        transport=ProfileBundleExportTransport.CLEARTEXT_LOCAL,
        bundle_schema_version=1,
        data_categories=("profile",),
        started_at=_WHEN,
        updated_at=_WHEN,
        event_occurred_at=_WHEN,
    )
    repository.save(operation)
    return operation, staged


def test_scoped_reconciliation_cleans_only_own_orphan_and_discloses_only_own_operation(tmp_path: Path) -> None:
    own_id, foreign_id = str(uuid4()), str(uuid4())
    repository = ProfileBundleExportJournalRepository(storage_root=tmp_path)
    own, own_staged = _prepared(repository, tmp_path, own_id, "own")
    foreign, foreign_staged = _prepared(repository, tmp_path, foreign_id, "foreign")
    foreign_before = foreign_staged.read_bytes()

    with bundled_indexed_authority().operation() as authority:
        outcome = reconcile_prepared_exports(
            journal=repository,
            profile_decode_context=authority.profile_decode_context(),
            authorized_profile_id=own_id,
        )

    assert tuple(item.operation_id for item in outcome.reconciled) == (own.operation_id,)
    assert outcome.failures == ()
    assert not own_staged.exists()
    assert not repository.path_for(own.operation_id).exists()
    assert foreign_staged.read_bytes() == foreign_before
    assert repository.load(foreign.operation_id) == foreign
    assert foreign_id not in repr(outcome)
    assert foreign.operation_id not in repr(outcome)
    assert str(foreign_staged) not in repr(outcome)


def test_unknown_journal_ownership_refuses_scoped_recovery_without_identity_disclosure(tmp_path: Path) -> None:
    own_id = str(uuid4())
    repository = ProfileBundleExportJournalRepository(storage_root=tmp_path)
    own, own_staged = _prepared(repository, tmp_path, own_id, "own")
    unknown_id = "d" * 64
    unknown_path = repository.path_for(unknown_id)
    unknown_path.write_text("{invalid journal", encoding="utf-8")

    with bundled_indexed_authority().operation() as authority, pytest.raises(ProfileExportError) as caught:
        reconcile_prepared_exports(
            journal=repository,
            profile_decode_context=authority.profile_decode_context(),
            authorized_profile_id=own_id,
        )

    assert caught.value.context == {"reconciliation_available": False}
    disclosed = str(caught.value) + repr(caught.value.context)
    assert unknown_id not in disclosed
    assert str(unknown_path) not in disclosed
    assert unknown_path.is_file()
    assert own_staged.is_file()
    assert repository.load(own.operation_id) == own

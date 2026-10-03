"""Portable-export journals retain one execution-independent target path."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from cadrumo.adapters.persistence.profile.tests.profile_registration import register_cli_profile

from ....adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from ....application.user_profile.bundle_export import (
    export_profile_bundle,
    prepare_profile_export,
    reconcile_prepared_exports,
)
from ....application.user_profile.bundle_export_contracts import (
    ProfileBundleExportPurpose,
    ProfileBundleExportRequest,
    ProfileBundleExportTarget,
    ProfileBundleExportTransport,
)
from ....application.user_profile.bundle_export_operation import (
    ProfileBundleExportJournalError,
    ProfileBundleExportJournalRepository,
    ProfileBundleExportOperation,
    ProfileBundleExportOperationStatus,
    derive_export_operation_id,
    profile_export_staged_path,
)
from ....core.hashing import sha256_hex
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.user_profile.errors import ProfileExportError

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_WHEN = datetime(2026, 9, 27, tzinfo=UTC)


def _request(destination: Path) -> ProfileBundleExportRequest:
    return ProfileBundleExportRequest(
        destination=destination,
        purpose=ProfileBundleExportPurpose.PORTABLE_TRANSFER,
        transport=ProfileBundleExportTransport.CLEARTEXT_LOCAL,
    )


def _prepared_journal(
    repository: ProfileBundleExportJournalRepository, *, profile_id: str, destination: Path
) -> ProfileBundleExportOperation:
    target = ProfileBundleExportTarget(destination=destination)
    purpose = ProfileBundleExportPurpose.PORTABLE_TRANSFER
    operation = ProfileBundleExportOperation(
        operation_id=derive_export_operation_id(
            profile_id=profile_id, target_identity=target.identity, purpose=purpose
        ),
        status=ProfileBundleExportOperationStatus.PREPARED,
        profile_id=profile_id,
        display_name="Synthetic export subject",
        target_identity=target.identity,
        destination=str(destination),
        staged_path=str(profile_export_staged_path(destination, process_id=os.getpid(), nonce="a" * 8)),
        content_sha256=sha256_hex(b"synthetic bundle"),
        purpose=purpose,
        transport=ProfileBundleExportTransport.CLEARTEXT_LOCAL,
        bundle_schema_version=1,
        data_categories=("profile",),
        started_at=_WHEN,
        updated_at=_WHEN,
        event_occurred_at=_WHEN,
    )
    repository.save(operation)
    return operation


def test_prepared_export_recovers_at_original_absolute_path_after_cwd_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A later process directory cannot retarget a staged cleartext bundle."""
    first, later = tmp_path / "first", tmp_path / "later"
    first.mkdir()
    later.mkdir()
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = register_cli_profile(label="Anchored export", log_in=False)
        repository = ProfileBundleExportJournalRepository()
        monkeypatch.chdir(first)
        with bundled_indexed_authority().operation() as authority:
            decode = authority.profile_decode_context()
            prepared = prepare_profile_export(
                _request(Path("portable.bundle")),
                journal=repository,
                profile_decode_context=decode,
                authorized_profile_id=profile_id,
            )
            staged = prepared.staged_path
            assert prepared.operation.destination == str(first / "portable.bundle")
            assert staged.is_absolute() and staged.is_file()
            assert prepared.operation.target_identity == str(first / "portable.bundle")

            monkeypatch.chdir(later)
            recovered = reconcile_prepared_exports(
                journal=repository,
                profile_decode_context=decode,
                authorized_profile_id=profile_id,
            )
        assert tuple(item.operation_id for item in recovered.reconciled) == (prepared.operation.operation_id,)
        assert recovered.failures == ()
        assert not staged.exists()
        assert not repository.path_for(prepared.operation.operation_id).exists()
        assert not (later / "portable.bundle").exists()


def test_relative_export_request_publishes_to_anchored_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, later = tmp_path / "first", tmp_path / "later"
    first.mkdir()
    later.mkdir()
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = register_cli_profile(label="Anchored publication", log_in=False)
        monkeypatch.chdir(first)
        with bundled_indexed_authority().operation() as authority:
            result = export_profile_bundle(
                _request(Path("portable.bundle")),
                profile_decode_context=authority.profile_decode_context(),
                authorized_profile_id=profile_id,
            )
        monkeypatch.chdir(later)
        assert result.destination == first / "portable.bundle"
        assert result.destination.is_file()
        assert not (later / "portable.bundle").exists()


def test_legacy_relative_journal_is_retained_when_cwd_changes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Unsupported relative recovery never guesses where old cleartext lives."""
    first, later = tmp_path / "first", tmp_path / "later"
    first.mkdir()
    later.mkdir()
    repository = ProfileBundleExportJournalRepository(storage_root=tmp_path)
    profile_id = str(uuid4())
    monkeypatch.chdir(first)
    operation = _prepared_journal(repository, profile_id=profile_id, destination=Path("legacy.bundle"))
    staged = first / operation.staged_path
    staged.write_bytes(b"synthetic bundle")
    before = repository.path_for(operation.operation_id).read_bytes()

    monkeypatch.chdir(later)
    with bundled_indexed_authority().operation() as authority:
        recovered = reconcile_prepared_exports(
            journal=repository,
            profile_decode_context=authority.profile_decode_context(),
            authorized_profile_id=profile_id,
        )
    assert recovered.reconciled == ()
    assert len(recovered.failures) == 1
    assert recovered.failures[0].journal_id == operation.operation_id
    assert repository.path_for(operation.operation_id).read_bytes() == before
    assert staged.read_bytes() == b"synthetic bundle"
    assert not (later / operation.staged_path).exists()


def test_unresolved_same_identity_cannot_replace_the_only_staged_journal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = tmp_path / "first"
    first.mkdir()
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = register_cli_profile(label="Retained export", log_in=False)
        repository = ProfileBundleExportJournalRepository()
        monkeypatch.chdir(first)
        operation = _prepared_journal(repository, profile_id=profile_id, destination=Path("legacy.bundle"))
        staged = first / operation.staged_path
        staged.write_bytes(b"synthetic bundle")
        journal_path = repository.path_for(operation.operation_id)
        before = journal_path.read_bytes()

        with bundled_indexed_authority().operation() as authority, pytest.raises(ProfileExportError) as refused:
            export_profile_bundle(
                _request(first / "legacy.bundle"),
                profile_decode_context=authority.profile_decode_context(),
                authorized_profile_id=profile_id,
            )
        assert refused.value.context == {"journal_present": True, "destination_published": False}
        assert journal_path.read_bytes() == before
        assert staged.read_bytes() == b"synthetic bundle"
        assert not (first / "legacy.bundle").exists()
        assert tuple(first.glob("legacy.bundle.*.export-tmp")) == (staged,)


def test_exclusive_create_preserves_malformed_same_identity_journal(tmp_path: Path) -> None:
    repository = ProfileBundleExportJournalRepository(storage_root=tmp_path)
    operation = _prepared_journal(
        repository,
        profile_id=str(uuid4()),
        destination=tmp_path / "portable.bundle",
    )
    journal_path = repository.path_for(operation.operation_id)
    journal_path.write_bytes(b"{")

    with pytest.raises(ProfileBundleExportJournalError) as refused:
        repository.create(operation)
    assert refused.value.context == {"journal_present": True}
    assert journal_path.read_bytes() == b"{"


def test_missing_parent_retains_journal_until_target_lock_is_available(tmp_path: Path) -> None:
    """The missing-parent observation cannot authorize stale-scan deletion."""
    repository = ProfileBundleExportJournalRepository(storage_root=tmp_path)
    profile_id = str(uuid4())
    destination = tmp_path / "unavailable" / "portable.bundle"
    operation = _prepared_journal(repository, profile_id=profile_id, destination=destination)
    before = repository.path_for(operation.operation_id).read_bytes()

    with bundled_indexed_authority().operation() as authority:
        recovered = reconcile_prepared_exports(
            journal=repository,
            profile_decode_context=authority.profile_decode_context(),
            authorized_profile_id=profile_id,
        )
    assert recovered.reconciled == ()
    assert len(recovered.failures) == 1
    assert recovered.failures[0].journal_id == operation.operation_id
    assert repository.path_for(operation.operation_id).read_bytes() == before
    assert not destination.parent.exists()

"""Real-behavior tests for durable all-profile configuration reset."""

from __future__ import annotations

import shutil
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import SecretStr

from ...adapters.persistence.storage.custody.acceleration_receipt import profile_session_path
from ...core.bucket_pointer import read_pointer
from ...core.directory_scan import iter_directory, scan_directory
from ...tests.profile_capsule import open_test_profile_session

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_A_ID = "11111111-1111-4111-8111-111111111111"
_PROFILE_B_ID = "22222222-2222-4222-8222-222222222222"
_PROFILE_C_ID = "33333333-3333-4333-8333-333333333333"
_DANGLING_ID = "44444444-4444-4444-8444-444444444444"
_OVERRIDE_REASON = "Court order requiring erasure before the statutory retention date."


@contextmanager
def _isolated_reset_root(tmp_path: Path) -> Generator[Path]:
    from ...tests.secure_sql import isolated_profile_storage_root

    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        yield root


def _create_profile(
    profile_id: str,
    *,
    label: str,
    tax_id: str,
) -> None:
    """Seed one profile in the state the production registration door leaves.

    The empty filing catalogue snapshot this used to record here is now written
    by the shared seeding door itself, through the same recorder registration
    calls, so every suite that seeds a profile gets the fact rather than only
    the ones that remembered to restore it.

    The empty LEGAL case snapshot is still recorded here rather than at that
    door. Registration DOES now record one -- ``try_record_legal_hold_snapshot``
    runs on the production registration path -- so the older claim that no
    production door writes it is no longer true. What remains true, and is why
    this stays visible, is that the recorded value is always the empty tuple:
    nothing in the product ever records an OPEN case, so a legal hold cannot
    become true outside a test. Seeding it here keeps that gap where a reader
    of this suite meets it, instead of behind a door that makes every seeded
    profile look like a real one.
    """
    from ...tests.user_profile import register_minimal_profile
    from ..evidence.profile_legal_hold import LegalHoldCaseAuthority

    with open_test_profile_session(profile_id):
        register_minimal_profile(
            profile_id=profile_id,
            display_name=label,
            overrides={"identity.tax_id": tax_id, "identity.name": label},
        )
    LegalHoldCaseAuthority().record_open_case_snapshot(
        profile_id=UUID(profile_id),
        open_case_ids=(),
        observed_at=datetime.now(UTC),
    )


def _delete_profile_through_custody(profile_id: str, *, root: Path) -> None:
    """Delete one profile through the sanctioned custody transaction.

    Replaces the retired ``delete_profile_with_lifecycle_span``, whose whole
    span now lives behind the custody transaction owner: prepare the journal,
    take the confirmation bound to it, execute. The owner facts are recorded
    first because the preflight consumes their projections and refuses outright
    when they are absent -- that refusal is the hold guard working, not setup
    noise.
    """
    from ..evidence.profile_legal_hold import LegalHoldCaseAuthority
    from ..filing.retention import FilingRetentionAuthority
    from ..user_profile.lifecycle import ProfileCapsuleLifecycle

    observed_at = datetime.now(UTC)
    identity = UUID(profile_id)
    LegalHoldCaseAuthority(root=root).record_open_case_snapshot(
        profile_id=identity,
        open_case_ids=(),
        observed_at=observed_at,
    )
    FilingRetentionAuthority(root=root).record_filing_catalogue(
        profile_id=identity,
        records=(),
        observed_at=observed_at,
    )
    lifecycle = ProfileCapsuleLifecycle(root=root)
    journal = lifecycle.prepare_delete(profile_id=identity)
    lifecycle.delete(lifecycle.confirm_delete(journal))


def _remove_bucket_directory_out_of_band(profile_id: str, *, root: Path) -> None:
    """Remove one bucket directory WITHOUT going through custody, on purpose.

    The guard under test is that a reset detects its target changing beneath
    it, so the change must not be a sanctioned deletion -- a custody delete is
    an authorised transaction and would prove nothing about detection. It could
    not be used here in any case: this profile carries a filing, so the
    retention hold refuses the transaction outright.

    Replaces the retired ``remove_profile_bucket_directory``. No supported path
    produces this state; forging it is the only way to exercise the detector.
    """
    from ...adapters.persistence.storage.sql.engine import dispose_engines_for_bucket
    from ...adapters.persistence.storage.storage_path_definitions import BUCKETS_DIRNAME

    # An out-of-band remover is some OTHER actor, which would not be holding
    # this process's SQLite handle on the bucket. Releasing it first is what
    # makes the forgery faithful; without it the removal fails on Windows for a
    # reason the scenario under test does not contain.
    dispose_engines_for_bucket(profile_id)
    shutil.rmtree(root / BUCKETS_DIRNAME / profile_id)


def _capsule_dir_for(root: Path, profile_id: str) -> Path:
    from ...adapters.persistence.storage.storage_path_definitions import BUCKETS_DIRNAME

    return root / BUCKETS_DIRNAME / profile_id


def _write_active_pointer(root: Path, bucket_id: str) -> None:
    from ...core.bucket_pointer import BucketPointer, write_pointer

    write_pointer(
        root,
        BucketPointer.selected(bucket_id=bucket_id, transition_revision=0),
    )


def _persist_filing(
    bucket_id: str,
    *,
    filing_year: int,
    seed: str,
) -> None:
    """Save one filing record and refresh the snapshot the filing path refreshes.

    The catalogue is written directly rather than through ``persist_filed_revision``,
    so the retention snapshot the filing path refreshes immediately after its
    catalogue save has to be refreshed here too, through the same recorder. The
    snapshot is the ONLY thing a deletion preflight can read: the filing records
    themselves sit in the bucket's encrypted store, under a key a reset holding
    locks on unopened targets does not have.
    """
    from ...adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
    from ...core.period import Period
    from ...domain.modelos.codes import ModeloCode
    from ...domain.modelos.filing_record import ModeloRecord, ModeloRecordCatalogue, derive_filing_record_id
    from ..filing.retention import try_record_filing_retention_snapshot

    work_unit_id = (seed * 64)[:64]
    revision_id = ((chr(ord(seed) + 1)) * 64)[:64]
    record_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        filed_by="aeat.cli.modelo.file",
    )
    record = ModeloRecord(
        filing_record_id=record_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        bucket_id=bucket_id,
        modelo=ModeloCode("303"),
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, "2T"),
        filed_at=datetime(filing_year, 7, 1, tzinfo=UTC),
        filed_by="aeat.cli.modelo.file",
    )
    with open_test_profile_session(bucket_id):
        repository = ModeloRecordCatalogueRepository(bucket_id=bucket_id)
        catalogue = repository.load()
        saved = ModeloRecordCatalogue(
            records={**catalogue.records, record_id: record},
        )
        repository.save(saved)
    assert try_record_filing_retention_snapshot(
        bucket_id=bucket_id,
        records=tuple(saved.records.values()),
        observed_at=datetime.now(UTC),
    )


def _fingerprint(bucket_id: str) -> str:
    from ..bucket_maintenance.contracts import AssessBucketDeletionCommand
    from ..bucket_maintenance.service import BucketMaintenanceService

    assessment = BucketMaintenanceService().assess_deletion(
        AssessBucketDeletionCommand(bucket_id=bucket_id),
    )
    assert assessment.fingerprint is not None
    return assessment.fingerprint.digest


def test_start_and_resume_require_explicit_confirmation(tmp_path: Path) -> None:
    from ..config_reset import (
        ConfigResetConfirmationRequiredError,
        resume_config_reset,
        start_config_reset,
    )

    with _isolated_reset_root(tmp_path):
        with pytest.raises(ConfigResetConfirmationRequiredError):
            start_config_reset(confirmed=False)
        with pytest.raises(ConfigResetConfirmationRequiredError):
            resume_config_reset("a" * 64, confirmed=False)


def test_start_discovers_live_and_dangling_targets_then_completes(
    tmp_path: Path,
) -> None:
    """Discovery covers a live capsule and a dangling pointer, and erases both.

    A profile already deleted through custody is deliberately NOT among them.
    Discovery lists committed capsules, and a completed custody deletion leaves
    none -- it removes the tombstone as its final step. This case once asserted
    such a profile was still discovered, which was true of the deletion
    primitive it originally used and stopped being true when it was re-pointed
    onto the custody transaction; the expectations were not carried across.

    The profile deleted here therefore stays in the fixture as the thing that
    must NOT reappear, and the acquisition lock moved to a live target, where
    clearing it is a contract the reset actually holds.
    """
    from ...adapters.persistence.storage.bucket.directory_layout import bucket_paths
    from ...core.auth_provider import AuthProviderKind
    from ...core.bucket_pointer import pointer_path
    from ...core.config import load_settings
    from ...core.storage_taxonomy import StorageCategory
    from ...core.storage_taxonomy_locations import storage_location
    from .._config_reset_models import (
        ConfigResetAuthClearanceMode,
        ConfigResetOperationStatus,
        ConfigResetTargetPhase,
    )
    from .._config_reset_repository import ConfigResetJournalRepository
    from ..auth.acquisition_lock import acquire_auth_acquisition_lock, auth_acquisition_lock_path
    from ..auth.certificate_source_operations import (
        register_operator_certificate_source,
        set_operator_certificate_source_secret,
    )
    from ..config_reset import start_config_reset

    with _isolated_reset_root(tmp_path) as root:
        root.mkdir(parents=True, exist_ok=True)
        cold_default_database = root / storage_location(StorageCategory.ROOT_FALLBACK_DATABASE).subpath
        cold_default_bytes = b"cold-default-database-is-not-a-profile-bucket"
        cold_default_database.write_bytes(cold_default_bytes)
        _create_profile(_PROFILE_A_ID, label="Alpha operator", tax_id="00000000T")
        _create_profile(_PROFILE_B_ID, label="Beta operator", tax_id="00000001R")
        _delete_profile_through_custody(_PROFILE_B_ID, root=root)

        certificate_path = tmp_path / "operator.p12"
        certificate_path.write_bytes(b"test certificate")
        _write_active_pointer(root, _PROFILE_A_ID)
        # Registering a certificate source and its secret needs the profile
        # OPEN: the source record is a row inside the capsule and the secret's
        # lookup digest is derived from the bucket's key. Doing it cold refuses,
        # which is the same wall the reset meets from the other side.
        with open_test_profile_session(_PROFILE_A_ID):
            register_operator_certificate_source(
                name="personal",
                certificate_path=certificate_path,
            )
            set_operator_certificate_source_secret(
                name="personal",
                secret=SecretStr("test-passphrase"),
            )

        settings = load_settings()
        secret_blob_root = settings.cadrumo_blob_store_dir
        assert any(path.is_file() for path in iter_directory(secret_blob_root, recursive=True))
        # The lock is acquired for whichever profile the pointer names, so the
        # pointer picks the subject here; the reset's own pointer is written
        # below.
        _write_active_pointer(root, _PROFILE_A_ID)
        lock_path = auth_acquisition_lock_path(
            settings,
            AuthProviderKind.CLAVE_PERMANENTE,
            bucket_id=_PROFILE_A_ID,
        )
        with acquire_auth_acquisition_lock(
            settings,
            AuthProviderKind.CLAVE_PERMANENTE,
            ttl_seconds=60,
            operation="test-config-reset",
        ):
            assert lock_path.is_file()
            _write_active_pointer(root, _DANGLING_ID)
            operation = start_config_reset(confirmed=True)
            assert lock_path.exists() is False

        assert operation.status is ConfigResetOperationStatus.COMPLETE
        assert tuple(target.bucket_id for target in operation.targets) == (
            _PROFILE_A_ID,
            _DANGLING_ID,
        )
        assert all(target.bucket_id != "cadrumo.db" for target in operation.targets)
        assert operation.pointer_snapshot.record.bucket_id == _DANGLING_ID
        assert operation.pointer_snapshot.record.transition_revision == 0
        assert operation.summary is not None
        assert operation.summary.target_count == 2
        assert operation.summary.deleted_count == 1
        assert operation.summary.already_absent_count == 1
        for target in operation.targets:
            assert target.phase is ConfigResetTargetPhase.DELETED
            assert target.completed_at is not None
            if target.exists_at_snapshot:
                assert target.deletion_marker is not None
                assert target.fingerprint is not None
                assert target.deletion_marker.operation_id == operation.operation_id
                assert target.deletion_marker.fingerprint == target.fingerprint.digest
            else:
                assert target.deletion_marker is None

        assert pointer_path(root).is_file()
        assert read_pointer(root).bucket_id is None
        assert bucket_paths(root, _PROFILE_A_ID).bucket_dir.exists() is False
        assert bucket_paths(root, _PROFILE_B_ID).bucket_dir.exists() is False
        assert bucket_paths(root, _DANGLING_ID).bucket_dir.exists() is False
        assert cold_default_database.read_bytes() == cold_default_bytes
        # Every target here was LOCKED, so the certificate secret held outside
        # the capsule could be neither addressed nor removed, and it outlives
        # the erase. The reset records that it did rather than reporting a
        # clean sweep; the ciphertext is unreadable, every wrapping of its key
        # having gone with the capsule.
        assert any(path.is_file() for path in scan_directory(secret_blob_root, recursive=True))
        # The claim that the residue is unreadable rests on this: the capsule
        # carried the password and recovery envelopes and the key sentinel, and
        # the session receipt outside it is the only other wrapping of the same
        # key. Both are gone, so nothing that could unwrap the leftover remains.
        assert profile_session_path(storage_root=root, profile_id=UUID(_PROFILE_A_ID)).exists() is False
        for target in operation.targets:
            clearance = target.auth_clearance
            assert clearance is not None
            assert clearance.mode is ConfigResetAuthClearanceMode.CAPSULE_DESTRUCTION
            assert clearance.removed_out_of_bucket_secret_records is None
        cleared_locks = {
            target.bucket_id: target.auth_clearance.cleared_lock_provider_ids
            for target in operation.targets
            if target.auth_clearance is not None
        }
        assert cleared_locks[_PROFILE_A_ID] == (AuthProviderKind.CLAVE_PERMANENTE.value,)
        assert cleared_locks[_DANGLING_ID] == ()
        assert ConfigResetJournalRepository().load(operation.operation_id) == operation


def test_a_locked_dangling_target_has_its_key_free_lock_cleared_and_says_what_it_could_not_do(
    tmp_path: Path,
) -> None:
    """The auth phase's whole contract, on a target with no capsule to erase.

    Deliberately built on a dangling pointer target: it isolates the auth phase
    from the capsule-deletion path, so what is asserted here is the ruling and
    nothing downstream of it. The acquisition lock is a plaintext file outside
    any capsule, so the reset can and must clear it without a key, while the
    revocation the reset cannot reach is recorded as unreached rather than
    reported as done.
    """
    from ...core.auth_provider import AuthProviderKind
    from ...core.config import load_settings
    from .._config_reset_models import (
        ConfigResetAuthClearanceMode,
        ConfigResetOperationStatus,
        ConfigResetTargetPhase,
    )
    from ..auth.acquisition_lock import acquire_auth_acquisition_lock, auth_acquisition_lock_path
    from ..config_reset import start_config_reset

    with _isolated_reset_root(tmp_path) as root:
        root.mkdir(parents=True, exist_ok=True)
        _write_active_pointer(root, _DANGLING_ID)
        settings = load_settings()
        lock_path = auth_acquisition_lock_path(
            settings,
            AuthProviderKind.CLAVE_PERMANENTE,
            bucket_id=_DANGLING_ID,
        )
        with acquire_auth_acquisition_lock(
            settings,
            AuthProviderKind.CLAVE_PERMANENTE,
            ttl_seconds=60,
            operation="test-dangling-target-auth-phase",
        ):
            assert lock_path.is_file()
            operation = start_config_reset(confirmed=True)

        assert operation.status is ConfigResetOperationStatus.COMPLETE
        target = operation.targets[0]
        assert target.bucket_id == _DANGLING_ID
        assert target.exists_at_snapshot is False
        assert target.phase is ConfigResetTargetPhase.DELETED
        clearance = target.auth_clearance
        assert clearance is not None
        assert clearance.mode is ConfigResetAuthClearanceMode.CAPSULE_DESTRUCTION
        assert clearance.removed_out_of_bucket_secret_records is None
        assert clearance.cleared_lock_provider_ids == (AuthProviderKind.CLAVE_PERMANENTE.value,)
        assert lock_path.exists() is False


def test_a_profile_from_the_seeding_door_alone_is_deletion_assessable(
    tmp_path: Path,
) -> None:
    """Seeding a profile records the same empty filing snapshot registration does.

    The distinction under test is between an EMPTY recorded snapshot and an
    ABSENT one, which are not the same fact: absence means nobody asked the
    filing owner and refuses, emptiness means it answered and clears. Asserting
    the assessment answers is therefore the whole point -- a seeded profile
    whose snapshot were merely defaulted to nothing-retained would pass this
    while destroying the distinction, so the paired assertion is that a
    profile whose recorded snapshot is REMOVED refuses again.
    """
    from ...domain.buckets.errors import BucketDeleteRefusedError
    from ..bucket_maintenance.contracts import AssessBucketDeletionCommand
    from ..bucket_maintenance.service import BucketMaintenanceService
    from ..filing.retention import FilingRetentionAuthority

    with _isolated_reset_root(tmp_path) as root:
        from ...tests.user_profile import register_minimal_profile

        with open_test_profile_session(_PROFILE_A_ID):
            register_minimal_profile(profile_id=_PROFILE_A_ID, display_name="Alpha operator")

        service = BucketMaintenanceService()
        assessment = service.assess_deletion(AssessBucketDeletionCommand(bucket_id=_PROFILE_A_ID))
        assert assessment.exists is True
        assert assessment.retention is not None
        assert assessment.retention.blocks_erase is False
        assert assessment.retention.retained == ()

        FilingRetentionAuthority(root=root).path(UUID(_PROFILE_A_ID)).unlink()
        with pytest.raises(BucketDeleteRefusedError):
            service.assess_deletion(AssessBucketDeletionCommand(bucket_id=_PROFILE_A_ID))


def test_retention_preflight_pauses_before_auth_pointer_or_bucket_mutation(
    tmp_path: Path,
) -> None:
    from ...core.bucket_pointer import pointer_path
    from .._config_reset_models import (
        ConfigResetOperationStatus,
        ConfigResetPauseReason,
        ConfigResetTargetPhase,
    )
    from ..config_reset import (
        ConfigResetAlreadyRunningError,
        resume_config_reset,
        start_config_reset,
    )

    with _isolated_reset_root(tmp_path) as root:
        _create_profile(_PROFILE_A_ID, label="Alpha operator", tax_id="00000000T")
        _create_profile(_PROFILE_B_ID, label="Beta operator", tax_id="00000001R")
        _persist_filing(_PROFILE_B_ID, filing_year=2025, seed="a")
        _write_active_pointer(root, _PROFILE_A_ID)
        pointer_before = pointer_path(root).read_bytes()
        fingerprints_before = {
            _PROFILE_A_ID: _fingerprint(_PROFILE_A_ID),
            _PROFILE_B_ID: _fingerprint(_PROFILE_B_ID),
        }

        operation = start_config_reset(confirmed=True)

        assert operation.status is ConfigResetOperationStatus.PAUSED
        assert operation.pause_reason is ConfigResetPauseReason.RETENTION_UNRESOLVED
        assert operation.paused_target_ids == (_PROFILE_B_ID,)
        assert pointer_path(root).read_bytes() == pointer_before
        assert {
            _PROFILE_A_ID: _fingerprint(_PROFILE_A_ID),
            _PROFILE_B_ID: _fingerprint(_PROFILE_B_ID),
        } == fingerprints_before
        phases = {target.bucket_id: target.phase for target in operation.targets}
        assert phases == {
            _PROFILE_A_ID: ConfigResetTargetPhase.RETENTION_APPROVED,
            _PROFILE_B_ID: ConfigResetTargetPhase.SNAPSHOTTED,
        }
        assert all(target.retention is not None for target in operation.targets)

        with pytest.raises(ConfigResetAlreadyRunningError) as raised:
            start_config_reset(confirmed=True)
        assert raised.value.context == {"operation_id": operation.operation_id}

        completed = resume_config_reset(
            operation.operation_id,
            confirmed=True,
            acknowledge_retention_override=True,
            retention_override_reason=_OVERRIDE_REASON,
        )
        assert completed.status is ConfigResetOperationStatus.COMPLETE
        assert completed.summary is not None
        assert completed.summary.retention_override_count == 1


def test_resume_converges_after_a_target_is_removed_out_of_band(
    tmp_path: Path,
) -> None:
    from .._config_reset_models import (
        ConfigResetOperationStatus,
        ConfigResetPauseReason,
        ConfigResetTargetPhase,
    )
    from ..config_reset import resume_config_reset, start_config_reset

    with _isolated_reset_root(tmp_path) as root:
        _create_profile(_PROFILE_A_ID, label="Alpha operator", tax_id="00000000T")
        _create_profile(_PROFILE_B_ID, label="Beta operator", tax_id="00000001R")
        _persist_filing(_PROFILE_B_ID, filing_year=2025, seed="a")
        _write_active_pointer(root, _PROFILE_A_ID)

        paused = start_config_reset(confirmed=True)
        assert paused.status is ConfigResetOperationStatus.PAUSED
        assert paused.pause_reason is ConfigResetPauseReason.RETENTION_UNRESOLVED

        _remove_bucket_directory_out_of_band(_PROFILE_B_ID, root=root)

        changed = resume_config_reset(paused.operation_id, confirmed=True)
        assert changed.status is ConfigResetOperationStatus.PAUSED
        assert changed.pause_reason is ConfigResetPauseReason.TARGET_STATE_CHANGED
        assert changed.paused_target_ids == (_PROFILE_B_ID,)
        vanished = next(target for target in changed.targets if target.bucket_id == _PROFILE_B_ID)
        assert vanished.exists_at_snapshot is False
        assert vanished.fingerprint is None

        completed = resume_config_reset(changed.operation_id, confirmed=True)
        assert completed.status is ConfigResetOperationStatus.COMPLETE
        assert completed.summary is not None
        assert completed.summary.deleted_count == 1
        assert completed.summary.already_absent_count == 1
        phases = {target.bucket_id: target.phase for target in completed.targets}
        assert phases == {
            _PROFILE_A_ID: ConfigResetTargetPhase.DELETED,
            _PROFILE_B_ID: ConfigResetTargetPhase.DELETED,
        }


def test_status_is_a_read_only_journal_view(tmp_path: Path) -> None:
    from .._config_reset_repository import ConfigResetJournalRepository
    from ..config_reset import config_reset_status, start_config_reset

    with _isolated_reset_root(tmp_path):
        _create_profile(_PROFILE_A_ID, label="Alpha operator", tax_id="00000000T")
        _persist_filing(_PROFILE_A_ID, filing_year=2025, seed="c")
        operation = start_config_reset(confirmed=True)
        repository = ConfigResetJournalRepository()
        journal_path = repository.path_for(operation.operation_id)
        before = journal_path.read_bytes()

        assert config_reset_status(operation.operation_id) == operation
        assert config_reset_status() == operation
        assert journal_path.read_bytes() == before


def test_resume_pauses_once_when_target_content_changed_then_accepts_new_snapshot(
    tmp_path: Path,
) -> None:
    from .._config_reset_models import ConfigResetOperationStatus, ConfigResetPauseReason
    from ..config_reset import resume_config_reset, start_config_reset

    with _isolated_reset_root(tmp_path) as root:
        _create_profile(_PROFILE_A_ID, label="Alpha operator", tax_id="00000000T")
        _persist_filing(_PROFILE_A_ID, filing_year=2025, seed="e")
        operation = start_config_reset(confirmed=True)
        original_fingerprint = operation.targets[0].fingerprint
        assert original_fingerprint is not None

        # A filing does NOT move the capsule digest: it lands in the database,
        # which the inventory covers by path only, and in a retention snapshot
        # that lives outside the capsule. Planting a file inside the capsule is
        # what actually changes the target this reset snapshotted.
        (_capsule_dir_for(root, _PROFILE_A_ID) / "planted.v1.json").write_bytes(b'{"planted": true}')
        changed = resume_config_reset(
            operation.operation_id,
            confirmed=True,
            acknowledge_retention_override=True,
            retention_override_reason=_OVERRIDE_REASON,
        )

        assert changed.status is ConfigResetOperationStatus.PAUSED
        assert changed.pause_reason is ConfigResetPauseReason.TARGET_STATE_CHANGED
        assert changed.paused_target_ids == (_PROFILE_A_ID,)
        assert changed.targets[0].fingerprint is not None
        assert changed.targets[0].fingerprint.digest != original_fingerprint.digest

        completed = resume_config_reset(
            operation.operation_id,
            confirmed=True,
            acknowledge_retention_override=True,
            retention_override_reason=_OVERRIDE_REASON,
        )
        assert completed.status is ConfigResetOperationStatus.COMPLETE


def test_resume_adds_changed_pointer_target_under_the_same_operation(
    tmp_path: Path,
) -> None:
    from ...adapters.persistence.storage.bucket.directory_layout import bucket_paths
    from .._config_reset_models import ConfigResetOperationStatus, ConfigResetPauseReason
    from ..config_reset import resume_config_reset, start_config_reset

    with _isolated_reset_root(tmp_path) as root:
        _create_profile(_PROFILE_A_ID, label="Alpha operator", tax_id="00000000T")
        _persist_filing(_PROFILE_A_ID, filing_year=2025, seed="3")
        operation = start_config_reset(confirmed=True)

        _create_profile(_PROFILE_C_ID, label="Gamma operator", tax_id="00000002W")
        changed = resume_config_reset(
            operation.operation_id,
            confirmed=True,
            acknowledge_retention_override=True,
            retention_override_reason=_OVERRIDE_REASON,
        )

        assert changed.status is ConfigResetOperationStatus.PAUSED
        assert changed.pause_reason is ConfigResetPauseReason.POINTER_CHANGED
        assert changed.paused_target_ids == (_PROFILE_C_ID,)
        assert tuple(target.bucket_id for target in changed.targets) == (
            _PROFILE_A_ID,
            _PROFILE_C_ID,
        )
        assert bucket_paths(root, _PROFILE_A_ID).bucket_dir.is_dir()
        assert bucket_paths(root, _PROFILE_C_ID).bucket_dir.is_dir()

        completed = resume_config_reset(
            operation.operation_id,
            confirmed=True,
            acknowledge_retention_override=True,
            retention_override_reason=_OVERRIDE_REASON,
        )
        assert completed.status is ConfigResetOperationStatus.COMPLETE
        assert tuple(target.bucket_id for target in completed.targets) == (
            _PROFILE_A_ID,
            _PROFILE_C_ID,
        )


def test_resume_detects_an_a_to_b_to_a_pointer_coordinate_change(tmp_path: Path) -> None:
    """ABA selection equality cannot hide a changed reset preflight witness."""
    from .._config_reset_models import ConfigResetPauseReason
    from ..config_reset import resume_config_reset, start_config_reset
    from ..user_profile.profile_pointer import active_profile_pointer_transaction

    with _isolated_reset_root(tmp_path) as root:
        _create_profile(_PROFILE_A_ID, label="Alpha operator", tax_id="00000000T")
        _persist_filing(_PROFILE_A_ID, filing_year=2025, seed="c")
        operation = start_config_reset(confirmed=True)
        before = operation.pointer_snapshot.record
        assert before.bucket_id == _PROFILE_A_ID

        with active_profile_pointer_transaction(root) as transaction:
            intermediate = transaction.select(_PROFILE_C_ID)
            returned = transaction.select(_PROFILE_A_ID)
        assert intermediate.transition_revision == before.transition_revision + 1
        assert returned.transition_revision == before.transition_revision + 2
        assert returned.bucket_id == before.bucket_id
        assert returned != before

        resumed = resume_config_reset(
            operation.operation_id,
            confirmed=True,
            acknowledge_retention_override=True,
            retention_override_reason=_OVERRIDE_REASON,
        )
        assert resumed.pause_reason is ConfigResetPauseReason.POINTER_CHANGED
        assert resumed.pointer_snapshot.record == returned

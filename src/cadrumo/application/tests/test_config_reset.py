"""Real-behavior tests for durable all-profile configuration reset."""

from __future__ import annotations

from collections.abc import Generator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import SecretStr

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


def _profile_facts(
    *,
    tax_id: str,
    name: str,
    overrides: Mapping[str, object] | None = None,
):
    from ...domain.user_profile import UserProfileFact

    values: dict[str, object] = {
        "identity.tax_id": tax_id,
        "identity.name": name,
        "tax_residence.ccaa": "madrid",
        "tax_residence.jurisdiction_scope": "common_regime",
        "iva.regime": "GENERAL",
        "provenance.source": "manual_cli",
    }
    if overrides:
        values.update(overrides)
    return tuple(UserProfileFact.model_validate({"path": path, "value": value}) for path, value in values.items())


def _create_profile(
    profile_id: str,
    *,
    label: str,
    tax_id: str,
) -> None:
    from ..user_profile import profile_create_storage_span, register_active_profile
    from ..wizard import WIZARD_FLOWS
    from ..workflow import workflow_state_repository

    assert WIZARD_FLOWS
    with profile_create_storage_span(profile_id):
        workflow_state_repository().update(
            lambda current: register_active_profile(
                current,
                profile_id=profile_id,
                display_name=label,
                facts=_profile_facts(tax_id=tax_id, name=label),
            ),
        )


def _write_active_pointer(root: Path, bucket_id: str) -> None:
    from ...core import BucketPointer, write_pointer

    write_pointer(
        root,
        BucketPointer(bucket_id=bucket_id, schema_version=1),
    )


def _persist_filing(
    bucket_id: str,
    *,
    filing_year: int,
    seed: str,
) -> None:
    from ...adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
    from ...core import Period
    from ...domain.modelos import (
        ModeloCode,
        ModeloRecord,
        ModeloRecordCatalogue,
        derive_filing_record_id,
    )
    from ..user_profile import profile_storage_session

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
    with profile_storage_session(bucket_id):
        repository = ModeloRecordCatalogueRepository(bucket_id=bucket_id)
        catalogue = repository.load()
        repository.save(
            ModeloRecordCatalogue(
                records={**catalogue.records, record_id: record},
            ),
        )


def _fingerprint(bucket_id: str) -> str:
    from ..bucket_maintenance import AssessBucketDeletionCommand, BucketMaintenanceService

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


def test_start_discovers_live_tombstoned_and_dangling_targets_then_completes(
    tmp_path: Path,
) -> None:
    from ...adapters.persistence.storage.bucket import bucket_paths
    from ...core import AuthProviderKind, pointer_path
    from ...core.config import load_settings
    from .._config_reset_models import ConfigResetOperationStatus, ConfigResetTargetPhase
    from .._config_reset_repository import ConfigResetJournalRepository
    from ..auth import (
        acquire_auth_acquisition_lock,
        auth_acquisition_lock_path,
        register_operator_certificate_source,
        set_operator_certificate_source_secret,
    )
    from ..config_reset import start_config_reset
    from ..user_profile import delete_profile_with_lifecycle_span

    with _isolated_reset_root(tmp_path) as root:
        root.mkdir(parents=True, exist_ok=True)
        cold_default_database = root / "cadrumo.db"
        cold_default_bytes = b"cold-default-database-is-not-a-profile-bucket"
        cold_default_database.write_bytes(cold_default_bytes)
        _create_profile(_PROFILE_A_ID, label="Alpha operator", tax_id="00000000T")
        _create_profile(_PROFILE_B_ID, label="Beta operator", tax_id="00000001R")
        delete_profile_with_lifecycle_span(_PROFILE_B_ID)

        certificate_path = tmp_path / "operator.p12"
        certificate_path.write_bytes(b"test certificate")
        _write_active_pointer(root, _PROFILE_A_ID)
        register_operator_certificate_source(
            name="personal",
            certificate_path=certificate_path,
        )
        set_operator_certificate_source_secret(
            name="personal",
            secret=SecretStr("test-passphrase"),
        )

        settings = load_settings()
        secret_blob_root = settings.cadrumo_blob_store_dir / "blobs"
        assert any(path.is_file() for path in secret_blob_root.rglob("*"))
        _write_active_pointer(root, _PROFILE_B_ID)
        lock_path = auth_acquisition_lock_path(
            settings,
            AuthProviderKind.CLAVE_PERMANENTE,
            bucket_id=_PROFILE_B_ID,
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
            _PROFILE_B_ID,
            _DANGLING_ID,
        )
        assert all(target.bucket_id != "cadrumo.db" for target in operation.targets)
        assert operation.pointer_snapshot.present is True
        assert operation.pointer_snapshot.bucket_id == _DANGLING_ID
        assert operation.pointer_snapshot.content_sha256 is not None
        assert operation.summary is not None
        assert operation.summary.target_count == 3
        assert operation.summary.deleted_count == 2
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

        assert pointer_path(root).exists() is False
        assert bucket_paths(root, _PROFILE_A_ID).bucket_dir.exists() is False
        assert bucket_paths(root, _PROFILE_B_ID).bucket_dir.exists() is False
        assert bucket_paths(root, _DANGLING_ID).bucket_dir.exists() is False
        assert cold_default_database.read_bytes() == cold_default_bytes
        assert tuple(path for path in secret_blob_root.rglob("*") if path.is_file()) == ()
        assert ConfigResetJournalRepository().load(operation.operation_id) == operation


def test_retention_preflight_pauses_before_auth_pointer_or_bucket_mutation(
    tmp_path: Path,
) -> None:
    from ...core import pointer_path
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
    from ..user_profile import remove_profile_bucket_directory

    with _isolated_reset_root(tmp_path) as root:
        _create_profile(_PROFILE_A_ID, label="Alpha operator", tax_id="00000000T")
        _create_profile(_PROFILE_B_ID, label="Beta operator", tax_id="00000001R")
        _persist_filing(_PROFILE_B_ID, filing_year=2025, seed="a")
        _write_active_pointer(root, _PROFILE_A_ID)

        paused = start_config_reset(confirmed=True)
        assert paused.status is ConfigResetOperationStatus.PAUSED
        assert paused.pause_reason is ConfigResetPauseReason.RETENTION_UNRESOLVED

        remove_profile_bucket_directory(_PROFILE_B_ID)

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

    with _isolated_reset_root(tmp_path):
        _create_profile(_PROFILE_A_ID, label="Alpha operator", tax_id="00000000T")
        _persist_filing(_PROFILE_A_ID, filing_year=2025, seed="e")
        operation = start_config_reset(confirmed=True)
        original_fingerprint = operation.targets[0].fingerprint
        assert original_fingerprint is not None

        _persist_filing(_PROFILE_A_ID, filing_year=2024, seed="1")
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
    from ...adapters.persistence.storage.bucket import bucket_paths
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

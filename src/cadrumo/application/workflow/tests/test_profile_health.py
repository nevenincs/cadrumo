"""Real-behavior tests for active-profile health and pointer repair."""

from __future__ import annotations

from pathlib import Path

import pytest

from ....adapters.persistence.storage import SecureObjectRepository, has_active_bucket_session
from ....adapters.persistence.storage.bucket import bucket_paths, manifest_path
from ....application.user_profile import UserProfileLifecycleRepository
from ....core import BucketPointer, pointer_path, read_pointer, write_pointer
from ....core.config import override_settings
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ....tests.secure_sql import isolated_runtime_profile
from ... import wizard as _wizard  # noqa: F401
from .._profile_health import (
    assess_active_profile_health,
    assess_active_profile_health_with_session,
    repair_active_profile_pointer,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "31313131-3131-4313-8313-313131313131"
_PROFILE_LABEL = "Operator"


_READY_PROFILE_FACTS: tuple[UserProfileFact, ...] = (
    UserProfileFact(path="identity.tax_id", value="00000000T"),
    UserProfileFact(path="identity.name", value="Test Operator"),
    UserProfileFact(path="tax_residence.ccaa", value="madrid"),
    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
    UserProfileFact(path="iva.regime", value="GENERAL"),
    UserProfileFact(path="provenance.source", value="manual_cli"),
    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
    UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
    UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
)


def _seed_ready_profile_record(bucket_id: str, repository: SecureObjectRepository) -> None:
    UserProfileLifecycleRepository(bucket_id=bucket_id, objects=repository).save(
        UserProfileRecord(
            profile_id=bucket_id,
            display_name=_PROFILE_LABEL,
            facts=_READY_PROFILE_FACTS,
        ),
    )


def test_active_profile_health_reports_missing_profile_record(tmp_path: Path) -> None:
    with isolated_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_BUCKET_ID,
        label=_PROFILE_LABEL,
    ) as profile:
        write_pointer(profile.storage_root, BucketPointer(bucket_id=_BUCKET_ID, schema_version=1))
        with override_settings(cadrumo_active_profile=None):
            health = assess_active_profile_health()

    assert health.active_profile == _BUCKET_ID
    assert health.source == "pointer"
    assert health.registered_bucket is True
    assert health.profile_record_present is False
    assert health.status == "missing_profile_record"
    assert health.repairable_by_clearing_pointer is True
    assert health.next_action == "aeat config repair profile --clear-active --yes"


def test_profile_repair_clears_only_degraded_pointer(tmp_path: Path) -> None:
    with isolated_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_BUCKET_ID,
        label=_PROFILE_LABEL,
    ) as profile:
        write_pointer(profile.storage_root, BucketPointer(bucket_id=_BUCKET_ID, schema_version=1))
        with override_settings(cadrumo_active_profile=None):
            dry_run = repair_active_profile_pointer(clear_active=True, confirmed=False)
            assert dry_run.dry_run is True
            assert dry_run.cleared_pointer is False
            assert read_pointer(profile.storage_root) is not None

            repaired = repair_active_profile_pointer(clear_active=True, confirmed=True)

        assert repaired.dry_run is False
        assert repaired.cleared_pointer is True
        assert repaired.after is not None
        assert repaired.after.status == "none"
        assert read_pointer(profile.storage_root) is None


def test_profile_repair_does_not_clear_healthy_pointer(tmp_path: Path) -> None:
    with isolated_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_BUCKET_ID,
        label=_PROFILE_LABEL,
    ) as profile:
        _seed_ready_profile_record(_BUCKET_ID, profile.repository)
        write_pointer(profile.storage_root, BucketPointer(bucket_id=_BUCKET_ID, schema_version=1))

        with override_settings(cadrumo_active_profile=None):
            health = assess_active_profile_health()
            repaired = repair_active_profile_pointer(clear_active=True, confirmed=True)

        assert health.status == "ready"
        assert health.source == "pointer"
        assert repaired.dry_run is True
        assert repaired.cleared_pointer is False
    assert read_pointer(profile.storage_root) is not None


def test_profile_health_opens_a_cold_session_for_a_sibling_process_profile(tmp_path: Path) -> None:
    """Read a durable profile after the creating process's bucket session has closed."""
    with isolated_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_BUCKET_ID,
        label=_PROFILE_LABEL,
    ) as profile:
        _seed_ready_profile_record(_BUCKET_ID, profile.repository)
        write_pointer(profile.storage_root, BucketPointer(bucket_id=_BUCKET_ID, schema_version=1))
        storage_root = profile.storage_root
        secret_store_backend = profile.settings.cadrumo_secret_store_backend
        secret_store_dir = profile.settings.cadrumo_secret_store_dir
        secret_passphrase = profile.settings.cadrumo_secret_passphrase

    assert has_active_bucket_session() is False
    with override_settings(
        cadrumo_local_storage_root=storage_root,
        cadrumo_active_profile=None,
        cadrumo_secret_store_backend=secret_store_backend,
        cadrumo_secret_store_dir=secret_store_dir,
        cadrumo_secret_passphrase=secret_passphrase,
    ):
        health = assess_active_profile_health_with_session()

    assert health.status == "ready"
    assert health.source == "pointer"
    assert health.profile_record_present is True
    assert health.repairable_by_clearing_pointer is False
    assert has_active_bucket_session() is False


def test_profile_repair_clears_pointer_sourced_unreadable_manifest(tmp_path: Path) -> None:
    """Clear a pointer-sourced unreadable manifest without rewriting or backfilling it."""
    with isolated_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_BUCKET_ID,
        label=_PROFILE_LABEL,
    ) as profile:
        write_pointer(profile.storage_root, BucketPointer(bucket_id=_BUCKET_ID, schema_version=1))
        target = manifest_path(bucket_paths(profile.storage_root, _BUCKET_ID))
        malformed_manifest = b"not valid toml = [\n"
        target.write_bytes(malformed_manifest)

        with override_settings(cadrumo_active_profile=None):
            before = assess_active_profile_health()
            repaired = repair_active_profile_pointer(clear_active=True, confirmed=True)

        assert before.status == "manifest_unreadable"
        assert before.source == "pointer"
        assert before.repairable_by_clearing_pointer is True
        assert repaired.before.status == "manifest_unreadable"
        assert repaired.before.repairable_by_clearing_pointer is True
        assert repaired.dry_run is False
        assert repaired.cleared_pointer is True
        assert repaired.after is not None
        assert repaired.after.status == "none"
        assert read_pointer(profile.storage_root) is None
        assert target.read_bytes() == malformed_manifest


def test_profile_repair_cold_noop_creates_no_lock_or_session(tmp_path: Path) -> None:
    """Keep a confirmed cold no-op dry-run and sessionless, with no pointer or lock sidecar."""
    storage_root = tmp_path / "cold-profile-health"
    target = pointer_path(storage_root)
    lock_sidecar = target.with_name(f"{target.name}.lock")

    with override_settings(cadrumo_local_storage_root=storage_root, cadrumo_active_profile=None):
        assert has_active_bucket_session() is False
        repaired = repair_active_profile_pointer(clear_active=True, confirmed=True)
        assert has_active_bucket_session() is False

    assert repaired.dry_run is True
    assert repaired.cleared_pointer is False
    assert repaired.before.status == "none"
    assert repaired.after is None
    assert target.exists() is False
    assert lock_sidecar.exists() is False
    assert storage_root.exists() is False


def test_manifest_without_status_is_not_backfilled_from_profile_record(tmp_path: Path) -> None:
    with isolated_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_BUCKET_ID,
        label=_PROFILE_LABEL,
    ) as profile:
        _seed_ready_profile_record(_BUCKET_ID, profile.repository)
        target = manifest_path(bucket_paths(profile.storage_root, _BUCKET_ID))
        legacy_text = "\n".join(
            line for line in target.read_text(encoding="utf-8").splitlines() if not line.startswith("status = ")
        )
        target.write_text(f"{legacy_text}\n", encoding="utf-8")

        broken = assess_active_profile_health()

        assert broken.status == "manifest_unreadable"
        assert broken.repairable_by_clearing_pointer is False
        assert broken.next_action == "unset CADRUMO_ACTIVE_PROFILE or switch to a readable profile"
        assert "status = " not in target.read_text(encoding="utf-8")

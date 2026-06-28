"""Real-behavior tests for active-profile health and pointer repair."""

from __future__ import annotations

from pathlib import Path

import pytest

from ....adapters.persistence.storage import SecureObjectRepository
from ....adapters.persistence.storage.bucket._layout import bucket_paths
from ....adapters.persistence.storage.bucket._manifest import BucketLifecycleStatus
from ....adapters.persistence.storage.bucket._manifest_io import manifest_path, read_manifest
from ....application.user_profile import UserProfileLifecycleRepository
from ....core import BucketPointer, read_pointer, write_pointer
from ....core.config import override_settings
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ....tests.secure_sql import isolated_runtime_profile
from ... import wizard as _wizard  # noqa: F401
from .._profile_health import (
    assess_active_profile_health,
    repair_active_profile_manifest_status,
    repair_active_profile_pointer,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


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
            display_name=bucket_id,
            facts=_READY_PROFILE_FACTS,
        ),
    )


def test_active_profile_health_reports_missing_profile_record(tmp_path: Path) -> None:
    with isolated_runtime_profile(
        tmp_path=tmp_path,
        bucket_id="operator",
        label="Operator",
    ) as profile:
        write_pointer(profile.storage_root, BucketPointer(bucket_id="operator", schema_version=1))
        with override_settings(aeat_active_profile=None):
            health = assess_active_profile_health()

    assert health.active_profile == "operator"
    assert health.source == "pointer"
    assert health.registered_bucket is True
    assert health.profile_record_present is False
    assert health.status == "missing_profile_record"
    assert health.repairable_by_clearing_pointer is True
    assert health.next_action == "aeat config repair profile --clear-active --yes"


def test_profile_repair_clears_only_degraded_pointer(tmp_path: Path) -> None:
    with isolated_runtime_profile(
        tmp_path=tmp_path,
        bucket_id="operator",
        label="Operator",
    ) as profile:
        write_pointer(profile.storage_root, BucketPointer(bucket_id="operator", schema_version=1))
        with override_settings(aeat_active_profile=None):
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
        bucket_id="operator",
        label="Operator",
    ) as profile:
        _seed_ready_profile_record("operator", profile.repository)
        write_pointer(profile.storage_root, BucketPointer(bucket_id="operator", schema_version=1))

        with override_settings(aeat_active_profile=None):
            health = assess_active_profile_health()
            repaired = repair_active_profile_pointer(clear_active=True, confirmed=True)

        assert health.status == "ready"
        assert health.source == "pointer"
        assert repaired.dry_run is True
        assert repaired.cleared_pointer is False
        assert read_pointer(profile.storage_root) is not None


def test_manifest_status_repair_backfills_from_profile_record(tmp_path: Path) -> None:
    with isolated_runtime_profile(
        tmp_path=tmp_path,
        bucket_id="operator",
        label="Operator",
    ) as profile:
        _seed_ready_profile_record("operator", profile.repository)
        target = manifest_path(bucket_paths(profile.storage_root, "operator"))
        legacy_text = "\n".join(
            line for line in target.read_text(encoding="utf-8").splitlines() if not line.startswith("status = ")
        )
        target.write_text(f"{legacy_text}\n", encoding="utf-8")

        broken = assess_active_profile_health()
        repaired = repair_active_profile_manifest_status(confirmed=True)

        assert broken.status == "manifest_unreadable"
        assert broken.next_action == "aeat config repair profile --repair-manifest-status --yes"
        assert repaired.dry_run is False
        assert repaired.repaired is True
        assert repaired.status == BucketLifecycleStatus.ACTIVE.value
        assert repaired.after is not None
        assert repaired.after.status == "ready"
        assert read_manifest(bucket_paths(profile.storage_root, "operator")).status is BucketLifecycleStatus.ACTIVE

"""Real-behavior tests for active-profile health and pointer repair."""

from __future__ import annotations

from pathlib import Path

import pytest

from ...adapters.persistence.storage import EphemeralMasterKeyProvider
from ...adapters.persistence.storage.sql.engine import dispose_engine
from ...application.user_profile._orchestration import _ensure_profile_bucket_manifest
from ...application.user_profile._testing import register_minimal_profile
from ...core.config import override_settings
from ._bucket_pointer import BucketPointer
from ._bucket_pointer_io import read_pointer, write_pointer
from ._persistence import workflow_state_repository
from ._profile_health import assess_active_profile_health, repair_active_profile_pointer

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def test_active_profile_health_reports_missing_profile_record(tmp_path: Path) -> None:
    db_path = tmp_path / "profile-health.db"
    dispose_engine()
    provider = EphemeralMasterKeyProvider()
    provider.__enter__()
    try:
        with override_settings(
            aeat_database_url=f"sqlite:///{db_path.as_posix()}",
            aeat_local_storage_root=tmp_path,
            aeat_active_profile=None,
        ):
            _ensure_profile_bucket_manifest("operator")
            write_pointer(tmp_path, BucketPointer(bucket_id="operator", schema_version=1))

            health = assess_active_profile_health()

            assert health.active_profile == "operator"
            assert health.source == "pointer"
            assert health.registered_bucket is True
            assert health.profile_record_present is False
            assert health.status == "missing_profile_record"
            assert health.repairable_by_clearing_pointer is True
            assert health.next_action == "aeat config repair profile --clear-active --yes"
    finally:
        provider.__exit__(None, None, None)
        dispose_engine()


def test_profile_repair_clears_only_degraded_pointer(tmp_path: Path) -> None:
    db_path = tmp_path / "profile-repair.db"
    dispose_engine()
    provider = EphemeralMasterKeyProvider()
    provider.__enter__()
    try:
        with override_settings(
            aeat_database_url=f"sqlite:///{db_path.as_posix()}",
            aeat_local_storage_root=tmp_path,
            aeat_active_profile=None,
        ):
            _ensure_profile_bucket_manifest("operator")
            write_pointer(tmp_path, BucketPointer(bucket_id="operator", schema_version=1))

            dry_run = repair_active_profile_pointer(clear_active=True, confirmed=False)
            assert dry_run.dry_run is True
            assert dry_run.cleared_pointer is False
            assert read_pointer(tmp_path) is not None

            repaired = repair_active_profile_pointer(clear_active=True, confirmed=True)
            assert repaired.dry_run is False
            assert repaired.cleared_pointer is True
            assert repaired.after is not None
            assert repaired.after.status == "none"
            assert read_pointer(tmp_path) is None
    finally:
        provider.__exit__(None, None, None)
        dispose_engine()


def test_profile_repair_does_not_clear_healthy_pointer(tmp_path: Path) -> None:
    db_path = tmp_path / "profile-healthy.db"
    dispose_engine()
    provider = EphemeralMasterKeyProvider()
    provider.__enter__()
    try:
        with override_settings(
            aeat_database_url=f"sqlite:///{db_path.as_posix()}",
            aeat_local_storage_root=tmp_path,
            aeat_active_profile=None,
        ):
            workflow_state_repository().update(
                lambda state: register_minimal_profile(
                    state,
                    profile_id="operator",
                    overrides={"activities.description": "software"},
                )
            )

            health = assess_active_profile_health()
            repaired = repair_active_profile_pointer(clear_active=True, confirmed=True)

            assert health.status == "ready"
            assert repaired.dry_run is True
            assert repaired.cleared_pointer is False
            assert read_pointer(tmp_path) is not None
    finally:
        provider.__exit__(None, None, None)
        dispose_engine()

"""Storage runtime readiness model tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from aeat.adapters.persistence.storage.errors import StorageValidationError
from aeat.adapters.persistence.storage.master_key._active_session import activate_session
from aeat.adapters.persistence.storage.master_key._bucket_session import BucketSession
from aeat.adapters.persistence.storage.runtime import (
    StorageRuntime,
    StorageRuntimeReadinessCode,
    inspect_bucket_storage_runtime,
    inspect_storage_runtime,
)
from aeat.adapters.persistence.storage.sql.secure_objects import SecureObjectWrite
from aeat.core.classification import SensitivityClass
from aeat.core.config import Settings, StorageRouteKind, override_settings
from aeat.core.errors import resolve_error_message

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]

_NOW = datetime(2026, 5, 26, 10, 0, tzinfo=UTC)
_KEK = b"k" * 32
_DEK = b"d" * 32


def _settings_for_bucket(root: Path, bucket_id: str) -> Settings:
    return Settings(aeat_local_storage_root=root, aeat_active_profile=bucket_id)


def _session(
    bucket_id: str,
    *,
    opened_at: datetime = _NOW,
    idle_minutes: int = 15,
    unsecured_backend: bool = False,
) -> BucketSession:
    return BucketSession.open(
        bucket_id=bucket_id,
        kek=_KEK,
        dek=_DEK,
        idle_minutes=idle_minutes,
        opened_at=opened_at,
        unsecured_backend=unsecured_backend,
    )


def _issue_codes(runtime: StorageRuntime) -> tuple[StorageRuntimeReadinessCode, ...]:
    return tuple(issue.code for issue in runtime.readiness.issues)


def test_runtime_ready_when_route_and_active_session_match(tmp_path: Path) -> None:
    settings = _settings_for_bucket(tmp_path, "bucket-a")

    with activate_session(_session("bucket-a")):
        runtime = inspect_storage_runtime(settings, now=_NOW)

    assert runtime.readiness.ready is True
    assert runtime.readiness.code is StorageRuntimeReadinessCode.READY
    assert runtime.route_kind is StorageRouteKind.ACTIVE_BUCKET_DATABASE
    assert runtime.route_attached_to_active_bucket is True
    assert runtime.active_session is not None
    assert runtime.active_session.active is True
    assert runtime.active_session.expired is False
    assert runtime.readiness.issues == ()


def test_runtime_reports_missing_session_without_touching_route(tmp_path: Path) -> None:
    settings = _settings_for_bucket(tmp_path, "bucket-a")

    runtime = inspect_storage_runtime(settings, now=_NOW)

    assert runtime.readiness.ready is False
    assert runtime.readiness.code is StorageRuntimeReadinessCode.NO_ACTIVE_SESSION
    assert runtime.route_kind is StorageRouteKind.ACTIVE_BUCKET_DATABASE
    assert runtime.active_session is None
    assert _issue_codes(runtime) == (StorageRuntimeReadinessCode.NO_ACTIVE_SESSION,)


def test_runtime_reports_expired_active_session(tmp_path: Path) -> None:
    settings = _settings_for_bucket(tmp_path, "bucket-a")
    opened_at = _NOW - timedelta(minutes=20)

    with activate_session(_session("bucket-a", opened_at=opened_at, idle_minutes=5)):
        runtime = inspect_storage_runtime(settings, now=_NOW)

    assert runtime.readiness.ready is False
    assert runtime.readiness.code is StorageRuntimeReadinessCode.SESSION_EXPIRED
    assert runtime.active_session is not None
    assert runtime.active_session.expired is True
    assert _issue_codes(runtime) == (StorageRuntimeReadinessCode.SESSION_EXPIRED,)


def test_runtime_reports_sealed_active_session(tmp_path: Path) -> None:
    settings = _settings_for_bucket(tmp_path, "bucket-a")
    session = _session("bucket-a")
    session.close()

    with activate_session(session):
        runtime = inspect_storage_runtime(settings, now=_NOW)

    assert runtime.readiness.ready is False
    assert runtime.readiness.code is StorageRuntimeReadinessCode.SESSION_SEALED
    assert runtime.active_session is not None
    assert runtime.active_session.sealed is True
    assert _issue_codes(runtime) == (StorageRuntimeReadinessCode.SESSION_SEALED,)


def test_runtime_reports_root_fallback_route_as_unready(tmp_path: Path) -> None:
    settings = Settings(aeat_local_storage_root=tmp_path)

    with activate_session(_session("bucket-a")):
        runtime = inspect_storage_runtime(settings, now=_NOW)

    assert runtime.readiness.ready is False
    assert runtime.route_kind is StorageRouteKind.ROOT_FALLBACK_DATABASE
    assert _issue_codes(runtime) == (StorageRuntimeReadinessCode.ROUTE_NOT_ACTIVE_BUCKET,)


def test_runtime_reports_route_and_session_bucket_mismatch(tmp_path: Path) -> None:
    settings = _settings_for_bucket(tmp_path, "bucket-a")

    with activate_session(_session("bucket-b")):
        runtime = inspect_storage_runtime(settings, now=_NOW)

    assert runtime.readiness.ready is False
    assert runtime.readiness.code is StorageRuntimeReadinessCode.ROUTE_BUCKET_MISMATCH
    assert runtime.active_session is not None
    assert _issue_codes(runtime) == (StorageRuntimeReadinessCode.ROUTE_BUCKET_MISMATCH,)


def test_runtime_reports_unsecured_backend_as_unready(tmp_path: Path) -> None:
    settings = _settings_for_bucket(tmp_path, "bucket-a")

    with activate_session(_session("bucket-a", unsecured_backend=True)):
        runtime = inspect_storage_runtime(settings, now=_NOW)

    assert runtime.readiness.ready is False
    assert runtime.readiness.code is StorageRuntimeReadinessCode.UNSECURED_BACKEND
    assert runtime.active_session is not None
    assert runtime.active_session.unsecured_backend is True
    assert _issue_codes(runtime) == (StorageRuntimeReadinessCode.UNSECURED_BACKEND,)


def test_runtime_reports_explicit_database_url_without_public_path_leak(tmp_path: Path) -> None:
    explicit_db = tmp_path / "bucket-a-private" / "explicit.db"
    settings = Settings(
        aeat_local_storage_root=tmp_path / "state-root-private",
        aeat_database_url=f"sqlite:///{explicit_db.as_posix()}",
    )

    with activate_session(_session("bucket-a-private")):
        runtime = inspect_storage_runtime(settings, now=_NOW)

    dumped = json.dumps(runtime.model_dump(mode="json"), sort_keys=True)
    assert runtime.readiness.ready is False
    assert runtime.route_kind is StorageRouteKind.EXPLICIT_DATABASE_URL
    assert runtime.route_has_database_path is True
    assert StorageRuntimeReadinessCode.ROUTE_NOT_ACTIVE_BUCKET.value in dumped
    assert "bucket-a-private" not in dumped
    assert "explicit.db" not in dumped
    assert "state-root-private" not in dumped


def test_named_bucket_runtime_refuses_live_explicit_database_url(tmp_path: Path) -> None:
    settings = Settings(
        aeat_local_storage_root=tmp_path / "state-root-private",
        aeat_database_url=f"sqlite:///{(tmp_path / 'explicit.db').as_posix()}",
    )

    with activate_session(_session("bucket-a")):
        runtime = inspect_bucket_storage_runtime("bucket-a", settings, now=_NOW)

    assert runtime.readiness.ready is False
    assert runtime.route_kind is StorageRouteKind.EXPLICIT_DATABASE_URL
    assert _issue_codes(runtime) == (StorageRuntimeReadinessCode.ROUTE_NOT_ACTIVE_BUCKET,)


def test_runtime_creates_bucket_attached_secure_object_repository(tmp_path: Path) -> None:
    settings = _settings_for_bucket(tmp_path, "bucket-a")

    with (
        override_settings(
            aeat_local_storage_root=tmp_path,
        ),
        activate_session(_session("bucket-a")),
    ):
        runtime = inspect_storage_runtime(settings, now=_NOW)
        repo = runtime.secure_object_repository()
        repo.save_many(
            (
                SecureObjectWrite(
                    namespace="aeat.test.runtime",
                    object_key="object-1",
                    classification=SensitivityClass.FINANCIAL,
                    schema_version=1,
                    written_at=_NOW,
                    payload=b"runtime-payload",
                ),
            )
        )
        loaded = repo.load(
            "aeat.test.runtime",
            "object-1",
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=1,
        )

    assert loaded is not None
    assert loaded.payload == b"runtime-payload"
    assert (tmp_path / "buckets" / "bucket-a" / "db" / "aeat.db").exists()


def test_runtime_repository_factory_refuses_unready_runtime(tmp_path: Path) -> None:
    settings = _settings_for_bucket(tmp_path, "bucket-a")
    runtime = inspect_storage_runtime(settings, now=_NOW)

    with override_settings(aeat_output_language="en"):
        with pytest.raises(StorageValidationError, match="storage runtime is not ready") as raised:
            runtime.secure_object_repository()

        rendered = resolve_error_message(raised.value)

    assert raised.value.translated_message == "errors.storage.runtime.not_ready"
    assert "Storage runtime is not ready for profile-bound storage" in rendered
    assert "unlock a profile" in rendered


def test_runtime_repository_factory_rechecks_live_session(tmp_path: Path) -> None:
    settings = _settings_for_bucket(tmp_path, "bucket-a")

    with activate_session(_session("bucket-a")):
        runtime = inspect_storage_runtime(settings, now=_NOW)

    with pytest.raises(StorageValidationError, match="no active bucket session"):
        runtime.secure_object_repository()


def test_runtime_repository_factory_rechecks_session_bucket(tmp_path: Path) -> None:
    settings = _settings_for_bucket(tmp_path, "bucket-a")

    with activate_session(_session("bucket-a")):
        runtime = inspect_storage_runtime(settings, now=_NOW)

    with (
        activate_session(_session("bucket-b")),
        pytest.raises(StorageValidationError, match="active bucket session changed"),
    ):
        runtime.secure_object_repository()


def test_runtime_repository_factory_rechecks_sealed_session(tmp_path: Path) -> None:
    settings = _settings_for_bucket(tmp_path, "bucket-a")
    sealed_session = _session("bucket-a")
    sealed_session.close()

    with activate_session(_session("bucket-a")):
        runtime = inspect_storage_runtime(settings, now=_NOW)

    with (
        activate_session(sealed_session),
        pytest.raises(StorageValidationError, match="active bucket session is sealed"),
    ):
        runtime.secure_object_repository()


def test_runtime_repository_factory_rechecks_expired_session(tmp_path: Path) -> None:
    settings = _settings_for_bucket(tmp_path, "bucket-a")
    expired_session = _session(
        "bucket-a",
        opened_at=datetime(2000, 1, 1, tzinfo=UTC),
        idle_minutes=5,
    )

    with activate_session(_session("bucket-a")):
        runtime = inspect_storage_runtime(settings, now=_NOW)

    with (
        activate_session(expired_session),
        pytest.raises(StorageValidationError, match="active bucket session has expired"),
    ):
        runtime.secure_object_repository()


def test_runtime_repository_factory_rechecks_unsecured_session(tmp_path: Path) -> None:
    settings = _settings_for_bucket(tmp_path, "bucket-a")

    with activate_session(_session("bucket-a")):
        runtime = inspect_storage_runtime(settings, now=_NOW)

    with (
        activate_session(_session("bucket-a", unsecured_backend=True)),
        pytest.raises(StorageValidationError, match="active bucket session uses unsecured backend"),
    ):
        runtime.secure_object_repository()

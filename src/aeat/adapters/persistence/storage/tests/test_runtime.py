"""Storage runtime readiness model tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from .....core import BucketPointer, write_pointer
from .....core.config import Settings, StorageRouteKind, override_settings
from .....core.errors import AeatError, resolve_error_message
from .....core.external_constants import OutputLanguage
from .._namespace_registry import STORAGE_NAMESPACE_REGISTRY, WORKFLOW_STATE_NAMESPACE
from ..errors import StorageValidationError
from ..master_key._active_session import activate_session
from ..master_key._bucket_session import BucketSession
from ..runtime import (
    StorageRuntime,
    StorageRuntimeReadinessCode,
    inspect_bucket_storage_runtime,
    inspect_storage_runtime,
)
from ..runtime_repository import (
    secure_object_repository_for_active_bucket,
    secure_object_repository_for_active_bucket_or_default_route,
    secure_object_repository_for_cold_bootstrap_state,
)
from ..sql import SecureObjectRepository
from ..sql.secure_objects import SecureObjectWrite

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_NOW = datetime.now(UTC).replace(microsecond=0)
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
    kek: bytes = _KEK,
    dek: bytes = _DEK,
) -> BucketSession:
    return BucketSession.open(
        bucket_id=bucket_id,
        kek=kek,
        dek=dek,
        idle_minutes=idle_minutes,
        opened_at=opened_at,
        unsecured_backend=unsecured_backend,
    )


def _sealed_session(bucket_id: str) -> BucketSession:
    session = _session(bucket_id)
    session.close()
    return session


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


@pytest.mark.parametrize(
    ("session", "expected_code", "expected_session_flag"),
    (
        (
            _session("bucket-a", opened_at=_NOW - timedelta(minutes=20), idle_minutes=5),
            StorageRuntimeReadinessCode.SESSION_EXPIRED,
            "expired",
        ),
        (
            _sealed_session("bucket-a"),
            StorageRuntimeReadinessCode.SESSION_SEALED,
            "sealed",
        ),
        (
            _session("bucket-b"),
            StorageRuntimeReadinessCode.ROUTE_BUCKET_MISMATCH,
            None,
        ),
        (
            _session("bucket-a", unsecured_backend=True),
            StorageRuntimeReadinessCode.UNSECURED_BACKEND,
            "unsecured_backend",
        ),
    ),
    ids=(
        "expired",
        "sealed",
        "bucket-mismatch",
        "unsecured-backend",
    ),
)
def test_runtime_reports_unready_active_session_states(
    tmp_path: Path,
    session: BucketSession,
    expected_code: StorageRuntimeReadinessCode,
    expected_session_flag: str | None,
) -> None:
    settings = _settings_for_bucket(tmp_path, "bucket-a")

    with activate_session(session):
        runtime = inspect_storage_runtime(settings, now=_NOW)

    assert runtime.readiness.ready is False
    assert runtime.readiness.code is expected_code
    assert runtime.active_session is not None
    if expected_session_flag is not None:
        assert getattr(runtime.active_session, expected_session_flag) is True
    assert _issue_codes(runtime) == (expected_code,)


def test_runtime_reports_root_fallback_route_as_unready(tmp_path: Path) -> None:
    settings = Settings(aeat_local_storage_root=tmp_path)

    with activate_session(_session("bucket-a")):
        runtime = inspect_storage_runtime(settings, now=_NOW)

    assert runtime.readiness.ready is False
    assert runtime.route_kind is StorageRouteKind.ROOT_FALLBACK_DATABASE
    assert _issue_codes(runtime) == (StorageRuntimeReadinessCode.ROUTE_NOT_ACTIVE_BUCKET,)


def test_runtime_repository_factory_refuses_route_and_session_bucket_mismatch(tmp_path: Path) -> None:
    settings = _settings_for_bucket(tmp_path, "bucket-a")

    with activate_session(_session("bucket-b")):
        runtime = inspect_storage_runtime(settings, now=_NOW)
        with pytest.raises(StorageValidationError) as raised:
            runtime.secure_object_repository()

    assert runtime.readiness.code is StorageRuntimeReadinessCode.ROUTE_BUCKET_MISMATCH
    assert raised.value.translated_message == "errors.storage.runtime.not_ready"


def test_runtime_repository_factory_refuses_initial_unsecured_backend(tmp_path: Path) -> None:
    settings = _settings_for_bucket(tmp_path, "bucket-a")

    with activate_session(_session("bucket-a", unsecured_backend=True)):
        runtime = inspect_storage_runtime(settings, now=_NOW)
        with pytest.raises(StorageValidationError) as raised:
            runtime.secure_object_repository()

    assert runtime.readiness.code is StorageRuntimeReadinessCode.UNSECURED_BACKEND
    assert raised.value.translated_message == "errors.storage.runtime.not_ready"


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
    issue = runtime.readiness.issues[0]
    assert "AEAT_DATABASE_URL" in issue.message
    assert "AEAT_LOCAL_STORAGE_ROOT" in issue.recovery_hint
    with pytest.raises(StorageValidationError) as raised:
        runtime.require_ready()
    assert isinstance(raised.value, AeatError)
    assert raised.value.context is not None
    assert "AEAT_DATABASE_URL" in str(raised.value.context["recovery"])
    assert "AEAT_LOCAL_STORAGE_ROOT" in str(raised.value.context["recovery"])


def test_named_bucket_runtime_rejects_blank_bucket_with_localized_validation(tmp_path: Path) -> None:
    settings = Settings(aeat_local_storage_root=tmp_path)

    with pytest.raises(StorageValidationError, match="bucket_id must not be blank") as excinfo:
        inspect_bucket_storage_runtime("   ", settings, now=_NOW)

    assert excinfo.value.translated_message == "errors.integrity.integrity_storage_validation"


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
        assert repo.namespace_registry is STORAGE_NAMESPACE_REGISTRY
        namespace = WORKFLOW_STATE_NAMESPACE.namespace
        object_key = WORKFLOW_STATE_NAMESPACE.require_default_object_key()
        repo.save_many(
            (
                SecureObjectWrite(
                    namespace=namespace,
                    object_key=object_key,
                    classification=WORKFLOW_STATE_NAMESPACE.sensitivity,
                    schema_version=WORKFLOW_STATE_NAMESPACE.schema_version,
                    written_at=_NOW,
                    payload=b"runtime-payload",
                ),
            ),
        )
        loaded = repo.load(
            namespace,
            object_key,
            expected_class=WORKFLOW_STATE_NAMESPACE.sensitivity,
            max_supported_version=WORKFLOW_STATE_NAMESPACE.schema_version,
        )

    assert loaded is not None
    assert loaded.payload == b"runtime-payload"
    assert (tmp_path / "buckets" / "bucket-a" / "db" / "aeat.db").exists()


def test_runtime_repository_rejects_unregistered_namespace_writes(tmp_path: Path) -> None:
    settings = _settings_for_bucket(tmp_path, "bucket-a")
    namespace = "aeat.test.runtime.unregistered"

    with (
        override_settings(
            aeat_local_storage_root=tmp_path,
        ),
        activate_session(_session("bucket-a")),
    ):
        runtime = inspect_storage_runtime(settings, now=_NOW)
        repo = runtime.secure_object_repository()
        with pytest.raises(StorageValidationError) as raised:
            repo.save(
                namespace=namespace,
                object_key="runtime-policy-key",
                classification=WORKFLOW_STATE_NAMESPACE.sensitivity,
                schema_version=WORKFLOW_STATE_NAMESPACE.schema_version,
                written_at=_NOW,
                payload=b"runtime-policy-payload",
            )
        unregistered_rows = tuple(row for row in repo.iter_all_records_raw() if row.namespace == namespace)

    assert raised.value.translated_message == "errors.storage.namespace.unregistered"
    assert unregistered_rows == ()


def test_runtime_bound_repository_refuses_write_after_session_bucket_changes(tmp_path: Path) -> None:
    settings = _settings_for_bucket(tmp_path, "bucket-a")
    namespace = WORKFLOW_STATE_NAMESPACE.namespace
    object_key = "stale-session-write"

    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_output_language="en"),
        activate_session(_session("bucket-a")),
    ):
        runtime = inspect_storage_runtime(settings, now=_NOW)
        repo = runtime.secure_object_repository()
        with activate_session(_session("bucket-b")):
            with pytest.raises(StorageValidationError) as raised:
                repo.save(
                    namespace=namespace,
                    object_key=object_key,
                    classification=WORKFLOW_STATE_NAMESPACE.sensitivity,
                    schema_version=WORKFLOW_STATE_NAMESPACE.schema_version,
                    written_at=_NOW,
                    payload=b"stale-session-payload",
                )
            rendered = resolve_error_message(raised.value)

        loaded = repo.load(
            namespace,
            object_key,
            expected_class=WORKFLOW_STATE_NAMESPACE.sensitivity,
            max_supported_version=WORKFLOW_STATE_NAMESPACE.schema_version,
        )

    assert raised.value.translated_message == "errors.storage.runtime.not_ready"
    assert "active bucket session changed" in rendered
    assert loaded is None


def test_runtime_bound_repository_refuses_raw_key_write_after_session_bucket_changes(tmp_path: Path) -> None:
    settings = _settings_for_bucket(tmp_path, "bucket-a")
    namespace = WORKFLOW_STATE_NAMESPACE.namespace
    hashed_object_key = b"h" * 32

    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_output_language="en"),
        activate_session(_session("bucket-a")),
    ):
        runtime = inspect_storage_runtime(settings, now=_NOW)
        repo = runtime.secure_object_repository()
        with activate_session(_session("bucket-b")):
            with pytest.raises(StorageValidationError) as raised:
                repo.save_with_raw_key(
                    namespace=namespace,
                    hashed_object_key=hashed_object_key,
                    classification=WORKFLOW_STATE_NAMESPACE.sensitivity,
                    schema_version=WORKFLOW_STATE_NAMESPACE.schema_version,
                    written_at=_NOW,
                    payload=b"stale-raw-session-payload",
                )
            rendered = resolve_error_message(raised.value)

        raw_row_exists = repo.exists_by_raw_key(namespace, hashed_object_key)

    assert raised.value.translated_message == "errors.storage.runtime.not_ready"
    assert "active bucket session changed" in rendered
    assert raw_row_exists is False


def test_runtime_bound_repository_refuses_write_after_session_becomes_unsecured(tmp_path: Path) -> None:
    settings = _settings_for_bucket(tmp_path, "bucket-a")
    namespace = WORKFLOW_STATE_NAMESPACE.namespace
    object_key = "unsecured-session-write"

    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_output_language="en"),
        activate_session(_session("bucket-a")),
    ):
        runtime = inspect_storage_runtime(settings, now=_NOW)
        repo = runtime.secure_object_repository()
        with activate_session(_session("bucket-a", unsecured_backend=True)):
            with pytest.raises(StorageValidationError) as raised:
                repo.save(
                    namespace=namespace,
                    object_key=object_key,
                    classification=WORKFLOW_STATE_NAMESPACE.sensitivity,
                    schema_version=WORKFLOW_STATE_NAMESPACE.schema_version,
                    written_at=_NOW,
                    payload=b"unsecured-session-payload",
                )
            rendered = resolve_error_message(raised.value)

        loaded = repo.load(
            namespace,
            object_key,
            expected_class=WORKFLOW_STATE_NAMESPACE.sensitivity,
            max_supported_version=WORKFLOW_STATE_NAMESPACE.schema_version,
        )

    assert raised.value.translated_message == "errors.storage.runtime.not_ready"
    assert "unsecured backend" in rendered
    assert loaded is None


def test_runtime_bound_repository_refuses_quarantine_after_session_bucket_changes(tmp_path: Path) -> None:
    settings = _settings_for_bucket(tmp_path, "bucket-a")
    namespace = WORKFLOW_STATE_NAMESPACE.namespace
    object_key = "stale-quarantine-row"

    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_output_language="en"),
        activate_session(_session("bucket-a")),
    ):
        runtime = inspect_storage_runtime(settings, now=_NOW)
        repo = runtime.secure_object_repository()
        repo.save(
            namespace=namespace,
            object_key=object_key,
            classification=WORKFLOW_STATE_NAMESPACE.sensitivity,
            schema_version=WORKFLOW_STATE_NAMESPACE.schema_version,
            written_at=_NOW,
            payload=b"quarantine-guard-payload",
        )

        with activate_session(_session("bucket-b", kek=b"x" * 32, dek=b"y" * 32)):
            with pytest.raises(StorageValidationError) as raised:
                repo.quarantine_unreadable_rows()
            rendered = resolve_error_message(raised.value)

        loaded = repo.load(
            namespace,
            object_key,
            expected_class=WORKFLOW_STATE_NAMESPACE.sensitivity,
            max_supported_version=WORKFLOW_STATE_NAMESPACE.schema_version,
        )

    assert raised.value.translated_message == "errors.storage.runtime.not_ready"
    assert "active bucket session changed" in rendered
    assert loaded is not None
    assert loaded.payload == b"quarantine-guard-payload"


def test_runtime_bound_repository_refuses_diagnostics_after_session_bucket_changes(tmp_path: Path) -> None:
    settings = _settings_for_bucket(tmp_path, "bucket-a")
    namespace = WORKFLOW_STATE_NAMESPACE.namespace
    object_key = "stale-diagnostic-row"

    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_output_language="en"),
        activate_session(_session("bucket-a")),
    ):
        runtime = inspect_storage_runtime(settings, now=_NOW)
        repo = runtime.secure_object_repository()
        repo.save(
            namespace=namespace,
            object_key=object_key,
            classification=WORKFLOW_STATE_NAMESPACE.sensitivity,
            schema_version=WORKFLOW_STATE_NAMESPACE.schema_version,
            written_at=_NOW,
            payload=b"diagnostic-guard-payload",
        )

        with activate_session(_session("bucket-b", kek=b"x" * 32, dek=b"y" * 32)):
            diagnostic_calls = (
                lambda: repo.exists(namespace, object_key),
                lambda: tuple(repo.iter_all_records_raw()),
                repo.list_namespaces,
                lambda: repo.probe_namespace_integrity(namespace),
                lambda: tuple(repo.iter_namespace_decryptability(namespace)),
                lambda: repo.list_keys(namespace),
                lambda: tuple(
                    repo.iter_records_with_failures(
                        namespace,
                        expected_class=WORKFLOW_STATE_NAMESPACE.sensitivity,
                        max_supported_version=WORKFLOW_STATE_NAMESPACE.schema_version,
                    ),
                ),
                lambda: repo.peek_metadata(namespace, object_key),
            )
            for diagnostic_call in diagnostic_calls:
                with pytest.raises(StorageValidationError) as raised:
                    diagnostic_call()
                assert raised.value.translated_message == "errors.storage.runtime.not_ready"

        loaded = repo.load(
            namespace,
            object_key,
            expected_class=WORKFLOW_STATE_NAMESPACE.sensitivity,
            max_supported_version=WORKFLOW_STATE_NAMESPACE.schema_version,
        )

    assert loaded is not None
    assert loaded.payload == b"diagnostic-guard-payload"


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


def test_cold_bootstrap_repository_is_available_before_profile_selection(tmp_path: Path) -> None:
    with override_settings(aeat_local_storage_root=tmp_path, aeat_active_profile=None):
        repository = secure_object_repository_for_cold_bootstrap_state()

    assert isinstance(repository, SecureObjectRepository)
    assert repository.namespace_registry is STORAGE_NAMESPACE_REGISTRY


def test_default_route_repository_carries_namespace_registry_before_profile_selection(tmp_path: Path) -> None:
    settings = Settings(aeat_local_storage_root=tmp_path, aeat_active_profile=None)

    repository = secure_object_repository_for_active_bucket_or_default_route(settings)

    assert isinstance(repository, SecureObjectRepository)
    assert repository.namespace_registry is STORAGE_NAMESPACE_REGISTRY


def test_active_bucket_repository_refusal_carries_localized_details(tmp_path: Path) -> None:
    with override_settings(
        aeat_local_storage_root=tmp_path,
        aeat_active_profile=None,
        aeat_output_language="en",
    ):
        with pytest.raises(StorageValidationError) as raised:
            secure_object_repository_for_active_bucket()
        rendered = resolve_error_message(raised.value)

    assert raised.value.translated_message == "errors.storage.runtime.not_ready"
    assert raised.value.context is not None
    assert "No active bucket session" in str(raised.value.context["details"])
    assert "No active bucket session" in rendered


def test_cold_bootstrap_repository_refuses_active_profile(tmp_path: Path) -> None:
    with (
        override_settings(
            aeat_local_storage_root=tmp_path,
            aeat_active_profile="bucket-a",
            aeat_output_language="en",
        ),
        pytest.raises(StorageValidationError) as excinfo,
    ):
        secure_object_repository_for_cold_bootstrap_state()
    assert excinfo.value.translated_message == "errors.storage.runtime.cold_bootstrap_active_profile_refused"


def test_cold_bootstrap_repository_refuses_settings_scoped_active_profile(
    tmp_path: Path,
) -> None:
    settings = Settings(
        aeat_local_storage_root=tmp_path,
        aeat_active_profile="bucket-a",
        aeat_output_language=OutputLanguage.EN,
    )

    with pytest.raises(StorageValidationError) as excinfo:
        secure_object_repository_for_cold_bootstrap_state(settings)
    assert excinfo.value.translated_message == "errors.storage.runtime.cold_bootstrap_active_profile_refused"


def test_cold_bootstrap_repository_refuses_explicit_database_route(tmp_path: Path) -> None:
    settings = Settings(
        aeat_database_url=f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}",
        aeat_output_language=OutputLanguage.EN,
    )

    with pytest.raises(StorageValidationError) as excinfo:
        secure_object_repository_for_cold_bootstrap_state(settings)
    assert excinfo.value.translated_message == "errors.storage.runtime.cold_bootstrap_explicit_database_refused"


def test_default_route_repository_refuses_settings_scoped_active_profile_without_session(
    tmp_path: Path,
) -> None:
    settings = _settings_for_bucket(tmp_path, "bucket-a")

    with pytest.raises(StorageValidationError, match="no active bucket session"):
        secure_object_repository_for_active_bucket_or_default_route(settings)


def test_default_route_repository_refuses_pointer_scoped_active_profile_without_session(
    tmp_path: Path,
) -> None:
    """A plaintext pointer selects a runtime bucket; it must not fall back to root DB."""

    write_pointer(tmp_path, BucketPointer(bucket_id="bucket-a", schema_version=1))

    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_active_profile=None),
        pytest.raises(StorageValidationError, match="no active bucket session"),
    ):
        secure_object_repository_for_active_bucket_or_default_route()


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

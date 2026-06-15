"""Tests for shared secure SQL isolation helpers."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ..adapters.persistence.storage import has_active_bucket_session
from ..adapters.persistence.storage.bucket._manifest_io import read_manifest
from ..adapters.persistence.storage.master_key._active_session import activate_session
from ..adapters.persistence.storage.master_key._bucket_session import BucketSession
from ..adapters.persistence.storage.runtime import StorageRuntimeReadinessCode, inspect_storage_runtime
from ..adapters.persistence.storage.sql.engine import dispose_engine, get_engine
from ..adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ..core.classification import SensitivityClass
from ..core.config import StorageRouteKind, load_settings, override_settings
from .secure_sql import (
    dev_test_database_password,
    isolated_cli_runtime_profile,
    isolated_ephemeral_secure_sql,
    isolated_profile_storage_root,
    isolated_runtime_profile,
    read_db_at_rest_bytes,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def test_read_db_at_rest_bytes_includes_the_wal_sidecar(tmp_path: Path) -> None:
    """The at-rest reader scans the ``-wal`` sidecar, not just the main ``.db``.

    Non-tautology lock for every at-rest plaintext scan routed through
    ``read_db_at_rest_bytes``: in WAL mode a just-committed row lives in the
    ``<db>-wal`` sidecar until a checkpoint folds it into the main file. A scan
    that read only the main ``.db`` would miss it and pass tautologically. This
    pins the helper's contract directly and deterministically (without relying
    on SQLite checkpoint timing): the combined view must include the sidecar
    bytes, and a main-only read must not. If the helper ever stops reading the
    sidecar, this fails first.
    """
    db_path = tmp_path / "x.db"
    db_path.write_bytes(b"MAIN_DB_CONTENT")
    (tmp_path / "x.db-wal").write_bytes(b"WAL_SIDECAR_SENTINEL")

    combined = read_db_at_rest_bytes(db_path)
    assert b"MAIN_DB_CONTENT" in combined
    assert b"WAL_SIDECAR_SENTINEL" in combined, "helper must include the -wal sidecar"
    assert b"WAL_SIDECAR_SENTINEL" not in db_path.read_bytes(), (
        "a main-only read must miss the sidecar -- this is the tautology the helper closes"
    )

    # With no sidecar present the helper still returns the main file bytes.
    plain_db = tmp_path / "plain.db"
    plain_db.write_bytes(b"ONLY_MAIN")
    assert read_db_at_rest_bytes(plain_db) == b"ONLY_MAIN"


_CONTROL_BUCKET_ID = "contamination-control"
_CONTROL_KEK = b"c" * 32
_CONTROL_DEK = b"p" * 32


def test_isolated_ephemeral_secure_sql_routes_default_engine_to_tmp_database(
    tmp_path: Path,
) -> None:
    with isolated_ephemeral_secure_sql(tmp_path=tmp_path):
        assert has_active_bucket_session()
        with get_engine().connect() as connection:
            database_rows = connection.exec_driver_sql("PRAGMA database_list").fetchall()

    database_paths = {Path(str(row[2])).resolve() for row in database_rows if row[2]}
    assert (tmp_path / "aeat.db").resolve() in database_paths
    assert not has_active_bucket_session()


def test_isolated_ephemeral_secure_sql_does_not_mutate_active_profile_database(tmp_path: Path) -> None:
    storage_root = tmp_path / "operator-storage"
    control_database = storage_root / "buckets" / _CONTROL_BUCKET_ID / "db" / "aeat.db"
    isolated_root = tmp_path / "isolated-storage"
    isolated_database = isolated_root / "aeat.db"

    with override_settings(aeat_local_storage_root=storage_root, aeat_active_profile=_CONTROL_BUCKET_ID):
        dispose_engine()
        try:
            with activate_session(_control_session()):
                SecureObjectRepository().save(
                    namespace="aeat.tests.contamination.control",
                    object_key="active-profile-row",
                    classification=SensitivityClass.FINANCIAL,
                    schema_version=1,
                    written_at=datetime.now(UTC),
                    payload=b"active-profile-control",
                )
            dispose_engine()
            control_rows_before = _secure_object_row_count(control_database)

            with isolated_ephemeral_secure_sql(tmp_path=isolated_root):
                SecureObjectRepository().save(
                    namespace="aeat.tests.contamination.isolated",
                    object_key="isolated-row",
                    classification=SensitivityClass.FINANCIAL,
                    schema_version=1,
                    written_at=datetime.now(UTC),
                    payload=b"isolated-helper-row",
                )

            control_rows_after = _secure_object_row_count(control_database)
        finally:
            dispose_engine()

    assert control_rows_before == 1
    assert control_rows_after == control_rows_before
    assert _secure_object_row_count(isolated_database) == 1


def test_isolated_runtime_profile_provisions_manifest_runtime_and_repository(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_CONTROL_BUCKET_ID) as profile:
        manifest = read_manifest(profile.paths)
        profile.repository.save(
            namespace="aeat.tests.runtime.profile",
            object_key="runtime-row",
            classification=SensitivityClass.FINANCIAL,
            schema_version=1,
            written_at=datetime.now(UTC),
            payload=b"runtime-profile-row",
        )

        runtime = inspect_storage_runtime(profile.settings)

    assert manifest.bucket_id == _CONTROL_BUCKET_ID
    assert manifest.label == "Test runtime profile"
    assert profile.runtime.readiness.code is StorageRuntimeReadinessCode.READY
    assert runtime.route_kind is StorageRouteKind.ACTIVE_BUCKET_DATABASE
    assert runtime.route_attached_to_active_bucket
    assert _secure_object_row_count(profile.paths.db_dir / "aeat.db") == 1
    assert not (profile.storage_root / "aeat.db").exists()
    assert not has_active_bucket_session()


def test_profile_bootstrap_storage_uses_shared_dev_database_password(tmp_path: Path) -> None:
    expected = "unique-dev-test-database-password-for-profile-bootstrap"
    with (
        override_settings(aeat_dev_test_database_password=expected),
        isolated_profile_storage_root(tmp_path=tmp_path),
    ):
        settings = load_settings()

    assert settings.aeat_secret_passphrase is not None
    assert settings.aeat_secret_passphrase.get_secret_value() == expected
    assert dev_test_database_password(settings) == expected


def test_isolated_cli_runtime_profile_routes_workflow_and_modelo_repositories_to_active_bucket(
    tmp_path: Path,
) -> None:
    from ..application.workflow._persistence import workflow_state_repository
    from ..domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
    from ..domain.modelos._repository import WorkUnitCatalogueRepository

    with isolated_cli_runtime_profile(tmp_path=tmp_path, bucket_id=_CONTROL_BUCKET_ID) as profile:
        workflow_state_repository().update(lambda state: state)
        work_units = WorkUnitCatalogueRepository()
        revisions = CalculationRevisionCatalogueRepository()

        work_units.save(work_units.load())
        revisions.save(revisions.load())

        active_bucket = workflow_state_repository().load().active_profile_bucket_id()
        database_path = profile.paths.db_dir / "aeat.db"

    assert active_bucket == _CONTROL_BUCKET_ID
    assert work_units.bucket_id == _CONTROL_BUCKET_ID
    assert revisions.bucket_id == _CONTROL_BUCKET_ID
    assert _secure_object_row_count(database_path) == 3
    assert not has_active_bucket_session()


def _control_session() -> BucketSession:
    return BucketSession.open(
        bucket_id=_CONTROL_BUCKET_ID,
        kek=_CONTROL_KEK,
        dek=_CONTROL_DEK,
        idle_minutes=15,
        opened_at=datetime.now(UTC),
    )


def _secure_object_row_count(database_path: Path) -> int:
    with sqlite3.connect(database_path) as connection:
        return int(connection.execute("SELECT COUNT(*) FROM secure_objects").fetchone()[0])

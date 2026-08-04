"""Tests for shared secure SQL isolation helpers."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ..adapters.persistence.storage import (
    MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE,
    MODELO_WORK_UNIT_CATALOGUE_NAMESPACE,
    WORKFLOW_STATE_NAMESPACE,
    has_active_bucket_session,
)
from ..adapters.persistence.storage.bucket import bucket_paths, read_manifest
from ..adapters.persistence.storage.master_key import (
    BucketSession,
    activate_session,
    close_active_bucket_session,
    load_profile_session_key,
)
from ..adapters.persistence.storage.runtime import StorageRuntimeReadinessCode, inspect_storage_runtime
from ..adapters.persistence.storage.sql.engine import dispose_engine, get_engine
from ..adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ..application.user_profile import login_profile
from ..application.workflow import read_profile_bucket
from ..core import StorageCategory, storage_location
from ..core.classification import SensitivityClass
from ..core.config import StorageRouteKind, load_settings, override_settings
from .cli_runner import invoke_cached_cli
from .secure_sql import (
    dev_test_database_password,
    isolated_cli_runtime_profile,
    isolated_ephemeral_secure_sql,
    isolated_profile_storage_root,
    isolated_runtime_profile,
    read_db_at_rest_bytes,
    reap_profile_session_keys,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_REAP_LABEL = "harness-reap-operator"


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
    assert (tmp_path / storage_location(StorageCategory.ROOT_FALLBACK_DATABASE).subpath).resolve() in database_paths
    assert not has_active_bucket_session()


def test_isolated_ephemeral_secure_sql_does_not_mutate_active_profile_database(tmp_path: Path) -> None:
    storage_root = tmp_path / "operator-storage"
    control_database = bucket_paths(storage_root, _CONTROL_BUCKET_ID).database_file
    isolated_root = tmp_path / "isolated-storage"
    isolated_database = isolated_root / storage_location(StorageCategory.ROOT_FALLBACK_DATABASE).subpath

    with override_settings(cadrumo_local_storage_root=storage_root, cadrumo_active_profile=_CONTROL_BUCKET_ID):
        dispose_engine()
        try:
            with activate_session(_control_session()):
                SecureObjectRepository().save(
                    namespace="cadrumo-tests.contamination.control",
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
                    namespace="cadrumo-tests.contamination.isolated",
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
            namespace="cadrumo-tests.runtime.profile",
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
    assert _secure_object_row_count(profile.paths.database_file) == 1
    assert not (profile.storage_root / storage_location(StorageCategory.ROOT_FALLBACK_DATABASE).subpath).exists()
    assert not has_active_bucket_session()


def test_profile_bootstrap_storage_uses_shared_dev_database_password(tmp_path: Path) -> None:
    expected = "unique-dev-test-database-password-for-profile-bootstrap"
    with (
        override_settings(cadrumo_dev_test_database_password=expected),
        isolated_profile_storage_root(tmp_path=tmp_path),
    ):
        settings = load_settings()

    assert settings.cadrumo_secret_passphrase is not None
    assert settings.cadrumo_secret_passphrase.get_secret_value() == expected
    assert dev_test_database_password(settings) == expected


def test_isolated_cli_runtime_profile_routes_workflow_and_modelo_repositories_to_active_bucket(
    tmp_path: Path,
) -> None:
    from ..adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
    from ..adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ..application.workflow import WorkflowState, workflow_state_repository

    with isolated_cli_runtime_profile(tmp_path=tmp_path, bucket_id=_CONTROL_BUCKET_ID) as profile:
        workflow_repository = workflow_state_repository()
        workflow_repository.save(WorkflowState())
        work_units = WorkUnitCatalogueRepository()
        revisions = CalculationRevisionCatalogueRepository()

        work_units.save(work_units.load())
        revisions.save(revisions.load())

        active_bucket = workflow_repository.load().active_profile_bucket_id()
        database_path = profile.paths.database_file

    assert active_bucket == _CONTROL_BUCKET_ID
    assert work_units.bucket_id == _CONTROL_BUCKET_ID
    assert revisions.bucket_id == _CONTROL_BUCKET_ID
    assert _secure_object_namespaces(database_path) == tuple(
        sorted(
            (
                WORKFLOW_STATE_NAMESPACE.namespace,
                MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE.namespace,
                MODELO_WORK_UNIT_CATALOGUE_NAMESPACE.namespace,
            ),
        ),
    )
    assert not has_active_bucket_session()


class TestHarnessReapsSessionKeys:
    """The shared harness must not leak OS-keychain entries per test run.

    A login mints a ``cadrumo:profile-session`` keychain entry keyed by
    bucket uuid, and a test's storage root is a temporary directory that
    production never reaps. Because every run mints a FRESH uuid, a
    harness without this teardown deposits one permanent orphan per
    leaking test per run — measured at 58 orphans from a single 54-test
    pass, and 552 accumulated on one workstation before the credential
    store saturated and ``CredWrite`` began failing host-wide.

    The two halves are split so the reap-a-known-id contract stays
    verifiable on a host whose credential store is unreachable, and only
    the half that genuinely needs custody carries ``os_keychain``.
    """

    def test_reap_is_a_no_op_for_an_unpopulated_root(self, tmp_path: Path) -> None:
        """An empty root enumerates to nothing and must not raise.

        Teardown runs after every test using the harness, including tests
        that never provisioned a bucket, so a reap that raised on an
        absent ``buckets/`` directory would convert an unrelated passing
        test into an error.
        """
        reap_profile_session_keys(tmp_path / "never-created")

    def test_reap_skips_a_directory_that_is_not_a_bucket_identity(self, tmp_path: Path) -> None:
        """A non-identity directory name can address no entry, so it is skipped.

        The reap recovers identities from directory names; a stray
        directory under ``buckets/`` must be ignored rather than raise the
        canonical-identity refusal out of a teardown.
        """
        bucket_paths(tmp_path, "not-a-uuid").bucket_dir.mkdir(parents=True)
        reap_profile_session_keys(tmp_path)

    @pytest.mark.os_keychain
    def test_login_inside_the_harness_leaves_no_keychain_entry(self, tmp_path: Path) -> None:
        """A real login's session key is gone once the harness context exits.

        Keyed on the bucket uuid this test created rather than on a global
        credential count, so a peer process minting concurrently on the
        same workstation cannot make the assertion pass or fail
        spuriously. The custody precondition is asserted FIRST: without it
        a host that minted nothing would report a clean reap, which is
        exactly the false-clean a saturated credential store produces.
        """
        with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
            created = invoke_cached_cli(
                [
                    "config",
                    "profile",
                    "create",
                    _REAP_LABEL,
                    "--quiet",
                    "--accept-defaults",
                    "--tax-id",
                    "12345678Z",
                    "--entity-type",
                    "natural_person",
                    "--name",
                    "Harness",
                    "--surnames",
                    "Reap",
                    "--activity",
                    "design",
                ],
            )
            assert created.exit_code == 0, created.output
            close_active_bucket_session()
            pointer = read_profile_bucket(_REAP_LABEL)
            assert pointer is not None
            bucket_id = pointer.bucket_id

            login_profile()
            if load_profile_session_key(bucket_id=bucket_id) is None:
                pytest.fail(
                    "login custodied no keychain session key, so a reap cannot be "
                    "observed: this host has no usable OS credential store. The "
                    "login itself succeeded and correctly degraded to a "
                    "process-scoped session; only the custody half is unavailable.",
                )
            assert storage_root.is_dir()

        assert load_profile_session_key(bucket_id=bucket_id) is None, (
            "the harness teardown left a cadrumo:profile-session keychain entry "
            f"behind for bucket {bucket_id}; every run of every login test would "
            "deposit one more permanent orphan in the developer's credential store"
        )


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


def _secure_object_namespaces(database_path: Path) -> tuple[str, ...]:
    with sqlite3.connect(database_path) as connection:
        return tuple(
            str(row[0])
            for row in connection.execute(
                "SELECT namespace FROM secure_objects ORDER BY namespace",
            )
        )

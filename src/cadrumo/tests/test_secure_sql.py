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
)
from ..adapters.persistence.storage.bucket import bucket_paths
from ..adapters.persistence.storage.master_key import (
    BucketSession,
    activate_session,
)
from ..adapters.persistence.storage.sql.engine import dispose_engine
from ..adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ..adapters.persistence.storage.tests.profile_capsule_runtime import (
    derive_test_bucket_key,
    publish_test_profile_capsule,
)
from ..core.storage_taxonomy_locations import storage_location
from ..core.storage_taxonomy import StorageCategory
from ..core.classification import SensitivityClass
from ..core.config import load_settings, override_settings
from .secure_sql import (
    dev_test_database_password,
    isolated_cli_runtime_profile,
    isolated_ephemeral_secure_sql,
    isolated_profile_storage_root,
    read_db_at_rest_bytes,
    reap_profile_session_keys,
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


#: A bucket is a published profile capsule, so its identifier is a profile
#: UUID and nothing else -- a free-form label names a bucket no production
#: path could ever create, and capsule publication refuses it outright.
_CONTROL_BUCKET_ID = "44444444-4444-4444-8444-444444444444"
_CONTROL_NAMESPACE = "cadrumo-tests.contamination.control"


def test_isolated_ephemeral_secure_sql_does_not_mutate_active_profile_database(tmp_path: Path) -> None:
    storage_root = tmp_path / "operator-storage"
    control_database = bucket_paths(storage_root, _CONTROL_BUCKET_ID).database_file
    isolated_root = tmp_path / "isolated-storage"
    isolated_database = isolated_root / storage_location(StorageCategory.ROOT_FALLBACK_DATABASE).subpath

    with override_settings(cadrumo_local_storage_root=storage_root, cadrumo_active_profile=_CONTROL_BUCKET_ID):
        dispose_engine()
        publish_test_profile_capsule(_CONTROL_BUCKET_ID, label="Contamination control", root=storage_root)
        try:
            with activate_session(_control_session()):
                SecureObjectRepository().save(
                    namespace=_CONTROL_NAMESPACE,
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

    # Anchored on the control namespace rather than a whole-table tally: the
    # bucket also carries the rows capsule publication writes when it brings
    # the bucket into existence, and a tally would encode that moment instead
    # of the property under test.
    assert _secure_object_namespaces(control_database).count(_CONTROL_NAMESPACE) == 1
    assert control_rows_after == control_rows_before
    assert _secure_object_row_count(isolated_database) == 1


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
    from ..application.workflow.persistence import workflow_state_repository
    from ..application.workflow.state_models import WorkflowState

    with isolated_cli_runtime_profile(tmp_path=tmp_path, bucket_id=_CONTROL_BUCKET_ID) as profile:
        # The fixture brings its bucket into existence by publishing a capsule,
        # so the bucket is legitimately non-empty before this test writes
        # anything. Baselining rather than pinning a literal set keeps the
        # assertion about routing, not about what publication happens to write.
        published = _secure_object_namespaces(profile.paths.database_file)
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
                *published,
                WORKFLOW_STATE_NAMESPACE.namespace,
                MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE.namespace,
                MODELO_WORK_UNIT_CATALOGUE_NAMESPACE.namespace,
            ),
        ),
    )


class TestHarnessReapsSessionKeys:
    """The shared harness must not leak OS-keychain entries per test run.

    A login mints a ``cadrumo:profile-session`` keychain entry keyed by
    bucket uuid, and a test's storage root is a temporary directory that
    production never reaps. Because every run mints a FRESH uuid, a
    harness without this teardown deposits one permanent orphan per
    leaking test per run — measured at 58 orphans from a single 54-test
    pass, and 552 accumulated on one workstation before the credential
    store saturated and ``CredWrite`` began failing host-wide.

    These no-custody controls keep teardown harmless for empty and invalid
    directory entries. The real keychain deletion contract lives with the
    persistence-owned runtime-context lifecycle tests.
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


def _control_session() -> BucketSession:
    """Open the control bucket under the one test-owned key derivation.

    Sharing the persistence test runtime's canonical key derivation with the
    published capsule is what makes this session able to read what publication
    wrote; a pair of arbitrary key literals would open a session that agrees
    with nothing else in the bucket.
    """
    return BucketSession.open(
        bucket_id=_CONTROL_BUCKET_ID,
        kek=derive_test_bucket_key(_CONTROL_BUCKET_ID, purpose="kek"),
        dek=derive_test_bucket_key(_CONTROL_BUCKET_ID, purpose="dek"),
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

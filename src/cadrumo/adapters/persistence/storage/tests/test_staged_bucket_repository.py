"""The staged-bucket repository factory: the one route the runtime cannot serve.

Capsule creation writes revision one into a staging directory that only becomes
``buckets/<bucket_id>/`` at the publishing rename, so there is no published
bucket for the runtime to attach to and no ambient session serving it. This
module proves the factory really is runtime-owned where it matters -- namespace
registry, session binding, secure-session requirement, engine lifetime -- rather
than a direct construction wearing a nicer name.

Real SQLite, a real master-key provider, a real bucket session. Nothing mocked.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from .....tests.master_key import EphemeralMasterKeyProvider
from .._secure_object_namespaces import STORAGE_NAMESPACE_REGISTRY, WORKFLOW_STATE_NAMESPACE
from ..errors import StorageError, StorageValidationError
from ..master_key import BucketSession, activate_session
from ..runtime_repository import secure_object_repository_for_staged_bucket
from ..sql.secure_objects import SecureObjectWrite

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_NOW = datetime(2026, 8, 16, 10, 0, 0, tzinfo=UTC)
_BUCKET_ID = "6b5f0a17-2c48-4d93-9a01-7e2d4c8b3f56"
_OTHER_BUCKET_ID = "c47e9b02-15da-4f6e-8b73-9d0a5e1c2847"
_KEK = b"k" * 32
_DEK = b"d" * 32


def _session(bucket_id: str) -> BucketSession:
    return BucketSession.open(
        bucket_id=bucket_id,
        kek=_KEK,
        dek=_DEK,
        idle_minutes=15,
        opened_at=datetime.now(UTC),
    )


def _staging_database(tmp_path: Path) -> Path:
    """Return a staging path shaped like the one capsule creation writes."""
    return tmp_path / "capsules" / f".{_BUCKET_ID}.staging-transaction" / "db" / "cadrumo.db"


def test_staged_repository_round_trips_a_real_row_before_publication(tmp_path: Path) -> None:
    """The staged database accepts and returns a secure object with no published bucket."""
    database_file = _staging_database(tmp_path)
    namespace = WORKFLOW_STATE_NAMESPACE.namespace
    object_key = WORKFLOW_STATE_NAMESPACE.require_default_object_key()

    with (
        EphemeralMasterKeyProvider(),
        activate_session(_session(_BUCKET_ID)),
        secure_object_repository_for_staged_bucket(_BUCKET_ID, database_file=database_file) as repo,
    ):
        assert repo.namespace_registry is STORAGE_NAMESPACE_REGISTRY
        repo.save_many(
            (
                SecureObjectWrite(
                    namespace=namespace,
                    object_key=object_key,
                    classification=WORKFLOW_STATE_NAMESPACE.sensitivity,
                    schema_version=WORKFLOW_STATE_NAMESPACE.schema_version,
                    written_at=_NOW,
                    payload=b"staged-revision-one",
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
    assert loaded.payload == b"staged-revision-one"
    # The staged file is a real database on disk, and it is NOT inside a bucket
    # root: publication is what moves it there.
    assert database_file.is_file()
    assert not (tmp_path / "buckets").exists()


def test_staged_repository_disposes_its_engine_on_exit(tmp_path: Path) -> None:
    """Engine lifetime is owned by the factory, so a caller cannot leak the pool.

    This is the property that makes the helper a genuine replacement for the
    direct construction it exists to retire -- a plain factory returning a
    repository would hand back an engine whose pooled connections nobody closes.

    The assertion is on ``dispose``'s real observable effect: it REPLACES the
    connection pool, releasing every pooled connection. It deliberately does
    not assert that the escaped repository stops working -- SQLAlchemy builds a
    fresh pool on the next use, so an engine remains usable after disposal and
    a "now it raises" test would simply be false.
    """
    database_file = _staging_database(tmp_path)

    with (
        EphemeralMasterKeyProvider(),
        activate_session(_session(_BUCKET_ID)),
        secure_object_repository_for_staged_bucket(_BUCKET_ID, database_file=database_file) as repo,
    ):
        engine = repo.engine
        # Take a connection so the pool is genuinely populated; disposing an
        # untouched pool would prove nothing about releasing connections.
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
        pool_before = engine.pool

    assert engine.pool is not pool_before, (
        "the staged repository's engine was not disposed on exit, so its pooled "
        "connections outlive the staging span the factory exists to bound"
    )


def test_staged_repository_refuses_a_session_serving_another_bucket(tmp_path: Path) -> None:
    """The session binding is enforced, not decorative.

    Staging runs inside the creating transaction, so the only session that may
    reach these rows is the one holding that profile's just-minted key. A
    session serving a different profile writing here would cross capsules.
    """
    database_file = _staging_database(tmp_path)

    with (
        EphemeralMasterKeyProvider(),
        activate_session(_session(_OTHER_BUCKET_ID)),
        secure_object_repository_for_staged_bucket(_BUCKET_ID, database_file=database_file) as repo,
        pytest.raises(StorageValidationError) as raised,
    ):
        repo.save(
            namespace=WORKFLOW_STATE_NAMESPACE.namespace,
            object_key=WORKFLOW_STATE_NAMESPACE.require_default_object_key(),
            classification=WORKFLOW_STATE_NAMESPACE.sensitivity,
            schema_version=WORKFLOW_STATE_NAMESPACE.schema_version,
            written_at=_NOW,
            payload=b"cross-capsule-write",
        )

    assert raised.value.translated_message == "errors.storage.runtime.not_ready"


def test_staged_repository_refuses_a_path_inside_an_unpublished_bucket(tmp_path: Path) -> None:
    """A staging path is not a licence to conjure the bucket root.

    Pointing the factory at ``buckets/<id>/`` must still meet the engine's
    refusal: a bucket exists only once its profile capsule is published, and
    creating the directory here would occupy the destination publication has
    to claim.
    """
    database_file = tmp_path / "buckets" / _BUCKET_ID / "db" / "cadrumo.db"

    with (
        EphemeralMasterKeyProvider(),
        activate_session(_session(_BUCKET_ID)),
        pytest.raises(StorageError) as raised,
        secure_object_repository_for_staged_bucket(_BUCKET_ID, database_file=database_file),
    ):
        pass

    assert "capsule is published" in str(raised.value)
    assert not (tmp_path / "buckets" / _BUCKET_ID).exists()

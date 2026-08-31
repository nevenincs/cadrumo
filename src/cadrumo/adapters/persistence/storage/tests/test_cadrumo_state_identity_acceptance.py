"""Cross-boundary acceptance proof for the Cadrumo persistence identity cut."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from .....core.config import Settings
from .....core.config_state_root import FormerProductStateError
from .....domain.buckets.errors import BucketImportError
from .....tests.secure_sql import isolated_runtime_profile
from ..bucket._export_header import ARCHIVE_SCHEMA_VERSION, ExportArchiveHeader
from ..bucket._sealed_archive_reader import read_sealed_archive
from ..bucket._sealed_archive_writer import write_sealed_archive
from ..errors import StorageValidationError
from ..runtime_repository import secure_object_repository_for_active_bucket
from ..secure_object_namespaces import AEAT_BROWSER_SESSION_NAMESPACE
from ..sql.engine import create_engine_from_settings, dispose_engine

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "74747474-7474-4474-8474-747474747474"
_INSTANT = datetime(2026, 7, 12, 18, 0, tzinfo=UTC)


def test_fresh_state_uses_one_cadrumo_identity_across_persistence_boundaries(tmp_path: Path) -> None:
    """Fresh root, SQL, session, namespace, and archive identities agree."""
    platform_base = tmp_path / "platform-data"
    storage_root = platform_base / "cadrumo" / "storage"
    settings = Settings(cadrumo_local_storage_root=storage_root, cadrumo_active_profile=None)
    # "cadrumo.db" is the independent oracle for the on-disk byte-identity this
    # acceptance test defends -- the point is that the canonical product name
    # actually landed on disk, not that the accessor agrees with itself.
    database_path = storage_root / "cadrumo.db"
    engine = create_engine_from_settings(settings)
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("select 1")
    finally:
        engine.dispose()
        dispose_engine(settings)

    session_path = Path(".cadrumo/auth/sessions") / f"{_BUCKET_ID}-certificate.json"
    case_root = tmp_path / "fresh-session-case"
    with isolated_runtime_profile(tmp_path=case_root, bucket_id=_BUCKET_ID):
        repository = secure_object_repository_for_active_bucket()
        repository.save(
            namespace=AEAT_BROWSER_SESSION_NAMESPACE.namespace,
            object_key=session_path.as_posix(),
            classification=AEAT_BROWSER_SESSION_NAMESPACE.sensitivity,
            schema_version=AEAT_BROWSER_SESSION_NAMESPACE.schema_version,
            written_at=_INSTANT,
            payload=b"canonical-session-envelope",
        )
        session_record = repository.load(
            AEAT_BROWSER_SESSION_NAMESPACE.namespace,
            session_path.as_posix(),
            expected_class=AEAT_BROWSER_SESSION_NAMESPACE.sensitivity,
            max_supported_version=AEAT_BROWSER_SESSION_NAMESPACE.schema_version,
        )
        session_namespaces = {record.namespace for record in repository.iter_all_records_raw()}

    archive_path = tmp_path / "profile.cadrumo-bucket.tar.gz"
    header = ExportArchiveHeader(
        product="cadrumo",
        bucket_id=_BUCKET_ID,
        manifest_digest="7" * 64,
        archive_schema_version=ARCHIVE_SCHEMA_VERSION,
        created_at=_INSTANT,
    )
    write_sealed_archive(archive_path, header=header, payload_bytes=b"encrypted-envelope")
    archive = read_sealed_archive(archive_path)

    assert storage_root == platform_base / "cadrumo" / "storage"
    assert database_path.is_file()
    assert session_path.as_posix().startswith(".cadrumo/auth/sessions/")
    assert session_record is not None
    assert session_record.payload == b"canonical-session-envelope"
    # The property is product identity, not a tally. This pinned the exact set
    # back when the fixture provisioned a bare bucket tree, so the row this test
    # wrote was the only one present. The fixture now publishes a real capsule
    # -- the only way a bucket can come into existence -- which legitimately
    # brings the profile record and the creation event with it, and re-pinning
    # the set would just re-encode whatever publication happens to write today.
    #
    # Asserted on the ROOT segment rather than on the absence of "aeat":
    # `cadrumo.outbound.aeat.auth.sessions` correctly carries the authority's
    # name in its path, because the referent there IS the tax authority. What
    # must never appear is a namespace ROOTED at the retired product name.
    assert AEAT_BROWSER_SESSION_NAMESPACE.namespace in session_namespaces
    assert session_namespaces, "the fresh bucket persisted nothing, so this proves no identity"
    assert all(namespace.split(".")[0] == "cadrumo" for namespace in session_namespaces), session_namespaces
    assert archive.header.product == "cadrumo"
    assert archive.payload_bytes == b"encrypted-envelope"
    assert not (platform_base / "aeat").exists()
    assert not (storage_root / "aeat.db").exists()
    assert not (tmp_path / "profile.aeat-bucket.tar.gz").exists()


def test_former_states_are_refused_without_mutation_or_canonical_creation(tmp_path: Path) -> None:
    """Former database, namespace, and bundle identities create no successor."""
    database_root = tmp_path / "former-database-case"
    former_database = database_root / "aeat.db"
    database_root.mkdir()
    former_database.write_bytes(b"former-database-bytes")
    with pytest.raises(FormerProductStateError):
        Settings(cadrumo_local_storage_root=database_root, cadrumo_active_profile=None)
    assert former_database.read_bytes() == b"former-database-bytes"
    # "cadrumo.db" is the independent oracle again: the refusal must not
    # silently materialise the canonical fallback name beside the former one.
    assert not (database_root / "cadrumo.db").exists()

    case_root = tmp_path / "former-namespace-case"
    with isolated_runtime_profile(tmp_path=case_root, bucket_id=_BUCKET_ID):
        repository = secure_object_repository_for_active_bucket()
        with pytest.raises(StorageValidationError):
            repository.save(
                namespace="aeat.outbound.aeat.auth.sessions",
                object_key="former-namespace",
                classification=AEAT_BROWSER_SESSION_NAMESPACE.sensitivity,
                schema_version=AEAT_BROWSER_SESSION_NAMESPACE.schema_version,
                written_at=_INSTANT,
                payload=b"former-namespace-bytes",
            )
        assert repository.exists(AEAT_BROWSER_SESSION_NAMESPACE.namespace, "former-namespace") is False
        assert all(
            not record.namespace.startswith(("aeat.", "aeat-test.", "aeat-tests."))
            for record in repository.iter_all_records_raw()
        )

    former_bundle = tmp_path / "former-bundle.aeat-bucket.tar.gz"
    former_bundle.write_bytes(b"former-bundle-bytes")
    with pytest.raises(BucketImportError):
        read_sealed_archive(former_bundle)
    assert former_bundle.read_bytes() == b"former-bundle-bytes"
    assert not (tmp_path / "former-bundle.cadrumo-bucket.tar.gz").exists()

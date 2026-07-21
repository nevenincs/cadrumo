"""Cross-boundary acceptance proof for the Cadrumo persistence identity cut."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from .....core import FormerProductStateError
from .....core.config import Settings
from .....domain.buckets import BucketImportError
from .....tests.secure_sql import isolated_runtime_profile
from .. import (
    AEAT_BROWSER_SESSION_NAMESPACE,
    StorageValidationError,
    create_engine_from_settings,
    dispose_engine,
    secure_object_repository_for_active_bucket,
)
from ..bucket import ExportArchiveHeader, read_sealed_archive, write_sealed_archive

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "74747474-7474-4474-8474-747474747474"
_INSTANT = datetime(2026, 7, 12, 18, 0, tzinfo=UTC)


def test_fresh_state_uses_one_cadrumo_identity_across_persistence_boundaries(tmp_path: Path) -> None:
    """Fresh root, SQL, session, namespace, and archive identities agree."""
    platform_base = tmp_path / "platform-data"
    storage_root = platform_base / "cadrumo" / "storage"
    settings = Settings(cadrumo_local_storage_root=storage_root, cadrumo_active_profile=None)
    database_path = storage_root / "cadrumo.db"
    engine = create_engine_from_settings(settings)
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("select 1")
    finally:
        engine.dispose()
        dispose_engine(settings)

    session_path = Path(".cadrumo/auth/sessions") / f"{_BUCKET_ID}-certificate.json"
    with isolated_runtime_profile(tmp_path=tmp_path / "fresh-session-case", bucket_id=_BUCKET_ID):
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
        recovery_wrap_present=False,
        archive_schema_version=3,
        created_at=_INSTANT,
    )
    write_sealed_archive(archive_path, header=header, payload_envelope_bytes=b"encrypted-envelope")
    archive = read_sealed_archive(archive_path)

    assert storage_root == platform_base / "cadrumo" / "storage"
    assert database_path.is_file()
    assert session_path.as_posix().startswith(".cadrumo/auth/sessions/")
    assert session_record is not None
    assert session_record.payload == b"canonical-session-envelope"
    assert session_namespaces == {"cadrumo.outbound.aeat.auth.sessions"}
    assert archive.header.product == "cadrumo"
    assert archive.payload_envelope_bytes == b"encrypted-envelope"
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
    assert not (database_root / "cadrumo.db").exists()

    with isolated_runtime_profile(tmp_path=tmp_path / "former-namespace-case", bucket_id=_BUCKET_ID):
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

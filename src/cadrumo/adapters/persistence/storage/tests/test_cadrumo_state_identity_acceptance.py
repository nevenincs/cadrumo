"""Cross-boundary acceptance proof for the Cadrumo persistence identity cut."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from .....core._config_state_root import FormerProductStateError, StateRootInputs, resolve_state_root
from .....core.auth_session_keys import aeat_auth_session_storage_state_path
from .....core.config import Settings
from .....tests.secure_sql import isolated_runtime_profile
from ....outbound.aeat.auth import _session_store
from .. import AEAT_BROWSER_SESSION_NAMESPACE, StorageValidationError
from ..bucket import ExportArchiveHeader
from ..bucket._sealed_archive_errors import SealedArchiveHeaderError
from ..bucket._sealed_archive_reader import read_sealed_archive
from ..bucket._sealed_archive_writer import write_sealed_archive
from ..runtime_repository import secure_object_repository_for_active_bucket
from ..sql import create_engine_from_settings, dispose_engine

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "74747474-7474-4474-8474-747474747474"
_INSTANT = datetime(2026, 7, 12, 18, 0, tzinfo=UTC)


def test_fresh_state_uses_one_cadrumo_identity_across_persistence_boundaries(tmp_path: Path) -> None:
    """Fresh root, SQL, session, namespace, and archive identities agree."""
    platform_base = tmp_path / "platform-data"
    resolution = resolve_state_root(
        StateRootInputs(
            project_root_candidate=tmp_path / "site-packages" / "cadrumo",
            platform="win32",
            environ={"LOCALAPPDATA": str(platform_base)},
            home=tmp_path / "home",
        ),
    )
    settings = Settings(cadrumo_local_storage_root=resolution.storage_root, cadrumo_active_profile=None)
    database_path = resolution.storage_root / "cadrumo.db"
    engine = create_engine_from_settings(settings)
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("select 1")
    finally:
        engine.dispose()
        dispose_engine(settings)

    session_path = aeat_auth_session_storage_state_path(_BUCKET_ID, "certificate")
    with isolated_runtime_profile(tmp_path=tmp_path / "fresh-session-case", bucket_id=_BUCKET_ID):
        _session_store.save(session_path, storage_state={"cookies": [], "origins": []}, metadata={})
        session_record = _session_store.load(session_path)
        session_namespaces = {
            record.namespace for record in secure_object_repository_for_active_bucket().iter_all_records_raw()
        }

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

    assert resolution.storage_root == platform_base / "cadrumo" / "storage"
    assert database_path.is_file()
    assert session_path.as_posix().startswith(".cadrumo/auth/sessions/")
    assert session_record is not None
    assert session_namespaces == {"cadrumo.outbound.aeat.auth.sessions"}
    assert archive.header.product == "cadrumo"
    assert archive.payload_envelope_bytes == b"encrypted-envelope"
    assert not (platform_base / "aeat").exists()
    assert not (resolution.storage_root / "aeat.db").exists()
    assert not (tmp_path / "profile.aeat-bucket.tar.gz").exists()


def test_former_states_are_refused_without_mutation_or_canonical_creation(tmp_path: Path) -> None:
    """Every recognizable former identity stays opaque and creates no successor."""
    platform_base = tmp_path / "former-root-case"
    former_root_marker = platform_base / "aeat" / "storage" / "root.bin"
    former_root_marker.parent.mkdir(parents=True)
    former_root_marker.write_bytes(b"former-root-bytes")
    with pytest.raises(FormerProductStateError):
        resolve_state_root(
            StateRootInputs(
                project_root_candidate=tmp_path / "installed" / "cadrumo",
                platform="win32",
                environ={"LOCALAPPDATA": str(platform_base)},
                home=tmp_path / "home",
            ),
        )
    assert former_root_marker.read_bytes() == b"former-root-bytes"
    assert not (platform_base / "cadrumo").exists()

    database_root = tmp_path / "former-database-case"
    former_database = database_root / "aeat.db"
    database_root.mkdir()
    former_database.write_bytes(b"former-database-bytes")
    with pytest.raises(FormerProductStateError):
        Settings(cadrumo_local_storage_root=database_root, cadrumo_active_profile=None)
    assert former_database.read_bytes() == b"former-database-bytes"
    assert not (database_root / "cadrumo.db").exists()

    with isolated_runtime_profile(tmp_path=tmp_path / "former-session-case", bucket_id=_BUCKET_ID):
        current_session = aeat_auth_session_storage_state_path(_BUCKET_ID, "certificate")
        former_session = Path(".aeat/auth/sessions") / current_session.name
        repository = secure_object_repository_for_active_bucket()
        repository.save(
            namespace=AEAT_BROWSER_SESSION_NAMESPACE.namespace,
            object_key=former_session.as_posix(),
            classification=AEAT_BROWSER_SESSION_NAMESPACE.sensitivity,
            schema_version=AEAT_BROWSER_SESSION_NAMESPACE.schema_version,
            written_at=_INSTANT,
            payload=b"former-session-bytes",
        )
        with pytest.raises(_session_store.FormerProductAuthSessionStateError):
            _session_store.save(current_session, storage_state={"cookies": [], "origins": []}, metadata={})
        former_record = repository.load(
            AEAT_BROWSER_SESSION_NAMESPACE.namespace,
            former_session.as_posix(),
            expected_class=AEAT_BROWSER_SESSION_NAMESPACE.sensitivity,
            max_supported_version=AEAT_BROWSER_SESSION_NAMESPACE.schema_version,
        )
        assert former_record is not None
        assert former_record.payload == b"former-session-bytes"
        assert repository.exists(AEAT_BROWSER_SESSION_NAMESPACE.namespace, current_session.as_posix()) is False
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
    with pytest.raises(SealedArchiveHeaderError):
        read_sealed_archive(former_bundle)
    assert former_bundle.read_bytes() == b"former-bundle-bytes"
    assert not (tmp_path / "former-bundle.cadrumo-bucket.tar.gz").exists()

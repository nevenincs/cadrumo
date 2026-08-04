"""Pytest fixtures for registry CLI tests."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....adapters.persistence.storage.master_key import BucketSession, activate_session
from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....core.config import override_settings
from ....tests.secure_sql import dev_test_database_password, isolated_runtime_profile
from ._registry_cli_support import _BUCKET_ID, _clear_cli_env, _set_cli_env

_SESSION_OPENED_AT = datetime(2099, 5, 28, 15, 55, tzinfo=UTC)


@pytest.fixture(scope="module", autouse=True)
def _isolated_registry_cli_backend(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    tmp_path = tmp_path_factory.mktemp("registry-cli")
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as runtime:
        _set_cli_env(
            {
                "CADRUMO_LOCAL_STORAGE_ROOT": str(runtime.storage_root),
                "CADRUMO_ACTIVE_PROFILE": runtime.bucket_id,
                "CADRUMO_SECRET_STORE_BACKEND": "file",
                "CADRUMO_SECRET_STORE_DIR": str(tmp_path / "fallback-store"),
                "CADRUMO_BLOB_STORE_DIR": str(tmp_path / "blobs"),
                "CADRUMO_AUDIT_DIR": str(tmp_path / "audit"),
                "CADRUMO_SECRET_PASSPHRASE": dev_test_database_password(runtime.settings),
                "CADRUMO_OUTPUT_LANGUAGE": "en",
            },
        )
        yield
    _clear_cli_env()


@pytest.fixture(autouse=True)
def _isolated_secure_backend(tmp_path: Path) -> Iterator[None]:
    """Point encrypted SQL runtime at a per-test active bucket."""

    with (
        override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile=_BUCKET_ID) as settings,
        activate_session(_session()),
    ):
        dispose_engine(settings)
        try:
            yield
        finally:
            dispose_engine(settings)


def _session() -> BucketSession:
    return BucketSession.open(
        bucket_id=_BUCKET_ID,
        kek=b"k" * 32,
        dek=b"d" * 32,
        idle_minutes=15,
        opened_at=_SESSION_OPENED_AT,
    )

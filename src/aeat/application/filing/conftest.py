"""Shared fixtures for application/filing tests.

Centralises the encrypted-storage backend setup (master-key provider +
SQL engine + secret store override + disposal teardown) so the per-file
copies in ``_test_repository``, ``_test_history_repository``, and
``_test_complementaria_repository`` collapse into one autouse conftest
fixture.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ...adapters.persistence.storage import (
    EncryptedBlobStore,
    EphemeralMasterKeyProvider,
    SecretStore,
    override_secret_store,
)
from ...adapters.persistence.storage.sql.engine import dispose_engine


@pytest.fixture(autouse=True)
def _patch_secure_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    dispose_engine()
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{tmp_path / 'aeat.db'}")
    provider = EphemeralMasterKeyProvider()
    with provider:
        blob_store = EncryptedBlobStore(
            root_dir=tmp_path / "blobs",
            master_key_provider=provider,
        )
        secret_store = SecretStore(
            store_dir=tmp_path / "secrets",
            blob_store=blob_store,
            master_key_provider=provider,
        )
        override_secret_store(secret_store)
        try:
            yield
        finally:
            override_secret_store(None)
            dispose_engine()

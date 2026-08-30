"""Fixture visibility boundary for secret-store tests."""

import secrets
from collections.abc import Iterator
from pathlib import Path

import pytest

from ......tests.master_key import EphemeralMasterKeyProvider
from ...blob_store import EncryptedBlobStore
from ...crypto.aead import KEY_SIZE
from ...tests.fixed_master_key import fixed_master_key  # noqa: F401
from ..store import SecretStore


@pytest.fixture
def store(tmp_path: Path) -> Iterator[SecretStore]:
    provider = EphemeralMasterKeyProvider(key=secrets.token_bytes(KEY_SIZE))
    blob_store = EncryptedBlobStore(root_dir=tmp_path / "store-root", master_key_provider=provider)
    yield SecretStore(
        store_dir=tmp_path / "fallback-store",
        blob_store=blob_store,
        master_key_provider=provider,
    )

"""Fixture visibility boundary for blob-store tests."""

import secrets
from collections.abc import Iterator
from pathlib import Path

import pytest

from ......tests.master_key import EphemeralMasterKeyProvider
from ...crypto.aead import KEY_SIZE
from ...tests.fixed_master_key import fixed_master_key  # noqa: F401
from .._blob_store import EncryptedBlobStore


@pytest.fixture
def store(tmp_path: Path) -> Iterator[EncryptedBlobStore]:
    provider = EphemeralMasterKeyProvider(key=secrets.token_bytes(KEY_SIZE))
    yield EncryptedBlobStore(root_dir=tmp_path / "blob-store", master_key_provider=provider)

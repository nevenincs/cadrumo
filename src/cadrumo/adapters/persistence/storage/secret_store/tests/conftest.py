"""Fixture visibility boundary for secret-store tests."""

import secrets
from collections.abc import Iterator
from pathlib import Path

import pytest

from ...blob_store.blob_store import EncryptedBlobStore
from ...crypto.aead import KEY_SIZE
from ...tests.ephemeral_bucket_session import EphemeralBucketSession
from ...tests.fixed_master_key import fixed_master_key
from ..store import SecretStore

__all__ = ["fixed_master_key"]


@pytest.fixture
def store(tmp_path: Path) -> Iterator[SecretStore]:
    with EphemeralBucketSession(key=secrets.token_bytes(KEY_SIZE)):
        yield SecretStore(
            store_dir=tmp_path / "fallback-store",
            blob_store=EncryptedBlobStore(root_dir=tmp_path / "store-root"),
        )

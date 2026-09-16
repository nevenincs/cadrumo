"""Fixture visibility boundary for blob-store tests."""

import secrets
from collections.abc import Iterator
from pathlib import Path

import pytest

from ...crypto.aes_gcm import KEY_SIZE
from ...tests.ephemeral_bucket_session import EphemeralBucketSession
from ...tests.fixed_master_key import fixed_master_key
from ..blob_store import EncryptedBlobStore

__all__ = ["fixed_master_key"]


@pytest.fixture
def store(tmp_path: Path) -> Iterator[EncryptedBlobStore]:
    with EphemeralBucketSession(key=secrets.token_bytes(KEY_SIZE)):
        yield EncryptedBlobStore(root_dir=tmp_path / "blob-store")

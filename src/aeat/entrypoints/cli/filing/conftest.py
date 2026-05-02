"""Shared filing-CLI test fixtures.

Installs an :class:`EphemeralMasterKeyProvider` for every test that
hits the CLI's ciphertext-at-rest persistence path so the
:class:`FilingDraftRepository` round-trips against a real on-disk
secret store rather than the production master key.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _patch_master_key(tmp_path: Path) -> Iterator[None]:
    from ....adapters.persistence.storage import (
        EncryptedBlobStore,
        EphemeralMasterKeyProvider,
        SecretStore,
        override_master_key_provider,
        override_secret_store,
    )

    provider = EphemeralMasterKeyProvider()
    blob_store = EncryptedBlobStore(
        root_dir=tmp_path / "blobs",
        master_key_provider=provider,
    )
    secret_store = SecretStore(
        store_dir=tmp_path / "secrets",
        blob_store=blob_store,
        master_key_provider=provider,
    )
    override_master_key_provider(provider)
    override_secret_store(secret_store)
    try:
        yield
    finally:
        override_master_key_provider(None)
        override_secret_store(None)


@pytest.fixture(autouse=True)
def _force_english_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin CLI output to English so test assertions stay readable.

    The production default is ``es``; this fixture only affects
    test output, not runtime behaviour.
    """
    monkeypatch.setenv("AEAT_OUTPUT_LANGUAGE", "en")

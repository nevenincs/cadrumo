"""Shared review-package test fixtures.

Every test in :mod:`aeat.application.review` that persists a draft
through the ciphertext-at-rest
:class:`aeat.domain.filing.FilingDraftRepository` needs an
:class:`aeat.adapters.persistence.storage.EphemeralMasterKeyProvider`
installed via
:func:`aeat.adapters.persistence.storage.override_master_key_provider`.

Hosting the autouse fixture in this conftest keeps individual test
modules free of crypto-bootstrapping boilerplate.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _patch_master_key(tmp_path: Path) -> Iterator[None]:
    from ...adapters.persistence.storage import (
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

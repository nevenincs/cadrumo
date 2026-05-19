"""Shared review-package test fixtures.

Every test in :mod:`aeat.application.review` that persists a draft
through the ciphertext-at-rest
:class:`aeat.domain.filing.FilingDraftRepository` needs an
:class:`aeat.adapters.persistence.storage.EphemeralMasterKeyProvider`
active for the duration of the test (via its context-manager
interface).

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
    with provider:
        override_secret_store(secret_store)
        try:
            yield
        finally:
            override_secret_store(None)

"""Shared review-package test fixtures."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....core.config import override_settings
from ....core.config_support import SecretStoreBackend


@pytest.fixture(autouse=True)
def isolated_review_storage(tmp_path: Path) -> Iterator[None]:
    """Keep review tests on an isolated, explicitly unsecured test root."""
    with override_settings(
        cadrumo_local_storage_root=tmp_path,
        cadrumo_active_profile=None,
        cadrumo_secret_store_backend=SecretStoreBackend.UNSECURED,
        cadrumo_secret_passphrase=None,
    ):
        yield

"""Shared review-package test fixtures."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import SecretStr

from ...adapters.persistence.storage.sql import dispose_engine
from ...core.config import SecretStoreBackend, override_settings
from ...tests.secure_sql import dev_test_database_password


@pytest.fixture(autouse=True)
def _file_backed_review_storage(tmp_path: Path) -> Iterator[None]:
    with override_settings(
        aeat_local_storage_root=tmp_path,
        aeat_active_profile=None,
        aeat_secret_store_backend=SecretStoreBackend.FILE,
        aeat_secret_passphrase=SecretStr(dev_test_database_password()),
    ) as settings:
        dispose_engine(settings)
        try:
            yield
        finally:
            dispose_engine(settings)

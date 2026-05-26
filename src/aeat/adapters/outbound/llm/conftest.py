"""Test isolation for LLM secure-object persistence."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....core.config import load_settings, override_settings
from ...persistence.storage import EphemeralMasterKeyProvider
from ...persistence.storage.sql.engine import dispose_engine


@pytest.fixture(autouse=True)
def _secure_object_test_backend(tmp_path: Path) -> Iterator[None]:
    """Route LLM cache and usage persistence through a per-test encrypted DB."""

    with override_settings(
        aeat_local_storage_root=tmp_path,
        aeat_active_profile="llm-test",
        aeat_secret_passphrase=load_settings().aeat_dev_test_database_password,
    ) as settings:
        dispose_engine(settings)
        with EphemeralMasterKeyProvider():
            try:
                yield
            finally:
                dispose_engine(settings)

"""Test isolation for LLM secure-object persistence."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ...persistence.storage import EphemeralMasterKeyProvider, override_master_key_provider
from ...persistence.storage.sql import dispose_engine


@pytest.fixture(autouse=True)
def _secure_object_test_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Route LLM cache and usage persistence through a per-test encrypted DB."""

    dispose_engine()
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}")
    override_master_key_provider(EphemeralMasterKeyProvider())
    try:
        yield
    finally:
        override_master_key_provider(None)
        dispose_engine()

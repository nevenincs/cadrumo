"""Shared fixtures for application/filing tests.

Centralises the encrypted-storage backend setup (master-key provider +
SQL engine + secret store override + disposal teardown) so the per-file
copies in ``_test_repository``, ``_test_history_repository``, and
``_test_complementaria_repository`` collapse into one autouse conftest
fixture.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ...adapters.persistence.storage.master_key._active_session import activate_session
from ...adapters.persistence.storage.master_key._bucket_session import BucketSession
from ...adapters.persistence.storage.sql.engine import dispose_engine
from ...core.config import override_settings

_BUCKET_ID = "filing-test"
_KEK = b"k" * 32
_DEK = b"d" * 32


def _session() -> BucketSession:
    return BucketSession.open(
        bucket_id=_BUCKET_ID,
        kek=_KEK,
        dek=_DEK,
        idle_minutes=15,
        opened_at=datetime.now(UTC),
    )


@pytest.fixture(autouse=True)
def _active_bucket_runtime(tmp_path: Path) -> Iterator[None]:
    dispose_engine()
    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_active_profile=_BUCKET_ID),
        activate_session(_session()),
    ):
        try:
            yield
        finally:
            dispose_engine()

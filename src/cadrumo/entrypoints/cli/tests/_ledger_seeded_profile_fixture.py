"""Canonical seeded-profile fixtures for ledger CLI journeys."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....application.workflow import WorkflowState
from ....core.config import override_settings
from ....tests.profile_capsule import open_test_profile_session
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile

__all__ = ["_isolated_backend"]

_BUCKET_ID = "00000000-0000-4000-8000-000000000000"


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    dispose_engine()
    with (
        override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_output_language="en"),
        isolated_profile_storage_root(tmp_path=tmp_path),
        open_test_profile_session(_BUCKET_ID),
    ):
        try:
            register_minimal_profile(WorkflowState(), profile_id=_BUCKET_ID)
            yield
        finally:
            dispose_engine()

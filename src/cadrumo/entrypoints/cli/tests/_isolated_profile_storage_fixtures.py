"""Canonical profile-storage isolation fixtures for CLI test modules."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....tests.active_profile_isolated_backend_fixture import active_profile_isolated_backend_fixture
from ....tests.secure_sql import isolated_sessionless_storage_root


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path: Path) -> Iterator[None]:
    with isolated_sessionless_storage_root(tmp_path=tmp_path):
        yield


active_profile_isolated_backend = active_profile_isolated_backend_fixture()


llm_profile_isolated_backend = active_profile_isolated_backend_fixture(
    bucket_id="00000000-0000-4000-8000-000000000000",
    settings_overrides={"cadrumo_output_language": "en"},
)


_LIVE_FX_BACKEND: dict[str, object] = {
    "bucket_id": "00000000-0000-4000-8000-000000000000",
    "dispose_engine_around": True,
    "settings_overrides": {"cadrumo_output_language": "en", "cadrumo_live_tests_enabled": "1"},
}

live_fx_isolated_backend = active_profile_isolated_backend_fixture(**_LIVE_FX_BACKEND)  # type: ignore[arg-type]

#: The same seeded world, built once per file instead of once per test, for
#: suites whose every test only reads it. The parameters are shared with the
#: function-scoped fixture above so the two cannot drift apart.
live_fx_isolated_backend_per_module = active_profile_isolated_backend_fixture(
    **_LIVE_FX_BACKEND,  # type: ignore[arg-type]
    scope="module",
)

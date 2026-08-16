"""Canonical profile-storage isolation fixtures for CLI test modules."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Literal

import pytest

from ....tests.active_profile_isolated_backend_fixture import active_profile_isolated_backend_fixture
from ....tests.secure_sql import isolated_sessionless_storage_root
from ....tests.seeded_isolated_backend_fixture import seeded_isolated_backend_fixture


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path: Path) -> Iterator[None]:
    with isolated_sessionless_storage_root(tmp_path=tmp_path):
        yield


active_profile_isolated_backend = active_profile_isolated_backend_fixture()


llm_profile_isolated_backend = active_profile_isolated_backend_fixture(
    bucket_id="00000000-0000-4000-8000-000000000000",
    settings_overrides={"cadrumo_output_language": "en"},
)


_LIVE_FX_BUCKET_ID = "00000000-0000-4000-8000-000000000000"
_LIVE_FX_SETTINGS = {"cadrumo_output_language": "en", "cadrumo_live_tests_enabled": "1"}


def _live_fx_backend(*, scope: Literal["function", "module"]) -> Callable[..., Iterator[None]]:
    """Build the live-FX backend fixture at the requested scope.

    Both scopes are built here rather than from two literal call sites so the
    bucket id and settings overrides cannot drift apart between them.
    """
    return active_profile_isolated_backend_fixture(
        bucket_id=_LIVE_FX_BUCKET_ID,
        dispose_engine_around=True,
        settings_overrides=_LIVE_FX_SETTINGS,
        scope=scope,
    )


live_fx_isolated_backend = _live_fx_backend(scope="function")

#: The same seeded world, built once per file instead of once per test, for
#: suites whose every test only reads it.
live_fx_isolated_backend_per_module = _live_fx_backend(scope="module")


def live_fx_seeded_backend(
    *,
    seed: Callable[[], None],
) -> tuple[Callable[..., Iterator[Path]], Callable[..., Iterator[None]]]:
    """Build the live-FX (origin, per-test) pair for a suite with costly seeding.

    For suites that DO mutate, where the module-scoped variant above would let
    one test's classify or split reach the next. Each test still gets its own
    storage root; only the seeding is shared, as a copy.
    """
    return seeded_isolated_backend_fixture(
        seed=seed,
        bucket_id=_LIVE_FX_BUCKET_ID,
        settings_overrides=_LIVE_FX_SETTINGS,
    )

"""Canonical profile-storage isolation fixtures for CLI test modules."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import TypedDict

import pytest

from ....adapters.persistence.storage.tests.active_profile_isolated_backend_fixture import (
    active_profile_isolated_backend_fixture,
    module_scoped_profile_isolated_backend_fixture,
)
from ....adapters.persistence.storage.tests.secure_sql import isolated_sessionless_storage_root
from ....adapters.persistence.storage.tests.seeded_isolated_backend_fixture import seeded_isolated_backend_fixture


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path: Path) -> Iterator[None]:
    with isolated_sessionless_storage_root(tmp_path=tmp_path):
        yield


active_profile_isolated_backend = active_profile_isolated_backend_fixture()


llm_profile_isolated_backend = active_profile_isolated_backend_fixture(
    bucket_id="00000000-0000-4000-8000-000000000000",
    settings_overrides={"cadrumo_output_language": "en"},
)


_RECORDED_FX_BUCKET_ID = "00000000-0000-4000-8000-000000000000"
_RECORDED_FX_SETTINGS = {"cadrumo_output_language": "en"}


class _RecordedFxBackendArguments(TypedDict):
    bucket_id: str
    dispose_engine_around: bool
    settings_overrides: dict[str, str]


#: The shared arguments both recorded-FX bindings below are built from. They are
#: module constants rather than a wrapper's parameters: what must not drift
#: between the two scopes is these VALUES, and naming them once achieves that
#: without a function that returns a different fixture per call -- a shape the
#: static fixture census cannot resolve.
_RECORDED_FX_BACKEND_ARGUMENTS: _RecordedFxBackendArguments = {
    "bucket_id": _RECORDED_FX_BUCKET_ID,
    "dispose_engine_around": True,
    "settings_overrides": _RECORDED_FX_SETTINGS,
}

recorded_fx_isolated_backend = active_profile_isolated_backend_fixture(**_RECORDED_FX_BACKEND_ARGUMENTS)

#: The same seeded world, built once per file instead of once per test, for
#: suites whose every test only reads it.
recorded_fx_isolated_backend_per_module = module_scoped_profile_isolated_backend_fixture(
    **_RECORDED_FX_BACKEND_ARGUMENTS,
)


def recorded_fx_seeded_backend(
    *,
    seed: Callable[[], None],
) -> tuple[Callable[..., Iterator[Path]], Callable[..., Iterator[None]]]:
    """Build the recorded-FX (origin, per-test) pair for a suite with costly seeding.

    For suites that DO mutate, where the module-scoped variant above would let
    one test's classify or split reach the next. Each test still gets its own
    storage root; only the seeding is shared, as a copy.
    """
    return seeded_isolated_backend_fixture(
        seed=seed,
        bucket_id=_RECORDED_FX_BUCKET_ID,
        settings_overrides=_RECORDED_FX_SETTINGS,
    )

"""Registry loader cache isolation under pytest (the #44 test-isolation fix).

The loader's cross-process ``/tmp`` ``aeat_registry_*.pkl`` disk pickle is keyed by
file mtime and SHARED across pytest-xdist worker processes, so a parallel ``-n`` run
could serve a stale/transient compiled registry from one worker to another (the #44
isolation gap that flaked the M303-2009 ledger tests under the P05 sweep). The loader
now skips that disk pickle under pytest -- ``registry_disk_cache_enabled()`` is
``False`` whenever ``PYTEST_CURRENT_TEST`` / ``PYTEST_XDIST_WORKER`` is set -- relying
on the per-process ``lru_cache`` for in-run perf so each worker compiles from the
current TOML.

These tests pin that invariant: the gate is OFF in the test environment (so no
cross-worker stale-pickle race is possible), and removing the pytest env markers
restores the production path (so the gate is genuine pytest-detection, not an
unconditional disable). They read the real gate -- no mocks, no tautology.
"""

from __future__ import annotations

import os

import pytest

from .....tests.env_scope import scoped_env_var
from .._loader import registry_disk_cache_enabled

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_registry_disk_cache_disabled_under_pytest() -> None:
    """The shared ``/tmp`` disk pickle is gated OFF whenever pytest is running.

    ``PYTEST_CURRENT_TEST`` is set by pytest during every test phase, so the gate
    must report the disk cache disabled here -- the invariant that removes the
    cross-worker stale-pickle race the #44 root-cause identified.
    """
    assert "PYTEST_CURRENT_TEST" in os.environ, "sanity: this test runs under pytest"
    assert registry_disk_cache_enabled() is False


def test_registry_disk_cache_enabled_without_pytest_markers() -> None:
    """With the pytest env markers removed, the production disk cache is ENABLED.

    Proves the gate is genuine pytest-detection (not an unconditional disable):
    clearing ``PYTEST_CURRENT_TEST`` and ``PYTEST_XDIST_WORKER`` restores the
    production path, so production keeps its startup-time registry disk cache.
    """
    with scoped_env_var("PYTEST_CURRENT_TEST", None), scoped_env_var("PYTEST_XDIST_WORKER", None):
        assert registry_disk_cache_enabled() is True

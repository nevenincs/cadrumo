"""Registry loader cache isolation under pytest (the #44 test-isolation fix).

The loader's cross-process ``/tmp`` ``aeat_registry_*.pkl`` disk pickle is keyed by
file mtime and SHARED across pytest-xdist worker processes, so a parallel ``-n`` run
could serve a stale/transient compiled registry from one worker to another (the #44
isolation gap that flaked the M303-2009 ledger tests under the P05 sweep). The loader
now skips that disk pickle under pytest -- including collection before
``PYTEST_CURRENT_TEST`` is set -- relying on the per-process ``lru_cache`` for
in-run perf so each worker compiles from the current TOML.

These tests pin that invariant: the gate is OFF in the test environment (so no
cross-worker stale-pickle race is possible), and removing the pytest env markers
restores the production path (so the gate is genuine pytest-detection, not an
unconditional disable). They read the real gate -- no mocks, no tautology.

The bundled-tree fingerprint TTL tests below pin a related but distinct
invariant: the fingerprint cache's directory-mtime walk is only skippable for
the package-bundled, read-only registry tree, never for a mutable authoring
tree (a ``tmp_path`` synthetic registry, or any path other than the bundled
root), so a peer's live TOML edit in this shared worktree is never masked by
an overlong TTL window.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from .....core.resources import bundled_path
from .._loader import (
    _collect_registry_tree_fingerprints,
    clear_fingerprint_cache,
    is_bundled_registry_root,
    registry_disk_cache_enabled,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_registry_disk_cache_disabled_under_pytest() -> None:
    """The shared ``/tmp`` disk pickle is gated OFF whenever pytest is running.

    The pytest process itself is enough to disable the gate, including collection
    before ``PYTEST_CURRENT_TEST`` is present -- the invariant that removes the
    cross-worker stale-pickle race the #44 root-cause identified.
    """
    assert "PYTEST_CURRENT_TEST" in os.environ, "sanity: this test runs under pytest"
    assert registry_disk_cache_enabled() is False


def test_registry_disk_cache_enabled_without_pytest_markers() -> None:
    """With the pytest env markers removed, the production disk cache is ENABLED.

    Proves the gate is genuine pytest-detection (not an unconditional disable):
    a clean child interpreter without pytest loaded and without pytest env markers
    restores the production path, so production keeps its startup-time registry disk cache.
    """
    env = os.environ.copy()
    for name in ("PYTEST_CURRENT_TEST", "PYTEST_XDIST_WORKER", "PYTEST_VERSION"):
        env.pop(name, None)

    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from aeat.domain.calculations.registry._loader import registry_disk_cache_enabled; "
                "print(registry_disk_cache_enabled())"
            ),
        ],
        check=True,
        capture_output=True,
        env=env,
        text=True,
    )
    assert completed.stdout.strip() == "True"


def test_is_bundled_registry_root_identifies_the_real_bundled_tree() -> None:
    """The predicate recognises the package-bundled registry root by resolved path."""
    bundled_root = bundled_path("registry", "aeat").resolve()
    assert is_bundled_registry_root(bundled_root) is True


def test_is_bundled_registry_root_rejects_a_mutable_authoring_tree(tmp_path: Path) -> None:
    """A ``tmp_path`` synthetic registry is never mistaken for the bundled tree.

    This is the safety half of the bundled-TTL win: a mutable authoring tree
    (a test fixture here, but structurally the same shape as a dev checkout
    path passed explicitly) must never receive the longer bundled TTL, or a
    concurrent edit to it would go undetected for the longer window.
    """
    registry_root = tmp_path / "registry" / "aeat"
    registry_root.mkdir(parents=True)
    assert is_bundled_registry_root(registry_root) is False
    assert is_bundled_registry_root(registry_root.resolve()) is False


def test_bundled_tree_fingerprint_cache_hit_skips_the_directory_walk() -> None:
    """A same-process bundled-tree fingerprint call within the TTL reuses the cached tuple.

    Proves the real behavior (not a mock): two fingerprint calls milliseconds
    apart on the bundled tree return the SAME tuple object, which is only
    possible when the second call short-circuited before rebuilding the
    fingerprint list -- i.e. it skipped the directory-mtime walk entirely
    rather than recomputing it to compare against the cached copy.
    """
    clear_fingerprint_cache()
    bundled_root = bundled_path("registry", "aeat").resolve()
    assert is_bundled_registry_root(bundled_root) is True

    first = _collect_registry_tree_fingerprints(bundled_root)
    second = _collect_registry_tree_fingerprints(bundled_root)
    assert second is first, "a bundled-tree cache hit must reuse the cached fingerprint tuple, not rebuild it"


def test_bundled_tree_fingerprint_cache_survives_past_the_mutable_tree_ttl() -> None:
    """The bundled tree's TTL window outlives the strict mutable-tree window.

    Sleeping past the 1-second mutable-tree TTL and then re-requesting the
    bundled tree's fingerprint must still hit the cache (real elapsed time,
    no mocked clock), proving the bundled tree genuinely gets a longer TTL
    rather than merely tolerating a race on an unmodified test machine.
    """
    clear_fingerprint_cache()
    bundled_root = bundled_path("registry", "aeat").resolve()

    first = _collect_registry_tree_fingerprints(bundled_root)
    time.sleep(1.2)
    second = _collect_registry_tree_fingerprints(bundled_root)
    assert second is first, "the bundled tree's TTL must outlive the strict 1-second mutable-tree window"

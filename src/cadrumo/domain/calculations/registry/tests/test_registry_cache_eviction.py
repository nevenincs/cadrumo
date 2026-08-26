"""Fingerprint-count eviction for the registry disk-cache pickles.

One pickle accumulates per registry-tree fingerprint, so the cache directory is
bounded by pruning the oldest pickles beyond
``cadrumo_registry_disk_cache_max_entries`` after each write. These tests
exercise the real prune helper against real files on disk.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pytest

from .....core.config import override_settings
from .....core.directory_scan import scan_directory
from .._compiled_cache import _evict_stale_registry_pickles
from ..loader_cache import registry_disk_cache_max_entries

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_LOGGER = logging.getLogger(__name__)


def _write_pickle(directory: Path, name: str, mtime_ns: int) -> Path:
    path = directory / name
    path.write_bytes(b"payload")
    os.utime(path, ns=(mtime_ns, mtime_ns))
    return path


def test_max_entries_reads_the_setting() -> None:
    with override_settings(cadrumo_registry_disk_cache_max_entries=3):
        assert registry_disk_cache_max_entries() == 3


def test_eviction_keeps_newest_and_prunes_oldest(tmp_path: Path) -> None:
    base = 1_000_000_000
    kept_newest = [_write_pickle(tmp_path, f"cadrumo_registry_{i}.pkl", base + i) for i in range(5)]

    with override_settings(cadrumo_registry_disk_cache_max_entries=3):
        _evict_stale_registry_pickles(tmp_path, logger=_LOGGER)

    surviving = set(scan_directory(tmp_path, pattern="cadrumo_registry_*.pkl"))
    # The three newest (largest mtime) survive; the two oldest are pruned.
    assert surviving == set(kept_newest[2:])
    assert not kept_newest[0].exists()
    assert not kept_newest[1].exists()


def test_eviction_ignores_unrelated_files(tmp_path: Path) -> None:
    base = 2_000_000_000
    _write_pickle(tmp_path, "cadrumo_registry_a.pkl", base + 1)
    foreign = tmp_path / "aeat_registry_legacy.pkl"
    foreign.write_bytes(b"legacy")
    unrelated = tmp_path / "notes.txt"
    unrelated.write_bytes(b"keep me")

    with override_settings(cadrumo_registry_disk_cache_max_entries=1):
        _evict_stale_registry_pickles(tmp_path, logger=_LOGGER)

    # Only cadrumo_registry_*.pkl is in scope; the one in-scope file is within
    # the ceiling, and unrelated files are never touched.
    assert (tmp_path / "cadrumo_registry_a.pkl").exists()
    assert foreign.exists()
    assert unrelated.exists()


def test_eviction_never_raises_on_a_missing_directory(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    with override_settings(cadrumo_registry_disk_cache_max_entries=2):
        # Best-effort: a vanished/absent cache directory must not raise.
        _evict_stale_registry_pickles(missing, logger=_LOGGER)

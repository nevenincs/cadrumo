"""Retention pruning for per-run trace directories.

The run-trace store keeps one subdirectory per ``run_id`` under
``cadrumo_runs_dir`` and formerly grew without bound. ``prune_run_traces``
gives it a declared retention lifecycle: run directories whose modification
time is older than ``cadrumo_runs_retention_days`` are removed, and the
surviving directories are size-pruned oldest-first until the store fits under
``cadrumo_runs_max_total_bytes`` (the newest directory is always kept). Age is
set here with ``os.utime`` on real directories (run traces are plain files with
no bucket session), and the prune runs under the real clock.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ....tests.storage_scope import relocated_storage_path, storage_overrides
from ... import StorageCategory
from ...config import override_settings
from ...directory_scan import DirectoryEntryKind, scan_directory
from ..models import RunOutcome, RunTrace
from ..store import EVENTS_FILENAME, TRACE_FILENAME, prune_run_traces, save_trace

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_FRESH_RUN_ID = "aaaaaaaaaaaaaaaa"
_STALE_RUN_ID = "bbbbbbbbbbbbbbbb"


def _make_run_dir(
    runs_dir: Path,
    run_id: str,
    *,
    age_days: int,
    anchor: datetime,
    events_bytes: int = 0,
) -> Path:
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True)
    (run_dir / TRACE_FILENAME).write_text("{}", encoding="utf-8")
    if events_bytes:
        (run_dir / EVENTS_FILENAME).write_bytes(b"x" * events_bytes)
    stamp = (anchor - timedelta(days=age_days)).timestamp()
    os.utime(run_dir, (stamp, stamp))
    return run_dir


def test_prune_removes_run_dirs_older_than_retention_window(tmp_path: Path) -> None:
    runs_dir = relocated_storage_path(tmp_path, StorageCategory.RUNS)
    anchor = datetime.now(UTC)
    fresh = _make_run_dir(runs_dir, _FRESH_RUN_ID, age_days=1, anchor=anchor)
    stale = _make_run_dir(runs_dir, _STALE_RUN_ID, age_days=45, anchor=anchor)

    with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)):
        removed = prune_run_traces(retention_days=30)

    assert removed == 1
    assert fresh.exists()
    assert not stale.exists()


def test_prune_keeps_everything_inside_the_window(tmp_path: Path) -> None:
    runs_dir = relocated_storage_path(tmp_path, StorageCategory.RUNS)
    anchor = datetime.now(UTC)
    a = _make_run_dir(runs_dir, _FRESH_RUN_ID, age_days=1, anchor=anchor)
    b = _make_run_dir(runs_dir, _STALE_RUN_ID, age_days=5, anchor=anchor)

    with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)):
        removed = prune_run_traces(retention_days=30)

    assert removed == 0
    assert a.exists()
    assert b.exists()


def test_prune_ignores_non_run_directories(tmp_path: Path) -> None:
    runs_dir = relocated_storage_path(tmp_path, StorageCategory.RUNS)
    anchor = datetime.now(UTC)
    _make_run_dir(runs_dir, _STALE_RUN_ID, age_days=45, anchor=anchor)
    # A stray non-run-id directory, even if old, is out of scope and untouched.
    stray = runs_dir / "not-a-run-id"
    stray.mkdir()
    old = (anchor - timedelta(days=90)).timestamp()
    os.utime(stray, (old, old))

    with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)):
        removed = prune_run_traces(retention_days=30)

    assert removed == 1
    assert stray.exists()
    assert not (runs_dir / _STALE_RUN_ID).exists()


def test_prune_missing_runs_directory_is_a_noop(tmp_path: Path) -> None:
    with override_settings(**storage_overrides(tmp_path / "does-not-exist", StorageCategory.RUNS)):
        assert prune_run_traces(retention_days=30) == 0


def test_prune_defaults_to_central_retention_setting(tmp_path: Path) -> None:
    runs_dir = relocated_storage_path(tmp_path, StorageCategory.RUNS)
    anchor = datetime.now(UTC)
    _make_run_dir(runs_dir, _FRESH_RUN_ID, age_days=1, anchor=anchor)
    _make_run_dir(runs_dir, _STALE_RUN_ID, age_days=400, anchor=anchor)

    with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)):
        removed = prune_run_traces()

    assert removed == 1
    assert (runs_dir / _FRESH_RUN_ID).exists()
    assert not (runs_dir / _STALE_RUN_ID).exists()


def test_save_trace_write_path_fires_retention_prune(tmp_path: Path) -> None:
    """Saving a run trace triggers run-trace retention (no explicit prune call).

    A pre-existing stale run directory is removed by the prune that ``save_trace``
    runs at run finalisation, while the freshly-saved trace persists - proving
    retention fires on the production write path.
    """
    runs_dir = relocated_storage_path(tmp_path, StorageCategory.RUNS)
    anchor = datetime.now(UTC)
    stale = _make_run_dir(runs_dir, _STALE_RUN_ID, age_days=45, anchor=anchor)
    fresh_run_id = "cccccccccccccccc"
    trace = RunTrace(
        run_id=fresh_run_id,
        started_at=anchor,
        finished_at=anchor,
        entrypoint="cadrumo hello",
        arguments=(),
        corpus_sha256="a" * 64,
        db_sha256="b" * 64,
        cert_fingerprint="",
        outcome=RunOutcome.OK,
        replay_of=None,
    )

    with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)):
        save_trace(trace)

    assert not stale.exists()
    assert (runs_dir / fresh_run_id / TRACE_FILENAME).exists()


def test_prune_enforces_total_size_ceiling_oldest_first(tmp_path: Path) -> None:
    """Within-window run directories are size-pruned oldest-first to the ceiling.

    Three fresh directories total ~3000 bytes against a 2100-byte ceiling: only
    the oldest is removed (dropping the total under the ceiling), the two newer
    directories survive, and the on-disk total provably fits the cap.
    """
    runs_dir = relocated_storage_path(tmp_path, StorageCategory.RUNS)
    anchor = datetime.now(UTC)
    oldest = _make_run_dir(runs_dir, "dddddddddddddddd", age_days=3, anchor=anchor, events_bytes=1000)
    middle = _make_run_dir(runs_dir, "eeeeeeeeeeeeeeee", age_days=2, anchor=anchor, events_bytes=1000)
    newest = _make_run_dir(runs_dir, "ffffffffffffffff", age_days=1, anchor=anchor, events_bytes=1000)

    with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)):
        removed = prune_run_traces(retention_days=30, max_total_bytes=2100)

    assert removed == 1
    assert not oldest.exists()
    assert middle.exists()
    assert newest.exists()
    total = sum(f.stat().st_size for f in scan_directory(runs_dir, recursive=True, select=DirectoryEntryKind.FILES))
    assert total <= 2100


def test_prune_size_ceiling_never_removes_the_newest_run(tmp_path: Path) -> None:
    """The newest run directory survives even when it alone exceeds the ceiling."""
    runs_dir = relocated_storage_path(tmp_path, StorageCategory.RUNS)
    anchor = datetime.now(UTC)
    older = _make_run_dir(runs_dir, "dddddddddddddddd", age_days=2, anchor=anchor, events_bytes=500)
    newest = _make_run_dir(runs_dir, "eeeeeeeeeeeeeeee", age_days=1, anchor=anchor, events_bytes=5000)

    with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)):
        removed = prune_run_traces(retention_days=30, max_total_bytes=100)

    assert removed == 1
    assert not older.exists()
    assert newest.exists()


def test_prune_defaults_to_central_size_setting(tmp_path: Path) -> None:
    runs_dir = relocated_storage_path(tmp_path, StorageCategory.RUNS)
    anchor = datetime.now(UTC)
    oldest = _make_run_dir(runs_dir, "dddddddddddddddd", age_days=2, anchor=anchor, events_bytes=1000)
    newest = _make_run_dir(runs_dir, "eeeeeeeeeeeeeeee", age_days=1, anchor=anchor, events_bytes=1000)

    with override_settings(
        cadrumo_runs_max_total_bytes=1500,
        **storage_overrides(tmp_path, StorageCategory.RUNS),
    ):
        removed = prune_run_traces(retention_days=30)

    assert removed == 1
    assert not oldest.exists()
    assert newest.exists()

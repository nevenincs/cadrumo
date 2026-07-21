"""Retention sweep for per-session telemetry trajectory files (ADR H6).

Proves :func:`prune_telemetry` bounds the telemetry directory by age and by
count and NEVER removes the newest N sessions, and that
:class:`SessionTelemetryWriter` runs the sweep once at construction. Ages are
set deterministically with ``os.utime`` plus an injected reference clock, never
read from the wall clock in a way that could flake, so the bounds are exact.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from .._telemetry import SessionTelemetryWriter, TelemetryRetention, prune_telemetry

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_SECONDS_PER_DAY = 86_400


def _session_file(directory: Path, name: str, *, age_days: float, now: float) -> Path:
    """Write a session file and stamp its mtime to ``age_days`` before ``now``."""
    path = directory / f"{name}.jsonl"
    path.write_text("{}\n", encoding="utf-8")
    stamp = now - age_days * _SECONDS_PER_DAY
    os.utime(path, (stamp, stamp))
    return path


def _names(directory: Path) -> set[str]:
    return {path.name for path in directory.glob("*.jsonl")}


def test_prune_bounds_session_count_dropping_the_oldest(tmp_path: Path) -> None:
    now = time.time()
    for index in range(10):
        _session_file(tmp_path, f"s{index:02d}", age_days=float(index), now=now)
    # s00 (age 0) is newest ... s09 (age 9) is oldest; the count bound keeps the
    # newest five and prunes the rest, regardless of the generous age bound.
    removed = prune_telemetry(tmp_path, max_age_days=3650, max_sessions=5, keep_newest=2, now=now)
    assert _names(tmp_path) == {"s00.jsonl", "s01.jsonl", "s02.jsonl", "s03.jsonl", "s04.jsonl"}
    assert {path.name for path in removed} == {"s05.jsonl", "s06.jsonl", "s07.jsonl", "s08.jsonl", "s09.jsonl"}


def test_prune_removes_files_older_than_the_age_bound(tmp_path: Path) -> None:
    now = time.time()
    _session_file(tmp_path, "fresh", age_days=1, now=now)
    _session_file(tmp_path, "stale", age_days=45, now=now)
    # The count bound is slack; only the age bound bites, and only the stale file.
    removed = prune_telemetry(tmp_path, max_age_days=30, max_sessions=100, keep_newest=0, now=now)
    assert {path.name for path in removed} == {"stale.jsonl"}
    assert _names(tmp_path) == {"fresh.jsonl"}


def test_prune_never_removes_the_newest_n_even_when_all_are_stale(tmp_path: Path) -> None:
    now = time.time()
    for index in range(6):
        _session_file(tmp_path, f"s{index:02d}", age_days=100.0 + index, now=now)
    # Every file is older than the age bound AND the count bound is 1, yet the
    # newest three are protected unconditionally by keep_newest.
    removed = prune_telemetry(tmp_path, max_age_days=30, max_sessions=1, keep_newest=3, now=now)
    assert _names(tmp_path) == {"s00.jsonl", "s01.jsonl", "s02.jsonl"}
    assert {path.name for path in removed} == {"s03.jsonl", "s04.jsonl", "s05.jsonl"}


def test_keep_newest_is_load_bearing_the_newest_is_pruned_without_it(tmp_path: Path) -> None:
    now = time.time()
    for index in range(4):
        _session_file(tmp_path, f"s{index:02d}", age_days=100.0 + index, now=now)
    # Anti-tautology companion to the protection test: with keep_newest=0 the age
    # bound reaches the newest file too, proving the protection above is real.
    removed = prune_telemetry(tmp_path, max_age_days=30, max_sessions=100, keep_newest=0, now=now)
    assert {path.name for path in removed} == {"s00.jsonl", "s01.jsonl", "s02.jsonl", "s03.jsonl"}
    assert _names(tmp_path) == set()


def test_prune_on_missing_directory_is_a_noop(tmp_path: Path) -> None:
    missing = tmp_path / "absent"
    assert prune_telemetry(missing, max_age_days=1, max_sessions=1, keep_newest=0, now=time.time()) == ()


def test_prune_on_empty_directory_removes_nothing(tmp_path: Path) -> None:
    assert prune_telemetry(tmp_path, max_age_days=1, max_sessions=1, keep_newest=0, now=time.time()) == ()


def test_writer_sweeps_the_directory_at_construction(tmp_path: Path) -> None:
    now = time.time()
    for index in range(5):
        _session_file(tmp_path, f"old{index:02d}", age_days=100.0 + index, now=now)
    writer = SessionTelemetryWriter(
        session_id="new-session",
        directory=tmp_path,
        retention=TelemetryRetention(max_age_days=30, max_sessions=100, keep_newest=1),
    )
    # The construction sweep kept only the newest stale file (old00, age ~100d);
    # the others are past the 30-day age bound and are pruned.
    assert _names(tmp_path) == {"old00.jsonl"}
    # The writer's own file is created lazily on first record and is never a
    # sweep target (it does not exist at construction time).
    written = writer.record(tool_name="contract")
    assert written.sequence == 0
    assert writer.path.exists()
    assert writer.path.name == "new-session.jsonl"


def test_writer_retention_default_preserves_a_small_directory(tmp_path: Path) -> None:
    now = time.time()
    for index in range(3):
        _session_file(tmp_path, f"recent{index}", age_days=float(index), now=now)
    # Default bounds (30 days / 200 sessions / newest 20) leave a small, recent
    # directory untouched — pruning only bites a long-lived accretion.
    SessionTelemetryWriter(session_id="another", directory=tmp_path)
    assert _names(tmp_path) == {"recent0.jsonl", "recent1.jsonl", "recent2.jsonl"}

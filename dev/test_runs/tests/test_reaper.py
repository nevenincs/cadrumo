"""Safety contract for repository-local test-run retention."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from .. import reaper

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _run(root: Path, name: str, *, age: float, completed: bool, now: float) -> Path:
    directory = root / "2026-09-08" / name
    directory.mkdir(parents=True)
    if completed:
        (directory / "run.json").write_text(json.dumps({"exit_status": 0}), encoding="utf-8")
    os.utime(directory, (now - age, now - age))
    return directory


def test_completed_runs_are_retained_then_reclaimed_after_the_evidence_window(tmp_path: Path) -> None:
    now = 2_000_000_000.0
    recent = _run(tmp_path, "stamp-pytest-101-aaaaaaaa", age=60, completed=True, now=now)
    old = _run(
        tmp_path,
        "stamp-pytest-102-bbbbbbbb",
        age=reaper.COMPLETED_RETENTION_SECONDS + 1,
        completed=True,
        now=now,
    )

    verdicts = reaper.assess_run_directories(tmp_path, now=now)
    assert {row.directory: row.reclaimable for row in verdicts} == {recent: False, old: True}
    assert reaper.reclaim_run_directories(verdicts) == 1
    assert recent.is_dir()
    assert not old.exists()


def test_interrupted_run_requires_a_dead_owner_and_the_grace_period(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = 2_000_000_000.0
    live = _run(tmp_path, "stamp-pytest-201-aaaaaaaa", age=86_400, completed=False, now=now)
    young = _run(tmp_path, "stamp-pytest-202-bbbbbbbb", age=60, completed=False, now=now)
    dead = _run(
        tmp_path,
        "stamp-pytest-203-cccccccc",
        age=reaper.INTERRUPTED_GRACE_SECONDS + 1,
        completed=False,
        now=now,
    )
    monkeypatch.setattr(reaper, "process_is_live", lambda pid: pid == 201)

    verdicts = reaper.assess_run_directories(tmp_path, now=now)
    assert {row.directory: row.reclaimable for row in verdicts} == {live: False, young: False, dead: True}


def test_symlinks_are_never_assessed_or_removed(tmp_path: Path) -> None:
    target = tmp_path / "elsewhere"
    target.mkdir()
    date = tmp_path / "2026-09-08"
    date.mkdir()
    link = date / "stamp-pytest-999-dddddddd"
    # Unguarded: a host that cannot create a directory symlink raises here and
    # is reported as a red naming the OS refusal, rather than a green skip that
    # retires the "never follow a link" proof this case exists for.
    link.symlink_to(target, target_is_directory=True)

    assert reaper.assess_run_directories(tmp_path) == ()
    assert target.is_dir()

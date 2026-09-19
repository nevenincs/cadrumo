"""Safety contract for repository-local test-run reclamation."""

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


def test_a_completed_run_is_reclaimable_at_any_age_because_nothing_reads_it_back(tmp_path: Path) -> None:
    """No age threshold survives here: a finished run's directory is command output.

    The seconds-old run is the load-bearing case. A retention window spares it,
    and sparing it is what let 9.3 GB accumulate and what a dead-weight baseline
    grew against by globbing a previous run's signal file. Age is not a property
    this module is allowed to consult for a run that finished.
    """
    now = 2_000_000_000.0
    seconds_old = _run(tmp_path, "stamp-pytest-101-aaaaaaaa", age=60, completed=True, now=now)
    days_old = _run(tmp_path, "stamp-pytest-102-bbbbbbbb", age=30 * 86_400, completed=True, now=now)

    verdicts = reaper.assess_run_directories(tmp_path, now=now)
    assert {row.directory: row.reclaimable for row in verdicts} == {seconds_old: True, days_old: True}
    assert reaper.reclaim_run_directories(verdicts) == 2
    assert not seconds_old.exists()
    assert not days_old.exists()


def test_no_age_threshold_is_exposed_for_a_completed_run(tmp_path: Path) -> None:
    """The absence of the constant is the contract, not an implementation detail.

    A reinstated retention window would most naturally arrive as a module-level
    seconds value, so this asserts the module exposes exactly one threshold and
    that it is the liveness grace.
    """
    thresholds = {name for name in vars(reaper) if name.endswith("_SECONDS")}
    assert thresholds == {"INTERRUPTED_GRACE_SECONDS"}


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

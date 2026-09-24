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
    seconds value, so this pins the exact set. Both members bound how long
    UNFINISHED output may persist; neither can apply to a run that finished.
    """
    thresholds = {name for name in vars(reaper) if name.endswith("_SECONDS")}
    assert thresholds == {"INTERRUPTED_GRACE_SECONDS", "PID_TRUST_CEILING_SECONDS"}, (
        "a new seconds threshold appeared; both existing ones bound how long UNFINISHED output"
        " may persist, and a third that applies to a finished run would be a retention window"
    )


def test_a_recycled_pid_cannot_spare_unfinished_output_past_the_trust_ceiling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The PID answers "some process holds this id", not "this run still holds it".

    An id handed to another process spares a dead run's output forever, silently.
    It was doing that: 28 directories idle up to 168 hours, all apparently owned.
    So the liveness answer is believed only while a run could still plausibly be
    writing, and the pair below is the contract -- inside the ceiling the live
    owner wins, past it the directory goes even though the id still resolves.
    """
    now = 2_000_000_000.0
    inside = _run(tmp_path, "stamp-pytest-301-aaaaaaaa", age=3_600, completed=False, now=now)
    past = _run(
        tmp_path,
        "stamp-pytest-301-bbbbbbbb",
        age=reaper.PID_TRUST_CEILING_SECONDS + 1,
        completed=False,
        now=now,
    )
    monkeypatch.setattr(reaper, "process_is_live", lambda pid: True)

    verdicts = reaper.assess_run_directories(tmp_path, now=now)

    assert {row.directory: row.reclaimable for row in verdicts} == {inside: False, past: True}


def test_an_unowned_run_with_no_readable_pid_is_still_bounded(tmp_path: Path) -> None:
    """An unparseable name removes the fast path, not the bound.

    Without a PID there is nothing to resolve, so such a directory would be
    spared forever on the liveness branch alone. The ceiling is what stops a
    malformed name being a permanent exemption.
    """
    now = 2_000_000_000.0
    unowned = _run(tmp_path, "no-pid-here", age=reaper.PID_TRUST_CEILING_SECONDS + 1, completed=False, now=now)

    verdicts = reaper.assess_run_directories(tmp_path, now=now)

    assert [(row.directory, row.reclaimable) for row in verdicts] == [(unowned, True)]


def test_interrupted_run_requires_a_dead_owner_and_the_grace_period(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = 2_000_000_000.0
    live = _run(tmp_path, "stamp-pytest-201-aaaaaaaa", age=3_600, completed=False, now=now)
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


def _scratch(base: Path, name: str, *, age: float, now: float) -> Path:
    directory = base / name
    directory.mkdir(parents=True)
    os.utime(directory, (now - age, now - age))
    return directory


def test_run_scratch_follows_its_owner_and_the_grace_period(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    now = 2_000_000_000.0
    grace = reaper.INTERRUPTED_GRACE_SECONDS + 1
    live = _scratch(tmp_path, "cr-301-a1b2c3", age=grace, now=now)
    young = _scratch(tmp_path, "cr-302-d4e5f6", age=60, now=now)
    dead = _scratch(tmp_path, "cr-303-0a0b0c", age=grace, now=now)
    abandoned = _scratch(tmp_path, "cr-304-0d0e0f", age=reaper.PID_TRUST_CEILING_SECONDS + 1, now=now)
    monkeypatch.setattr(reaper, "process_is_live", lambda pid: pid in {301, 304})

    verdicts = reaper.assess_scratch_directories(tmp_path, now=now)

    assert {row.directory: row.reclaimable for row in verdicts} == {
        live: False,
        young: False,
        dead: True,
        abandoned: True,
    }


def test_run_scratch_assessment_ignores_what_other_programs_keep_in_temp(tmp_path: Path) -> None:
    """The temp base is shared, so only names shaped like a run's scratch are judged."""
    now = 2_000_000_000.0
    old = reaper.PID_TRUST_CEILING_SECONDS + 1
    for name in ("claude", "cadrumo-pytest-303", "cr-notapid-a1b2c3", "cr-303", "crx-303-a1b2c3"):
        _scratch(tmp_path, name, age=old, now=now)
    (tmp_path / "cr-305-a1b2c3").write_text("a file, not a scratch directory", encoding="utf-8")

    assert reaper.assess_scratch_directories(tmp_path, now=now) == ()

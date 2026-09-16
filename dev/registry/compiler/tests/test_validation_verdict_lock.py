"""Processes that start together validate a registry once, not once each.

Real child processes race on one empty verdict directory behind a shared start
barrier. Under the lock exactly one of them validates and records; without it
both do, which is the detector proving the race exists to be closed.
"""

from __future__ import annotations

import os
import sys
import textwrap
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from cadrumo.tests.audited_process import run_audited_process

from ..validation_verdict_cache import VERDICT_CACHE_DIR_ENV

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_KEY = "race-key"

_CHILD = textwrap.dedent(
    """
    import sys
    import time
    from contextlib import nullcontext
    from pathlib import Path

    from dev.registry.compiler.validation_verdict_cache import (
        is_validated,
        record_validated,
        verdict_validation_lock,
    )

    key, barrier, validations, locked = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4] == "1"
    Path(sys.argv[5]).touch()
    while not barrier.exists():
        time.sleep(0.01)
    with verdict_validation_lock(key) if locked else nullcontext():
        if not is_validated(key):
            with validations.open("a", encoding="utf-8") as sink:
                sink.write("validated\\n")
            # Hold the verdict back until the sibling has also checked, or a
            # bounded wait says it cannot (because the lock is keeping it out).
            deadline = time.monotonic() + 5.0
            while len(validations.read_text(encoding="utf-8").splitlines()) < 2 and time.monotonic() < deadline:
                time.sleep(0.05)
            record_validated(key, subject="registry")
    print("hit" if is_validated(key) else "miss")
    """
)


def _race(tmp_path: Path, *, locked: bool) -> tuple[int, list[str]]:
    cache = tmp_path / "verdicts"
    barrier = tmp_path / "go"
    validations = tmp_path / "validations.log"
    env = {**os.environ, VERDICT_CACHE_DIR_ENV: str(cache)}
    repo_root = Path(__file__).resolve().parents[4]
    ready = [tmp_path / f"ready-{index}" for index in range(2)]

    def run(marker: Path) -> str:
        completed = run_audited_process(
            [sys.executable, "-c", _CHILD, _KEY, str(barrier), str(validations), "1" if locked else "0", str(marker)],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert completed.returncode == 0, completed.stderr
        return str(completed.stdout).strip()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run, marker) for marker in ready]
        deadline = time.monotonic() + 60
        # Release both only once both are parked, so the race is real.
        while not all(marker.exists() for marker in ready):
            assert time.monotonic() < deadline, "children never reached the start barrier"
            time.sleep(0.05)
        barrier.touch()
        outcomes = [future.result() for future in futures]
    validated = validations.read_text(encoding="utf-8").splitlines() if validations.exists() else []
    assert not list(cache.glob("*.lock")), "a finished validation left its lock behind"
    return len(validated), outcomes


def test_two_processes_starting_together_validate_once(tmp_path: Path) -> None:
    validations, outcomes = _race(tmp_path, locked=True)

    assert validations == 1
    assert outcomes == ["hit", "hit"]


def test_without_the_lock_both_processes_validate(tmp_path: Path) -> None:
    validations, _ = _race(tmp_path, locked=False)

    assert validations == 2

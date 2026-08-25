"""Cross-process exclusion for the custody root lock, and its release on death.

``profile_custody_root_lock`` is the mutual exclusion behind EVERY custody
pointer mutation -- the active-profile pointer transaction and custody
compare-and-swap both take this exact identity. It is what stands between two
concurrent ``aeat config login`` invocations and a torn pointer, on a surface
whose operator is an autonomous agent that retries.

It had no direct test. Its bucket-lockfile sibling carries a whole module of
cross-process cases; this primitive, which guards the more dangerous mutation,
carried none -- so the claim in its own docstring that "sibling processes
retain kernel-enforced exclusion" was prose nothing executed.

The release-on-death case is the one that matters most and is least obvious.
This lock deliberately has NO stale-lockfile reclaim: unlike the bucket
lockfile, there is no recorded PID, no liveness probe and no lazy takeover, so
a holder that dies abruptly is forgiven ONLY because the kernel drops the
exclusion when the process goes. If that ever stopped being true, a single
crashed login would wedge every custody mutation on the machine permanently,
with no reclaim path and nothing to notice.

Real processes, real kernel primitives, a real storage root on disk. Nothing is
mocked, and the holder is killed rather than asked to exit so the death is
abrupt.
"""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from functools import cache
from pathlib import Path

import pytest

from ..errors import ProfileCustodyRecordError
from .._filesystem import profile_custody_root_lock

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

#: Import root the spawned holders and probes put on ``sys.path``. They are bare
#: interpreters rather than pytest workers, so they carry none of this run's
#: import configuration.
_REPO_SRC = Path(__file__).resolve().parents[6]


@cache
def _bare_interpreter_spawn_seconds() -> float:
    """Return this host's CURRENT cost of spawning a bare interpreter.

    Measured now rather than at authoring time, matching the sibling bucket
    lockfile module, so the readiness budget tracks load instead of encoding
    one machine's idle speed.
    """
    started = time.monotonic()
    subprocess.run([sys.executable, "-c", "import sys"], check=True, capture_output=True, timeout=120)
    return time.monotonic() - started


def _readiness_budget_seconds() -> float:
    """Return a load-proportional ceiling for the holder to signal readiness.

    A HANG GUARD, not a latency assertion. The holder pays for a fresh
    interpreter, the custody import chain and a lock acquisition, so a fixed
    ceiling fails for the scheduler rather than for the contract on a loaded
    shared box.
    """
    return max(30.0, _bare_interpreter_spawn_seconds() * 40.0)


def _holder_script(root: Path, ready_path: Path) -> str:
    """Render a subprocess that takes the root lock and holds it until killed."""
    return (
        "import sys, time\n"
        "from pathlib import Path\n"
        f"sys.path.insert(0, {str(_REPO_SRC)!r})\n"
        "from cadrumo.adapters.persistence.storage.custody._filesystem import profile_custody_root_lock\n"
        f"with profile_custody_root_lock(Path({str(root)!r}), timeout_seconds=30.0):\n"
        f"    Path({str(ready_path)!r}).write_text('ready', encoding='utf-8')\n"
        "    time.sleep(600)\n"
    )


def _probe_script(root: Path) -> str:
    """Render a subprocess that reports whether it could take the root lock."""
    return (
        "import sys\n"
        "from pathlib import Path\n"
        f"sys.path.insert(0, {str(_REPO_SRC)!r})\n"
        "from cadrumo.adapters.persistence.storage.custody._filesystem import profile_custody_root_lock\n"
        "try:\n"
        f"    with profile_custody_root_lock(Path({str(root)!r}), timeout_seconds=2.0):\n"
        "        print('ACQUIRED')\n"
        "except Exception as exc:\n"
        "    print('REFUSED', type(exc).__name__)\n"
    )


def _wait_for_ready(ready_path: Path, process: subprocess.Popen[bytes]) -> None:
    """Block until the holder signals readiness, dies, or the guard expires."""
    deadline = time.monotonic() + _readiness_budget_seconds()
    while time.monotonic() < deadline:
        if ready_path.exists():
            return
        exit_code = process.poll()
        if exit_code is not None:
            raise AssertionError(f"holder subprocess exited with code {exit_code} before signalling readiness")
        time.sleep(0.05)
    raise AssertionError("holder subprocess did not signal readiness within the budget")


def _probe(root: Path) -> str:
    """Run a probe process and return its verdict token."""
    script = _probe_script(root)
    completed = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    return completed.stdout.strip()


def test_a_second_process_cannot_take_a_held_root_lock(tmp_path: Path) -> None:
    """The exclusion the pointer transaction depends on, across real processes."""
    ready = tmp_path / "ready"
    script = _holder_script(tmp_path, ready)
    holder = subprocess.Popen([sys.executable, "-c", script])
    try:
        _wait_for_ready(ready, holder)

        assert _probe(tmp_path).startswith("REFUSED")
    finally:
        holder.kill()
        holder.wait(timeout=120)


def test_killing_the_holder_releases_the_root_lock(tmp_path: Path) -> None:
    """DISCRIMINATING: the kernel, not a reclaim path, forgives an abrupt death.

    There is no PID record and no staleness probe on this lock, so nothing in
    this codebase can take it back from a dead holder. A regression that made
    the exclusion outlive the process would strand every custody mutation with
    no way back, and would look exactly like the test above still passing.
    """
    ready = tmp_path / "ready"
    script = _holder_script(tmp_path, ready)
    holder = subprocess.Popen([sys.executable, "-c", script])
    _wait_for_ready(ready, holder)
    assert _probe(tmp_path).startswith("REFUSED")

    holder.kill()
    holder.wait(timeout=120)

    assert _probe(tmp_path) == "ACQUIRED"


def test_the_same_thread_may_re_enter_and_a_sibling_thread_may_not(tmp_path: Path) -> None:
    """Re-entrance is scoped to the owning thread, not to the process.

    Both halves belong together: the depth counter that lets a pointer
    transaction nest a compare-and-swap inside itself must not also let an
    unrelated worker thread walk into a half-applied mutation.
    """
    sibling: list[str] = []

    def _sibling_attempt() -> None:
        try:
            with profile_custody_root_lock(tmp_path, timeout_seconds=2.0):
                sibling.append("ACQUIRED")
        except ProfileCustodyRecordError:
            sibling.append("REFUSED")

    with profile_custody_root_lock(tmp_path, timeout_seconds=5.0):
        with profile_custody_root_lock(tmp_path, timeout_seconds=5.0):
            pass

        thread = threading.Thread(target=_sibling_attempt)
        thread.start()
        thread.join(timeout=120)

    assert sibling == ["REFUSED"]


def test_the_lock_is_reusable_after_a_clean_release(tmp_path: Path) -> None:
    """Baseline: exclusion is not a one-shot that wedges its own root."""
    with profile_custody_root_lock(tmp_path, timeout_seconds=5.0):
        pass

    with profile_custody_root_lock(tmp_path, timeout_seconds=5.0):
        pass

    assert _probe(tmp_path) == "ACQUIRED"

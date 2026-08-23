"""A session left open at interpreter exit is sealed by the exit hook.

``_active_session`` registers ``_close_active_session_at_exit`` with ``atexit``
at import, and that hook sweeps every live session through
``close_all_live_bucket_sessions``. It exists because the context-scoped close
is not enough on its own: ``atexit`` hooks run on the MAIN thread, and by PEP
567 semantics that thread observes no binding a worker made, so a session
opened on an embedding transport or TUI worker thread would keep its unwrapped DEK in
memory until the process died with it.

That hook had no test. The thread-isolation module beside this one explains the
mechanism in prose and asserts the contextvar behaviour around it, but nothing
established that the hook FIRES or that it seals anything -- and a registration
that is never exercised is indistinguishable from one that was deleted.

HOW THE OBSERVATION IS TAKEN. Nothing here patches ``atexit`` or calls the hook
by hand; calling it directly would prove the function works while saying
nothing about whether it is wired to interpreter shutdown, which is the actual
claim. Instead a real child interpreter opens a real session and exits
normally, and the observation is made from inside its own shutdown by a second
``atexit`` hook. Ordering is what makes that work: ``atexit`` runs hooks in
REVERSE registration order, so the observer registers BEFORE the substrate is
imported and therefore runs AFTER the substrate's hook has swept. The child
writes what it saw to a file, because stdout is unreliable that late in
shutdown.

The session is built from raw key bytes through the public constructor, so no
credential store, storage root or profile is involved: this is a property of
the substrate, and it must hold on a host where custody is unavailable.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

#: Run in a child interpreter. ``argv[1]`` is the evidence file.
_CHILD: Final = """
import atexit, json, sys
from pathlib import Path

evidence = Path(sys.argv[1])
observed = {}

def _observe_after_the_substrate_hook() -> None:
    # Registered FIRST, so under atexit's reverse ordering this runs LAST --
    # after the substrate's own hook has had its chance to sweep.
    observed["sealed_at_exit"] = session.sealed
    evidence.write_text(json.dumps(observed), encoding="utf-8")

atexit.register(_observe_after_the_substrate_hook)

# Imported only now, so the substrate's hook is registered after the observer.
from datetime import UTC, datetime

from cadrumo.adapters.persistence.storage.master_key import BucketSession

session = BucketSession.open(
    bucket_id="exit-hook-probe",
    kek=b"k" * 32,
    dek=b"d" * 32,
    idle_minutes=5,
    opened_at=datetime.now(UTC),
)
observed["sealed_before_exit"] = session.sealed
# Deliberately NOT closed: the exit hook is the subject.
"""


def _run_child(tmp_path: Path, *, source: str) -> dict[str, object]:
    """Run one child interpreter to completion and return what it recorded."""
    evidence = tmp_path / "exit-observation.json"
    completed = subprocess.run(  # noqa: S603 - fixed argv, no shell, test-owned source
        [sys.executable, "-c", source, str(evidence)],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert completed.returncode == 0, f"child failed: {completed.stderr[-800:]}"
    assert evidence.is_file(), f"child left no observation; stderr: {completed.stderr[-800:]}"
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_a_session_left_open_is_sealed_by_the_interpreter_exit_hook(tmp_path: Path) -> None:
    """DISCRIMINATING: the sweep that keeps a worker thread's DEK from outliving its use."""
    observed = _run_child(tmp_path, source=_CHILD)

    assert observed["sealed_before_exit"] is False, (
        "the session was already sealed before shutdown, so this run proves nothing about the hook"
    )
    assert observed["sealed_at_exit"] is True, (
        "a session left open was still unsealed after the interpreter's exit hooks ran; the "
        "atexit sweep in `_active_session` is not reaching live sessions"
    )


def test_the_observation_is_taken_after_the_substrate_hook_runs(tmp_path: Path) -> None:
    """ANTI-TAUTOLOGY: the observer must be capable of seeing an UNSEALED session.

    If the observer ran before the sweep -- or the evidence were written at any
    point other than shutdown -- it would report the pre-exit state, and the
    assertion above would be measuring the wrong instant while passing. This
    runs the identical child with the substrate's hook deregistered, so only
    the ordering differs, and requires the observer to report `False`.
    """
    without_sweep = _CHILD.replace(
        'observed["sealed_before_exit"] = session.sealed',
        'observed["sealed_before_exit"] = session.sealed\n'
        "import atexit as _a\n"
        "from cadrumo.adapters.persistence.storage.master_key import _active_session as _s\n"
        "_a.unregister(_s._close_active_session_at_exit)\n",
    )

    observed = _run_child(tmp_path, source=without_sweep)

    assert observed["sealed_at_exit"] is False, (
        "with the substrate's exit hook deregistered the session was still sealed at exit, so "
        "something other than that hook is sealing it and the primary assertion is not "
        "measuring what it claims"
    )

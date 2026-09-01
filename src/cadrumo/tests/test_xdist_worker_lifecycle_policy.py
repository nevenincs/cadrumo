"""A dead xdist worker must end the session, not be silently replaced.

The repository already bounds a hung TEST with ``timeout``. Nothing bounded a
dead WORKER, and that is the failure it kept hitting: a test parked in
``subprocess.wait()`` cannot be interrupted by the thread timeout method, so
when the ceiling fires the worker exits uncleanly rather than the test failing.

xdist's default response is to replace the node and carry on. Both of its
outcomes were observed here. It re-ran the dead worker's test on the
replacement, reporting ONE test id as THREE failures; and it wedged the
loadscope scheduler outright (``KeyError: <WorkerController gw6>`` in
``_assign_work_unit``, because a replacement node has no registered
collection), sitting thirty minutes with no output on an idle box.

Either outcome is worse than stopping: one corrupts the result set, the other
burns a CI runner to its lane timeout. ``--max-worker-restart=0`` makes the
death terminal and names the test the worker died on.

This gate pins that setting. It is deliberately a cheap unit check over the
committed configuration rather than a live xdist boot: the expensive real-pool
proof already exists in ``test_worker_count_hook_harness``, and a policy that
can be deleted in one line deserves a check that runs in every lane.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Final

import pytest

from .inventory import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: The flag that makes a worker death terminal. ``0`` restarts, and therefore
#: tolerates, nothing.
_POLICY_FLAG: Final = "--max-worker-restart=0"

_PYPROJECT: Final[Path] = REPO_ROOT / "pyproject.toml"


def _configured_addopts() -> str:
    """Return the committed pytest ``addopts`` string."""
    config = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    return str(config["tool"]["pytest"]["ini_options"]["addopts"])


def _declares_terminal_worker_death(addopts: str) -> bool:
    """Return whether ``addopts`` makes a worker death terminal.

    Matches the flag rather than merely the option name, because
    ``--max-worker-restart=2`` is the tolerant setting this gate exists to
    reject and would satisfy a name-only check.
    """
    return _POLICY_FLAG in addopts.split()


def test_addopts_make_a_dead_worker_terminal() -> None:
    """The committed configuration refuses to replace a dead worker."""
    addopts = _configured_addopts()

    assert addopts.strip(), "pytest addopts resolved empty; this gate would pass over nothing"
    assert _declares_terminal_worker_death(addopts), (
        f"pytest addopts must carry {_POLICY_FLAG!r} so a dead xdist worker ends the session.\n"
        "Without it xdist replaces the node and either re-runs the dead worker's test "
        "(one test id reported as several failures) or wedges its scheduler with no output.\n"
        f"addopts is currently: {addopts}"
    )


@pytest.mark.parametrize(
    "tolerant",
    [
        "-n auto --dist=loadfile",
        "-n auto --max-worker-restart=1",
        "-n auto --max-worker-restart=4 --strict-markers",
        "-n auto --max-worker-restart 0",
    ],
)
def test_the_detector_rejects_every_tolerant_configuration(tolerant: str) -> None:
    """The control: each way of tolerating a worker death is refused.

    Without this the gate above could pass by matching anything at all. The
    cases are the real ways the policy erodes -- dropped entirely, or set to a
    non-zero restart budget. The space-separated spelling is rejected too: xdist
    accepts it, but this gate pins one canonical form so the assertion above
    cannot be satisfied by a string it did not intend.
    """
    assert not _declares_terminal_worker_death(tolerant)


def test_the_detector_accepts_the_committed_form() -> None:
    """The positive control: the detector is not simply always False."""
    assert _declares_terminal_worker_death(f"-n auto {_POLICY_FLAG} --strict-markers")

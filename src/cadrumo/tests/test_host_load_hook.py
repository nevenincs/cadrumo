"""Real-subprocess proof of the pre-timeout host-load stamp.

:mod:`cadrumo.tests._host_load_hook` is reachable only through pytest-timeout's
``pytest_timeout_set_timer`` / ``pytest_timeout_cancel_timer`` seam, and the
whole point of it is that the stamp reaches the output of a run that ends in
``os._exit(1)``. Neither property can be proven by importing the module and
calling its functions: that would prove the formatter's arithmetic and nothing
about whether pytest-timeout invokes the hook, whether the ceiling still fires
once a second implementation is registered against a ``firstresult`` hookspec,
or whether the bytes survive the capture layer and the hard exit.

So every case below boots a REAL pytest subprocess against a throwaway fixture
tree whose ``conftest.py`` delegates to the real hook module -- the exact code
under test, not a reimplementation -- and reads what the run actually printed.
This is the same real-subprocess idiom already established by
:mod:`cadrumo.tests.test_worker_count_hook` and
:mod:`cadrumo.tests.test_acceptance_wall_catalogue`.

The two cases are a matched pair, and the second is what makes the first mean
something. A stamp that appeared on every test would satisfy the first case
while carrying no information; a ceiling that no longer fired would satisfy it
while having silently disabled the timeout the stamp exists to annotate. So one
case proves the stamp appears on a run that really does hit the ceiling, and
the other proves a fast test under the identical ceiling produces no stamp at
all.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from ._host_load_hook import STAMP_PREFIX

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SUBPROCESS_TIMEOUT_SECONDS = 120

#: The probe's own ceiling. Small enough to keep the case quick, large enough
#: that the stamp's lead still lands inside it rather than at t=0.
_PROBE_TIMEOUT_SECONDS = 4

_PROBE_CONFTEST = """
from cadrumo.tests._host_load_hook import arm_pre_timeout_stamp, disarm_pre_timeout_stamp


def pytest_timeout_set_timer(item, settings):
    arm_pre_timeout_stamp(item, settings)
    return None


def pytest_timeout_cancel_timer(item):
    disarm_pre_timeout_stamp(item)
    return None
"""

_HANGING_PROBE_TEST = """
import time


def test_probe_that_outlives_its_ceiling():
    time.sleep(600)
"""

_FAST_PROBE_TEST = """
def test_probe_that_finishes_well_inside_its_ceiling():
    assert True
"""


def _run_probe(*, probe_source: str) -> subprocess.CompletedProcess[str]:
    """Boot a real pytest subprocess over ``probe_source`` under a real ceiling.

    Args:
        probe_source: Body of the throwaway ``test_probe.py``.

    Returns:
        The completed process, whose combined output is what the run actually
        emitted -- including anything written past the capture layer.
    """
    with tempfile.TemporaryDirectory(prefix="host-load-hook-poc-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        (tmp_path / "conftest.py").write_text(_PROBE_CONFTEST, encoding="utf-8")
        (tmp_path / "test_probe.py").write_text(probe_source, encoding="utf-8")

        return subprocess.run(  # noqa: S603 - fixed interpreter argv; every other token is a module-local literal.
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "--no-header",
                "-p",
                "no:cacheprovider",
                f"--timeout={_PROBE_TIMEOUT_SECONDS}",
                "test_probe.py",
            ],
            cwd=tmp_path,
            env=dict(os.environ),
            capture_output=True,
            text=True,
            check=False,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        )


def test_the_stamp_reaches_the_output_of_a_run_that_really_hits_the_ceiling() -> None:
    """A timed-out run carries the host-load stamp, and still times out."""

    result = _run_probe(probe_source=_HANGING_PROBE_TEST)
    output = result.stdout + result.stderr

    # The ceiling must still fire. This is the load-bearing half: both hookspecs
    # are ``firstresult``, so an implementation that returned a value instead of
    # ``None`` would stop the hook call, pytest-timeout's own ``trylast``
    # implementation would never install the real timer, and the probe would sit
    # for its full 600-second sleep. A run that ends promptly is the evidence the
    # ceiling survived the second implementation.
    assert result.returncode != 0, f"the probe's ceiling did not fire at all: {output!r}"
    assert "Timeout" in output, f"the run did not end at the pytest-timeout ceiling: {output!r}"

    assert STAMP_PREFIX in output, (
        f"no host-load stamp reached the output of a timed-out run; returncode={result.returncode} output={output!r}"
    )

    stamp = next(line for line in output.splitlines() if line.startswith(STAMP_PREFIX))
    assert "test_probe_that_outlives_its_ceiling" in stamp, (
        f"the stamp must name the node whose ceiling fired -- got {stamp!r}"
    )
    # A stamp that reported "unavailable" would still match the prefix while
    # carrying none of the load the stamp exists to record.
    assert "cpu=" in stamp and "python_processes=" in stamp, (
        f"the stamp carries no host reading; a stamp without one is not a measurement -- got {stamp!r}"
    )


def test_a_test_that_finishes_inside_its_ceiling_emits_no_stamp() -> None:
    """The stamp is a timeout diagnostic, not a per-test banner.

    Same ceiling, same registered hooks, a test that simply passes: the timer
    must be cancelled on the way out and print nothing. Without this case the
    first one is satisfied just as well by a stamp emitted unconditionally,
    which would carry no information about load at all.
    """

    result = _run_probe(probe_source=_FAST_PROBE_TEST)
    output = result.stdout + result.stderr

    assert result.returncode == 0, f"the fast probe should pass cleanly: {output!r}"
    assert STAMP_PREFIX not in output, (
        f"a test that finished inside its ceiling must emit no host-load stamp -- got {output!r}"
    )

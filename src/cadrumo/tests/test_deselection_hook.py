"""Real-subprocess proof of the marker-deselection reporting hook.

:mod:`cadrumo.tests._deselection_hook` is a ``pytest_terminal_summary`` hook
whose entire product is terminal output, and whose trigger conditions are
session facts pytest assembles (the aggregated ``deselected`` stat, the
``-m`` expression, the ``--collect-only`` flag). Calling ``apply`` directly
with a hand-built reporter would prove only that the function writes strings
it was given the inputs to write; it would not prove that pytest calls it,
that the stats it reads carry what it expects, or that the banner reaches a
reader. So every case below boots a REAL, fresh pytest subprocess against a
throwaway fixture tree wired to the real hook module (the exact module under
test, not a reimplementation) and asserts on the ACTUAL captured output,
following the real-subprocess idiom established by
:mod:`cadrumo.tests.test_worker_count_hook`.

The xdist case is the load-bearing one. Marker deselection happens inside
xdist workers, so the controller's stats never receive the deselected count
-- which is exactly the default ``-n auto`` invocation this hook most needs
to cover. The hook therefore triggers the empty-selection banner on the
executed count rather than the deselected count, and only that real
``-n``-booted run can prove it.

No mocks: each run is a genuine pytest boot of the real hook.

See Also:
    :mod:`cadrumo.tests._deselection_hook`
        The hook under test.
    :mod:`cadrumo.tests.test_worker_count_hook`
        Sibling conftest hook proven by the same real-subprocess idiom.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from ._deselection_hook import apply

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SUBPROCESS_TIMEOUT_SECONDS = 120

_PROBE_INI = """
[pytest]
markers =
    unit: fast lane
    integration: slow lane
"""

_PROBE_CONFTEST = """
from cadrumo.tests._deselection_hook import apply as _report_deselection


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    _report_deselection(terminalreporter, exitstatus, config)
"""

_PROBE_ALL_INTEGRATION = """
import pytest

pytestmark = [pytest.mark.integration]


def test_one():
    assert True


def test_two():
    assert True
"""

_PROBE_MIXED = """
import pytest


@pytest.mark.unit
def test_selected():
    assert True


@pytest.mark.integration
def test_deselected():
    assert True
"""


def _probe_output(probe_body: str, *extra_args: str) -> str:
    """Boot a real pytest subprocess over a throwaway tree wired to the real hook.

    The tree is created under the system temp directory rather than inside
    the repository so the subprocess cannot pick up this project's own
    ``addopts`` (which pin ``-m unit -n auto``) and contaminate the
    selection under test.

    Args:
        probe_body: Source of the probe test module to run.
        *extra_args: Extra pytest arguments (the ``-m`` expression, ``-n``,
            ``--collect-only``) that set up the case.

    Returns:
        The subprocess's combined stdout and stderr.
    """
    with tempfile.TemporaryDirectory(prefix="deselection-hook-poc-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        (tmp_path / "pytest.ini").write_text(_PROBE_INI, encoding="utf-8")
        (tmp_path / "conftest.py").write_text(_PROBE_CONFTEST, encoding="utf-8")
        (tmp_path / "test_probe.py").write_text(probe_body, encoding="utf-8")

        result = subprocess.run(  # noqa: S603 - fixed interpreter argv; extra args are test-local literals.
            [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "test_probe.py", *extra_args],
            cwd=tmp_path,
            env=dict(os.environ),
            capture_output=True,
            text=True,
            check=False,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        )
        return result.stdout + result.stderr


def test_a_fully_deselected_run_is_reported_as_nothing_ran() -> None:
    """A run that selected nothing announces it instead of reporting success.

    This is the sharpest case the hook exists for: pytest's own footer says
    "no tests ran" quietly and exits without a failure, so the run that did
    nothing looks indistinguishable from the run that passed.
    """
    assert callable(apply)
    output = _probe_output(_PROBE_ALL_INTEGRATION, "-m", "unit")

    assert "NOTHING RAN" in output
    assert "executed 0 tests" in output
    # The banner must name the selection that caused it, or the reader cannot act.
    assert "unit" in output


def test_a_fully_deselected_xdist_run_still_reports_nothing_ran() -> None:
    """The empty-selection banner does not depend on the deselected count.

    xdist deselects inside its workers, so the controller's stats carry no
    deselected count on exactly the default ``-n auto`` invocation. A hook
    keyed on that count would go silent precisely where it is needed most;
    this drives a real ``-n``-booted run to prove it does not.
    """
    output = _probe_output(_PROBE_ALL_INTEGRATION, "-m", "unit", "-n", "2")

    assert "NOTHING RAN" in output


def test_a_partially_deselected_run_names_both_counts() -> None:
    """A partial run states how many ran and how many never executed."""
    output = _probe_output(_PROBE_MIXED, "-m", "unit")

    assert "PARTIAL RUN" in output
    assert "1 tests ran; 1 were DESELECTED" in output


def test_a_full_run_emits_no_banner() -> None:
    """Anti-false-positive: with nothing deselected, neither banner fires.

    Without this, a hook that printed unconditionally would satisfy every
    assertion above while training the reader to ignore the banner -- the
    exact habit the hook exists to break.
    """
    output = _probe_output(_PROBE_MIXED)

    assert "NOTHING RAN" not in output
    assert "PARTIAL RUN" not in output


def test_a_collect_only_run_emits_no_banner() -> None:
    """A collect-only run executes nothing BY DESIGN and is not flagged.

    Inventory checks are collect-only by nature; warning on them would fire
    the banner constantly and devalue it.
    """
    output = _probe_output(_PROBE_ALL_INTEGRATION, "-m", "unit", "--collect-only")

    assert "NOTHING RAN" not in output

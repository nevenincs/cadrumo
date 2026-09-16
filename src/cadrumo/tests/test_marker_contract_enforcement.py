"""Real-behaviour gate for reporting a marker-contract violation under xdist workers.

The taxonomy contract refuses a test that does not carry exactly one execution
marker and one ``hex_*`` marker. Raising is the clearest report at ``-n0``, but
:func:`cadrumo.tests.marker_hook.apply` runs INSIDE each xdist worker, where an
exception kills the worker: the controller then reports only
``assert not crashitem`` and names neither the test nor the contract, and the
real error appears solely on a ``-n0`` re-run. The violation therefore travels
the sanctioned ``workeroutput`` channel, exactly as the serial hold does.

The proof runs a REAL nested pytest over a generated two-test package -- one
sound test, one carrying both ``unit`` and ``integration`` -- through the real
hook, twice: once at ``-n0`` (the raise still reports) and once under real xdist
workers (the worker survives, the sound test runs, and the controller names the
violation). Nothing is patched or stubbed.

Anti-tautology: the ``-n0`` leg proves the worker-channel path did not replace
the raise, and the xdist leg asserts the run is NOT green and carries no
internal error -- the exact shape the old behaviour produced.

See Also:
    :mod:`cadrumo.tests.marker_hook`
        Hosts the collection hook this module exercises.
    :mod:`cadrumo.tests.test_serial_marker_enforcement`
        The same worker-to-controller handoff, proved for the ``serial`` hold.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from cadrumo.tests.audited_process import ensure_text_completed_process, run_audited_process

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_CONFTEST = """\
from cadrumo.tests.marker_hook import (
    apply,
    fail_session_on_marker_violations,
    record_marker_violations_from_node,
    report_marker_violations,
    reset_marker_violations,
)


def pytest_configure(config):
    reset_marker_violations()
    for name in ("unit", "integration", "hex_core"):
        config.addinivalue_line("markers", name + ": taxonomy marker")


def pytest_collection_modifyitems(config, items):
    apply(config, items)


def pytest_testnodedown(node, error):
    record_marker_violations_from_node(node)


def pytest_sessionfinish(session, exitstatus):
    fail_session_on_marker_violations(session)


def pytest_terminal_summary(terminalreporter):
    report_marker_violations(terminalreporter)
"""

_TEST_MODULE = """\
import pytest

pytestmark = [pytest.mark.hex_core]


@pytest.mark.unit
def test_well_marked():
    pass


@pytest.mark.unit
@pytest.mark.integration
def test_two_execution_markers():
    pass
"""

_VIOLATION_NODE = "test_generated.py::test_two_execution_markers"


def _nested_pytest(package: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run a real nested pytest over ``package`` with the shared hook installed."""
    return ensure_text_completed_process(
        run_audited_process(
            [
                sys.executable,
                "-m",
                "pytest",
                "-p",
                "no:cacheprovider",
                "-c",
                str(package / "pytest.ini"),
                "-v",
                *args,
                str(package / "test_generated.py"),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
            check=False,
        )
    )


@pytest.fixture
def mis_marked_package(tmp_path: Path) -> Path:
    """Materialise a package whose second test carries two execution markers."""
    (tmp_path / "pytest.ini").write_text("[pytest]\naddopts =\n", encoding="utf-8")
    (tmp_path / "conftest.py").write_text(textwrap.dedent(_CONFTEST), encoding="utf-8")
    (tmp_path / "test_generated.py").write_text(textwrap.dedent(_TEST_MODULE), encoding="utf-8")
    return tmp_path


def test_a_mis_marked_test_is_named_without_workers(mis_marked_package: Path) -> None:
    """At ``-n0`` the contract still raises, naming the node and both markers."""
    completed = _nested_pytest(mis_marked_package, "-n0")
    output = completed.stdout + completed.stderr

    assert completed.returncode == int(pytest.ExitCode.USAGE_ERROR), output
    assert _VIOLATION_NODE in output, f"the refusal must name the offending test:\n{output}"
    assert "must carry exactly one of" in output, f"the refusal must state the contract:\n{output}"
    assert "integration" in output and "unit" in output, f"the refusal must name what it found:\n{output}"


def test_a_mis_marked_test_is_reported_under_real_xdist_workers(mis_marked_package: Path) -> None:
    """Under real workers the violation reports instead of crashing the worker."""
    completed = _nested_pytest(mis_marked_package, "-n2", "--dist=loadfile")
    output = completed.stdout + completed.stderr

    assert "INTERNALERROR" not in output, f"a mis-marked test must not kill the worker:\n{output}"
    assert "crashitem" not in output, f"the controller must report the contract, not a crash:\n{output}"
    assert completed.returncode == int(pytest.ExitCode.USAGE_ERROR), output
    assert "MARKER CONTRACT VIOLATED" in output, f"the controller must report the violation:\n{output}"
    assert _VIOLATION_NODE in output, f"the report must name the offending test:\n{output}"
    assert "must carry exactly one of" in output, f"the report must state the contract:\n{output}"
    assert "MarkerContractViolationWarning" in output, f"the worker-side refusal must be announced:\n{output}"
    assert "1 passed" in completed.stdout, f"the soundly marked test must still run:\n{output}"

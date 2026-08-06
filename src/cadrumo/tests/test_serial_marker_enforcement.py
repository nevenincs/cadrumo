"""Real-behaviour gate for the ``serial`` marker's xdist hold.

``serial`` declares that a test "must run without xdist workers". Nothing
enforced that: pytest-xdist has no ``serial`` concept, and no scheduler hook in
this repository supplied one, so the marker was honoured only by the justfile
splitting the integration lane into a ``not serial`` parallel pass and a ``-n0``
serial pass. Every other invocation ran isolation-sensitive tests against a
run-varying set of co-resident files.
:func:`~tests._marker_hook._hold_serial_items_from_xdist` closes that, and this
module is its proof.

The proof runs a REAL nested pytest over a generated two-test package -- one
plain test, one ``serial`` -- through the real hook, twice: once at ``-n0``
(both must execute) and once under real xdist workers (the plain one executes,
the serial one is held and announced). Nothing is patched or stubbed; the
subprocess is the isolation boundary, so the assertions read the same terminal
output an operator would.

Anti-tautology: the ``-n0`` leg proves the hold is CONDITIONAL. A hook that
simply dropped every serial test, or one that never fired at all, fails one leg
or the other -- neither can satisfy both.

See Also:
    :mod:`~tests._marker_hook`
        Hosts the collection hook this module exercises.
    :mod:`~tests._deselection_hook`
        Reports deselection; documents why the worker-side deselected count
        never reaches the controller, which is why the hold also warns.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_MARKER_HOOK_MODULE = Path(__file__).resolve().parent / "_marker_hook.py"

_CONFTEST = """\
import sys
from pathlib import Path

sys.path.insert(0, {marker_hook_dir!r})

import _marker_hook


def pytest_configure(config):
    config.addinivalue_line("markers", "serial: isolation-sensitive")
    for name in ("unit", "hex_core"):
        config.addinivalue_line("markers", name + ": taxonomy marker")


def pytest_collection_modifyitems(config, items):
    _marker_hook.apply(config, items)
"""

_TEST_MODULE = """\
import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_parallel_safe():
    pass


@pytest.mark.serial
def test_needs_isolation():
    pass
"""


def _nested_pytest(package: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run a real nested pytest over ``package`` with the shared hook installed."""
    return subprocess.run(  # noqa: S603 - fixed interpreter argv over a repository-owned harness
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


@pytest.fixture
def serial_marker_package(tmp_path: Path) -> Path:
    """Materialise a two-test package wired to the real marker hook."""
    (tmp_path / "pytest.ini").write_text("[pytest]\naddopts =\n", encoding="utf-8")
    (tmp_path / "conftest.py").write_text(
        textwrap.dedent(_CONFTEST).format(marker_hook_dir=str(_MARKER_HOOK_MODULE.parent)),
        encoding="utf-8",
    )
    (tmp_path / "test_generated.py").write_text(textwrap.dedent(_TEST_MODULE), encoding="utf-8")
    return tmp_path


def test_serial_item_runs_when_no_xdist_workers_are_active(serial_marker_package: Path) -> None:
    """At ``-n0`` the hold must not fire: both tests execute.

    This is the conditional half of the contract. Without it a hook that
    unconditionally dropped every serial test would look correct.
    """
    completed = _nested_pytest(serial_marker_package, "-n0")

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "test_parallel_safe" in completed.stdout
    assert "test_needs_isolation" in completed.stdout, (
        f"a serial test must still run with no workers active:\n{completed.stdout}"
    )
    assert "2 passed" in completed.stdout, completed.stdout


def test_serial_item_is_held_and_announced_under_real_xdist_workers(serial_marker_package: Path) -> None:
    """Under real workers the serial item is held out, and the hold is stated.

    The announcement is asserted structurally -- the warning class name and the
    held node id -- never on the message prose.
    """
    completed = _nested_pytest(serial_marker_package, "-n2", "--dist=loadfile")
    output = completed.stdout + completed.stderr

    assert completed.returncode == 0, output
    assert "1 passed" in completed.stdout, output
    assert "test_needs_isolation" not in completed.stdout.split("warnings summary")[0], (
        f"the serial test must not execute while xdist workers are active:\n{completed.stdout}"
    )
    assert "SerialTestsHeldWarning" in output, f"the hold must be announced, not silent:\n{output}"
    assert "test_generated.py::test_needs_isolation" in output, f"the announcement must name the held test:\n{output}"

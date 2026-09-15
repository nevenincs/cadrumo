"""Real-subprocess proof of the unresolved-fixture collection refusal.

Each case boots a REAL nested pytest over a throwaway package whose conftest
wires the real hook module, and asserts on its exit status and output. Nothing
is patched: the subprocess is the isolation boundary.

The clean package exercises every legitimate way a closure name resolves --
a conftest fixture, a fixture visible only from its own directory, direct
parametrization, ``usefixtures`` and the built-in ``request`` -- so a detector
that refused too eagerly fails the clean leg, and one that never fired fails
every defect leg.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from cadrumo.tests.audited_process import ensure_text_completed_process, run_audited_process

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_HOOK_MODULE = Path(__file__).resolve().parent / "_fixture_resolution_hook.py"

_CONFTEST = """\
import sys

import pytest

sys.path.insert(0, {hook_dir!r})

import _fixture_resolution_hook


def pytest_configure(config):
    _fixture_resolution_hook.reset_refused_requests()
    for name in ("unit", "integration"):
        config.addinivalue_line("markers", name + ": lane marker")


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config, items):
    _fixture_resolution_hook.apply(config, items)


def pytest_testnodedown(node, error):
    _fixture_resolution_hook.record_refused_from_node(node)


def pytest_sessionfinish(session, exitstatus):
    _fixture_resolution_hook.fail_session_on_refused_requests(session)


def pytest_terminal_summary(terminalreporter):
    _fixture_resolution_hook.report_refused_requests(terminalreporter)


@pytest.fixture
def shared_value():
    return 3
"""

_OWNER_CONFTEST = """\
import pytest


@pytest.fixture
def owner_only_value(shared_value):
    return shared_value + 1
"""

_CLEAN_OWNER_MODULE = """\
import pytest


@pytest.mark.unit
def test_uses_conftest_and_directory_fixture(shared_value, owner_only_value, request):
    assert owner_only_value == shared_value + 1
    assert request.node.name


@pytest.mark.unit
@pytest.mark.parametrize("direct", [1, 2])
def test_direct_parametrization_resolves(direct, shared_value):
    assert direct < shared_value


@pytest.mark.unit
@pytest.mark.usefixtures("shared_value")
def test_usefixtures_resolves():
    pass
"""

_SIBLING_REQUESTS_INVISIBLE = """\
import pytest


@pytest.mark.unit
def test_sibling_cannot_see_owner_fixture(owner_only_value):
    assert owner_only_value
"""

_UNDEFINED_PARAMETER = """\
import pytest


@pytest.mark.unit
def test_selected_and_healthy(shared_value):
    assert shared_value == 3


@pytest.mark.integration
def test_requests_undefined(never_defined_snapshot, tmp_path):
    assert never_defined_snapshot
"""

_UNDEFINED_TRANSITIVE = """\
import pytest


@pytest.fixture
def wraps_missing(missing_dependency):
    return missing_dependency


@pytest.mark.unit
def test_transitively_unresolved(wraps_missing):
    assert wraps_missing
"""


def _package(root: Path, modules: dict[str, str]) -> Path:
    """Materialise a package wired to the real hook, with ``modules`` beneath it."""
    (root / "pytest.ini").write_text("[pytest]\naddopts =\n", encoding="utf-8")
    (root / "conftest.py").write_text(_CONFTEST.format(hook_dir=str(_HOOK_MODULE.parent)), encoding="utf-8")
    owner = root / "owner"
    owner.mkdir()
    (owner / "conftest.py").write_text(_OWNER_CONFTEST, encoding="utf-8")
    for relative, body in modules.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(textwrap.dedent(body), encoding="utf-8")
    return root


def _nested_pytest(package: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run a real nested pytest over ``package``."""
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
                "--rootdir",
                str(package),
                *args,
                str(package),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
            check=False,
        )
    )


def test_every_legitimate_resolution_route_collects_and_runs(tmp_path: Path) -> None:
    """Conftest, directory-scoped, parametrized, ``usefixtures`` and ``request`` all resolve."""
    package = _package(tmp_path, {"owner/test_clean.py": _CLEAN_OWNER_MODULE})

    completed = _nested_pytest(package, "-n0")
    output = completed.stdout + completed.stderr

    assert completed.returncode == int(pytest.ExitCode.OK), output
    assert "4 passed" in completed.stdout, output


def test_an_undefined_parameter_refuses_the_run_before_anything_executes(tmp_path: Path) -> None:
    """The refusal names the node and the fixture, and no test runs."""
    package = _package(tmp_path, {"test_undefined.py": _UNDEFINED_PARAMETER})

    completed = _nested_pytest(package, "-n0")
    output = completed.stdout + completed.stderr

    assert completed.returncode == int(pytest.ExitCode.USAGE_ERROR), output
    assert "test_undefined.py::test_requests_undefined" in output, output
    assert "never_defined_snapshot" in output, output
    assert "passed" not in completed.stdout, output


def test_a_collect_only_preflight_refuses_what_setup_would_have_errored_on(tmp_path: Path) -> None:
    """Collection alone surfaces the defect; pytest by itself exits 0 here."""
    package = _package(tmp_path, {"test_undefined.py": _UNDEFINED_PARAMETER})

    completed = _nested_pytest(package, "--collect-only", "-q")
    output = completed.stdout + completed.stderr

    assert completed.returncode == int(pytest.ExitCode.USAGE_ERROR), output
    assert "never_defined_snapshot" in output, output


def test_a_marker_deselected_dead_test_is_still_refused(tmp_path: Path) -> None:
    """A lane that would never execute the dead test still refuses it."""
    package = _package(tmp_path, {"test_undefined.py": _UNDEFINED_PARAMETER})

    completed = _nested_pytest(package, "-n0", "-m", "unit")
    output = completed.stdout + completed.stderr

    assert completed.returncode == int(pytest.ExitCode.USAGE_ERROR), output
    assert "test_undefined.py::test_requests_undefined" in output, output


def test_a_fixture_defined_only_in_an_invisible_conftest_is_refused(tmp_path: Path) -> None:
    """Resolution is node-scoped: a definition elsewhere in the tree does not count."""
    package = _package(
        tmp_path,
        {
            "owner/test_clean.py": _CLEAN_OWNER_MODULE,
            "sibling/test_sibling.py": _SIBLING_REQUESTS_INVISIBLE,
        },
    )

    completed = _nested_pytest(package, "-n0")
    output = completed.stdout + completed.stderr

    assert completed.returncode == int(pytest.ExitCode.USAGE_ERROR), output
    assert "sibling/test_sibling.py::test_sibling_cannot_see_owner_fixture" in output, output
    assert "owner/test_clean.py" not in output, output


def test_a_transitively_unresolved_dependency_is_refused(tmp_path: Path) -> None:
    """A defined fixture whose own dependency is missing leaves the test dead too."""
    package = _package(tmp_path, {"test_transitive.py": _UNDEFINED_TRANSITIVE})

    completed = _nested_pytest(package, "-n0")
    output = completed.stdout + completed.stderr

    assert completed.returncode == int(pytest.ExitCode.USAGE_ERROR), output
    assert "missing_dependency" in output, output


def test_real_xdist_workers_hand_the_refusal_to_the_controller(tmp_path: Path) -> None:
    """Under workers the run exits USAGE_ERROR and names the node, never an internal error."""
    package = _package(tmp_path, {"test_undefined.py": _UNDEFINED_PARAMETER})

    completed = _nested_pytest(package, "-n2", "-m", "unit")
    output = completed.stdout + completed.stderr

    assert completed.returncode == int(pytest.ExitCode.USAGE_ERROR), output
    assert "INTERNALERROR" not in output, output
    assert "UNRESOLVED FIXTURE REQUESTS" in output, output
    assert "test_undefined.py::test_requests_undefined" in output, output

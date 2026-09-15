"""Real-subprocess proof of the unresolved-fixture session refusal.

Each case boots a REAL nested pytest over a throwaway package whose conftest
wires the real hook module, and asserts on its exit status and on the refused
node ids the terminal summary names. Nothing is patched: the subprocess is the
isolation boundary.

Assertions read only the lines inside the refusal section and compare them as
an exact node-id map. Node ids use forward slashes on every platform, and exact
equality proves both halves at once: every dead test is named, and nothing
healthy -- a built-in, an override, a parametrized argument -- is.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from cadrumo.tests.audited_process import ensure_text_completed_process, run_audited_process

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_BANNER = "UNRESOLVED FIXTURE REQUESTS"
_RENDERED_NAMES_PREFIX = "unresolved fixture(s) "

_CONFTEST = """\
import pytest

from cadrumo.tests.fixture_resolution_hook import (
    apply,
    fail_session_on_refused_requests,
    record_refused_from_node,
    report_refused_requests,
    reset_refused_requests,
)


def pytest_configure(config):
    reset_refused_requests()
    for name in ("unit", "integration"):
        config.addinivalue_line("markers", name + ": lane marker")


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config, items):
    apply(config, items)


def pytest_testnodedown(node, error):
    record_refused_from_node(node)


def pytest_sessionfinish(session, exitstatus):
    fail_session_on_refused_requests(session)


def pytest_terminal_summary(terminalreporter):
    report_refused_requests(terminalreporter)


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
def test_selected_and_healthy(shared_value, tmp_path, monkeypatch):
    assert shared_value == 3


@pytest.mark.integration
def test_requests_undefined(never_defined_snapshot, tmp_path, monkeypatch):
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

_INDIRECT_PARAMETRIZATION = """\
import pytest


@pytest.mark.unit
@pytest.mark.parametrize("direct_value", [1])
def test_direct_argument_needs_no_fixture(direct_value):
    assert direct_value == 1


@pytest.mark.unit
@pytest.mark.parametrize("shared_value", [7], indirect=True)
def test_indirect_argument_with_a_real_fixture(shared_value):
    assert shared_value == 3


@pytest.mark.unit
@pytest.mark.parametrize("ghost_indirect", [5], indirect=True)
def test_indirect_argument_without_a_fixture(ghost_indirect):
    assert ghost_indirect
"""

_FAILURE_BESIDE_DEAD_TEST = """\
import pytest


@pytest.mark.unit
def test_genuinely_fails():
    assert 1 == 2


@pytest.mark.unit
def test_dead(never_defined_snapshot):
    assert never_defined_snapshot
"""

_CUSTOM_EXIT_BESIDE_DEAD_TEST = """\
import pytest


@pytest.mark.unit
def test_dead(never_defined_snapshot):
    assert never_defined_snapshot


@pytest.mark.unit
def test_stops_the_session():
    pytest.exit("stopping with a custom status", returncode=7)
"""

_CLASS_AND_MODULE_OVERRIDES = """\
import pytest


@pytest.fixture
def shared_value():
    return 30


@pytest.mark.unit
def test_module_override_wins(shared_value):
    assert shared_value == 30


@pytest.mark.unit
class TestClassScopedFixture:
    @pytest.fixture
    def shared_value(self):
        return 300

    @pytest.fixture
    def class_only_value(self):
        return 1

    def test_class_override_wins(self, shared_value, class_only_value):
        assert (shared_value, class_only_value) == (300, 1)


@pytest.mark.unit
def test_outside_the_class_cannot_see_its_fixture(class_only_value):
    assert class_only_value
"""

_AUTOUSE_WITH_MISSING_DEPENDENCY = """\
import pytest


@pytest.fixture(autouse=True)
def installs_something(missing_for_autouse):
    return missing_for_autouse


@pytest.mark.unit
def test_requests_nothing_itself():
    pass
"""


def _package(root: Path, modules: dict[str, str]) -> Path:
    """Materialise a package wired to the real hook, with ``modules`` beneath it."""
    (root / "pytest.ini").write_text("[pytest]\naddopts =\n", encoding="utf-8")
    (root / "conftest.py").write_text(_CONFTEST, encoding="utf-8")
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


def _refused(output: str) -> dict[str, str]:
    """Map each node id listed inside the refusal section to its rendered fixture names.

    Only indented lines between the section banner and the next separator are
    read, so progress lines, tracebacks and paths elsewhere in the output
    cannot satisfy or break an assertion.
    """
    lines = output.splitlines()
    start = next((index for index, line in enumerate(lines) if _BANNER in line), None)
    if start is None:
        return {}
    refused: dict[str, str] = {}
    for line in lines[start + 1 :]:
        if line.startswith("="):
            break
        if not line.startswith("  "):
            continue
        nodeid, _, rest = line.strip().partition(" (")
        refused[nodeid] = rest.rpartition(_RENDERED_NAMES_PREFIX)[2]
    return refused


def test_every_legitimate_resolution_route_collects_and_runs(tmp_path: Path) -> None:
    """Conftest, directory-scoped, parametrized, ``usefixtures`` and ``request`` all resolve."""
    package = _package(tmp_path, {"owner/test_clean.py": _CLEAN_OWNER_MODULE})

    completed = _nested_pytest(package, "-n0")
    output = completed.stdout + completed.stderr

    assert completed.returncode == int(pytest.ExitCode.OK), output
    assert "4 passed" in completed.stdout, output
    assert _BANNER not in output, output


def test_a_clean_package_under_real_xdist_workers_exits_zero(tmp_path: Path) -> None:
    """The worker hand-off adds no refusal of its own to a healthy distributed run."""
    package = _package(tmp_path, {"owner/test_clean.py": _CLEAN_OWNER_MODULE})

    completed = _nested_pytest(package, "-n2")
    output = completed.stdout + completed.stderr

    assert completed.returncode == int(pytest.ExitCode.OK), output
    assert "4 passed" in completed.stdout, output
    assert _BANNER not in output, output


def test_a_dead_test_fails_the_session_without_erasing_healthy_verdicts(tmp_path: Path) -> None:
    """The healthy test still runs; only the undefined name is refused, never the built-ins."""
    package = _package(tmp_path, {"test_undefined.py": _UNDEFINED_PARAMETER})

    completed = _nested_pytest(package, "-n0")
    output = completed.stdout + completed.stderr

    assert completed.returncode == int(pytest.ExitCode.USAGE_ERROR), output
    assert "1 passed" in completed.stdout, output
    assert _refused(output) == {"test_undefined.py::test_requests_undefined": "['never_defined_snapshot']"}, output


def test_a_collect_only_preflight_refuses_what_setup_would_have_errored_on(tmp_path: Path) -> None:
    """Collection alone surfaces the defect; pytest by itself exits 0 here."""
    package = _package(tmp_path, {"test_undefined.py": _UNDEFINED_PARAMETER})

    completed = _nested_pytest(package, "--collect-only", "-q")
    output = completed.stdout + completed.stderr

    assert completed.returncode == int(pytest.ExitCode.USAGE_ERROR), output
    assert _refused(output) == {"test_undefined.py::test_requests_undefined": "['never_defined_snapshot']"}, output


def test_a_marker_deselected_dead_test_is_still_refused(tmp_path: Path) -> None:
    """A lane that would never execute the dead test still refuses it."""
    package = _package(tmp_path, {"test_undefined.py": _UNDEFINED_PARAMETER})

    completed = _nested_pytest(package, "-n0", "-m", "unit")
    output = completed.stdout + completed.stderr

    assert completed.returncode == int(pytest.ExitCode.USAGE_ERROR), output
    assert _refused(output) == {"test_undefined.py::test_requests_undefined": "['never_defined_snapshot']"}, output


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
    assert _refused(output) == {
        "sibling/test_sibling.py::test_sibling_cannot_see_owner_fixture": "['owner_only_value']",
    }, output


def test_a_transitively_unresolved_dependency_is_refused(tmp_path: Path) -> None:
    """A defined fixture whose own dependency is missing leaves the test dead too."""
    package = _package(tmp_path, {"test_transitive.py": _UNDEFINED_TRANSITIVE})

    completed = _nested_pytest(package, "-n0")
    output = completed.stdout + completed.stderr

    assert completed.returncode == int(pytest.ExitCode.USAGE_ERROR), output
    assert _refused(output) == {"test_transitive.py::test_transitively_unresolved": "['missing_dependency']"}, output


def test_only_direct_parametrization_exempts_an_argument(tmp_path: Path) -> None:
    """An indirect argument still needs a real fixture; a direct one does not."""
    package = _package(tmp_path, {"test_indirect.py": _INDIRECT_PARAMETRIZATION})

    completed = _nested_pytest(package, "-n0")
    output = completed.stdout + completed.stderr

    assert completed.returncode == int(pytest.ExitCode.USAGE_ERROR), output
    assert "2 passed" in completed.stdout, output
    assert _refused(output) == {
        "test_indirect.py::test_indirect_argument_without_a_fixture[5]": "['ghost_indirect']",
    }, output


def test_class_and_module_overrides_resolve_while_class_fixtures_stay_class_scoped(tmp_path: Path) -> None:
    """Overrides are honoured; a class fixture requested outside the class is refused."""
    package = _package(tmp_path, {"test_overrides.py": _CLASS_AND_MODULE_OVERRIDES})

    completed = _nested_pytest(package, "-n0")
    output = completed.stdout + completed.stderr

    assert completed.returncode == int(pytest.ExitCode.USAGE_ERROR), output
    assert "2 passed" in completed.stdout, output
    assert _refused(output) == {
        "test_overrides.py::test_outside_the_class_cannot_see_its_fixture": "['class_only_value']",
    }, output


def test_an_autouse_fixture_with_a_missing_dependency_is_refused(tmp_path: Path) -> None:
    """A test that requests nothing is still dead when an autouse fixture cannot resolve."""
    package = _package(tmp_path, {"test_autouse.py": _AUTOUSE_WITH_MISSING_DEPENDENCY})

    completed = _nested_pytest(package, "-n0")
    output = completed.stdout + completed.stderr

    assert completed.returncode == int(pytest.ExitCode.USAGE_ERROR), output
    assert _refused(output) == {"test_autouse.py::test_requests_nothing_itself": "['missing_for_autouse']"}, output


def test_a_genuine_failure_beside_a_dead_test_exits_usage_error(tmp_path: Path) -> None:
    """``TESTS_FAILED`` is overridden, so a dead test cannot hide behind an ordinary red run."""
    package = _package(tmp_path, {"test_failing.py": _FAILURE_BESIDE_DEAD_TEST})

    completed = _nested_pytest(package, "-n0")
    output = completed.stdout + completed.stderr

    assert completed.returncode == int(pytest.ExitCode.USAGE_ERROR), output
    assert "1 failed" in completed.stdout, output
    assert _refused(output) == {"test_failing.py::test_dead": "['never_defined_snapshot']"}, output


def test_a_custom_pytest_exit_status_is_preserved(tmp_path: Path) -> None:
    """A more specific verdict than a plain pass or fail is never replaced."""
    package = _package(tmp_path, {"test_custom_exit.py": _CUSTOM_EXIT_BESIDE_DEAD_TEST})

    completed = _nested_pytest(package, "-n0", "-p", "no:randomly")
    output = completed.stdout + completed.stderr

    assert completed.returncode == 7, output


def test_real_xdist_workers_hand_the_refusal_to_the_controller(tmp_path: Path) -> None:
    """Under workers the run exits USAGE_ERROR and names the node, never an internal error."""
    package = _package(tmp_path, {"test_undefined.py": _UNDEFINED_PARAMETER})

    completed = _nested_pytest(package, "-n2", "-m", "unit")
    output = completed.stdout + completed.stderr

    assert completed.returncode == int(pytest.ExitCode.USAGE_ERROR), output
    assert "INTERNALERROR" not in output, output
    assert _refused(output) == {"test_undefined.py::test_requests_undefined": "['never_defined_snapshot']"}, output

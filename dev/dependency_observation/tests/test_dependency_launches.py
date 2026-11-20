"""An observed process's child launches are judged: only a child that journals itself leaves the observation complete.

The unit cases drive ``Observation.audit`` and ``Observation.instrument_child``
with synthetic events and never install the process-global hook. The real
subprocess cases run an observed parent that starts real children, because an
audit hook can never be removed from the process that installs it. Expected
digests are computed here with ``hashlib``, independently of the observer.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from dev.packaging.command_execution import run_command

from ..census_admission import PRODUCT_CENSUS, SUPPORT_CENSUSES
from ..observation import CHECKOUT_ROOT_FILE, CHILD_SCRIPT_NAME, Observation

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_WORKTREE = Path(__file__).resolve().parents[3]
_PACKAGE = "dev/dependency_observation"
#: A second script copy whose launches the observation under test registers as journalling itself.
WORKER_SCRIPT_NAME = "registered_worker.py"
_JOURNALS_UNDER_TEST = "journals-under-test"
_CENSUS_LOADER = "src/cadrumo/tests/module_target_inventory.py"
_PAYLOAD = b"\x00child payload\xff"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write(path: Path, data: bytes | str = b"") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data.encode() if isinstance(data, str) else data)
    return path


@pytest.fixture
def root(tmp_path: Path) -> Path:
    directory = tmp_path / "checkout"
    directory.mkdir()
    return directory.resolve()


@pytest.fixture
def journals(tmp_path: Path) -> Path:
    directory = tmp_path / "journals"
    directory.mkdir()
    return directory.resolve()


@pytest.fixture
def observation(root: Path) -> Observation:
    return Observation(root, started_ns=time.time_ns())


@pytest.fixture
def adopting(observation: Observation, journals: Path) -> Observation:
    observation.adopt_journal_directory(journals, (WORKER_SCRIPT_NAME, CHILD_SCRIPT_NAME))
    return observation


def _popen(observation: Observation, command: object) -> None:
    observation.audit("subprocess.Popen", (None, command, None, None))


def _reasons(observation: Observation) -> str:
    return "\n".join(observation.incomplete)


# Which launches are covered ------------------------------------------------------


@pytest.mark.parametrize("script", [WORKER_SCRIPT_NAME, CHILD_SCRIPT_NAME])
def test_a_popen_running_a_registered_script_copy_is_covered(
    adopting: Observation, journals: Path, script: str
) -> None:
    _popen(adopting, [sys.executable, "-I", "-B", str(journals / script), "token"])
    assert adopting.incomplete == []


def test_a_registered_script_copy_is_matched_without_regard_to_case(adopting: Observation, journals: Path) -> None:
    _popen(adopting, [sys.executable, str(journals / WORKER_SCRIPT_NAME).swapcase()])
    assert adopting.incomplete == []


def test_a_string_command_naming_a_registered_script_copy_is_covered(adopting: Observation, journals: Path) -> None:
    _popen(adopting, f'"{sys.executable}" "{journals / WORKER_SCRIPT_NAME}"')
    assert adopting.incomplete == []


@pytest.mark.parametrize(
    "command",
    [
        [sys.executable, "-c", "pass"],
        [sys.executable, "-m", "json.tool"],
        "cmd /c echo",
        [sys.executable, str(Path("elsewhere") / WORKER_SCRIPT_NAME)],
    ],
    ids=["dash-c", "foreign-module", "shell-string", "same-name-script-elsewhere"],
)
def test_a_popen_that_runs_no_registered_script_makes_the_observation_incomplete(
    adopting: Observation, command: object
) -> None:
    _popen(adopting, command)
    assert "unobserved child process" in _reasons(adopting)


def test_a_popen_is_unobserved_when_the_process_adopted_no_journal_directory(observation: Observation) -> None:
    _popen(observation, [sys.executable, "-c", "pass"])
    assert "unobserved child process" in _reasons(observation)


@pytest.mark.parametrize("event", ["os.system", "os.spawn", "os.exec", "os.startfile", "os.fork", "os.forkpty"])
def test_any_other_process_launching_event_makes_the_observation_incomplete(adopting: Observation, event: str) -> None:
    adopting.audit(event, ("anything",))
    assert adopting.incomplete == [f"unobserved child process ({event})"]


def test_a_covered_popen_is_not_made_incomplete_by_the_native_launch_it_is_built_on(
    adopting: Observation, journals: Path
) -> None:
    _popen(adopting, [sys.executable, str(journals / WORKER_SCRIPT_NAME)])
    adopting.audit("_winapi.CreateProcess", (None, "cmd", None, None, 0, 0, None, None, None))
    assert adopting.incomplete == []


def test_a_covered_popen_covers_exactly_one_native_launch(adopting: Observation, journals: Path) -> None:
    _popen(adopting, [sys.executable, str(journals / WORKER_SCRIPT_NAME)])
    adopting.audit("os.posix_spawn", ("python", ["python"], {}))
    assert adopting.incomplete == []
    adopting.audit("os.posix_spawn", ("python", ["python"], {}))
    assert adopting.incomplete == ["unjudged child process (os.posix_spawn)"]


@pytest.mark.parametrize("event", ["_winapi.CreateProcess", "os.posix_spawn"])
def test_a_native_launch_with_no_judged_popen_before_it_makes_the_observation_incomplete(
    adopting: Observation, event: str
) -> None:
    adopting.audit(event, ("x",))
    assert adopting.incomplete == [f"unjudged child process ({event})"]


def test_a_native_launch_is_not_covered_by_a_popen_judged_on_another_thread(
    adopting: Observation, journals: Path
) -> None:
    worker = threading.Thread(target=_popen, args=(adopting, [sys.executable, str(journals / WORKER_SCRIPT_NAME)]))
    worker.start()
    worker.join()
    adopting.audit("_winapi.CreateProcess", ("x",))
    assert adopting.incomplete == ["unjudged child process (_winapi.CreateProcess)"]


# Native launches through ctypes --------------------------------------------------


def test_a_native_create_process_whose_command_line_names_a_registered_script_is_covered(
    adopting: Observation, journals: Path
) -> None:
    adopting.audit("ctypes.dlsym", (object(), "CreateProcessW"))
    adopting.audit("ctypes.create_unicode_buffer", (f'"{sys.executable}" "{journals / CHILD_SCRIPT_NAME}" tok', 260))
    adopting.settle_launches()
    assert adopting.incomplete == []


def test_a_native_create_process_whose_command_line_names_no_registered_script_is_incomplete(
    adopting: Observation,
) -> None:
    adopting.audit("ctypes.dlsym", (object(), "CreateProcessA"))
    adopting.audit("ctypes.create_unicode_buffer", ("cmd /c echo", 260))
    adopting.settle_launches()
    assert "unobserved child process cmd /c echo" in _reasons(adopting)


def test_a_native_create_process_lookup_with_no_command_line_ever_seen_is_incomplete_when_settled(
    adopting: Observation,
) -> None:
    adopting.audit("ctypes.dlsym", (object(), "CreateProcessW"))
    assert adopting.incomplete == []
    adopting.settle_launches()
    assert adopting.incomplete == ["native CreateProcessW launch with an unseen command line"]
    adopting.settle_launches()
    assert len(adopting.incomplete) == 1, "a settled lookup is reported once"


def test_a_native_create_process_buffer_sized_by_an_integer_is_incomplete(adopting: Observation) -> None:
    adopting.audit("ctypes.dlsym", (object(), "CreateProcessW"))
    adopting.audit("ctypes.create_unicode_buffer", (260, None))
    assert adopting.incomplete == ["native CreateProcessW launch with an unseen command line"]


def test_other_native_lookups_and_unrelated_buffers_are_not_launches(adopting: Observation) -> None:
    adopting.audit("ctypes.dlsym", (object(), "GetCurrentProcessId"))
    adopting.audit("ctypes.create_unicode_buffer", ("cmd /c echo", 260))
    adopting.settle_launches()
    assert adopting.incomplete == []


def test_a_native_lookup_is_settled_by_note_imported_modules(adopting: Observation) -> None:
    adopting.audit("ctypes.dlsym", (object(), "CreateProcessW"))
    adopting.note_imported_modules()
    assert "native CreateProcessW launch with an unseen command line" in _reasons(adopting)


# Rewriting a Python -m checkout child --------------------------------------------


@pytest.fixture
def checkout_module(root: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    _write(root / "tiny_child.py", "print('hello')\n")
    monkeypatch.syspath_prepend(str(root))
    return "tiny_child"


def test_a_python_dash_m_checkout_module_child_is_routed_through_the_bootstrap(
    adopting: Observation, journals: Path, tmp_path: Path, checkout_module: str
) -> None:
    journal = tmp_path / "parent.journal"
    adopting.attach_journal_path(journal)
    rewritten = adopting.instrument_child([sys.executable, "-S", "-m", checkout_module, "arg-one", "--flag"])

    assert isinstance(rewritten, list)
    token = rewritten[3]
    assert rewritten == [
        sys.executable,
        "-S",
        str(journals / CHILD_SCRIPT_NAME),
        token,
        checkout_module,
        "arg-one",
        "--flag",
    ]
    assert len(token) == 32 and set(token) <= set("0123456789abcdef")
    lines = [line.split("	") for line in journal.read_text(encoding="utf-8").splitlines()]
    assert [line[0] for line in lines] == ["B"]
    # The rewritten command is itself a registered script launch, so its Popen is covered.
    _popen(adopting, rewritten)
    assert adopting.incomplete == []


def test_each_instrumented_child_gets_its_own_token(adopting: Observation, checkout_module: str) -> None:
    command = [sys.executable, "-m", checkout_module]
    first, second = adopting.instrument_child(command), adopting.instrument_child(command)
    assert isinstance(first, list) and isinstance(second, list)
    assert first[2] != second[2]


def test_a_tuple_command_is_rewritten_to_a_list(adopting: Observation, journals: Path, checkout_module: str) -> None:
    rewritten = adopting.instrument_child((sys.executable, "-m", checkout_module))
    assert isinstance(rewritten, list)
    assert rewritten[1] == str(journals / CHILD_SCRIPT_NAME)


def test_a_child_command_is_left_alone_when_the_process_has_no_journal_directory(
    observation: Observation, checkout_module: str
) -> None:
    command = [sys.executable, "-m", checkout_module]
    assert observation.instrument_child(command) is command
    # Left alone, the launch is judged unobserved.
    _popen(observation, command)
    assert "unobserved child process" in _reasons(observation)


@pytest.mark.parametrize(
    "build",
    [
        lambda module: [sys.executable, "-m", "json.tool"],
        lambda module: [sys.executable, "-c", "pass"],
        lambda module: ["not-a-interpreter", "-m", module],
        lambda module: [sys.executable, "script.py", "-m", module],
        lambda module: [sys.executable, "-m", "no_such_checkout_module"],
        lambda module: f"{sys.executable} -m {module}",
        lambda module: [sys.executable, "-m", module, 7],
    ],
    ids=["stdlib-module", "dash-c", "not-python", "script-first", "unresolved-module", "string", "non-text-word"],
)
def test_any_other_command_is_left_unrewritten(
    adopting: Observation, checkout_module: str, build: Callable[[str], object]
) -> None:
    command = build(checkout_module)
    assert adopting.instrument_child(command) is command


# Reading the child's journal -----------------------------------------------------


def test_a_missing_child_journal_adds_nothing(observation: Observation, journals: Path) -> None:
    observation.harvest(journals)
    assert observation.incomplete == []


def test_an_empty_child_journal_adds_nothing(observation: Observation, journals: Path) -> None:
    _write(journals / "deadbeef.journal", b"")
    observation.harvest(journals)
    assert observation.incomplete == []
    assert observation.files == {} and observation.listings == {}


def test_a_journal_that_began_is_folded_in(observation: Observation, journals: Path, root: Path) -> None:
    data = root / "data.bin"
    _write(data, b"x")
    digest = _sha(b"x")
    _write(journals / "deadbeef.journal", f"B\t-\t1\nF\t{digest}\t{data}\n")
    observation.harvest(journals)
    assert observation.incomplete == []
    assert observation.files == {data: digest}


def test_a_non_empty_journal_that_does_not_begin_is_incomplete(observation: Observation, journals: Path) -> None:
    _write(journals / "deadbeef.journal", "F\tabc\t/somewhere\n")
    observation.harvest(journals)
    assert "deadbeef.journal never began" in _reasons(observation)
    assert observation.files == {}


def test_a_journal_line_naming_an_expected_child_is_now_unreadable(observation: Observation, journals: Path) -> None:
    _write(journals / "child.journal", "B\t-\t1\nE\t150\tgrandchild\n")
    observation.harvest(journals)
    assert "has an unreadable line" in _reasons(observation)


def test_harvest_returns_the_journal_directory_to_the_checks_own(
    observation: Observation, journals: Path, tmp_path: Path
) -> None:
    own = tmp_path / "own"
    own.mkdir()
    observation.own_journals = own
    observation.adopt_journal_directory(journals)
    observation.harvest(journals)
    assert observation.journal_directory == own


# Real processes ------------------------------------------------------------------

_PARENT = """\
import json
import subprocess
import sys
from pathlib import Path

root, storage, scenario = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
sys.path.insert(0, str(root))
from dev.dependency_observation import observation as observing

observation = observing.observe_process(root)
journals = storage.parent / "journals-under-test"
child_script = Path(observing.__file__).with_name(observing.CHILD_SCRIPT_NAME)
observing.populate_journal_directory(observation, journals, {observing.CHILD_SCRIPT_NAME: child_script})
launch_start = {
    "module": [sys.executable, "-S", "-m", "tiny_child", "one"],
    "pointer-missing": [sys.executable, "-S", "-m", "tiny_child", "one"],
    "undeclared-module": [sys.executable, "-S", "-m", "undeclared_child"],
    "dash-c": [sys.executable, "-c", "print('plain')"],
    "foreign-module": [sys.executable, "-m", "json.tool", "--help"],
}[scenario]
if scenario == "pointer-missing":
    (journals / sys.argv[4]).unlink()
process = subprocess.Popen(
    launch_start, cwd=str(root), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True
)
output = process.communicate()[0]
observation.harvest(journals)
print(json.dumps({
    "args": process.args,
    "returncode": process.returncode,
    "output": output,
    "journals": str(journals),
    "files": {str(path): digest for path, digest in observation.files.items()},
    "incomplete": observation.incomplete,
}))
"""


def _census(*targets: str) -> str:
    source = {
        "package": "tiny_child",
        "source_root": ".",
        "subpackages": [],
        "exclude_test_packages": True,
        "exclude_test_module_prefixes": ["test_", "_test_", "conftest"],
    }
    target_set = {"kind": "python-module-names", "source": source, "targets": sorted(targets)}
    return json.dumps({"schema_version": 1, "target_sets": {"checkout": target_set}})


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    """A synthetic checkout holding its own copy of the observer, its census loader, a census and a tiny module."""
    directory = tmp_path / "real-checkout"
    for package in ("dev", _PACKAGE, "src/cadrumo/tests"):
        _write(directory / package / "__init__.py")
    for name in ("observation.py", "census_admission.py", CHILD_SCRIPT_NAME):
        shutil.copyfile(_WORKTREE / _PACKAGE / name, directory / _PACKAGE / name)
    shutil.copyfile(_WORKTREE / _CENSUS_LOADER, directory / _CENSUS_LOADER)
    _write(directory / PRODUCT_CENSUS, _census("tiny_child"))
    for partition in SUPPORT_CENSUSES:
        _write(directory / partition, _census("support_only"))
    _write(directory / "undeclared_child.py", "print('ran')\n")
    _write(directory / "src" / "cadrumo" / "__init__.py", "# package\n")
    _write(directory / "data" / "payload.bin", _PAYLOAD)
    _write(
        directory / "tiny_child.py",
        "import sys\nfrom pathlib import Path\n"
        "print(__name__, sys.argv[1:], Path('data/payload.bin').read_bytes().hex())\n",
    )
    (directory / "storage").mkdir()
    return directory.resolve()


def _observed_parent(checkout: Path, scenario: str, *extra: str) -> dict[str, object]:
    result = run_command(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            _PARENT,
            str(checkout),
            str(checkout / "storage" / "profile"),
            scenario,
            *extra,
        ],
        cwd=checkout,
        environment=None,
    )
    assert result.returncode == 0, result.stderr
    document = json.loads(result.stdout.strip().splitlines()[-1])
    assert isinstance(document, dict)
    return {str(name): value for name, value in document.items()}


def test_a_real_python_dash_m_child_runs_through_the_bootstrap_and_its_reads_reach_the_parent(checkout: Path) -> None:
    summary = _observed_parent(checkout, "module")

    args = summary["args"]
    journals = Path(str(summary["journals"]))
    assert journals == checkout / "storage" / _JOURNALS_UNDER_TEST
    assert isinstance(args, list)
    assert args[:2] == [sys.executable, "-S"]
    assert Path(args[2]) == journals / CHILD_SCRIPT_NAME
    assert args[4:] == ["tiny_child", "one"]
    assert summary["returncode"] == 0
    assert summary["output"] == f"__main__ ['one'] {_PAYLOAD.hex()}\n"

    journal = journals / f"{args[3]}.journal"
    assert journal.read_text(encoding="utf-8").startswith("B\t-\t")

    files = summary["files"]
    assert isinstance(files, dict)
    assert files[str(checkout / "data" / "payload.bin")] == _sha(_PAYLOAD)
    assert files[str(checkout / "tiny_child.py")] == _sha((checkout / "tiny_child.py").read_bytes())
    assert summary["incomplete"] == []


def test_a_real_child_that_dies_before_its_bootstrap_journals_adds_nothing(checkout: Path) -> None:
    summary = _observed_parent(checkout, "pointer-missing", CHECKOUT_ROOT_FILE)
    assert summary["returncode"] != 0
    assert summary["incomplete"] == []


def test_a_real_child_whose_module_the_census_does_not_declare_is_refused_and_journalled(checkout: Path) -> None:
    summary = _observed_parent(checkout, "undeclared-module")
    assert summary["returncode"] != 0
    assert summary["output"] == ""
    incomplete = summary["incomplete"]
    assert isinstance(incomplete, list)
    assert any("does not declare 'undeclared_child'" in str(reason) for reason in incomplete), incomplete


@pytest.mark.parametrize("scenario", ["dash-c", "foreign-module"])
def test_a_real_child_that_cannot_journal_makes_the_observation_incomplete(checkout: Path, scenario: str) -> None:
    summary = _observed_parent(checkout, scenario)
    incomplete = summary["incomplete"]
    assert isinstance(incomplete, list)
    assert any("unobserved child process" in str(reason) for reason in incomplete), incomplete


# Ending a judged launch ----------------------------------------------------------


def test_a_popen_that_returned_does_not_cover_a_later_native_launch(adopting: Observation, journals: Path) -> None:
    _popen(adopting, [sys.executable, str(journals / WORKER_SCRIPT_NAME)])
    adopting.end_launch()
    adopting.audit("os.posix_spawn", ("python", ["python"], {}))
    assert adopting.incomplete == ["unjudged child process (os.posix_spawn)"]


def test_a_native_launch_inside_the_judged_popen_is_still_covered_before_it_ends(
    adopting: Observation, journals: Path
) -> None:
    _popen(adopting, [sys.executable, str(journals / WORKER_SCRIPT_NAME)])
    adopting.audit("_winapi.CreateProcess", ("x",))
    adopting.end_launch()
    assert adopting.incomplete == []


_WRAPPED = """import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root))
from dev.dependency_observation import observation as observing


def posix_like_constructor(self, args, *arguments, **keywords):
    # A POSIX Popen raises its audit event and no native one afterwards.
    sys.audit("subprocess.Popen", None, args, None, None)


subprocess.Popen.__init__ = posix_like_constructor
observation = observing.observe_process(root)
journals = root / "journals"
journals.mkdir()
observation.adopt_journal_directory(journals, ["registered_worker.py"])
script = journals / "registered_worker.py"
subprocess.Popen([sys.executable, str(script)])
print("after popen", observation.incomplete)
sys.audit("os.posix_spawn", "python", ["python"], {})
print("after spawn", observation.incomplete)
"""


def test_the_real_popen_wrapper_ends_the_judged_launch_when_the_constructor_returns(checkout: Path) -> None:
    result = run_command([sys.executable, "-I", "-B", "-c", _WRAPPED, str(checkout)], cwd=checkout, environment=None)
    assert result.returncode == 0, result.stderr
    lines = result.stdout.strip().splitlines()
    assert lines[-2] == "after popen []"
    assert lines[-1] == "after spawn ['unjudged child process (os.posix_spawn)']"


_REAL_LAUNCH = """import json
import os
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root))
from dev.dependency_observation import observation as observing

observation = observing.observe_process(root)
journals = root / "journals"
journals.mkdir()
observation.adopt_journal_directory(journals, ["registered_worker.py"])
script = journals / "registered_worker.py"
script.write_text("pass\\n", encoding="utf-8")
# The real Popen constructor, wrapped by the observer: on POSIX it forks and
# execs without a native audit event, on Windows it raises _winapi.CreateProcess.
process = subprocess.Popen([sys.executable, "-I", "-S", str(script)])
process.wait()
after_popen = list(observation.incomplete)
if hasattr(os, "posix_spawn"):
    child = os.posix_spawn(sys.executable, [sys.executable, "-I", "-S", "-c", "pass"], dict(os.environ))
    os.waitpid(child, 0)
else:
    # No posix_spawn here: raise the event a real call raises, through the installed hook.
    sys.audit("os.posix_spawn", sys.executable, [sys.executable], {})
print(json.dumps({"returncode": process.returncode, "after_popen": after_popen, "after_spawn": observation.incomplete}))
"""


def test_a_real_popen_that_returned_leaves_a_later_posix_spawn_unobserved(checkout: Path) -> None:
    """The observer's real Popen wrapper ends its judged launch, so an unrelated spawn after it is not covered.

    POSIX runs a real ``os.posix_spawn``. A platform without one raises the
    same audit event through the real hook, after a real covered Popen.
    """
    result = run_command(
        [sys.executable, "-I", "-B", "-c", _REAL_LAUNCH, str(checkout)], cwd=checkout, environment=None
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout.strip().splitlines()[-1])
    assert summary["returncode"] == 0
    assert summary["after_popen"] == []
    assert summary["after_spawn"] == ["unjudged child process (os.posix_spawn)"]

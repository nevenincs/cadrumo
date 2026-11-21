"""An inherited run's bootstrap, option judgment and harvest.

The unit cases drive pure functions, the environment builder, the harvest of
hand-made journal directories and ``Observation.audit`` with synthetic launch
events, and never install the process-global hook. The integration cases start
real Python processes with the run's environment: a real child, a missing roots
file, and a parent that starts a child with a reduced environment. Expected
digests are computed here with ``hashlib``, independently of the observer.
"""

from __future__ import annotations

import hashlib
import os
import sys
import time
from pathlib import Path

import pytest

from dev.packaging.command_execution import run_command

from ..observation import (
    INHERITED_JOURNALS_VARIABLE,
    INHERITED_ROOTS_FILE,
    INHERITED_SITE_DIRECTORY,
    InheritedJournals,
    Observation,
    _isolating,
    harvest_inherited,
    prepare_inherited_journals,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_WORKTREE = Path(__file__).resolve().parents[3]
_PYTHON_PATH = "PYTHONPATH"


@pytest.fixture
def root(tmp_path: Path) -> Path:
    directory = tmp_path / "checkout"
    directory.mkdir()
    return directory.resolve()


@pytest.fixture
def journals(tmp_path: Path, root: Path) -> InheritedJournals:
    return prepare_inherited_journals(tmp_path / "journals", observed_root=root, tooling_root=_WORKTREE)


# The interpreter options that stop a child importing the inherited bootstrap ---------


@pytest.mark.unit
@pytest.mark.parametrize(
    "words",
    [
        pytest.param(["python", "-I", "-c", "pass"], id="isolated"),
        pytest.param(["python", "-E", "script.py"], id="ignore-environment"),
        pytest.param(["python", "-S", "script.py"], id="no-site"),
        pytest.param(["python", "-BI", "script.py"], id="grouped-isolated"),
        pytest.param(["python", "-BES", "script.py"], id="grouped-environment-and-site"),
        pytest.param(["python", "-X", "importtime", "-I", "script.py"], id="after-an-x-option-and-its-value"),
        pytest.param(["python", "-Xutf8", "-I", "script.py"], id="after-a-joined-x-option"),
        pytest.param(["python", "-Wignore", "-I", "script.py"], id="after-a-joined-warning-option"),
        pytest.param(["python", "-W", "error", "-S", "script.py"], id="after-a-warning-option-and-its-value"),
    ],
)
def test_an_option_that_stops_the_bootstrap_is_isolating(words: list[str]) -> None:
    assert _isolating(words) is True


@pytest.mark.unit
@pytest.mark.parametrize(
    "words",
    [
        pytest.param(["python", "script.py"], id="a-script"),
        pytest.param(["python", "-c", "pass"], id="a-command"),
        pytest.param(["python", "-B", "-u", "script.py"], id="harmless-options"),
        pytest.param(["python", "-X", "utf8", "script.py"], id="an-x-option-and-its-value"),
        pytest.param(["python", "-Xutf8", "script.py"], id="a-joined-x-option"),
        pytest.param(["python", "-X", "I", "script.py"], id="an-x-value-that-spells-an-option"),
        pytest.param(["python", "-XI", "script.py"], id="a-joined-x-value-that-spells-an-option"),
        pytest.param(["python", "-W", "E", "script.py"], id="a-warning-value-that-spells-an-option"),
        pytest.param(["python", "-c", "pass", "-I"], id="an-option-after-the-command-is-the-programs"),
        pytest.param(["python", "-m", "module", "-S"], id="an-option-after-the-module-is-the-programs"),
        pytest.param(["python", "script.py", "-E"], id="an-option-after-the-script-is-the-programs"),
        pytest.param(["python", "-Bc", "pass", "-I"], id="grouped-with-the-command-option"),
        pytest.param(["python", "--version"], id="a-long-option"),
        pytest.param(["python", "-", "-I"], id="standard-input"),
        pytest.param(["python"], id="no-arguments"),
    ],
)
def test_other_command_lines_keep_the_bootstrap(words: list[str]) -> None:
    assert _isolating(words) is False


# The environment that makes a process observe itself -----------------------------------


@pytest.mark.unit
def test_the_environment_names_the_journals_and_puts_the_bootstrap_first(tmp_path: Path) -> None:
    journals = InheritedJournals(tmp_path / "journals")
    given = {"KEPT": "1", _PYTHON_PATH: os.pathsep.join(("elsewhere", "other"))}

    environment = journals.environment(given)

    assert environment[INHERITED_JOURNALS_VARIABLE] == str(tmp_path / "journals")
    assert environment[_PYTHON_PATH].split(os.pathsep) == [
        str(tmp_path / "journals" / INHERITED_SITE_DIRECTORY),
        "elsewhere",
        "other",
    ]
    assert environment["KEPT"] == "1"
    assert INHERITED_JOURNALS_VARIABLE not in given
    assert given[_PYTHON_PATH] == os.pathsep.join(("elsewhere", "other"))


@pytest.mark.unit
def test_the_environment_without_a_python_path_holds_only_the_bootstrap(tmp_path: Path) -> None:
    environment = InheritedJournals(tmp_path / "journals").environment({})

    assert environment[_PYTHON_PATH] == str(tmp_path / "journals" / INHERITED_SITE_DIRECTORY)


@pytest.mark.unit
def test_the_environment_lists_each_python_path_entry_once_and_the_bootstrap_first(tmp_path: Path) -> None:
    journals = InheritedJournals(tmp_path / "journals")
    site = str(tmp_path / "journals" / INHERITED_SITE_DIRECTORY)
    given = {_PYTHON_PATH: os.pathsep.join(("a", site, "b", "a", "", "b"))}

    environment = journals.environment(given)

    assert environment[_PYTHON_PATH].split(os.pathsep) == [site, "a", "b"]
    assert journals.environment(environment) == environment


# Judging a launch: the command line Windows reports is one string ----------------------


def _inherited(root: Path, journals: InheritedJournals) -> Observation:
    observation = Observation(root, started_ns=time.time_ns())
    observation.inherited_journals = journals.directory
    return observation


def _popen(observation: Observation, command: object, environment: object = None) -> None:
    observation.audit("subprocess.Popen", (None, command, None, environment))


@pytest.mark.unit
@pytest.mark.parametrize("quoted", [False, True], ids=["plain", "quoted-program"])
def test_an_isolated_python_command_line_given_as_one_string_is_incomplete(
    root: Path, journals: InheritedJournals, quoted: bool
) -> None:
    observation = _inherited(root, journals)
    program = f'"{sys.executable}"' if quoted else sys.executable

    _popen(observation, f"{program} -I -c pass", journals.environment(os.environ))

    assert "isolated from the inherited observer" in "\n".join(observation.incomplete)


@pytest.mark.unit
def test_a_python_command_line_given_as_one_string_that_keeps_the_environment_is_covered(
    root: Path, journals: InheritedJournals
) -> None:
    observation = _inherited(root, journals)

    _popen(observation, f'"{sys.executable}" -c "pass"', journals.environment(os.environ))
    _popen(observation, [sys.executable, "-c", "pass"], journals.environment(os.environ))

    assert observation.incomplete == []


@pytest.mark.unit
def test_a_non_python_command_line_given_as_one_string_is_incomplete(root: Path, journals: InheritedJournals) -> None:
    observation = _inherited(root, journals)

    _popen(observation, "cmd /c exit 0", journals.environment(os.environ))

    assert "unobserved child process" in "\n".join(observation.incomplete)


# Harvesting a run's journals ------------------------------------------------------------


@pytest.mark.unit
def test_a_run_in_which_no_process_journalled_is_incomplete(tmp_path: Path, root: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()

    observation = harvest_inherited(InheritedJournals(empty), root)

    assert "no process of the run was observed" in observation.incomplete
    assert observation.files == {}


@pytest.mark.unit
def test_a_journal_that_holds_nothing_does_not_count_as_a_process_that_began(tmp_path: Path, root: Path) -> None:
    directory = tmp_path / "journals"
    directory.mkdir()
    (directory / "killed.journal").write_text("", encoding="utf-8")

    observation = harvest_inherited(InheritedJournals(directory), root)

    assert "no process of the run was observed" in observation.incomplete


@pytest.mark.unit
def test_a_journal_that_says_it_is_incomplete_makes_the_harvest_incomplete(tmp_path: Path, root: Path) -> None:
    directory = tmp_path / "journals"
    directory.mkdir()
    (directory / "one.journal").write_text("B\t-\t1\nX\t-\tsome reason\n", encoding="utf-8")

    observation = harvest_inherited(InheritedJournals(directory), root)

    assert observation.incomplete == ["worker: some reason"]


# Real processes started with the run's environment --------------------------------------


def _run(argv: list[str], root: Path, environment: dict[str, str]) -> None:
    result = run_command(argv, cwd=root, environment=environment)
    assert result.returncode == 0, result.stderr


@pytest.mark.integration
def test_a_real_python_process_journals_the_checkout_file_it_read(root: Path, journals: InheritedJournals) -> None:
    (root / "data.txt").write_bytes(b"consumed bytes")
    program = "from pathlib import Path; Path('data.txt').read_bytes()"

    _run([sys.executable, "-c", program], root, journals.environment(os.environ))

    observation = harvest_inherited(journals, root)
    assert observation.incomplete == []
    assert observation.files[root / "data.txt"] == hashlib.sha256(b"consumed bytes").hexdigest()


@pytest.mark.integration
def test_a_bootstrap_that_cannot_read_its_roots_makes_the_harvest_incomplete_and_the_program_still_runs(
    root: Path, journals: InheritedJournals
) -> None:
    (journals.directory / INHERITED_ROOTS_FILE).unlink()
    program = "from pathlib import Path; Path('ran.txt').write_text('ran')"

    _run([sys.executable, "-c", program], root, journals.environment(os.environ))

    assert (root / "ran.txt").read_text(encoding="utf-8") == "ran"
    observation = harvest_inherited(journals, root)
    assert any("bootstrap failed in process" in reason for reason in observation.incomplete), observation.incomplete
    assert "no process of the run was observed" not in observation.incomplete


_PARENT = """\
import os, subprocess, sys

dropped = sys.argv[1]
environment = dict(os.environ)
environment.pop(dropped, None)
subprocess.run([sys.executable, "-c", "pass"], env=environment, check=True)
"""


@pytest.mark.integration
@pytest.mark.parametrize("dropped", [INHERITED_JOURNALS_VARIABLE, _PYTHON_PATH])
def test_a_child_that_drops_the_inherited_environment_makes_the_harvest_incomplete(
    root: Path, journals: InheritedJournals, dropped: str
) -> None:
    _run([sys.executable, "-c", _PARENT, dropped], root, journals.environment(os.environ))

    observation = harvest_inherited(journals, root)

    assert any("without the inherited observer's environment" in reason for reason in observation.incomplete), (
        observation.incomplete
    )


@pytest.mark.integration
def test_a_child_that_keeps_the_inherited_environment_leaves_the_harvest_complete(
    root: Path, journals: InheritedJournals
) -> None:
    _run([sys.executable, "-c", _PARENT, "UNRELATED_VARIABLE"], root, journals.environment(os.environ))

    observation = harvest_inherited(journals, root)

    assert observation.incomplete == []
    assert len(list(journals.directory.glob("*.journal"))) >= 2


# Directories the run created -------------------------------------------------------------


def _journal(directory: Path, name: str, *lines: str) -> None:
    (directory / f"{name}.journal").write_text("".join(f"{line}\n" for line in ("B\t-\t1", *lines)), encoding="utf-8")


@pytest.mark.unit
def test_reads_under_a_created_directory_are_dropped_and_their_conflicts_are_no_conflict(
    tmp_path: Path, root: Path
) -> None:
    directory = tmp_path / "journals"
    directory.mkdir()
    holder = root / "var"
    holder.mkdir()
    scratch = holder / "scratch"
    _journal(
        directory,
        "a",
        f"D\t{'1' * 64}\t{holder}",
        f"C\t-\t{scratch}",
        f"F\t{'2' * 64}\t{scratch / 'x.txt'}",
        f"D\t{'3' * 64}\t{scratch}",
    )
    # The reading process's journal sorts before the creating one's, and its digests differ.
    _journal(
        directory, "0", f"F\t{'4' * 64}\t{scratch / 'x.txt'}", f"D\t{'5' * 64}\t{scratch}", f"D\t{'6' * 64}\t{holder}"
    )

    observation = harvest_inherited(InheritedJournals(directory), root)

    assert observation.incomplete == []
    assert observation.files == {}
    assert observation.listings == {holder: hashlib.sha256(b"").hexdigest()}


@pytest.mark.unit
def test_a_conflict_outside_a_created_directory_still_makes_the_harvest_incomplete(tmp_path: Path, root: Path) -> None:
    directory = tmp_path / "journals"
    directory.mkdir()
    _journal(directory, "a", f"C\t-\t{root / 'scratch'}", f"F\t{'1' * 64}\t{root / 'data.txt'}")
    _journal(directory, "b", f"F\t{'2' * 64}\t{root / 'data.txt'}")

    observation = harvest_inherited(InheritedJournals(directory), root)

    assert any("changed between the processes that read it" in reason for reason in observation.incomplete)


_SCRATCH_PARENT = """import os, subprocess, sys, tempfile
from pathlib import Path

holder = Path(sys.argv[1])
os.listdir(holder)
child = "import os, sys; from pathlib import Path; os.listdir(sys.argv[1]); Path(sys.argv[1], 'a.txt').read_text()"
with tempfile.TemporaryDirectory(dir=holder) as scratch:
    Path(scratch, "a.txt").write_text("first")
    subprocess.run([sys.executable, "-c", child, scratch], check=True)
    Path(scratch, "a.txt").write_text("second")
    Path(scratch, "a.txt").read_text()
"""


@pytest.mark.integration
def test_scratch_two_processes_read_under_the_checkout_is_no_input_and_leaves_the_harvest_complete(
    root: Path, journals: InheritedJournals
) -> None:
    holder = root / "var" / "storage" / "tmp"
    holder.mkdir(parents=True)

    _run([sys.executable, "-c", _SCRATCH_PARENT, str(holder)], root, journals.environment(os.environ))

    observation = harvest_inherited(journals, root)
    assert observation.incomplete == []
    assert list(holder.iterdir()) == []
    assert not [
        path for path in (*observation.files, *observation.listings) if path.is_relative_to(holder) and path != holder
    ]
    assert observation.listings[holder] == hashlib.sha256(b"").hexdigest()


@pytest.mark.integration
def test_a_directory_made_with_exist_ok_that_was_already_there_is_not_created(
    root: Path, journals: InheritedJournals
) -> None:
    (root / "pre").mkdir()
    (root / "pre" / "data.txt").write_bytes(b"already here")
    program = "from pathlib import Path; Path('pre').mkdir(exist_ok=True); Path('pre/data.txt').read_bytes()"

    _run([sys.executable, "-c", program], root, journals.environment(os.environ))

    observation = harvest_inherited(journals, root)
    assert observation.incomplete == []
    assert observation.created == set()
    assert observation.files[root / "pre" / "data.txt"] == hashlib.sha256(b"already here").hexdigest()

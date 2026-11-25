"""The dependency observer records exactly the checkout inputs a process consumed.

``Observation.audit`` is a plain method, so the unit cases drive it with
synthetic audit events and never install the process-global hook. The
subprocess cases run real child interpreters, because an audit hook can never
be removed from the process that installs it. Expected digests are computed
here with ``hashlib``, independently of the observer.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import sys
import time
from pathlib import Path

import pytest

from dev.packaging.command_execution import run_command

from ..observation import CHECKOUT_ROOT_FILE, CHILD_SCRIPT_NAME, Observation, file_digest

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_WORKTREE = Path(__file__).resolve().parents[3]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _names_digest(*names: str) -> str:
    return _sha("\n".join(sorted(names)).encode("utf-8"))


def _write(path: Path, data: bytes | str = b"") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data.encode() if isinstance(data, str) else data)
    return path


def _opened(observation: Observation, path: Path, mode: str | None = "rb", flags: int = 0) -> None:
    observation.audit("open", (str(path), mode, flags))


@pytest.fixture
def root(tmp_path: Path) -> Path:
    directory = tmp_path / "checkout"
    directory.mkdir()
    return directory.resolve()


@pytest.fixture
def observation(root: Path) -> Observation:
    return Observation(root, started_ns=time.time_ns())


def test_a_read_open_records_the_files_content_digest(root: Path, observation: Observation) -> None:
    target = _write(root / "src" / "mod.py", b"print('observed')\n")
    _opened(observation, target)
    assert observation.files == {target: _sha(b"print('observed')\n")}
    assert observation.incomplete == []


@pytest.mark.parametrize("mode", ["r", "rb", "rt", "r+", "rb+", "a+", "ab+"])
def test_an_open_that_can_consume_the_existing_bytes_is_recorded(
    root: Path, observation: Observation, mode: str
) -> None:
    target = _write(root / "readable.txt", b"existing")
    _opened(observation, target, mode)
    assert observation.files == {target: _sha(b"existing")}


@pytest.mark.parametrize("mode", ["w", "wb", "x", "xb", "a", "ab", "w+", "wb+", "x+"])
def test_an_open_that_never_reads_the_existing_bytes_is_ignored(
    root: Path, observation: Observation, mode: str
) -> None:
    target = _write(root / "out.txt", b"existing")
    _opened(observation, target, mode)
    assert observation.files == {}
    assert observation.listings == {}


@pytest.mark.parametrize("flags", [os.O_RDONLY, os.O_RDWR, os.O_RDWR | os.O_APPEND])
def test_an_open_by_flags_that_can_read_is_recorded(root: Path, observation: Observation, flags: int) -> None:
    target = _write(root / "flagged.txt", b"flag bytes")
    observation.audit("open", (str(target), None, flags))
    assert observation.files == {target: _sha(b"flag bytes")}


@pytest.mark.parametrize(
    "flags",
    [os.O_WRONLY, os.O_WRONLY | os.O_TRUNC, os.O_RDWR | os.O_TRUNC, os.O_RDWR | os.O_CREAT | os.O_EXCL],
    ids=["wronly", "wronly-trunc", "rdwr-trunc", "rdwr-excl"],
)
def test_an_open_by_flags_that_write_only_truncate_or_exclusively_create_is_ignored(
    root: Path, observation: Observation, flags: int
) -> None:
    target = _write(root / "flagged.txt", b"flag bytes")
    observation.audit("open", (str(target), None, flags))
    assert observation.files == {}
    assert observation.listings == {}


def test_file_digest_names_a_directory_a_file_and_an_absent_path(root: Path) -> None:
    (root / "folder").mkdir()
    target = _write(root / "file.bin", b"\x00digest me")
    assert file_digest(root / "folder") == "directory"
    assert file_digest(target) == _sha(b"\x00digest me")
    assert file_digest(root / "nothing-here") == "absent"


def test_a_bytecode_read_is_recorded_as_its_source(root: Path, observation: Observation) -> None:
    source = _write(root / "pkg" / "mod.py", b"x = 1\n")
    bytecode = root / "pkg" / "__pycache__" / "mod.cpython-313.pyc"
    _opened(observation, bytecode)
    assert observation.files == {source: _sha(b"x = 1\n")}


@pytest.mark.parametrize("excluded", [".venv", ".tmp", "build", ".git", ".cache"])
def test_a_file_under_an_excluded_tree_is_ignored(root: Path, observation: Observation, excluded: str) -> None:
    target = _write(root / excluded / "inner" / "file.txt", b"noise")
    _opened(observation, target)
    observation.audit("os.listdir", (str(root / excluded / "inner"),))
    assert observation.files == {}
    assert observation.listings == {}


def test_a_listing_records_the_sorted_entry_names_and_ignores_bytecode_caches(
    root: Path, observation: Observation
) -> None:
    directory = root / "data"
    _write(directory / "b.txt")
    _write(directory / "a.txt")
    _write(directory / "__pycache__" / "a.cpython-313.pyc")
    observation.audit("os.listdir", (str(directory),))
    assert observation.listings == {directory: _names_digest("a.txt", "b.txt")}


def test_scandir_records_a_listing_like_listdir(root: Path, observation: Observation) -> None:
    directory = root / "scanned"
    _write(directory / "only.txt")
    observation.audit("os.scandir", (str(directory),))
    assert observation.listings == {directory: _names_digest("only.txt")}


def test_a_listing_with_no_path_records_the_working_directory(
    root: Path, observation: Observation, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(root / "here.txt")
    monkeypatch.chdir(root)
    observation.audit("os.listdir", (None,))
    assert observation.listings == {root: _names_digest("here.txt")}


def test_a_listing_digest_changes_when_an_entry_is_added_but_not_for_a_bytecode_cache(
    root: Path, observation: Observation
) -> None:
    directory = root / "data"
    _write(directory / "a.txt")
    before = Observation(root, started_ns=0)
    before.audit("os.listdir", (str(directory),))
    _write(directory / "__pycache__" / "x.pyc")
    cache_added = Observation(root, started_ns=0)
    cache_added.audit("os.listdir", (str(directory),))
    _write(directory / "added.txt")
    entry_added = Observation(root, started_ns=0)
    entry_added.audit("os.listdir", (str(directory),))
    assert cache_added.listings == before.listings
    assert entry_added.listings[directory] != before.listings[directory]
    assert entry_added.listings[directory] == _names_digest("a.txt", "added.txt")


def test_a_listing_by_file_descriptor_makes_the_observation_incomplete(observation: Observation) -> None:
    observation.audit("os.listdir", (7,))
    assert len(observation.incomplete) == 1
    assert "file descriptor" in observation.incomplete[0]


def test_an_sqlite_uri_connection_records_the_database_file(root: Path, observation: Observation) -> None:
    database = _write(root / "registry" / "authority.sqlite", b"sqlite-bytes")
    observation.audit("sqlite3.connect", (f"file:{database.as_posix()}?mode=ro&immutable=1",))
    assert observation.files == {database: _sha(b"sqlite-bytes")}


def test_an_in_memory_sqlite_connection_records_nothing(observation: Observation) -> None:
    observation.audit("sqlite3.connect", (":memory:",))
    assert observation.files == {}
    assert observation.incomplete == []


def test_a_recorded_files_parent_listing_is_recorded_too(root: Path, observation: Observation) -> None:
    target = _write(root / "dir" / "file.txt", b"content")
    _write(root / "dir" / "sibling.txt")
    _opened(observation, target)
    assert observation.listings == {root / "dir": _names_digest("file.txt", "sibling.txt")}


def test_nothing_is_recorded_while_suspended(root: Path, observation: Observation) -> None:
    target = _write(root / "quiet.txt", b"q")
    with observation.suspended():
        _opened(observation, target)
        observation.audit("os.listdir", (str(root),))
    assert observation.files == {}
    assert observation.listings == {}
    _opened(observation, target)
    assert set(observation.files) == {target}, "recording resumes after the block"


def test_the_first_seen_digest_is_kept_when_the_file_changes_afterwards(root: Path, observation: Observation) -> None:
    target = _write(root / "moving.txt", b"first")
    _opened(observation, target)
    target.write_bytes(b"second")
    _opened(observation, target)
    assert observation.files == {target: _sha(b"first")}


def test_a_file_that_is_absent_when_read_is_recorded_as_absent(root: Path, observation: Observation) -> None:
    _opened(observation, root / "missing.txt")
    assert observation.files == {root / "missing.txt": "absent"}


def test_an_event_with_an_unexpected_shape_is_an_incomplete_observation_not_a_crash(observation: Observation) -> None:
    observation.audit("open", ())
    assert observation.incomplete
    assert "observer fault" in observation.incomplete[0]


# Worker journals ----------------------------------------------------------------


def _journal_lines(path: Path) -> list[list[str]]:
    return [line.split("\t") for line in path.read_text(encoding="utf-8").splitlines()]


def test_an_attached_journal_starts_with_begin_then_replays_and_streams_observations(
    root: Path, observation: Observation, tmp_path: Path
) -> None:
    early = _write(root / "early.txt", b"early")
    _opened(observation, early)
    journal_path = tmp_path / "1.journal"
    with journal_path.open("w", encoding="utf-8") as journal:
        observation.attach_journal(journal)
        late = _write(root / "late" / "late.txt", b"late")
        _opened(observation, late)
        observation.note_incomplete("reason one")
        lines = _journal_lines(journal_path)

    assert lines[0][0] == "B"
    kinds = [line[0] for line in lines[1:]]
    assert kinds[:2] == ["F", "D"], "the observations made before attaching are replayed first"
    assert lines[1][1:] == [_sha(b"early"), str(early)]
    assert lines[2][1:] == [_names_digest("early.txt"), str(root)]
    assert ["F", _sha(b"late"), str(late)] in lines
    assert ["D", _names_digest("late.txt"), str(late.parent)] in lines
    assert lines[-1] == ["X", "-", "reason one"]


def test_a_journal_folds_into_another_observation_with_the_same_digests(
    root: Path, observation: Observation, tmp_path: Path
) -> None:
    target = _write(root / "sub" / "f.txt", b"payload")
    journal_path = tmp_path / "2.journal"
    with journal_path.open("w", encoding="utf-8") as journal:
        observation.attach_journal(journal)
        _opened(observation, target)

    parent = Observation(root, started_ns=0)
    parent.merge_journal(journal_path)
    assert parent.files == {target: _sha(b"payload")}
    assert parent.listings == {target.parent: _names_digest("f.txt")}
    assert parent.incomplete == []


def test_merging_keeps_the_first_digest_the_parent_already_saw(root: Path, tmp_path: Path) -> None:
    target = root / "shared.txt"
    journal = _write(tmp_path / "3.journal", f"B\t-\t1\nF\t{'b' * 64}\t{target}\n")
    parent = Observation(root, started_ns=0)
    parent.files[target] = "a" * 64
    parent.merge_journal(journal)
    assert parent.files[target] == "a" * 64


@pytest.mark.parametrize(
    ("text", "fragment"),
    [
        ("F\tabc\t/somewhere\n", "never began"),
        ("B\t-\t1\nZ\tabc\t/somewhere\n", "unreadable line"),
        ("B\t-\t1\nX\t-\tsqlite fault\n", "worker: sqlite fault"),
    ],
    ids=["no-begin", "unreadable-line", "worker-reported-incomplete"],
)
def test_a_damaged_or_incomplete_worker_journal_makes_the_observation_incomplete(
    root: Path, tmp_path: Path, text: str, fragment: str
) -> None:
    parent = Observation(root, started_ns=0)
    parent.merge_journal(_write(tmp_path / "4.journal", text))
    assert any(fragment in reason for reason in parent.incomplete), parent.incomplete


def test_an_empty_worker_journal_adds_nothing(root: Path, tmp_path: Path) -> None:
    parent = Observation(root, started_ns=0)
    parent.merge_journal(_write(tmp_path / "5.journal", ""))
    assert parent.incomplete == []
    assert parent.files == {} and parent.listings == {}


def test_a_missing_journal_file_makes_the_observation_incomplete(root: Path, tmp_path: Path) -> None:
    parent = Observation(root, started_ns=0)
    parent.merge_journal(tmp_path / "absent.journal")
    assert any("unreadable worker journal" in reason for reason in parent.incomplete)


def test_harvest_reads_only_journal_files(root: Path, tmp_path: Path) -> None:
    kept = root / "kept.txt"
    ignored = root / "ignored.txt"
    directory = tmp_path / "journals"
    _write(directory / "10.journal", f"B\t-\t10\nF\t{'a' * 64}\t{kept}\n")
    _write(directory / "11.journal.tmp", f"B\t-\t11\nF\t{'a' * 64}\t{ignored}\n")
    _write(directory / "notes.txt", "garbage that is not a journal\n")
    _write(directory / "observed_worker.py", "# not a journal\n")
    parent = Observation(root, started_ns=0)
    parent.harvest(directory)
    assert set(parent.files) == {kept}
    assert parent.incomplete == []


def test_harvest_of_an_unreadable_directory_is_incomplete(root: Path, tmp_path: Path) -> None:
    parent = Observation(root, started_ns=0)
    parent.harvest(tmp_path / "no-such-directory")
    assert any("unreadable worker journal directory" in reason for reason in parent.incomplete)


# Imported modules ---------------------------------------------------------------


def _imported(root: Path, name: str, monkeypatch: pytest.MonkeyPatch) -> Path:
    module = _write(root / f"{name}.py", "VALUE = 1\n")
    monkeypatch.syspath_prepend(str(root))
    importlib.invalidate_caches()
    importlib.import_module(name)
    return module


def test_a_module_older_than_the_process_start_is_recorded_with_its_digest(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    name = "observed_old_module_fixture"
    module = _imported(root, name, monkeypatch)
    try:
        observation = Observation(root, started_ns=module.stat().st_mtime_ns + 5_000_000_000)
        observation.note_imported_modules()
        assert observation.files[module] == _sha(b"VALUE = 1\n")
        # The test process's own imports lie outside this root and are judged as such.
        assert not any("changed after the process started" in reason for reason in observation.incomplete)
    finally:
        sys.modules.pop(name, None)


def test_a_module_modified_at_or_after_the_process_start_is_unobservable(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    name = "observed_new_module_fixture"
    module = _imported(root, name, monkeypatch)
    try:
        observation = Observation(root, started_ns=module.stat().st_mtime_ns)
        observation.note_imported_modules()
        assert any("changed after the process started" in reason for reason in observation.incomplete)
    finally:
        sys.modules.pop(name, None)


# Real child interpreters -------------------------------------------------------


def _child(code: str, *arguments: str, cwd: Path) -> tuple[int, str, str]:
    result = run_command([sys.executable, "-I", "-B", "-c", code, *arguments], cwd=cwd, environment=None)
    return result.returncode, result.stdout, result.stderr


_POPULATE_CHILD = (
    "import json, sys\n"
    "from pathlib import Path\n"
    "sys.path.insert(0, sys.argv[1])\n"
    "from dev.dependency_observation.observation import observe_process, populate_journal_directory\n"
    "observation = observe_process(Path(sys.argv[2]))\n"
    "source = Path(sys.argv[3])\n"
    "populate_journal_directory(observation, Path(sys.argv[4]), {'copy.py': source})\n"
    "print(json.dumps(sorted(observation.worker_scripts)))\n"
)


def test_populating_a_journal_directory_copies_the_scripts_points_at_the_checkout_and_registers_the_copies(
    root: Path, tmp_path: Path
) -> None:
    source = _write(tmp_path / "source.py", b"print('script')\n")
    directory = tmp_path / "journals"
    code, out, err = _child(_POPULATE_CHILD, str(_WORKTREE), str(root), str(source), str(directory), cwd=tmp_path)
    assert code == 0, err
    assert (directory / "copy.py").read_bytes() == source.read_bytes()
    assert (directory / CHECKOUT_ROOT_FILE).read_text(encoding="utf-8") == str(root)
    registered = json.loads(out.strip().splitlines()[-1])
    assert str(directory / "copy.py") in registered


def test_adopting_a_journal_directory_registers_only_the_named_scripts(root: Path, tmp_path: Path) -> None:
    directory = tmp_path / "journals"
    default = Observation(root, started_ns=0)
    default.adopt_journal_directory(directory)
    assert {Path(script).name for script in default.worker_scripts} == {CHILD_SCRIPT_NAME}
    named = Observation(root, started_ns=0)
    named.adopt_journal_directory(directory, ("one.py", "two.py"))
    assert {Path(script).name for script in named.worker_scripts} == {"one.py", "two.py"}

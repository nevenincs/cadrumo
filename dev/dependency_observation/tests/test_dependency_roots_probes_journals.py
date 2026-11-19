"""Probes, aliased roots and disagreeing journals: what the observer records beyond plain reads.

The unit cases drive ``Observation`` methods directly. The probe wrappers
replace ``os.stat`` and friends for the life of the process that installs them,
so those cases run real child interpreters. Expected digests are computed here
with ``hashlib``, independently of the observer.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import time
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest

from dev.packaging.command_execution import run_command

from ..observation import Observation

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


@pytest.fixture
def root(tmp_path: Path) -> Path:
    directory = tmp_path / "checkout"
    directory.mkdir()
    return directory.resolve()


@pytest.fixture
def outside() -> Iterator[Path]:
    """A real directory outside the temporary directory, so off the observer's allowlist."""
    directory = _WORKTREE / ".tmp" / "2026-11-19-docsverify" / "tests-scratch" / f"outside-{uuid.uuid4().hex}"
    directory.mkdir(parents=True)
    try:
        yield directory.resolve()
    finally:
        shutil.rmtree(directory, ignore_errors=True)


@pytest.fixture
def observation(root: Path) -> Observation:
    return Observation(root, started_ns=time.time_ns())


def _link(target: Path, link: Path) -> None:
    """Make ``link`` a directory junction (Windows) or symbolic link to ``target``."""
    if sys.platform == "win32":
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
    else:
        os.symlink(target, link, target_is_directory=True)


# Observation.probe ---------------------------------------------------------------


def test_probing_a_file_records_its_digest_and_its_directory_listing(root: Path, observation: Observation) -> None:
    target = _write(root / "dir" / "probed.bin", b"probe bytes")
    _write(root / "dir" / "sibling.txt")
    observation.probe(str(target))
    assert observation.files == {target: _sha(b"probe bytes")}
    assert observation.listings == {root / "dir": _names_digest("probed.bin", "sibling.txt")}


def test_probing_a_directory_records_directory(root: Path, observation: Observation) -> None:
    (root / "folder").mkdir()
    observation.probe(root / "folder")
    assert observation.files == {root / "folder": "directory"}


def test_probing_an_absent_path_records_absent(root: Path, observation: Observation) -> None:
    observation.probe(root / "missing.txt")
    assert observation.files == {root / "missing.txt": "absent"}


def test_probing_accepts_bytes_paths(root: Path, observation: Observation) -> None:
    target = _write(root / "bytes.bin", b"b")
    observation.probe(os.fsencode(target))
    assert observation.files == {target: _sha(b"b")}


@pytest.mark.parametrize("argument", [3, None, 1.5, ["a"]], ids=["descriptor", "none", "float", "list"])
def test_probing_something_that_is_not_a_path_records_nothing(observation: Observation, argument: object) -> None:
    observation.probe(argument)
    assert observation.files == {}
    assert observation.incomplete == []


def test_probing_while_suspended_records_nothing(root: Path, observation: Observation) -> None:
    inside = _write(root / "inside.txt", b"inside")
    with observation.suspended():
        observation.probe(inside)
    assert observation.files == {}


# Probes in a real process --------------------------------------------------------

_PROBING_CHILD = """\
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from dev.dependency_observation.observation import observe_process

root = Path(sys.argv[2])
observation = observe_process(root)
os.path.exists(root / "os-missing.txt")
os.path.exists(root / "os-dir")
os.stat(root / "os-stat.bin")
os.lstat(root / "os-lstat.bin")
os.path.isfile(root / "os-isfile.bin")
os.path.isdir(root / "os-isdir")
os.path.getsize(root / "os-getsize.bin")
os.access(root / "os-access.bin", os.R_OK)
Path(root / "path-missing.txt").exists()
Path(root / "path-exists.bin").exists()
Path(root / "path-is-file.bin").is_file()
Path(root / "path-not-file").is_file()
print(json.dumps({str(path): digest for path, digest in observation.files.items()}))
"""

_PROBED_FILES = {
    "os-stat.bin": b"stat",
    "os-lstat.bin": b"lstat",
    "os-isfile.bin": b"isfile",
    "os-getsize.bin": b"getsize",
    "os-access.bin": b"access",
    "path-exists.bin": b"exists",
    "path-is-file.bin": b"is_file",
}
_PROBED_DIRECTORIES = ("os-dir", "os-isdir", "path-not-file")
_PROBED_ABSENT = ("os-missing.txt", "path-missing.txt")


@pytest.fixture(scope="module")
def probed(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, str]]:
    root = tmp_path_factory.mktemp("probe-checkout").resolve()
    for name, content in _PROBED_FILES.items():
        _write(root / name, content)
    for name in _PROBED_DIRECTORIES:
        (root / name).mkdir()
    result = run_command(
        [sys.executable, "-I", "-B", "-c", _PROBING_CHILD, str(_WORKTREE), str(root)],
        cwd=root,
        environment=None,
    )
    assert result.returncode == 0, result.stderr
    document = json.loads(result.stdout.strip().splitlines()[-1])
    assert isinstance(document, dict)
    return root, {str(path): str(digest) for path, digest in document.items()}


@pytest.mark.parametrize("name", sorted(_PROBED_FILES))
def test_an_existence_or_metadata_probe_of_a_file_records_its_digest(
    probed: tuple[Path, dict[str, str]], name: str
) -> None:
    root, files = probed
    assert files[str(root / name)] == _sha(_PROBED_FILES[name])


@pytest.mark.parametrize("name", _PROBED_DIRECTORIES)
def test_an_existence_or_metadata_probe_of_a_directory_records_directory(
    probed: tuple[Path, dict[str, str]], name: str
) -> None:
    root, files = probed
    assert files[str(root / name)] == "directory"


@pytest.mark.parametrize("name", _PROBED_ABSENT)
def test_an_existence_probe_of_a_missing_path_records_absent(probed: tuple[Path, dict[str, str]], name: str) -> None:
    root, files = probed
    assert files[str(root / name)] == "absent"


# Aliased roots -------------------------------------------------------------------


def test_a_path_reached_through_a_junction_or_symlink_is_recorded_under_the_resolved_root(
    root: Path, tmp_path: Path
) -> None:
    target = _write(root / "src" / "mod.py", b"x = 1\n")
    alias = tmp_path / "alias"
    _link(root, alias)
    observation = Observation(root, started_ns=time.time_ns())
    observation.audit("open", (str(alias / "src" / "mod.py"), "rb", 0))
    assert observation.files == {target: _sha(b"x = 1\n")}
    assert observation.listings == {root / "src": _names_digest("mod.py")}


def test_a_root_given_as_an_alias_resolves_and_records_reads_by_either_spelling(root: Path, tmp_path: Path) -> None:
    first = _write(root / "one.txt", b"1")
    second = _write(root / "two.txt", b"2")
    alias = tmp_path / "alias"
    _link(root, alias)
    observation = Observation(alias, started_ns=time.time_ns())
    assert observation.root == root
    observation.audit("open", (str(alias / "one.txt"), "rb", 0))
    observation.audit("open", (str(root / "two.txt"), "rb", 0))
    assert observation.files == {first: _sha(b"1"), second: _sha(b"2")}


def test_a_path_reached_through_a_link_to_a_directory_outside_the_root_is_recorded_with_its_digest(
    root: Path, outside: Path, observation: Observation
) -> None:
    _write(outside / "target" / "file.txt", b"outside")
    alias = outside / "alias-to-target"
    _link(outside / "target", alias)
    observation.audit("open", (str(alias / "file.txt"), "rb", 0))
    assert observation.files == {alias / "file.txt": _sha(b"outside")}
    assert observation.listings == {}
    assert observation.incomplete == []


# Disagreeing journals ------------------------------------------------------------


def _journal(directory: Path, name: str, *lines: str) -> Path:
    return _write(directory / f"{name}.journal", "B\t-\t1\n" + "".join(f"{line}\n" for line in lines))


def test_two_journals_with_different_digests_for_one_file_make_the_observation_incomplete(
    root: Path, tmp_path: Path
) -> None:
    target = root / "shared.txt"
    _journal(tmp_path, "1", f"F\t{'a' * 64}\t{target}")
    _journal(tmp_path, "2", f"F\t{'b' * 64}\t{target}")
    parent = Observation(root, started_ns=0)
    parent.harvest(tmp_path)
    assert parent.files == {target: "a" * 64}, "the first digest is kept"
    assert any(f"{target} changed between the processes" in reason for reason in parent.incomplete), parent.incomplete


def test_two_journals_with_different_listing_digests_make_the_observation_incomplete(
    root: Path, tmp_path: Path
) -> None:
    directory = root / "listed"
    _journal(tmp_path, "1", f"D\t{'a' * 64}\t{directory}")
    _journal(tmp_path, "2", f"D\t{'b' * 64}\t{directory}")
    parent = Observation(root, started_ns=0)
    parent.harvest(tmp_path)
    assert any(f"{directory} changed between the processes" in reason for reason in parent.incomplete)


def test_a_journal_that_disagrees_with_the_parents_own_digest_makes_the_observation_incomplete(
    root: Path, tmp_path: Path
) -> None:
    target = _write(root / "shared.txt", b"parent read this")
    parent = Observation(root, started_ns=0)
    parent.note_file(str(target))
    journal = _journal(tmp_path, "worker", f"F\t{_sha(b'worker read that')}\t{target}")
    parent.merge_journal(journal)
    assert parent.files == {target: _sha(b"parent read this")}
    assert any("changed between the processes" in reason for reason in parent.incomplete), parent.incomplete


def test_journals_that_agree_on_every_digest_leave_the_observation_complete(root: Path, tmp_path: Path) -> None:
    target = _write(root / "shared.txt", b"same bytes")
    line = f"F\t{_sha(b'same bytes')}\t{target}"
    _journal(tmp_path, "1", line)
    _journal(tmp_path, "2", line)
    parent = Observation(root, started_ns=0)
    parent.note_file(str(target))
    parent.harvest(tmp_path)
    assert parent.incomplete == []
    assert parent.files == {target: _sha(b"same bytes")}

"""Reads outside the checkout: recorded by absolute path, allowlisted, or Python source that makes the run incomplete.

The unit cases drive ``Observation`` methods with synthetic audit events. The
allowlist cases name nonexistent absolute paths, because the judgement is
lexical and a path under the temporary directory is itself allowlisted. The
real-observer case runs a child interpreter whose observer lives in a synthetic
checkout and which imports a module from a directory outside that checkout,
placed under the worktree's scratch tree rather than the temporary directory.
Expected digests are computed here with ``hashlib``, independently of the observer.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest

from dev.packaging.command_execution import run_command

from ..dependency_observation import (
    CHILD_SCRIPT_NAME,
    WORKER_SCRIPT_NAME,
    Observation,
    _is_foreign_source,
    _uri_path,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]

_WORKTREE = Path(__file__).resolve().parents[4]
_SEQUENCES = "dev/docs/sequences"
_SCRATCH = _WORKTREE / ".tmp" / "2026-11-19-docsverify" / "tests-scratch"
_FOREIGN = "source read outside the checkout"
#: A drive-rooted directory no real file lives in, outside every allowlisted tree.
_NOWHERE = Path(os.path.abspath(os.sep + "docs-observer-nowhere"))


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _names_digest(*names: str) -> str:
    return _sha("\n".join(sorted(names)).encode("utf-8"))


def _write(path: Path, data: bytes | str = b"") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data.encode() if isinstance(data, str) else data)
    return path


def _opened(observation: Observation, path: Path) -> None:
    observation.audit("open", (str(path), "rb", 0))


@pytest.fixture
def root(tmp_path: Path) -> Path:
    directory = tmp_path / "checkout"
    directory.mkdir()
    return directory.resolve()


@pytest.fixture
def observation(root: Path) -> Observation:
    return Observation(root, started_ns=time.time_ns())


@pytest.fixture
def outside() -> Iterator[Path]:
    """A real directory outside the temporary directory and so off the allowlist."""
    directory = _SCRATCH / f"outside-{uuid.uuid4().hex}"
    directory.mkdir(parents=True)
    try:
        yield directory.resolve()
    finally:
        shutil.rmtree(directory, ignore_errors=True)


# Recording outside data ------------------------------------------------------------


def test_an_outside_data_file_is_recorded_by_absolute_path_with_its_digest(
    outside: Path, observation: Observation
) -> None:
    target = _write(outside / "table.json", b'{"rate": 21}')
    _opened(observation, target)
    assert observation.files == {target: _sha(b'{"rate": 21}')}
    assert observation.listings == {}, "an outside read does not add its parent listing"
    assert observation.incomplete == []


def test_an_outside_probe_is_recorded_as_its_digest_absent_or_directory(
    outside: Path, observation: Observation
) -> None:
    present = _write(outside / "present.txt", b"here")
    (outside / "sub").mkdir()
    observation.probe(present)
    observation.probe(outside / "missing.txt")
    observation.probe(outside / "sub")
    assert observation.files == {
        present: _sha(b"here"),
        outside / "missing.txt": "absent",
        outside / "sub": "directory",
    }
    assert observation.listings == {}
    assert observation.incomplete == []


def test_an_outside_listing_is_recorded_with_its_sorted_names(outside: Path, observation: Observation) -> None:
    _write(outside / "b.txt")
    _write(outside / "a.txt")
    observation.audit("os.listdir", (str(outside),))
    assert observation.listings == {outside: _names_digest("a.txt", "b.txt")}
    assert observation.files == {}


def test_probing_the_checkout_root_records_no_listing_of_its_parent(root: Path, observation: Observation) -> None:
    observation.probe(root)
    assert observation.files == {root: "directory"}
    assert observation.listings == {}


def test_an_outside_python_source_makes_the_observation_incomplete_and_is_not_recorded(
    outside: Path, observation: Observation
) -> None:
    source = _write(outside / "helper.py", b"x = 1\n")
    _opened(observation, source)
    assert observation.files == {}
    assert len(observation.incomplete) == 1
    assert observation.incomplete[0] == f"{_FOREIGN}: {source}"
    _opened(observation, source)
    assert len(observation.incomplete) == 1, "the same source is reported once"


@pytest.mark.parametrize("suffix", [".py", ".pyc", ".pyd", ".pth", ".PY"])
def test_every_python_source_suffix_outside_the_allowlist_is_foreign(observation: Observation, suffix: str) -> None:
    _opened(observation, _NOWHERE / "pkg" / f"mod{suffix}")
    assert [reason.startswith(_FOREIGN) for reason in observation.incomplete] == [True]


def test_a_cadrumo_named_package_outside_the_checkout_is_foreign(observation: Observation) -> None:
    _opened(observation, _NOWHERE / "othercheckout" / "src" / "cadrumo_fake" / "mod.py")
    assert [reason.startswith(_FOREIGN) for reason in observation.incomplete] == [True]


def test_a_non_python_file_in_a_cadrumo_named_directory_is_recorded_not_foreign(
    outside: Path, observation: Observation
) -> None:
    target = _write(outside / "cadrumo_data" / "table.toml", b"a = 1\n")
    _opened(observation, target)
    assert observation.files == {target: _sha(b"a = 1\n")}
    assert observation.incomplete == []


# The allowlist ---------------------------------------------------------------------


@pytest.mark.parametrize("name", ["site-packages", "sys.prefix", "sys.base_prefix", "temporary directory"])
def test_an_allowlisted_python_source_is_skipped(root: Path, monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    interpreter = _NOWHERE / "python"
    for attribute in ("prefix", "base_prefix", "exec_prefix", "base_exec_prefix"):
        monkeypatch.setattr(sys, attribute, str(interpreter / attribute))
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(_NOWHERE / "temp"))
    observation = Observation(root, started_ns=time.time_ns())
    path = {
        "site-packages": _NOWHERE / "venv" / "Lib" / "site-packages" / "pkg" / "mod.py",
        "sys.prefix": interpreter / "prefix" / "Lib" / "library_module.py",
        "sys.base_prefix": interpreter / "base_prefix" / "Lib" / "library_module.py",
        "temporary directory": _NOWHERE / "temp" / "scratch" / "helper.py",
    }[name]
    _opened(observation, path)
    observation.probe(path)
    observation.audit("os.listdir", (str(path.parent),))
    assert observation.files == {}
    assert observation.listings == {}
    assert observation.incomplete == []


def test_a_python_source_beside_but_outside_the_allowlisted_trees_is_foreign(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "prefix", str(_NOWHERE / "python" / "prefix"))
    observation = Observation(root, started_ns=time.time_ns())
    _opened(observation, _NOWHERE / "python" / "prefix-sibling" / "mod.py")
    assert [reason.startswith(_FOREIGN) for reason in observation.incomplete] == [True]


def test_an_allow_outside_directory_is_skipped_and_a_sibling_is_not(observation: Observation) -> None:
    extra = _NOWHERE / "extra"
    observation.allow_outside(extra)
    _opened(observation, extra / "helper.py")
    _opened(observation, extra / "data.json")
    observation.audit("os.listdir", (str(extra / "inner"),))
    assert observation.files == {} and observation.listings == {} and observation.incomplete == []
    _opened(observation, _NOWHERE / "sibling" / "helper.py")
    assert len(observation.incomplete) == 1


def test_the_null_device_is_skipped(observation: Observation) -> None:
    observation.audit("open", (os.devnull, "rb", 0))
    observation.probe(os.devnull)
    assert observation.files == {} and observation.incomplete == []


def test_the_temporary_directory_data_is_skipped(observation: Observation) -> None:
    observation.audit("open", (str(Path(tempfile.gettempdir()) / "docs-observer-scratch" / "data.bin"), "rb", 0))
    assert observation.files == {} and observation.incomplete == []


def test_a_site_packages_data_file_is_skipped(observation: Observation) -> None:
    _opened(observation, _NOWHERE / "env" / "site-packages" / "pkg" / "data.json")
    assert observation.files == {} and observation.incomplete == []


def test_a_cadrumo_named_source_under_site_packages_is_still_foreign(observation: Observation) -> None:
    _opened(observation, _NOWHERE / "env" / "site-packages" / "cadrumo_fake" / "mod.py")
    assert [reason.startswith(_FOREIGN) for reason in observation.incomplete] == [True]


def test_a_cadrumo_named_source_under_an_allow_outside_directory_is_still_foreign(observation: Observation) -> None:
    extra = _NOWHERE / "extra"
    observation.allow_outside(extra)
    _opened(observation, extra / "cadrumo_fake" / "mod.py")
    assert [reason.startswith(_FOREIGN) for reason in observation.incomplete] == [True]


# SQLite file URIs ------------------------------------------------------------------


def test_a_sqlite_uri_names_the_path_it_decodes_to(root: Path, observation: Observation) -> None:
    database = _write(root / "state dir" / "profile.db", b"sqlite bytes")
    uri = "file:" + ("/" if os.name == "nt" else "") + database.as_posix().replace(" ", "%20") + "?mode=ro"
    observation.audit("sqlite3.connect", (uri,))
    assert observation.files == {database: _sha(b"sqlite bytes")}


@pytest.mark.parametrize(
    ("uri", "windows", "posix"),
    [
        ("file:///X:/a/b.db?mode=ro", "X:/a/b.db", "/X:/a/b.db"),
        ("file:///C:/dir%20name/b.db", "C:/dir name/b.db", "/C:/dir name/b.db"),
        ("file:///a/b.db", "/a/b.db", "/a/b.db"),
        ("file:/a/b.db?cache=shared", "/a/b.db", "/a/b.db"),
        ("file:relative.db", "relative.db", "relative.db"),
        ("file::memory:?cache=shared", ":memory:", ":memory:"),
    ],
    ids=["drive-letter", "escaped-space", "rooted", "single-slash", "relative", "memory"],
)
def test_uri_path_decodes_a_file_uri_to_its_filesystem_path(uri: str, windows: str, posix: str) -> None:
    assert _uri_path(uri) == (windows if os.name == "nt" else posix)


def test_a_shared_cache_memory_uri_records_nothing(observation: Observation) -> None:
    observation.audit("sqlite3.connect", ("file::memory:?cache=shared",))
    assert observation.files == {} and observation.incomplete == []


# The real observer -----------------------------------------------------------------

_CHILD = """\
import json
import sys
from pathlib import Path

root, outside = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(root))
from dev.docs.sequences import dependency_observation as observing

observation = observing.observe_process(root)
sys.path.insert(0, str(outside))
observation.note_imported_modules()
before = list(observation.incomplete)
import importlib

importlib.import_module(sys.argv[3])
observation.note_imported_modules()
print(json.dumps({"before": before, "incomplete": observation.incomplete}))
"""


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    """A synthetic checkout holding its own copy of the stdlib-only observer."""
    directory = tmp_path / "real-checkout"
    for package in ("dev", "dev/docs", _SEQUENCES):
        _write(directory / package / "__init__.py")
    for name in ("dependency_observation.py", CHILD_SCRIPT_NAME, WORKER_SCRIPT_NAME):
        shutil.copyfile(_WORKTREE / _SEQUENCES / name, directory / _SEQUENCES / name)
    return directory.resolve()


def _import_outside(checkout: Path, outside: Path, module: str) -> dict[str, list[str]]:
    result = run_command(
        [sys.executable, "-I", "-B", "-c", _CHILD, str(checkout), str(outside), module],
        cwd=checkout,
        environment=None,
    )
    assert result.returncode == 0, result.stderr
    document = json.loads(result.stdout.strip().splitlines()[-1])
    assert isinstance(document, dict)
    return {str(name): [str(item) for item in value] for name, value in document.items()}


def test_the_real_observer_marks_a_cadrumo_named_package_from_another_checkout_incomplete(
    checkout: Path, outside: Path
) -> None:
    module = _write(outside / "othercheckout" / "src" / "cadrumo_fake" / "mod.py", "VALUE = 1\n")
    _write(module.parent / "__init__.py")
    summary = _import_outside(checkout, module.parent.parent, "cadrumo_fake.mod")
    assert not any("cadrumo_fake" in reason for reason in summary["before"])
    assert any(reason.startswith(_FOREIGN) and "cadrumo_fake" in reason for reason in summary["incomplete"]), summary


def test_the_real_observer_marks_a_plain_package_outside_the_allowlist_incomplete(
    checkout: Path, outside: Path
) -> None:
    _write(outside / "plainpkg" / "__init__.py")
    _write(outside / "plainpkg" / "mod.py", "VALUE = 1\n")
    summary = _import_outside(checkout, outside, "plainpkg.mod")
    assert not any("plainpkg" in reason for reason in summary["before"])
    assert any(reason.startswith(_FOREIGN) and "plainpkg" in reason for reason in summary["incomplete"]), summary


@pytest.mark.parametrize(
    ("installed", "foreign"),
    [
        (("pydantic", "main.py"), False),
        (("cadrumo", "cli.py"), True),
        (("cadrumo_runtime", "host", "worker.py"), True),
        (("__editable___cadrumo_0_1_finder.py",), True),
        (("_cadrumo.pth",), True),
    ],
)
def test_only_what_is_installed_in_site_packages_decides_whether_its_source_is_foreign(
    tmp_path: Path, installed: tuple[str, ...], foreign: bool
) -> None:
    """A directory named like the product above an environment is not product code; an installed product is."""
    site_packages = tmp_path / "cadrumo" / ".venv" / "Lib" / "site-packages"

    assert _is_foreign_source(site_packages.joinpath(*installed), ()) is foreign

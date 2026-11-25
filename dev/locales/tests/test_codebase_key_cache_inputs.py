"""The shared codebase-key cache is keyed on every input the scan reads.

The scan reads more than the Python of its roots: key constants, registry and
navigation data, the fstring registry's catalogues and the published authority.
Each is declared with its discovery path, and these tests hold that declaration
to what the scan really reads and to what the cache really does with it.
"""

from __future__ import annotations

import ast
import inspect
import os
import shutil
import sys
import textwrap
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path

import pytest

from dev.paths import REPO_ROOT
from dev.quality import shared_scan

from .. import manager as manager_module
from ..discovery_paths import DISCOVERY_PATHS
from ..manager import LocaleManager, codebase_key_inputs
from ..paths import LOCALE_SOURCE_EXTRA_DIRS, LOCALES_DIR, SRC_DIR

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _reader_name(reader: Callable[[], Iterable[Path]]) -> str:
    return str(getattr(reader, "__name__", "reader"))


_READERS = [(declared.name, _reader_name(reader)) for declared in DISCOVERY_PATHS for reader in declared.inputs]
_LEDGER_KEYS_MODULE = REPO_ROOT / "dev" / "locales" / "desktop_ledger_catalogue_keys.py"


def _reader(path_name: str, reader_name: str) -> Callable[[], Iterable[Path]]:
    declared = next(row for row in DISCOVERY_PATHS if row.name == path_name)
    return next(reader for reader in declared.inputs if _reader_name(reader) == reader_name)


def test_every_declared_discovery_path_names_existing_inputs() -> None:
    for declared in DISCOVERY_PATHS:
        files = declared.files()
        assert files, f"{declared.name} declares no inputs"
        assert all(path.is_file() for path in files), declared.name


def test_the_cache_inputs_include_every_declared_input() -> None:
    declared = {path for row in DISCOVERY_PATHS for path in row.files()}

    assert declared <= set(codebase_key_inputs((SRC_DIR, *LOCALE_SOURCE_EXTRA_DIRS)))
    assert _LEDGER_KEYS_MODULE in declared


def test_the_scan_runs_only_declared_discovery_paths() -> None:
    """A path added to the scan body without a declaration is a path the cache does not follow."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(LocaleManager.scan_codebase_keys)))
    key_updates = [
        ast.unparse(node.args[0])
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "update"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "keys"
    ]

    assert sorted(key_updates) == ["declared.keys()", "scan_source_trees(source_roots)"]


class _Recorder:
    """Records data files opened under the checkout's source trees while armed."""

    def __init__(self) -> None:
        self.armed = False
        self.opened: set[Path] = set()

    def __call__(self, event: str, args: tuple[object, ...]) -> None:
        if not self.armed or event != "open" or not isinstance(args[0], str):
            return
        name = args[0]
        if name.endswith(_CODE_SUFFIXES) or "__pycache__" in name or not os.path.isabs(name):
            return
        path = Path(name)
        if path.is_relative_to(_SOURCE_TREES[0]) or path.is_relative_to(_SOURCE_TREES[1]):
            self.opened.add(path)


_CODE_SUFFIXES = (".py", ".pyc", ".pyd", ".dll")
_SOURCE_TREES = (REPO_ROOT / "src", REPO_ROOT / "dev")
_recorder = _Recorder()
sys.addaudithook(_recorder)


def test_every_data_file_the_real_scan_opens_is_a_declared_input() -> None:
    """Run the real scan and compare what it opened with what the cache is keyed on."""
    manager = LocaleManager(SRC_DIR, LOCALES_DIR, LOCALE_SOURCE_EXTRA_DIRS)
    _recorder.opened.clear()
    _recorder.armed = True
    try:
        manager.scan_codebase_keys()
    finally:
        _recorder.armed = False
    declared = set(codebase_key_inputs((SRC_DIR, *LOCALE_SOURCE_EXTRA_DIRS)))

    undeclared = sorted(
        path.relative_to(REPO_ROOT).as_posix()
        for path in _recorder.opened
        if path not in declared and not _is_catalogue_value_read(path)
    )

    assert not undeclared, f"the scan reads files the cache key does not cover: {undeclared[:20]}"


def _is_catalogue_value_read(path: Path) -> bool:
    """A locale catalogue read renders words; no discovery path takes a key from its text."""
    return path.suffix == ".yml" and path.is_relative_to(SRC_DIR / "locales")


@pytest.fixture
def mirror(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[[Path], Path]]:
    """Cache over a copy: the manager sees a repository under ``tmp_path`` and an isolated artifact root."""
    repository = tmp_path.resolve()
    monkeypatch.setattr(manager_module, "REPO_ROOT", repository)
    monkeypatch.setattr(shared_scan, "memo", {})
    monkeypatch.setenv("CADRUMO_RUN_ARTIFACT_ROOT", str(repository / "run-cache"))
    (repository / "src" / "planted").mkdir(parents=True)

    def copy(real: Path) -> Path:
        target = repository / real.relative_to(REPO_ROOT)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(real, target)
        return target

    yield copy


def _manager(repository: Path) -> LocaleManager:
    return LocaleManager(repository / "src" / "planted", repository / "locales")


def _counting_scan(
    monkeypatch: pytest.MonkeyPatch,
    inputs: Callable[[], list[Path]],
    result: Callable[[], frozenset[str]],
) -> list[None]:
    calls: list[None] = []

    def scan(self: LocaleManager) -> tuple[frozenset[str], tuple[str, ...]]:
        calls.append(None)
        return result(), ()

    monkeypatch.setattr(LocaleManager, "scan_codebase_keys", scan)
    monkeypatch.setattr(manager_module, "codebase_key_inputs", lambda roots: tuple(inputs()))
    return calls


def _string_constants(path: Path) -> frozenset[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return frozenset(
        node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)
    )


def test_removing_a_desktop_ledger_catalogue_key_changes_the_cached_scan(
    mirror: Callable[[Path], Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A key deleted from the desktop ledger key module is no longer required once the cache is consulted."""
    declared = {path for row in DISCOVERY_PATHS for path in row.files()}
    assert _LEDGER_KEYS_MODULE in declared
    copy = mirror(_LEDGER_KEYS_MODULE)
    repository = manager_module.REPO_ROOT
    calls = _counting_scan(monkeypatch, lambda: [copy], lambda: _string_constants(copy))
    removed = "desktop.ledger.action.go_to_period"

    first = _manager(repository).get_codebase_keys()
    again = _manager(repository).get_codebase_keys()
    copy.write_text(copy.read_text(encoding="utf-8").replace(f'        "{removed}",\n', ""), encoding="utf-8")
    edited = _manager(repository).get_codebase_keys()

    assert removed in first and first == again
    assert removed not in edited
    assert len(calls) == 2


@pytest.mark.parametrize(("path_name", "reader_name"), _READERS)
def test_an_edit_to_each_declared_input_invalidates_the_cached_scan(
    mirror: Callable[[Path], Path], monkeypatch: pytest.MonkeyPatch, path_name: str, reader_name: str
) -> None:
    files = sorted(_reader(path_name, reader_name)())
    assert files
    copies = [mirror(files[0]), mirror(files[-1])]
    generation = iter(range(100))
    calls = _counting_scan(monkeypatch, lambda: copies, lambda: frozenset({f"scan.run{next(generation)}"}))
    repository = manager_module.REPO_ROOT

    first = _manager(repository).get_codebase_keys()
    assert _manager(repository).get_codebase_keys() == first
    assert len(calls) == 1
    for index, copy in enumerate(dict.fromkeys(copies), start=2):
        with copy.open("ab") as handle:
            handle.write(b"\n")
        _manager(repository).get_codebase_keys()
        assert len(calls) == index, f"an edit to {copy.name} did not invalidate the cached scan"


def test_a_change_of_published_authority_generation_invalidates_the_cached_scan(
    mirror: Callable[[Path], Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The wizard descriptors are built against the published authority, which is no file of the scan."""
    from cadrumo.domain.calculations.registry import authority_location

    generation = ["generation-one"]
    monkeypatch.setattr(authority_location, "published_authority_generation", lambda: generation[0])
    calls = _counting_scan(monkeypatch, lambda: [mirror(_LEDGER_KEYS_MODULE)], lambda: frozenset({"scan.keys"}))
    repository = manager_module.REPO_ROOT

    _manager(repository).get_codebase_keys()
    _manager(repository).get_codebase_keys()
    generation[0] = "generation-two"
    _manager(repository).get_codebase_keys()

    assert len(calls) == 2

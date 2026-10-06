"""Interpreter startup confirms every package file without resolving each path or following a link."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import types
from collections import Counter
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import Any

import pytest

from dev._paths import REPO_ROOT
from dev.packaging.native.hashing import digest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

MANIFEST = "data/package-manifest.json"
NATIVE_MANIFEST = "data/native-modules.json"
PATH_FILE = "cadrumo/python.pth"
NAMES = ("python.exe", "lib/a.py", "lib/deep/b.py", "bin/native.dll")
INVALID = "Invalid package-relative path: {}"
MISSING = "Missing bundled file: {}"


@pytest.fixture
def prepared() -> list[Path]:
    """Package roots the stand-in native module was asked to prepare."""
    return []


@pytest.fixture
def bootstrap(prepared: list[Path]) -> Iterator[types.ModuleType]:
    """Load the shipped bootstrap source; only its native import-time module is absent here."""
    native = types.ModuleType("_cadrumo_native")
    vars(native)["prepare"] = lambda root, _manifest: prepared.append(root)
    sys.modules["_cadrumo_native"] = native
    spec = importlib.util.spec_from_file_location(
        "_cadrumo_bootstrap_under_test", REPO_ROOT / "native/interpreter/bootstrap.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        yield module
    finally:
        del sys.modules["_cadrumo_native"]


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return (tmp_path / "package").resolve()


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> Counter[str]:
    """Count the filesystem queries a start can make, each still answered by the real call."""
    counted: Counter[str] = Counter()

    def count(owner: Any, name: str) -> None:
        real = getattr(owner, name)

        def counting(*args: Any, **kwargs: Any) -> Any:
            counted[name] += 1
            return real(*args, **kwargs)

        monkeypatch.setattr(owner, name, counting)

    for name in ("scandir", "stat", "lstat"):
        count(os, name)
    count(os.path, "realpath")
    return counted


@pytest.fixture
def symlink(tmp_path: Path) -> Callable[[Path, Path], None]:
    """Create symbolic links, skipping only where this account is refused one."""
    probe = tmp_path / "symlink-probe"
    try:
        probe.symlink_to(tmp_path, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"symbolic links cannot be created here: {error}")
    probe.unlink()
    return lambda link, target: link.symlink_to(target, target_is_directory=target.is_dir())


@pytest.fixture(params=["symlink", "junction"])
def link_directory(request: pytest.FixtureRequest) -> Callable[[Path, Path], None]:
    """Create each kind of directory link the platform has."""
    if request.param == "symlink":
        return request.getfixturevalue("symlink")
    winapi = pytest.importorskip("_winapi", reason="junctions exist only on Windows")
    return lambda link, target: winapi.CreateJunction(str(target), str(link))


def _write(root: Path, names: Iterable[str]) -> dict[str, str]:
    for name in names:
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(f"content of {name}", encoding="utf-8")
    return {name: digest(root / name) for name in names}


def _stage(
    bootstrap: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    root: Path,
    files: dict[str, str],
    startup: Iterable[str] = ("python.exe",),
) -> None:
    """Point the shipped bootstrap at a synthetic package root built for this interpreter."""
    build = {"version": "1", "build_number": 1, "build_date": "d", "python": ".".join(map(str, sys.version_info[:3]))}
    manifest = {
        "build": build,
        "files": files,
        "startup_files": list(startup),
        "delegated_inventories": {},
        "user_docs": {"directory": "docs/user", "bundled": False},
    }
    (root / MANIFEST).parent.mkdir(parents=True, exist_ok=True)
    (root / MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(sys, "cadrumo_build", build, raising=False)
    # An absolute package root replaces the executable-relative anchor when joined.
    layout = {
        "package_root_from_executable": str(root),
        "files": {"package_manifest": MANIFEST, "native_manifest": NATIVE_MANIFEST, "path_file": PATH_FILE},
    }
    monkeypatch.setattr(bootstrap, "LAYOUT", layout)


def _refusal(bootstrap: types.ModuleType, *, full: bool = False) -> str:
    with pytest.raises(ImportError) as refused:
        bootstrap.verify(full=full)
    return str(refused.value)


def test_a_complete_package_starts_and_unlisted_files_stay_a_full_check_matter(
    root: Path, bootstrap: types.ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stage(bootstrap, monkeypatch, root, _write(root, NAMES))
    bootstrap.verify()
    bootstrap.verify(full=True)
    _write(root, ["lib/stray.py", "unlisted/stray.py"])
    bootstrap.verify()
    assert _refusal(bootstrap, full=True).startswith("Unexpected package files")


def test_the_host_entry_refuses_a_missing_file_before_preparing_native_code(
    root: Path, bootstrap: types.ModuleType, prepared: list[Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    (root / "cadrumo/site-packages").mkdir(parents=True)
    (root / PATH_FILE).write_text("site-packages\n", encoding="utf-8")
    (root / NATIVE_MANIFEST).parent.mkdir(parents=True)
    (root / NATIVE_MANIFEST).write_text(
        json.dumps({"python_paths": ["cadrumo/site-packages"], "modules": {}}), encoding="utf-8"
    )
    files = {**_write(root, NAMES), **{name: digest(root / name) for name in (PATH_FILE, NATIVE_MANIFEST)}}
    _stage(bootstrap, monkeypatch, root, files)
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setattr(sys, "meta_path", list(sys.meta_path))
    bootstrap.install()
    assert prepared == [root]
    assert isinstance(sys.meta_path[0], bootstrap.NativeModules)
    (root / "lib/deep/b.py").unlink()
    with pytest.raises(ImportError) as refused:
        bootstrap.install()
    assert str(refused.value) == MISSING.format("lib/deep/b.py")
    assert prepared == [root]


@pytest.mark.parametrize(("removed", "reported"), [("lib/deep/b.py", "lib/deep/b.py"), ("lib", "lib/a.py")])
def test_a_missing_file_or_directory_is_refused(
    root: Path, bootstrap: types.ModuleType, monkeypatch: pytest.MonkeyPatch, removed: str, reported: str
) -> None:
    _stage(bootstrap, monkeypatch, root, _write(root, NAMES))
    if (root / removed).is_dir():
        shutil.rmtree(root / removed)
    else:
        (root / removed).unlink()
    assert _refusal(bootstrap) == MISSING.format(reported)
    assert _refusal(bootstrap, full=True) == MISSING.format(reported)


def test_a_directory_where_a_file_belongs_is_refused(
    root: Path, bootstrap: types.ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stage(bootstrap, monkeypatch, root, _write(root, NAMES))
    (root / "lib/a.py").unlink()
    (root / "lib/a.py").mkdir()
    assert _refusal(bootstrap) == MISSING.format("lib/a.py")


def test_a_file_where_a_directory_belongs_is_refused(
    root: Path, bootstrap: types.ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stage(bootstrap, monkeypatch, root, _write(root, NAMES))
    shutil.rmtree(root / "lib/deep")
    (root / "lib/deep").write_text("not a directory", encoding="utf-8")
    assert _refusal(bootstrap) == MISSING.format("lib/deep/b.py")


@pytest.mark.parametrize("target", ["outside", "inside"])
def test_a_file_replaced_by_a_symbolic_link_is_refused(
    tmp_path: Path,
    root: Path,
    bootstrap: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    symlink: Callable[[Path, Path], None],
    target: str,
) -> None:
    _stage(bootstrap, monkeypatch, root, _write(root, NAMES))
    original = (tmp_path / "a.py") if target == "outside" else (root / "lib/original.py")
    (root / "lib/a.py").replace(original)
    symlink(root / "lib/a.py", original)
    assert digest(root / "lib/a.py") == digest(original)
    assert _refusal(bootstrap) == INVALID.format("lib/a.py")
    assert _refusal(bootstrap, full=True) == INVALID.format("lib/a.py")


@pytest.mark.parametrize(("linked", "reported"), [("lib", "lib/a.py"), ("lib/deep", "lib/deep/b.py")])
def test_a_directory_replaced_by_a_link_to_an_identical_tree_is_refused(
    tmp_path: Path,
    root: Path,
    bootstrap: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    link_directory: Callable[[Path, Path], None],
    linked: str,
    reported: str,
) -> None:
    _stage(bootstrap, monkeypatch, root, _write(root, NAMES))
    identical = tmp_path / "identical"
    shutil.move(root / linked, identical)
    link_directory(root / linked, identical)
    assert all((root / name).is_file() for name in NAMES)
    assert _refusal(bootstrap) == INVALID.format(reported)
    assert _refusal(bootstrap, full=True) == INVALID.format(reported)


@pytest.mark.parametrize(
    "entry",
    [
        "../outside.py",
        "lib/../../outside.py",
        "lib/../python.exe",
        "/python.exe",
        "{root}/python.exe",
        "C:/python.exe",
        "lib\\a.py",
        "lib//a.py",
        "./python.exe",
        "lib/",
        "",
    ],
    ids=[
        "dot-dot",
        "nested-dot-dot",
        "dot-dot-inside",
        "absolute",
        "absolute-inside",
        "drive",
        "backslash",
        "empty-segment",
        "dot",
        "trailing-slash",
        "empty",
    ],
)
def test_an_entry_that_is_not_a_plain_relative_path_is_refused_before_the_package_is_read(
    tmp_path: Path,
    root: Path,
    bootstrap: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    calls: Counter[str],
    entry: str,
) -> None:
    (tmp_path / "outside.py").write_text("outside the package", encoding="utf-8")
    entry = entry.format(root=root.as_posix())
    # Listed last, so a check made entry by entry would already have walked the valid ones.
    _stage(bootstrap, monkeypatch, root, {**_write(root, NAMES), entry: "0" * 64})
    calls.clear()
    assert _refusal(bootstrap) == INVALID.format(entry)
    assert calls["scandir"] == 0


@pytest.mark.parametrize("spelled", ["LIB/a.py", "lib/A.PY", "LIB/DEEP/B.PY"])
def test_a_differently_cased_name_is_present_exactly_where_the_filesystem_says_so(
    root: Path, bootstrap: types.ModuleType, monkeypatch: pytest.MonkeyPatch, spelled: str
) -> None:
    files = _write(root, NAMES)
    files[spelled] = files.pop(spelled.lower())
    _stage(bootstrap, monkeypatch, root, files)
    if (root / spelled).is_file():
        bootstrap.verify()
    else:
        assert _refusal(bootstrap) == MISSING.format(spelled)


def test_a_differently_cased_name_does_not_let_a_linked_directory_through(
    tmp_path: Path,
    root: Path,
    bootstrap: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    link_directory: Callable[[Path, Path], None],
) -> None:
    files = {name.replace("lib/a.py", "LIB/a.py"): value for name, value in _write(root, NAMES).items()}
    _stage(bootstrap, monkeypatch, root, files)
    identical = tmp_path / "identical"
    shutil.move(root / "lib", identical)
    link_directory(root / "lib", identical)
    folded = (root / "LIB/a.py").is_file()
    assert _refusal(bootstrap) == (INVALID if folded else MISSING).format("LIB/a.py")


def test_a_start_queries_the_filesystem_per_directory_not_per_file(
    tmp_path: Path, bootstrap: types.ModuleType, monkeypatch: pytest.MonkeyPatch, calls: Counter[str]
) -> None:
    directories = ("lib", "lib/deep", "lib/deep/er", "bin")

    def start(files_per_directory: int) -> tuple[Counter[str], list[Path]]:
        root = (tmp_path / f"package-{files_per_directory}").resolve()
        names = [f"{directory}/m{index}.py" for directory in directories for index in range(files_per_directory)]
        _stage(bootstrap, monkeypatch, root, _write(root, ["python.exe", *names]))
        calls.clear()
        bootstrap.verify()
        return Counter(calls), [root / name for name in names]

    few, _ = start(2)
    many, files = start(60)
    # The root and each directory are listed once however many files they hold.
    assert few["scandir"] == many["scandir"] == len(directories) + 1
    assert few == many
    # The counters do see a probe made file by file, so the equality above is not blind to one.
    calls.clear()
    assert all(file.resolve().is_file() for file in files)
    assert sum(calls.values()) >= len(files)

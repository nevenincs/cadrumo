"""Conformance vectors and installed-layout resolution of the storage root declaration."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

from cadrumo.core.errors.hierarchy import CoreValidationError
from cadrumo.core.storage_environment import (
    STORAGE_ROOT,
    ChildEnvironmentProfile,
    StorageMode,
    StorageModeEvidence,
    StoragePlatform,
    StorageRootRefusal,
    child_environment,
    ensure_storage_root,
    resolve_storage_root,
    storage_root_for,
)
from cadrumo.core.tests.checkout import project_root
from cadrumo.core.type_guards import is_str_keyed_dict
from cadrumo.tests.audited_process import ensure_text_completed_process, run_audited_process

from ..storage_vectors import StorageRootVector, storage_root_vectors

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _replay(vector: StorageRootVector) -> tuple[str | None, StorageRootRefusal | None]:
    try:
        root = resolve_storage_root(
            platform=vector.platform,
            mode=vector.mode,
            environ=dict(vector.environment),
            checkout=vector.checkout,
            channel=vector.channel,
        )
    except CoreValidationError as error:
        return None, StorageRootRefusal(str((error.context or {})["storage_root_refusal"]))
    return str(root), None


@pytest.mark.parametrize("vector", storage_root_vectors(), ids=lambda vector: vector.name)
def test_python_resolver_reproduces_every_vector(vector: StorageRootVector) -> None:
    assert _replay(vector) == (vector.expected_root, vector.refusal)


def test_vectors_are_well_formed_and_cover_every_platform_and_mode() -> None:
    vectors = storage_root_vectors()
    assert len({vector.name for vector in vectors}) == len(vectors)
    assert all((vector.expected_root is None) != (vector.refusal is None) for vector in vectors)
    assert {(vector.platform, vector.mode) for vector in vectors} == {
        (platform, mode) for platform in StoragePlatform for mode in StorageMode
    }
    assert {vector.refusal for vector in vectors} >= {
        StorageRootRefusal.INSTALLED_BASE_UNAVAILABLE,
        StorageRootRefusal.RELATIVE_OVERRIDE_INSTALLED,
    }
    for vector in vectors:
        environment = dict(vector.environment)
        if vector.platform is StoragePlatform.WINDOWS and vector.known_folder is not None:
            assert environment["LOCALAPPDATA"] == vector.known_folder
        if vector.platform is not StoragePlatform.WINDOWS:
            assert vector.known_folder is None
        if vector.mode is StorageMode.DEVELOPMENT:
            assert vector.checkout is not None


def test_vectors_project_onto_json() -> None:
    projected = [vector.as_contract() for vector in storage_root_vectors()]
    assert json.loads(json.dumps(projected)) == projected
    assert projected[0] == {
        "name": "windows-installed-default",
        "platform": "windows",
        "mode": "installed",
        "environment": {"LOCALAPPDATA": r"C:\Users\ada\AppData\Local"},
        "checkout": None,
        "known_folder": r"C:\Users\ada\AppData\Local",
        "channel": "stable",
        "expected_root": r"C:\Users\ada\AppData\Local\cadrumo",
        "refusal": None,
    }


def test_home_override_without_home_is_refused() -> None:
    with pytest.raises(CoreValidationError) as raised:
        resolve_storage_root(
            platform=StoragePlatform.LINUX,
            mode=StorageMode.INSTALLED,
            environ={STORAGE_ROOT.variable: "~/data"},
        )
    assert (raised.value.context or {})["storage_root_refusal"] == StorageRootRefusal.HOME_UNAVAILABLE.value


def test_development_without_checkout_is_refused() -> None:
    with pytest.raises(CoreValidationError) as raised:
        resolve_storage_root(platform=StoragePlatform.LINUX, mode=StorageMode.DEVELOPMENT, environ={})
    assert (raised.value.context or {})["storage_root_refusal"] == StorageRootRefusal.CHECKOUT_UNAVAILABLE.value


_PROBE = """
import json, sys
sys.path.insert(0, sys.argv[1])
from cadrumo.core import storage_environment as declaration
from cadrumo.core.errors.hierarchy import CoreValidationError
result = {"module": declaration.__file__, "mode": declaration.storage_mode().mode.value}
try:
    result["root"] = str(declaration.configured_storage_root())
except CoreValidationError as error:
    result["refusal"] = error.context["storage_root_refusal"]
result["checkout"] = "absent" if declaration.storage_mode().checkout is None else "present"
print(json.dumps(result))
"""


@pytest.fixture(scope="module")
def installed_site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Copy the importable core package into a site directory outside any checkout."""
    site = tmp_path_factory.mktemp("installed") / "Lib" / "site-packages"
    source = project_root() / "src" / "cadrumo"
    package = site / "cadrumo"
    package.mkdir(parents=True)
    shutil.copy2(source / "__init__.py", package / "__init__.py")
    shutil.copytree(source / "core", package / "core", ignore=shutil.ignore_patterns("tests", "__pycache__"))
    return site


def _installed_probe(site: Path, cwd: Path, environment: dict[str, str]) -> dict[str, str]:
    inherited = {
        name: value
        for name, value in os.environ.items()
        if name.upper() not in {*STORAGE_ROOT.precedence, "LOCALAPPDATA", "XDG_DATA_HOME", "HOME"}
    }
    completed = ensure_text_completed_process(
        run_audited_process(
            [sys.executable, "-c", _PROBE, str(site)],
            cwd=cwd,
            env={**inherited, **environment},
            capture_output=True,
            text=True,
            timeout=120,
        )
    )
    assert completed.returncode == 0, completed.stderr
    loaded: object = json.loads(completed.stdout)
    assert is_str_keyed_dict(loaded)
    result: dict[str, str] = {}
    for key, value in loaded.items():
        assert isinstance(value, str), (key, value)
        result[key] = value
    assert Path(result.pop("module")).is_relative_to(site)
    assert result.pop("mode") == StorageMode.INSTALLED.value
    assert result.pop("checkout") == "absent"
    return result


def _host_base() -> tuple[str, str]:
    if sys.platform == "win32":
        return "LOCALAPPDATA", "LOCALAPPDATA"
    if sys.platform == "darwin":
        return "HOME", "HOME"
    return "XDG_DATA_HOME", "HOME"


def _expected_installed_root(base: Path) -> Path:
    if sys.platform == "darwin":
        return base / "Library" / "Application Support" / STORAGE_ROOT.product_directory
    return base / STORAGE_ROOT.product_directory


def test_installed_root_is_the_same_from_any_directory(installed_site: Path, tmp_path: Path) -> None:
    variable, _missing = _host_base()
    base = tmp_path / "user-data"
    first, second = tmp_path / "launch-one", tmp_path / "launch-two"
    first.mkdir()
    second.mkdir()
    one = _installed_probe(installed_site, first, {variable: str(base)})
    two = _installed_probe(installed_site, second, {variable: str(base)})
    assert one == two == {"root": str(_expected_installed_root(base).resolve())}
    assert not (first / "var").exists() and not (second / "var").exists()


def test_installed_relative_override_is_refused(installed_site: Path, tmp_path: Path) -> None:
    variable, _missing = _host_base()
    result = _installed_probe(
        installed_site, tmp_path, {variable: str(tmp_path / "user-data"), STORAGE_ROOT.variable: "var/storage"}
    )
    assert result == {"refusal": StorageRootRefusal.RELATIVE_OVERRIDE_INSTALLED.value}


def test_installed_missing_base_is_refused(installed_site: Path, tmp_path: Path) -> None:
    assert _installed_probe(installed_site, tmp_path, {}) == {
        "refusal": StorageRootRefusal.INSTALLED_BASE_UNAVAILABLE.value
    }


def test_installed_absolute_override_wins_without_a_base(installed_site: Path, tmp_path: Path) -> None:
    explicit = tmp_path / "operator-root"
    result = _installed_probe(
        installed_site,
        tmp_path,
        {STORAGE_ROOT.variable: str(explicit), STORAGE_ROOT.development_variable: str(tmp_path / "ignored")},
    )
    assert result == {"root": str(explicit.resolve())}


def test_installed_ignores_the_development_variable(installed_site: Path, tmp_path: Path) -> None:
    variable, _missing = _host_base()
    base = tmp_path / "user-data"
    result = _installed_probe(
        installed_site,
        tmp_path,
        {variable: str(base), STORAGE_ROOT.development_variable: str(tmp_path / "shared")},
    )
    assert result == {"root": str(_expected_installed_root(base).resolve())}


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Known Folder contract")
def test_installed_default_matches_the_local_appdata_known_folder(installed_site: Path, tmp_path: Path) -> None:
    assert sys.platform == "win32"
    import ctypes
    import uuid
    from ctypes import wintypes

    class _Guid(ctypes.Structure):
        _fields_ = (("data", ctypes.c_byte * 16),)

    folder = _Guid()
    ctypes.memmove(folder.data, uuid.UUID("F1B32785-6FBA-4FCF-9D55-7B8E7F157091").bytes_le, 16)
    pointer = ctypes.c_wchar_p()
    shell32 = ctypes.WinDLL("shell32")
    shell32.SHGetKnownFolderPath.argtypes = (
        ctypes.POINTER(_Guid),
        wintypes.DWORD,
        wintypes.HANDLE,
        ctypes.POINTER(ctypes.c_wchar_p),
    )
    assert shell32.SHGetKnownFolderPath(ctypes.byref(folder), 0, None, ctypes.byref(pointer)) == 0
    known_folder = pointer.value
    ctypes.WinDLL("ole32").CoTaskMemFree(pointer)
    assert known_folder is not None
    local_appdata = os.environ["LOCALAPPDATA"]
    result = _installed_probe(installed_site, tmp_path, {"LOCALAPPDATA": local_appdata})
    assert result == {"root": str((Path(known_folder) / STORAGE_ROOT.product_directory).resolve())}


@pytest.mark.skipif(os.name == "nt", reason="POSIX directory permission contract")
def test_storage_root_is_created_owner_only(tmp_path: Path) -> None:
    root = ensure_storage_root(tmp_path / "fresh" / "root")
    assert root.stat().st_mode & 0o777 == STORAGE_ROOT.posix_directory_mode
    assert ensure_storage_root(root) == root


def test_a_checkout_resolves_on_an_undeclared_platform(tmp_path: Path) -> None:
    checkout = StorageModeEvidence(StorageMode.DEVELOPMENT, tmp_path)
    assert storage_root_for({}, checkout, sys_platform="plan9") == (tmp_path / "var" / "storage").resolve()
    relative = {STORAGE_ROOT.variable: "var/alternate"}
    assert storage_root_for(relative, checkout, sys_platform="plan9") == (tmp_path / "var" / "alternate").resolve()
    assert resolve_storage_root(platform=None, mode=StorageMode.DEVELOPMENT, environ={}, checkout="/src/checkout")
    environment = child_environment(
        ChildEnvironmentProfile.STRICT, tmp_path / "root", received={}, base={}, sys_platform="plan9"
    )
    assert environment[STORAGE_ROOT.variable] == str((tmp_path / "root").resolve())


def test_an_installed_package_on_an_undeclared_platform_is_refused(tmp_path: Path) -> None:
    installed = StorageModeEvidence(StorageMode.INSTALLED, None)
    with pytest.raises(CoreValidationError) as raised:
        storage_root_for({"HOME": str(tmp_path)}, installed, sys_platform="plan9")
    assert (raised.value.context or {})["storage_root_refusal"] == StorageRootRefusal.UNSUPPORTED_PLATFORM.value
    explicit = tmp_path / "operator-root"
    assert (
        storage_root_for({STORAGE_ROOT.variable: str(explicit)}, installed, sys_platform="plan9") == explicit.resolve()
    )

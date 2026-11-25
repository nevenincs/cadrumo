"""Build-scoped storage binding for Python build and release commands."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

from dev.cache_root import dev_cache_root
from dev.packaging.build_scratch_reclaim import require_build_path
from dev.packaging.build_storage import (
    WheelCacheLocationError,
    admitted_wheel_cache,
    build_environment,
    build_storage,
)
from dev.packaging.command_execution import run_command
from dev.packaging.runtime_wheel_acquisition import wheel_cache_dir
from dev.paths import REPO_ROOT, TEMP_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DERIVED_CACHE_VARIABLES = (
    "CADRUMO_REGISTRY_DISK_CACHE_DIR",
    "CADRUMO_RECORD_DESIGN_CACHE_DIR",
    "CADRUMO_CORPUS_TEXT_CACHE_DIR",
    "CADRUMO_REGISTRY_VERDICT_CACHE_DIR",
)
_WHEEL_CACHE_VARIABLE = "CADRUMO_RUNTIME_WHEEL_CACHE_DIR"
_ADMITTED_ROOT_VARIABLE = "CADRUMO_RUNTIME_WHEEL_CACHE_ADMITTED_ROOT"
_PRESERVED_TOOL_VARIABLES = (
    "UV_CACHE_DIR",
    "UV_TOOL_DIR",
    "XDG_CACHE_HOME",
    "HOME",
    "USERPROFILE",
    "CARGO_HOME",
    "RUSTUP_HOME",
    "NPM_CONFIG_CACHE",
    "CADRUMO_TOOL_CACHE_DIR",
)


def _expected_paths(work: Path, wheel_cache: Path) -> dict[str, str]:
    storage = work / "storage"
    cache = work / "cache"
    scratch = work / "scratch"
    temporary = work / "temporary"
    return {
        "CADRUMO_STORAGE_ROOT": str(storage),
        "CADRUMO_DEV_CACHE_ROOT": str(cache),
        "CADRUMO_DEV_CACHE_DIR": str(cache),
        "CADRUMO_PYTHON_CACHE_DIR": str(work / "python-cache"),
        "CADRUMO_TEST_LOG_ROOT": str(work / "test-logs"),
        "CADRUMO_SCRATCH_BASE": str(scratch),
        "CADRUMO_DEV_SCRATCH_DIR": str(scratch),
        "CADRUMO_DOCS_BUILD_ROOT": str(work / "docs"),
        "CADRUMO_DEV_ARTIFACTS_DIR": str(work / "artifacts"),
        **{name: str(cache / name.lower()) for name in _DERIVED_CACHE_VARIABLES},
        _WHEEL_CACHE_VARIABLE: str(wheel_cache),
        "TEMP": str(temporary),
        "TMP": str(temporary),
        "TMPDIR": str(temporary),
    }


@pytest.fixture
def build_owned_work_root() -> Iterator[Path]:
    parent = require_build_path(REPO_ROOT / "build" / "testing" / "build-storage-tests", repo_root=REPO_ROOT)
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="case-", dir=parent) as temporary:
        yield Path(temporary)


def test_build_storage_pins_application_paths_and_restores_process_state(
    build_owned_work_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    work = build_owned_work_root / "context-work"
    operator_cache_root = build_owned_work_root / "operator-dev-cache"
    wheel_cache = (REPO_ROOT / ".cache" / "build-storage-test-wheels").resolve()
    ambient = {name: f"ambient:{name}" for name in _expected_paths(work, wheel_cache) if name != _WHEEL_CACHE_VARIABLE}
    # The caller's cache resolves before isolation, so these two must be real locations.
    ambient["CADRUMO_STORAGE_ROOT"] = str(build_owned_work_root / "operator-storage")
    ambient["CADRUMO_DEV_CACHE_ROOT"] = str(operator_cache_root)
    for name, value in ambient.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv(_WHEEL_CACHE_VARIABLE, str(wheel_cache))
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "0")
    preserved = {name: f"operator:{name}" for name in _PRESERVED_TOOL_VARIABLES}
    for name, value in preserved.items():
        monkeypatch.setenv(name, value)
    previous_tempdir = tempfile.tempdir
    previous_no_bytecode = sys.dont_write_bytecode

    with build_storage(work) as selected:
        isolated = Path(os.environ["TEMP"]).parent
        expected = _expected_paths(isolated, wheel_cache)
        assert selected == work
        assert {name: os.environ[name] for name in expected} == expected
        assert isolated.is_relative_to(TEMP_ROOT)
        assert not isolated.is_relative_to(REPO_ROOT / "build")
        isolated_values = {name: value for name, value in expected.items() if name != _WHEEL_CACHE_VARIABLE}
        assert all(Path(value).is_relative_to(isolated) for value in isolated_values.values())
        assert all(Path(value).is_dir() for value in set(isolated_values.values()))
        assert os.environ["PYTHONDONTWRITEBYTECODE"] == "1"
        assert tempfile.gettempdir() == str(isolated / "temporary")
        assert sys.dont_write_bytecode is True
        assert {name: os.environ[name] for name in preserved} == preserved

    assert {name: os.environ[name] for name in ambient} == ambient
    assert os.environ[_WHEEL_CACHE_VARIABLE] == str(wheel_cache)
    assert os.environ["PYTHONDONTWRITEBYTECODE"] == "0"
    assert tempfile.tempdir == previous_tempdir
    assert sys.dont_write_bytecode is previous_no_bytecode
    assert {name: os.environ[name] for name in preserved} == preserved
    assert not isolated.exists()


def test_build_storage_restores_state_after_failure_and_refuses_unowned_paths(
    build_owned_work_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    work = build_owned_work_root / "failure-work"
    monkeypatch.delenv("CADRUMO_STORAGE_ROOT", raising=False)
    previous_tempdir = tempfile.tempdir
    previous_no_bytecode = sys.dont_write_bytecode
    isolated: Path | None = None

    with pytest.raises(RuntimeError, match="build failed"), build_storage(work):
        isolated = Path(os.environ["TEMP"]).parent
        assert os.environ["CADRUMO_STORAGE_ROOT"] == str(isolated / "storage")
        raise RuntimeError("build failed")

    assert "CADRUMO_STORAGE_ROOT" not in os.environ
    assert tempfile.tempdir == previous_tempdir
    assert sys.dont_write_bytecode is previous_no_bytecode
    assert isolated is not None
    assert not isolated.exists()

    with pytest.raises(ValueError, match="beneath"), build_storage(REPO_ROOT / "var" / "unowned-build-work"):
        pytest.fail("an unowned build directory was admitted")
    with pytest.raises(ValueError, match="below the repository build directory"), build_storage(REPO_ROOT / "build"):
        pytest.fail("the build root itself was admitted as work")


def test_the_shared_wheel_cache_is_admitted_only_below_a_machine_managed_cache_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A build shares the caller's wheel cache, never one in a source tree or an arbitrary location."""
    monkeypatch.delenv(_WHEEL_CACHE_VARIABLE, raising=False)
    assert admitted_wheel_cache(REPO_ROOT) == (dev_cache_root() / "runtime-wheel-cache").resolve()

    checkout_cache = REPO_ROOT / ".cache" / "runtime-wheel-cache"
    monkeypatch.setenv(_WHEEL_CACHE_VARIABLE, str(checkout_cache))
    assert admitted_wheel_cache(REPO_ROOT) == checkout_cache.resolve()

    monkeypatch.setenv(_WHEEL_CACHE_VARIABLE, str(REPO_ROOT / "dev" / "packaging" / "wheels"))
    with pytest.raises(WheelCacheLocationError, match="inside a source tree"):
        admitted_wheel_cache(REPO_ROOT)
    refused_work = REPO_ROOT / "build" / "testing" / "build-storage-tests" / "refused-cache"
    with pytest.raises(WheelCacheLocationError, match="inside a source tree"), build_environment(refused_work):
        pytest.fail("a source-tree wheel cache was passed through")

    outside = Path(REPO_ROOT.resolve().anchor) / "cadrumo-unmanaged-wheel-cache"
    monkeypatch.setenv(_WHEEL_CACHE_VARIABLE, str(outside))
    with pytest.raises(WheelCacheLocationError, match="must stay below"):
        admitted_wheel_cache(REPO_ROOT)


def _enter_child_environment(monkeypatch: pytest.MonkeyPatch, controls: dict[str, str]) -> None:
    """Give this process the environment a nested build child inherits from ``controls``."""
    for name, value in controls.items():
        monkeypatch.setenv(name, value)


def test_a_nested_build_of_a_copied_checkout_admits_the_cache_its_parent_admitted(
    build_owned_work_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The parent moves the development cache root, so only its exported admission reaches the child."""
    parent_cache_root = (
        REPO_ROOT / "var" / "storage" / "development" / f"nested-{build_owned_work_root.name}"
    ).resolve()
    monkeypatch.setenv("CADRUMO_DEV_CACHE_ROOT", str(parent_cache_root))
    monkeypatch.delenv(_WHEEL_CACHE_VARIABLE, raising=False)
    monkeypatch.delenv(_ADMITTED_ROOT_VARIABLE, raising=False)
    snapshot = build_owned_work_root / "snapshot"
    snapshot.mkdir()

    with build_environment(build_owned_work_root / "outer-work") as outer:
        cache = parent_cache_root / "runtime-wheel-cache"
        assert outer[_WHEEL_CACHE_VARIABLE] == str(cache)
        assert outer[_ADMITTED_ROOT_VARIABLE] == str(parent_cache_root)
        _enter_child_environment(monkeypatch, outer)

        assert admitted_wheel_cache(snapshot) == cache
        with build_environment(snapshot / "build" / "nested-work", repo_root=snapshot) as nested:
            assert nested[_WHEEL_CACHE_VARIABLE] == str(cache)
            assert nested[_ADMITTED_ROOT_VARIABLE] == str(parent_cache_root)

        # Without the parent's admission the moved cache root no longer covers it.
        monkeypatch.delenv(_ADMITTED_ROOT_VARIABLE)
        with pytest.raises(WheelCacheLocationError, match="must stay below"):
            admitted_wheel_cache(snapshot)


@pytest.mark.parametrize(
    ("exported", "message"),
    [
        (REPO_ROOT / "var" / "storage" / ".." / "storage" / "development", "not a canonical path"),
        (Path("var") / "storage" / "development", "not a canonical path"),
        (Path(REPO_ROOT.resolve().anchor), "filesystem root"),
        (REPO_ROOT.resolve() / "dev" / "packaging", "inside a source tree"),
    ],
)
def test_an_inherited_cache_root_is_refused_when_it_escapes_containment(
    build_owned_work_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    exported: Path,
    message: str,
) -> None:
    """The exported root is re-checked, so the variable cannot admit an arbitrary location."""
    snapshot = build_owned_work_root / "snapshot"
    snapshot.mkdir()
    monkeypatch.setenv(_WHEEL_CACHE_VARIABLE, str(REPO_ROOT / "var" / "storage" / "development" / "wheels"))
    monkeypatch.setenv(_ADMITTED_ROOT_VARIABLE, str(exported))

    with pytest.raises(WheelCacheLocationError, match=message):
        admitted_wheel_cache(snapshot)


def test_a_cache_outside_the_inherited_root_is_still_refused(
    build_owned_work_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = build_owned_work_root / "snapshot"
    snapshot.mkdir()
    monkeypatch.setenv("CADRUMO_DEV_CACHE_ROOT", str(build_owned_work_root / "isolated-cache"))
    monkeypatch.setenv(_ADMITTED_ROOT_VARIABLE, str((REPO_ROOT / "var" / "storage" / "development").resolve()))
    monkeypatch.setenv(_WHEEL_CACHE_VARIABLE, str(REPO_ROOT.resolve() / "var" / "other-wheels"))

    with pytest.raises(WheelCacheLocationError, match="must stay below"):
        admitted_wheel_cache(snapshot)


def test_build_storage_refuses_a_linked_work_root_before_creating_state(build_owned_work_root: Path) -> None:
    work = build_owned_work_root / "linked-work"
    outside = build_owned_work_root / "linked-storage-target"
    outside.mkdir()
    try:
        work.symlink_to(outside, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"directory symlinks are unavailable: {error}")

    with pytest.raises(ValueError, match="symlinks or junctions"), build_storage(work):
        pytest.fail("a linked storage directory was admitted")
    assert not (work / "cache").exists()
    assert not (work / "temporary").exists()
    assert not list(outside.iterdir())


def test_build_storage_cli_binds_child_environment_and_propagates_exit(build_owned_work_root: Path) -> None:
    work = build_owned_work_root / "cli-work"
    marker = work / "child.json"
    preserved = {name: f"operator:{name}" for name in _PRESERVED_TOOL_VARIABLES}
    environment = {**os.environ, **preserved}
    names = tuple(_expected_paths(work, wheel_cache_dir().resolve()))
    script = (
        "import json, os, sys, tempfile\n"
        f"names = {names!r}\n"
        f"preserved_names = {tuple(preserved)!r}\n"
        "payload = {\n"
        "    'environment': {name: os.environ[name] for name in names},\n"
        "    'no_bytecode': sys.dont_write_bytecode,\n"
        "    'preserved': {name: os.environ[name] for name in preserved_names},\n"
        "    'tempdir': tempfile.gettempdir(),\n"
        "}\n"
        "with open(sys.argv[1], 'w', encoding='utf-8') as stream:\n"
        "    json.dump(payload, stream)\n"
        "raise SystemExit(23)\n"
    )
    command = (
        sys.executable,
        "-B",
        "-m",
        "dev.packaging.build_storage",
        "--work",
        str(work),
        "--",
        sys.executable,
        "-B",
        "-c",
        script,
        str(marker),
    )
    result = run_command(command, cwd=REPO_ROOT, environment=environment)

    assert result.returncode == 23
    payload = json.loads(marker.read_text(encoding="utf-8"))
    isolated = Path(payload["environment"]["TEMP"]).parent
    expected = _expected_paths(isolated, wheel_cache_dir().resolve())
    assert payload["environment"] == expected
    assert isolated.is_relative_to(TEMP_ROOT)
    assert not isolated.exists()
    assert payload["tempdir"] == str(isolated / "temporary")
    assert payload["no_bytecode"] is True
    assert payload["preserved"] == preserved
    assert marker.resolve().is_relative_to((REPO_ROOT / "build").resolve())


def test_concurrent_build_environments_keep_child_state_independent(build_owned_work_root: Path) -> None:
    """Overlapping real children receive separate state without changing their parent."""
    names = ("CADRUMO_STORAGE_ROOT", "TEMP", "PYTHONDONTWRITEBYTECODE")
    ambient = {name: os.environ.get(name) for name in names}
    rendezvous = Barrier(2)
    script = (
        "import json, os, pathlib\n"
        "root = pathlib.Path(os.environ['CADRUMO_STORAGE_ROOT'])\n"
        "marker = root / 'manifest.json'\n"
        "marker.write_text(json.dumps({'storage': str(root), 'temporary': os.environ['TEMP']}))\n"
        "print(marker.read_text())\n"
    )

    def run_build(label: str) -> tuple[Path, dict[str, str]]:
        with build_environment(build_owned_work_root / label) as controls:
            isolated = Path(controls["TEMP"]).parent
            rendezvous.wait(timeout=30)
            result = run_command(
                (sys.executable, "-B", "-c", script),
                cwd=REPO_ROOT,
                environment={**os.environ, **controls},
            )
            assert result.returncode == 0, result.stderr
            raw: object = json.loads(result.stdout)
            assert isinstance(raw, dict)
            storage: object = raw.get("storage")
            temporary: object = raw.get("temporary")
            assert isinstance(storage, str)
            assert isinstance(temporary, str)
            payload = {"storage": storage, "temporary": temporary}
            assert storage == str(isolated / "storage")
            assert temporary == str(isolated / "temporary")
            assert isolated.is_relative_to(TEMP_ROOT)
            assert {name: os.environ.get(name) for name in names} == ambient
        assert not isolated.exists()
        return isolated, payload

    with ThreadPoolExecutor(max_workers=2) as workers:
        builds = [workers.submit(run_build, label) for label in ("first", "second")]
        first, second = [build.result() for build in builds]

    assert first[0] != second[0]
    assert first[1] != second[1]
    assert {name: os.environ.get(name) for name in names} == ambient


def test_build_storage_cli_rejects_paths_outside_build_before_running_command() -> None:
    work = REPO_ROOT / "var" / "build-storage-cli-rejected"
    result = run_command(
        (
            sys.executable,
            "-B",
            "-m",
            "dev.packaging.build_storage",
            "--work",
            str(work),
            "--",
            sys.executable,
            "-B",
            "-c",
            "raise SystemExit(0)",
        ),
        cwd=REPO_ROOT,
    )

    assert result.returncode == 2
    assert "build output must stay beneath" in result.stderr
    assert not work.exists()

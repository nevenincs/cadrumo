"""Build-scoped storage binding for Python build and release commands."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT
from dev.packaging.build_scratch_reclaim import require_build_path
from dev.packaging.build_storage import build_storage
from dev.packaging.command_execution import run_command

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DERIVED_CACHE_VARIABLES = (
    "CADRUMO_REGISTRY_DISK_CACHE_DIR",
    "CADRUMO_RECORD_DESIGN_CACHE_DIR",
    "CADRUMO_CORPUS_TEXT_CACHE_DIR",
    "CADRUMO_REGISTRY_VERDICT_CACHE_DIR",
    "CADRUMO_RUNTIME_WHEEL_CACHE_DIR",
)
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


def _expected_paths(work: Path) -> dict[str, str]:
    storage = work / "storage"
    cache = work / "cache"
    scratch = work / "scratch"
    temporary = work / "temporary"
    return {
        "CADRUMO_STORAGE_ROOT": str(storage),
        "CADRUMO_LOCAL_STORAGE_ROOT": str(storage),
        "CADRUMO_LOG_DIR": str(storage / "logs"),
        "CADRUMO_DEV_CACHE_ROOT": str(cache),
        "CADRUMO_DEV_CACHE_DIR": str(cache),
        "CADRUMO_PYTHON_CACHE_DIR": str(work / "python-cache"),
        "CADRUMO_TEST_LOG_ROOT": str(work / "test-logs"),
        "CADRUMO_SCRATCH_BASE": str(scratch),
        "CADRUMO_DEV_SCRATCH_DIR": str(scratch),
        "CADRUMO_DOCS_BUILD_ROOT": str(work / "docs"),
        "CADRUMO_DEV_ARTIFACTS_DIR": str(work / "artifacts"),
        **{name: str(cache / name.lower()) for name in _DERIVED_CACHE_VARIABLES},
        "CADRUMO_TEMP_DIR": str(temporary),
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
    expected = _expected_paths(work)
    for name in expected:
        monkeypatch.setenv(name, f"ambient:{name}")
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "0")
    preserved = {name: f"operator:{name}" for name in _PRESERVED_TOOL_VARIABLES}
    for name, value in preserved.items():
        monkeypatch.setenv(name, value)
    previous_tempdir = tempfile.tempdir
    previous_no_bytecode = sys.dont_write_bytecode

    with build_storage(work) as selected:
        assert selected == work
        assert {name: os.environ[name] for name in expected} == expected
        assert all(Path(value).is_relative_to(work) for value in expected.values())
        assert all(Path(value).is_dir() for value in set(expected.values()))
        assert os.environ["PYTHONDONTWRITEBYTECODE"] == "1"
        assert tempfile.gettempdir() == str(work / "temporary")
        assert sys.dont_write_bytecode is True
        assert {name: os.environ[name] for name in preserved} == preserved

    assert {name: os.environ[name] for name in expected} == {name: f"ambient:{name}" for name in expected}
    assert os.environ["PYTHONDONTWRITEBYTECODE"] == "0"
    assert tempfile.tempdir == previous_tempdir
    assert sys.dont_write_bytecode is previous_no_bytecode
    assert {name: os.environ[name] for name in preserved} == preserved


def test_build_storage_restores_state_after_failure_and_refuses_unowned_paths(
    build_owned_work_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    work = build_owned_work_root / "failure-work"
    monkeypatch.delenv("CADRUMO_LOCAL_STORAGE_ROOT", raising=False)
    previous_tempdir = tempfile.tempdir
    previous_no_bytecode = sys.dont_write_bytecode

    with pytest.raises(RuntimeError, match="build failed"), build_storage(work):
        assert os.environ["CADRUMO_LOCAL_STORAGE_ROOT"] == str(work / "storage")
        raise RuntimeError("build failed")

    assert "CADRUMO_LOCAL_STORAGE_ROOT" not in os.environ
    assert tempfile.tempdir == previous_tempdir
    assert sys.dont_write_bytecode is previous_no_bytecode

    with pytest.raises(ValueError, match="beneath"), build_storage(REPO_ROOT / "var" / "unowned-build-work"):
        pytest.fail("an unowned build directory was admitted")
    with pytest.raises(ValueError, match="below the repository build directory"), build_storage(REPO_ROOT / "build"):
        pytest.fail("the build root itself was admitted as work")


def test_build_storage_refuses_a_linked_controlled_child_before_creating_siblings(build_owned_work_root: Path) -> None:
    work = build_owned_work_root / "linked-work"
    work.mkdir()
    outside = build_owned_work_root / "linked-storage-target"
    outside.mkdir()
    try:
        (work / "storage").symlink_to(outside, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"directory symlinks are unavailable: {error}")

    with pytest.raises(ValueError, match="symlinks or junctions"), build_storage(work):
        pytest.fail("a linked storage directory was admitted")
    assert not (work / "cache").exists()
    assert not (work / "temporary").exists()


def test_build_storage_cli_binds_child_environment_and_propagates_exit(build_owned_work_root: Path) -> None:
    work = build_owned_work_root / "cli-work"
    marker = work / "child.json"
    expected = _expected_paths(work)
    preserved = {name: f"operator:{name}" for name in _PRESERVED_TOOL_VARIABLES}
    environment = {**os.environ, **preserved}
    names = tuple(expected)
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
    assert payload["environment"] == expected
    assert payload["tempdir"] == str(work / "temporary")
    assert payload["no_bytecode"] is True
    assert payload["preserved"] == preserved
    assert marker.resolve().is_relative_to((REPO_ROOT / "build").resolve())


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

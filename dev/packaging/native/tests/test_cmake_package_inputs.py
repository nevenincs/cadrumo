"""The generated graph consumes declared bootstraps and complete backend helpers."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ...command_execution import run_command
from ..action_cache import fingerprint
from ..layout import load_layout

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize("target", ["windows-x86-64", "linux-x86-64", "linux-aarch64", "macos-arm64"])
def test_declared_bootstrap_is_a_real_build_dependency(tmp_path: Path, target: str) -> None:
    layout = load_layout(target)
    contract = tmp_path / "layout.json"
    contract.write_text(json.dumps(layout), encoding="utf-8")
    (tmp_path / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 4.4)\nproject(BootstrapGraph LANGUAGES NONE)\n"
        f'file(READ "{contract.as_posix()}" layout)\n'
        f'include("{(REPO_ROOT / "native/cmake/PackageInputs.cmake").as_posix()}")\n'
        f'cadrumo_package_bootstrap(bootstrap "${{layout}}" "{REPO_ROOT.as_posix()}")\n'
        'add_custom_command(OUTPUT "${CMAKE_BINARY_DIR}/ready"\n'
        '  COMMAND "${CMAKE_COMMAND}" -E touch "${CMAKE_BINARY_DIR}/ready" DEPENDS "${bootstrap}")\n'
        'add_custom_target(bootstrap-fixture DEPENDS "${CMAKE_BINARY_DIR}/ready")\n'
        'file(WRITE "${CMAKE_BINARY_DIR}/selected-bootstrap.txt" "${bootstrap}")\n',
        encoding="utf-8",
    )
    cmake = shutil.which("cmake")
    assert cmake is not None
    build = tmp_path / "build"
    for command in (
        [cmake, "-S", str(tmp_path), "-B", str(build)],
        [cmake, "--build", str(build), "--target", "bootstrap-fixture"],
    ):
        result = run_command(command, cwd=tmp_path, timeout_seconds=60)
        assert result.returncode == 0, result.stdout + result.stderr
    observed = Path((build / "selected-bootstrap.txt").read_text(encoding="utf-8"))
    assert observed.resolve() == (REPO_ROOT / "native" / layout["bootstrap"]).resolve()
    assert (build / "ready").is_file()


def test_imported_posix_helper_is_enrolled_and_changes_cache_identity(tmp_path: Path) -> None:
    helper_root = tmp_path / "fixture/dev/packaging/native"
    platform = helper_root / "platforms"
    platform.mkdir(parents=True)
    adapter = platform / "linux.py"
    shared = platform / "posix.py"
    adapter.write_text("from . import posix\n", encoding="utf-8")
    shared.write_text("selected acquisition checks\n", encoding="utf-8")
    ignored = helper_root / "tests/test_fixture.py"
    ignored.parent.mkdir()
    ignored.write_text("not a builder input\n", encoding="utf-8")
    unrelated = helper_root / "assemble.py"
    unrelated.write_text("packaging owns this helper\n", encoding="utf-8")
    (tmp_path / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 4.4)\nproject(ProvisionInputs LANGUAGES NONE)\n"
        f'include("{(REPO_ROOT / "native/cmake/PackageInputs.cmake").as_posix()}")\n'
        f'cadrumo_provision_helpers(inputs "{(tmp_path / "fixture").as_posix()}")\n'
        'list(JOIN inputs "\\n" input_lines)\n'
        'file(WRITE "${CMAKE_BINARY_DIR}/inputs.txt" "${input_lines}\\n")\n',
        encoding="utf-8",
    )
    cmake = shutil.which("cmake")
    assert cmake is not None
    build = tmp_path / "build"
    result = run_command([cmake, "-S", str(tmp_path), "-B", str(build)], cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    inputs = build / "inputs.txt"
    assert {*map(Path, inputs.read_text(encoding="utf-8").splitlines())} == {adapter, shared}
    baseline = fingerprint(inputs)
    unrelated.write_text("changed assembly logic\n", encoding="utf-8")
    assert fingerprint(inputs) == baseline
    shared.write_text("changed decoder or redirect admission\n", encoding="utf-8")
    assert fingerprint(inputs) != baseline


def test_product_inputs_include_wheel_sources_without_installer_or_authoring_tools(tmp_path: Path) -> None:
    names = (
        "src/cadrumo/runtime.py",
        "src/cadrumo/tests/test_runtime.py",
        "packaging/companion/hatch_build.py",
        "packaging/companion/tests/test_hook.py",
        "packaging/authority/hatch_build.py",
        "packaging/scoop/generate.py",
        "packaging/scoop/tests/test_generate.py",
        "dev/registry/analysis/diagnostics.py",
        "dev/packaging/release_cohort.py",
    )
    fixture = tmp_path / "fixture"
    for name in names:
        path = fixture / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(name, encoding="utf-8")
    (tmp_path / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 4.4)\nproject(ProductInputs LANGUAGES NONE)\n"
        f'include("{(REPO_ROOT / "native/cmake/PackageInputs.cmake").as_posix()}")\n'
        'file(TO_NATIVE_PATH "packaging/authority" hook_directory)\n'
        f'cadrumo_product_inputs(inputs "{fixture.as_posix()}" packaging/companion "${{hook_directory}}")\n'
        'list(JOIN inputs "\\n" input_lines)\n'
        'file(WRITE "${CMAKE_BINARY_DIR}/inputs.txt" "${input_lines}\\n")\n',
        encoding="utf-8",
    )
    cmake = shutil.which("cmake")
    assert cmake is not None
    build = tmp_path / "build"
    result = run_command([cmake, "-S", str(tmp_path), "-B", str(build)], cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    observed = {Path(name).relative_to(fixture).as_posix() for name in (build / "inputs.txt").read_text().splitlines()}
    assert set(names) & observed == {
        "src/cadrumo/runtime.py",
        "packaging/companion/hatch_build.py",
        "packaging/authority/hatch_build.py",
    }

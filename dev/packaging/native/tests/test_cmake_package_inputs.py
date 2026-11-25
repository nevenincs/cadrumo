"""The generated graph consumes declared bootstraps and complete backend helpers."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from dev.paths import REPO_ROOT

from ...command_execution import run_command
from ..action_cache import enrolled_input_paths, fingerprint
from ..cached_command import inventory
from ..layout import load_layout

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize("backend", ["windows", "linux", "macos"])
def test_assembly_backend_currency_ignores_verification_siblings(tmp_path: Path, backend: str) -> None:
    platform = tmp_path / "dev/packaging/native/platforms"
    platform.mkdir(parents=True)
    producer = platform / f"{backend}.py"
    verifier = platform / f"{backend}_verify.py"
    producer.write_text("assembly producer one")
    verifier.write_text("verification one")
    if backend != "windows":
        for name in ("posix", "posix_assembly", "posix_images"):
            (platform / f"{name}.py").write_text(f"{name} helper", encoding="utf-8")
    script = tmp_path / "inputs.cmake"
    listing = tmp_path / "inputs.txt"
    script.write_text(
        f'include("{(REPO_ROOT / "native/cmake/PackageInputs.cmake").as_posix()}")\n'
        f'cadrumo_assembly_backend_inputs(inputs "{tmp_path.as_posix()}" "{backend}")\n'
        'list(JOIN inputs "\\n" contents)\n'
        f'file(WRITE "{listing.as_posix()}" "${{contents}}\\n")\n'
    )
    cmake = shutil.which("cmake")
    assert cmake is not None
    result = run_command([cmake, "-P", str(script)], cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    inputs = listing.read_text().splitlines()
    baseline = inventory(inputs)
    verifier.write_text("verification two")
    assert inventory(inputs) == baseline
    producer.write_text("assembly producer two")
    assert inventory(inputs) != baseline


@pytest.mark.parametrize("backend", ["linux", "macos"])
def test_posix_assembly_helpers_change_the_backend_identity(tmp_path: Path, backend: str) -> None:
    platform = tmp_path / "dev/packaging/native/platforms"
    platform.mkdir(parents=True)
    names = (backend, "posix", "posix_assembly", "posix_images")
    for name in names:
        (platform / f"{name}.py").write_text(f"{name} original\n", encoding="utf-8")
    script = tmp_path / "inputs.cmake"
    listing = tmp_path / "inputs.txt"
    script.write_text(
        f'include("{(REPO_ROOT / "native/cmake/PackageInputs.cmake").as_posix()}")\n'
        f'cadrumo_assembly_backend_inputs(inputs "{tmp_path.as_posix()}" "{backend}")\n'
        'list(JOIN inputs "\\n" contents)\n'
        f'file(WRITE "{listing.as_posix()}" "${{contents}}\\n")\n',
        encoding="utf-8",
    )
    cmake = shutil.which("cmake")
    assert cmake is not None
    result = run_command([cmake, "-P", str(script)], cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    inputs = listing.read_text(encoding="utf-8").splitlines()
    assert {*map(Path, inputs)} == {platform / f"{name}.py" for name in names}
    baseline = inventory(inputs)
    for name in ("posix_assembly", "posix_images"):
        path = platform / f"{name}.py"
        path.write_text(f"{name} changed\n", encoding="utf-8")
        assert inventory(inputs) != baseline
        path.write_text(f"{name} original\n", encoding="utf-8")


def test_assembly_consumes_payload_and_provenance_without_build_scratch(tmp_path: Path) -> None:
    product = tmp_path / "product"
    payload = product / "dependencies/module.py"
    payload.parent.mkdir(parents=True)
    payload.write_text("answer=1\n")
    provenance = product / "build/product-wheels.json"
    provenance.parent.mkdir(parents=True)
    provenance.write_text('{"wheel":"identity"}')
    agent_provenance = product / "agent-wheel.json"
    agent_provenance.write_text('{"wheel_sha256":"agent identity"}')
    scratch = product / "build/source/unrelated.txt"
    scratch.parent.mkdir()
    scratch.write_text("scratch one")
    script = tmp_path / "inputs.cmake"
    listing = tmp_path / "inputs.txt"
    script.write_text(
        f'include("{(REPO_ROOT / "native/cmake/PackageInputs.cmake").as_posix()}")\n'
        f'cadrumo_assembly_product_inputs(inputs "{product.as_posix()}")\n'
        'list(JOIN inputs "\\n" contents)\n'
        f'file(WRITE "{listing.as_posix()}" "${{contents}}\\n")\n'
    )
    cmake = shutil.which("cmake")
    assert cmake is not None
    result = run_command([cmake, "-P", str(script)], cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    inputs = listing.read_text().splitlines()
    original = inventory(inputs)
    scratch.write_text("scratch changed")
    assert inventory(inputs) == original
    payload.write_text("answer=2\n")
    assert inventory(inputs) != original
    payload.write_text("answer=1\n")
    provenance.write_text('{"wheel":"modified"}')
    assert inventory(inputs) != original
    provenance.write_text('{"wheel":"identity"}')
    agent_provenance.write_text('{"wheel_sha256":"changed agent identity"}')
    assert inventory(inputs) != original


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
        result = run_command(command, cwd=tmp_path, timeout_seconds=None)
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
    downloader = platform / "posix_sdk_download.py"
    adapter.write_text("from . import posix\n", encoding="utf-8")
    shared.write_text("selected acquisition checks\n", encoding="utf-8")
    downloader.write_text("admitted download checks\n", encoding="utf-8")
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
    assert {*map(Path, inputs.read_text(encoding="utf-8").splitlines())} == {adapter, shared, downloader}
    baseline = fingerprint(inputs)
    unrelated.write_text("changed assembly logic\n", encoding="utf-8")
    assert fingerprint(inputs) == baseline
    shared.write_text("changed decoder or redirect admission\n", encoding="utf-8")
    assert fingerprint(inputs) != baseline
    shared.write_text("selected acquisition checks\n", encoding="utf-8")
    downloader.write_text("changed download admission\n", encoding="utf-8")
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
        'list(JOIN inputs_trees "\\n" tree_lines)\n'
        'file(WRITE "${CMAKE_BINARY_DIR}/inputs.txt" "${input_lines}\\n${tree_lines}\\n")\n',
        encoding="utf-8",
    )
    cmake = shutil.which("cmake")
    assert cmake is not None
    build = tmp_path / "build"
    result = run_command([cmake, "-S", str(tmp_path), "-B", str(build)], cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    observed = {
        path.relative_to(fixture.resolve()).as_posix()
        for path in enrolled_input_paths(build / "inputs.txt", resolve_roots=True)
    }
    assert set(names) & observed == {
        "src/cadrumo/runtime.py",
        "packaging/companion/hatch_build.py",
        "packaging/authority/hatch_build.py",
    }


def _touch(root: Path, *names: str) -> None:
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(name, encoding="utf-8")


def test_product_trees_are_enumerated_when_the_manifest_is_read(tmp_path: Path) -> None:
    """A file added after the manifest was written is enrolled without running CMake again."""
    fixture = tmp_path / "fixture"
    _touch(
        fixture,
        "src/pkg/__init__.py",
        "src/pkg/tests/test_x.py",
        "src/pkg/conftest.py",
        "src/pkg/__pycache__/__init__.cpython-313.pyc",
        "src/pkg/data.lock",
        "src/pkg/.generated-export-stage-1/payload.bin",
    )
    script = tmp_path / "inputs.cmake"
    manifest = tmp_path / "inputs-product.txt"
    script.write_text(
        f'include("{(REPO_ROOT / "native/cmake/PackageInputs.cmake").as_posix()}")\n'
        f'cadrumo_product_inputs(inputs "{fixture.as_posix()}")\n'
        'list(JOIN inputs "\\n" input_lines)\n'
        'list(JOIN inputs_trees "\\n" tree_lines)\n'
        f'file(WRITE "{manifest.as_posix()}" "${{input_lines}}\\n${{tree_lines}}\\n")\n',
        encoding="utf-8",
    )
    cmake = shutil.which("cmake")
    assert cmake is not None
    result = run_command([cmake, "-P", str(script)], cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert f"tree\tproduct\t{fixture.as_posix()}\tsrc" in manifest.read_text(encoding="utf-8").splitlines()

    _touch(fixture, "src/pkg/new_module.py")

    root = fixture.resolve()
    observed = {path.relative_to(root).as_posix() for path in enrolled_input_paths(manifest, resolve_roots=True)}
    assert {name for name in observed if name.startswith("src/")} == {"src/pkg/__init__.py", "src/pkg/new_module.py"}


def test_docs_trees_keep_source_test_support_and_drop_documentation_artifacts(tmp_path: Path) -> None:
    root = tmp_path / "checkout"
    _touch(
        root,
        "src/pkg/tests/support.py",
        "src/pkg/__pycache__/support.cpython-313.pyc",
        "docs/index.md",
        "docs/_build/x.html",
        "dev/docs/builder.py",
        "dev/docs/tests/test_y.py",
        "dev/docs/.aeat-generated-export-transaction-7/state.json",
    )
    manifest = tmp_path / "inputs-user-docs.txt"
    manifest.write_text(
        "\n".join(f"tree\tdocs\t{root}\t{name}" for name in ("src", "docs", "dev/docs")) + "\n\n",
        encoding="utf-8",
    )

    observed = {path.relative_to(root).as_posix() for path in enrolled_input_paths(manifest)}

    assert observed == {"src/pkg/tests/support.py", "docs/index.md", "dev/docs/builder.py"}


def test_plain_path_lines_are_returned_unchanged_beside_tree_lines(tmp_path: Path) -> None:
    root = tmp_path / "checkout"
    _touch(root, "src/pkg/module.py")
    plain = tmp_path / "elsewhere/ready"
    manifest = tmp_path / "inputs.txt"
    manifest.write_text(f"{plain}\ntree\tproduct\t{root}\tsrc\n", encoding="utf-8")

    assert enrolled_input_paths(manifest) == [plain, root / "src/pkg/module.py"]


def test_unknown_tree_policy_is_refused(tmp_path: Path) -> None:
    manifest = tmp_path / "inputs.txt"
    manifest.write_text(f"tree\tunlisted\t{tmp_path}\tsrc\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Unknown input tree policy 'unlisted'"):
        enrolled_input_paths(manifest)


def test_malformed_tree_line_is_refused(tmp_path: Path) -> None:
    manifest = tmp_path / "inputs.txt"
    manifest.write_text(f"tree\tproduct\t{tmp_path}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Malformed tree line"):
        enrolled_input_paths(manifest)

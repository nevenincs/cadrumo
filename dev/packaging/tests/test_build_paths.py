"""CMake output ownership and cleanup containment."""

import json
import shutil
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT
from dev.packaging.command_execution import run_command
from dev.packaging.native.build_paths import build_paths
from dev.packaging.native.cleanup import clean

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def manifest(build: Path, paths: dict[str, str]) -> None:
    (build / "build-paths.json").write_text(
        json.dumps({"paths": paths, "cleanup": {"stage": list(paths)}}), encoding="utf-8"
    )
    (build / "CMakeCache.txt").write_text(f"CMAKE_HOME_DIRECTORY:INTERNAL={REPO_ROOT.as_posix()}\n", encoding="utf-8")


def test_cleanup_uses_declared_names_and_preserves_unowned_files(tmp_path: Path) -> None:
    manifest(tmp_path, {"stage": "payload/Release"})
    owned = tmp_path / "payload/Release"
    owned.mkdir(parents=True)
    (owned / "app.txt").write_text("generated", encoding="utf-8")
    retained = tmp_path / "unowned.txt"
    retained.write_text("retained", encoding="utf-8")
    clean(tmp_path, "stage")
    assert not owned.exists()
    assert retained.read_text(encoding="utf-8") == "retained"
    assert (tmp_path / "build-paths.json").is_file()


@pytest.mark.parametrize("relative", ["../outside", ".", "C:/outside", "/outside", "a\\b"])
def test_cleanup_validates_all_paths_before_deleting(tmp_path: Path, relative: str) -> None:
    manifest(tmp_path, {"valid": "stage", "invalid": relative})
    owned = tmp_path / "stage"
    owned.mkdir()
    with pytest.raises(ValueError):
        clean(tmp_path, "stage")
    assert owned.is_dir()


def test_manifest_is_required(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        build_paths(tmp_path)


def test_timing_cleanup_uses_its_declared_owner_without_removing_products(tmp_path: Path) -> None:
    manifest(tmp_path, {"timings": "diagnostics/phases", "product": "product"})
    document = json.loads((tmp_path / "build-paths.json").read_text(encoding="utf-8"))
    document["cleanup"] = {"timings": ["timings"]}
    (tmp_path / "build-paths.json").write_text(json.dumps(document), encoding="utf-8")
    timing = tmp_path / "diagnostics" / "phases"
    timing.mkdir(parents=True)
    (timing / "fixture.json").write_text("{}", encoding="utf-8")
    product = tmp_path / "product"
    product.mkdir()
    (product / "kept.whl").write_bytes(b"product")
    clean(tmp_path, "timings")
    assert not timing.exists()
    assert (product / "kept.whl").read_bytes() == b"product"


@pytest.mark.parametrize(
    ("declaration", "message"),
    [
        ("", ""),
        ("GENERATED other", "Duplicate build output key"),
        ("OTHER generated", "Duplicate build output directory"),
        ("OTHER generated/child", "Overlapping build output directories"),
        ("other other", "uppercase keys"),
        ("OTHER mixed_Case", "kebab-case path segments"),
    ],
)
def test_cmake_validates_output_names(tmp_path: Path, declaration: str, message: str) -> None:
    cmake = shutil.which("cmake")
    assert cmake is not None
    source = tmp_path / "repo"
    modules = source / "native" / "cmake"
    modules.mkdir(parents=True)
    (source / "CMakePresets.json").write_text(json.dumps({"configurePresets": [{"name": "fixture"}]}), encoding="utf-8")
    (source / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 4.4)\nproject(OutputNames NONE)\ninclude(native/cmake/BuildPaths.cmake)\n",
        encoding="utf-8",
    )
    shutil.copyfile(REPO_ROOT / "native/cmake/BinaryDirectory.cmake", modules / "BinaryDirectory.cmake")
    original = (REPO_ROOT / "native/cmake/BuildPaths.cmake").read_text(encoding="utf-8")
    changed = original.replace("  GENERATED generated", f"  GENERATED generated\n  {declaration}", 1)
    (modules / "BuildPaths.cmake").write_text(changed, encoding="utf-8")
    build = source / "build" / "fixture"
    result = run_command([cmake, "-S", str(source), "-B", str(build), "-G", "Ninja"], cwd=source)
    if not declaration:
        assert result.returncode == 0, result.stderr
        document = json.loads((build / "build-paths.json").read_text(encoding="utf-8"))
        assert document["paths"]["timings"] == "timings"
        assert document["cleanup"]["timings"] == ["timings"]
        return
    assert result.returncode != 0
    assert message in " ".join(result.stderr.split())
    assert not (build / "build-paths.json").exists()

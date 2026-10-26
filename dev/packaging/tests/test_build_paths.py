"""CMake output ownership and cleanup containment."""

import json
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT
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

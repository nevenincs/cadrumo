"""Command-line build ownership is restricted to configured repository presets."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from ...command_execution import run_command
from .. import build_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _project(root: Path, preset_name: str, source: str) -> None:
    relative_source = Path(source)
    project = root / relative_source
    project.mkdir(parents=True, exist_ok=True)
    (project / "CMakePresets.json").write_text(
        json.dumps({"configurePresets": [{"name": preset_name}]}), encoding="utf-8"
    )


def _configured_build(root: Path, preset_name: str, source: str) -> Path:
    build = root / "build" / preset_name
    build.mkdir(parents=True, exist_ok=True)
    (build / "build-paths.json").write_text(
        json.dumps({"source": str((root / source).resolve()), "paths": {"testing": "testing"}}),
        encoding="utf-8",
    )
    (build / "CMakeCache.txt").write_text(
        "\n".join(
            (
                f"CMAKE_HOME_DIRECTORY:INTERNAL={(root / source).resolve()}",
                f"CMAKE_CACHEFILE_DIR:INTERNAL={build.resolve()}",
            )
        ),
        encoding="utf-8",
    )
    return build


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "build").mkdir()
    _project(root, "native-one", ".")
    _project(root, "desktop-one", "native/desktop")
    _project(root, "distribution-one", "native/cmake/distribution")
    (root / "native/desktop/CMakePresets.json").write_text(
        json.dumps({"configurePresets": [{"name": "desktop-one"}]}), encoding="utf-8"
    )
    (root / "native/cmake/distribution/CMakePresets.json").write_text(
        json.dumps({"configurePresets": [{"name": "distribution-one"}]}), encoding="utf-8"
    )
    return root


@pytest.mark.parametrize(
    ("name", "source"),
    (("native-one", "."), ("desktop-one", "native/desktop"), ("distribution-one", "native/cmake/distribution")),
)
def test_admits_configured_visible_preset_builds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, source: str
) -> None:
    root = _root(tmp_path)
    monkeypatch.setattr(build_directory, "REPO_ROOT", root)
    build = _configured_build(root, name, source)
    assert build_directory.require_enrolled_build(build) == build.resolve()


def test_admits_relative_spelling_of_the_same_enrolled_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _root(tmp_path)
    monkeypatch.setattr(build_directory, "REPO_ROOT", root)
    build = _configured_build(root, "native-one", ".")
    monkeypatch.chdir(root)
    relative = Path("build/native-one")
    assert build_directory.require_enrolled_build(relative) == build.resolve()


@pytest.mark.parametrize("spelling", ("build/unknown", "build/.hidden", "build/native-one/../native-one"))
def test_rejects_unenrolled_hidden_and_traversing_build_spellings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spelling: str
) -> None:
    root = _root(tmp_path)
    monkeypatch.setattr(build_directory, "REPO_ROOT", root)
    with pytest.raises(ValueError):
        build_directory.require_enrolled_build(root / spelling)


def test_requires_a_configured_manifest_from_the_matching_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    monkeypatch.setattr(build_directory, "REPO_ROOT", root)
    build = root / "build/native-one"
    build.mkdir()
    with pytest.raises(ValueError, match="manifest"):
        build_directory.require_enrolled_build(build)

    _configured_build(root, "native-one", "native/desktop")
    with pytest.raises(ValueError, match="does not match preset"):
        build_directory.require_enrolled_build(build)


def test_configure_stage_may_admit_declared_outputs_before_cmake_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    monkeypatch.setattr(build_directory, "REPO_ROOT", root)
    build = _configured_build(root, "native-one", ".")
    (build / "CMakeCache.txt").unlink()
    requested = build / "testing" / "generated.json"
    assert build_directory.require_enrolled_build(build, configured=False) == build.resolve()
    assert build_directory.require_enrolled_output(build / "testing") == build / "testing"
    assert build_directory.require_enrolled_output(requested) == requested
    with pytest.raises(ValueError, match="CMake cache"):
        build_directory.require_enrolled_build(build)


@pytest.mark.parametrize("relative", ("unlisted/output.json", "testing/../other/output.json"))
def test_configure_stage_rejects_output_roots_unlisted_paths_and_traversal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, relative: str
) -> None:
    root = _root(tmp_path)
    monkeypatch.setattr(build_directory, "REPO_ROOT", root)
    build = _configured_build(root, "native-one", ".")
    (build / "CMakeCache.txt").unlink()
    with pytest.raises(ValueError):
        build_directory.require_enrolled_output(build / relative)


def test_configure_stage_rejects_linked_output_components(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _root(tmp_path)
    monkeypatch.setattr(build_directory, "REPO_ROOT", root)
    build = _configured_build(root, "native-one", ".")
    (build / "CMakeCache.txt").unlink()
    linked = build / "testing" / "linked"
    linked.parent.mkdir(parents=True)
    try:
        linked.symlink_to(tmp_path / "outside", target_is_directory=True)
    except OSError:
        pytest.skip("This host cannot create directory links")
    with pytest.raises(ValueError, match="symlinks or junctions"):
        build_directory.require_enrolled_output(linked / "new.json")


def test_rejects_linked_build_and_preset_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _root(tmp_path)
    monkeypatch.setattr(build_directory, "REPO_ROOT", root)
    _configured_build(root, "native-one", ".")
    outside = tmp_path / "outside"
    outside.mkdir()
    linked_build = root / "build/linked"
    try:
        linked_build.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("This host cannot create directory links")
    with pytest.raises(ValueError):
        build_directory.require_enrolled_build(linked_build)

    preset_file = root / "native/desktop/CMakePresets.json"
    preset_file.unlink()
    preset_file.symlink_to(root / "CMakePresets.json")
    with pytest.raises(ValueError, match="symlinks or junctions"):
        build_directory.require_enrolled_build(root / "build/native-one")


def test_real_cli_rejects_an_arbitrary_root_before_creating_it(tmp_path: Path) -> None:
    rogue = tmp_path / "rogue-build"
    result = run_command(
        [
            sys.executable,
            "-B",
            "-m",
            "dev.packaging.native.windows_msi",
            "reject-combined",
            "--build",
            str(rogue),
        ],
        cwd=build_directory.REPO_ROOT,
        timeout_seconds=30,
    )
    assert result.returncode != 0
    assert "beneath" in result.stderr or "enrolled" in result.stderr
    assert not rogue.exists()

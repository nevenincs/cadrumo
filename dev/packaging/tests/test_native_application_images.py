"""Application images: declared by the platform mapping, staged from CMake artifacts and verified."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from dev.packaging.command_execution import CommandResult
from dev.packaging.native.assemble import image_artifact, stage_application_images
from dev.packaging.native.hashing import digest
from dev.packaging.native.layout import (
    application_images,
    desktop_image,
    load_layout,
    staged_application_images,
)
from dev.packaging.native.platforms.windows_verify import verify_application_images

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

VERSION = "1.2.3"


def _desktop(**overrides: Any) -> dict[str, Any]:
    return {
        "name": "cadrumo",
        "placement": ".",
        "target": "desktop-host-build",
        "artifact": "CADRUMO_DESKTOP_HOST_EXECUTABLE",
        "desktop": True,
        "signed": True,
        "version_arguments": ["--headless", "--", "--version"],
        **overrides,
    }


def _manager(**overrides: Any) -> dict[str, Any]:
    return {
        "name": "cadrumo-manager",
        "placement": ".",
        "target": "rust_manager",
        "artifact": "CADRUMO_MANAGER_EXECUTABLE",
        "desktop": False,
        "signed": True,
        "version_arguments": ["--version"],
        **overrides,
    }


def _checkout(
    root: Path,
    images: list[dict[str, Any]],
    *,
    entrypoints: dict[str, str] | None = None,
    scripts: dict[str, str] | None = None,
    suffix: str = ".exe",
) -> Path:
    entrypoints = {"cadrumo-runtime": "Runtime"} if entrypoints is None else entrypoints
    scripts = {"cadrumo-runtime": "pkg.runtime:main"} if scripts is None else scripts
    (root / "native/platforms").mkdir(parents=True)
    shared = {
        "abi": 1,
        "paths": {"native": "bin", "stdlib": "python.zip", "packages": "cadrumo/site-packages", "docs": "docs"},
        "files": {"package_manifest": "data/package-manifest.json"},
        "entrypoints": entrypoints,
        "platforms": {"windows-x64": "platforms/windows-x64.json"},
    }
    platform = {
        "platform": "windows-x64",
        "paths": {"executable": f"python{suffix}"},
        "files": {"development_executable": f"python_d{suffix}"},
        "entrypoint_suffix": suffix,
        "application_images": images,
    }
    (root / "native/package-layout.json").write_text(json.dumps(shared), encoding="utf-8")
    (root / "native/platforms/windows-x64.json").write_text(json.dumps(platform), encoding="utf-8")
    lines = "\n".join(f"{json.dumps(name)} = {json.dumps(target)}" for name, target in scripts.items())
    (root / "pyproject.toml").write_text(f'[project]\nname = "x"\n\n[project.scripts]\n{lines}\n', encoding="utf-8")
    return root


def test_the_platform_mapping_declares_images_with_its_own_suffix(tmp_path: Path) -> None:
    layout = load_layout("windows-x64", root=_checkout(tmp_path, [_desktop(), _manager()]))

    images = application_images(layout)

    assert [(image.file, image.package_path, image.target, image.artifact) for image in images] == [
        ("cadrumo.exe", "cadrumo.exe", "desktop-host-build", "CADRUMO_DESKTOP_HOST_EXECUTABLE"),
        ("cadrumo-manager.exe", "cadrumo-manager.exe", "rust_manager", "CADRUMO_MANAGER_EXECUTABLE"),
    ]
    # Startup membership is opt-in; neither image declares it.
    assert [image.startup for image in images] == [False, False]
    assert [image.signed for image in images] == [True, True]
    desktop = desktop_image(layout)
    assert desktop is not None and desktop.file == "cadrumo.exe"


def test_the_checked_in_mapping_declares_the_desktop_image() -> None:
    layout = load_layout("windows-x64")

    desktop = desktop_image(layout)

    assert desktop is not None
    assert (desktop.package_path, desktop.target, desktop.startup) == ("cadrumo.exe", "desktop-host-build", False)


def test_startup_membership_is_declared_per_image(tmp_path: Path) -> None:
    layout = load_layout("windows-x64", root=_checkout(tmp_path, [_manager(startup=True)]))

    assert [image.startup for image in application_images(layout)] == [True]


def test_a_desktop_name_in_the_entrypoints_map_is_still_refused(tmp_path: Path) -> None:
    root = _checkout(tmp_path, [_desktop()], entrypoints={"cadrumo": "Desktop"}, scripts={"aeat": "pkg.cli:main"})

    with pytest.raises(ValueError, match="not a declared console script: cadrumo"):
        load_layout("windows-x64", root=root)


@pytest.mark.parametrize(
    ("images", "message"),
    [
        ([_desktop(), _desktop(artifact="OTHER_EXECUTABLE")], "Duplicate application image: cadrumo"),
        ([_desktop(), _manager(artifact="CADRUMO_DESKTOP_HOST_EXECUTABLE")], "share the artifact variable"),
        ([_desktop(), _manager(desktop=True)], "At most one application image is the desktop"),
        ([_desktop(name="python")], "collides with package file python.exe"),
        ([_desktop(name="cadrumo-runtime")], "collides with a console entrypoint: cadrumo-runtime"),
        ([{**_desktop(), "unknown": True}], "must declare"),
        ([{key: value for key, value in _desktop().items() if key != "signed"}], "must declare"),
        ([_desktop(name="Cadrumo")], "lowercase hyphenated identifier"),
        ([_desktop(target="desktop host")], "must name a CMake target"),
        ([_desktop(artifact="${CADRUMO}")], "must name the CMake variable"),
        ([_desktop(startup="yes")], "flags must be booleans"),
        ([_desktop(version_arguments=[""])], "version_arguments"),
    ],
)
def test_invalid_declarations_are_refused(tmp_path: Path, images: list[dict[str, Any]], message: str | None) -> None:
    root = _checkout(tmp_path, images)

    if message is None:
        load_layout("windows-x64", root=root)
        return
    with pytest.raises(ValueError, match=message):
        load_layout("windows-x64", root=root)


def test_names_collide_without_case_or_suffix(tmp_path: Path) -> None:
    root = _checkout(tmp_path / "docs-dir", [_desktop(name="docs")], suffix="")
    with pytest.raises(ValueError, match="collides with package file docs"):
        load_layout("windows-x64", root=root)
    shouting = _checkout(tmp_path / "case", [_desktop()])
    platform = shouting / "native/platforms/windows-x64.json"
    mapping = json.loads(platform.read_text(encoding="utf-8"))
    mapping["paths"]["executable"] = "CADRUMO.EXE"
    platform.write_text(json.dumps(mapping), encoding="utf-8")
    with pytest.raises(ValueError, match=re.escape("collides with package file CADRUMO.EXE")):
        load_layout("windows-x64", root=shouting)


def test_a_placement_outside_the_package_root_is_not_implemented(tmp_path: Path) -> None:
    root = _checkout(tmp_path, [_desktop(placement="Contents/MacOS")])

    with pytest.raises(NotImplementedError, match="placement 'Contents/MacOS' is not implemented"):
        load_layout("windows-x64", root=root)


def test_only_the_desktop_image_needs_bundled_documentation(tmp_path: Path) -> None:
    layout = load_layout("windows-x64", root=_checkout(tmp_path, [_desktop(), _manager()]))

    with_docs = [image.file for image in staged_application_images(layout, user_docs=True)]
    without_docs = [image.file for image in staged_application_images(layout, user_docs=False)]

    assert with_docs == ["cadrumo.exe", "cadrumo-manager.exe"]
    assert without_docs == ["cadrumo-manager.exe"]


def _staging(tmp_path: Path) -> tuple[Path, Path, dict[str, Any]]:
    binary = tmp_path / "build"
    (binary / "cargo/release").mkdir(parents=True)
    (binary / "cargo/release/cadrumo.exe").write_bytes(b"desktop image")
    (binary / "cargo/release/cadrumo-manager.exe").write_bytes(b"manager image")
    package = tmp_path / "package"
    package.mkdir()
    layout = load_layout("windows-x64", root=_checkout(tmp_path / "checkout", [_desktop(), _manager()]))
    return binary, package, layout


def test_staging_copies_each_image_from_its_artifact(tmp_path: Path) -> None:
    binary, package, layout = _staging(tmp_path)
    artifacts = {
        "cadrumo.exe": binary / "cargo/release/cadrumo.exe",
        "cadrumo-manager.exe": binary / "cargo/release/cadrumo-manager.exe",
    }

    staged = stage_application_images(package, application_images(layout), artifacts, binary)

    assert staged == ["cadrumo.exe", "cadrumo-manager.exe"]
    assert (package / "cadrumo.exe").read_bytes() == b"desktop image"
    assert (package / "cadrumo-manager.exe").read_bytes() == b"manager image"


def test_staging_refuses_a_missing_artifact(tmp_path: Path) -> None:
    binary, package, layout = _staging(tmp_path)
    images = staged_application_images(layout, user_docs=False)
    absent = {"cadrumo-manager.exe": binary / "cargo/release/absent.exe"}

    with pytest.raises(FileNotFoundError, match=r"artifact is missing.*build rust_manager"):
        stage_application_images(package, images, absent, binary)
    with pytest.raises(
        ValueError, match=re.escape("No artifact was supplied for application image cadrumo-manager.exe")
    ):
        stage_application_images(package, images, {}, binary)
    assert not any(package.iterdir())


def test_staging_refuses_unstaged_and_foreign_artifacts(tmp_path: Path) -> None:
    binary, package, layout = _staging(tmp_path)
    images = staged_application_images(layout, user_docs=False)
    manager = {"cadrumo-manager.exe": binary / "cargo/release/cadrumo-manager.exe"}

    with pytest.raises(ValueError, match=r"does not stage: \['cadrumo.exe'\]"):
        stage_application_images(
            package, images, {**manager, "cadrumo.exe": binary / "cargo/release/cadrumo.exe"}, binary
        )
    outside = tmp_path / "elsewhere.exe"
    outside.write_bytes(b"foreign")
    with pytest.raises(ValueError, match="outside the CMake binary directory"):
        stage_application_images(package, images, {"cadrumo-manager.exe": outside}, binary)
    (package / "cadrumo-manager.exe").write_bytes(b"assembled earlier")
    with pytest.raises(FileExistsError, match="collides with an assembled file"):
        stage_application_images(package, images, manager, binary)


@pytest.mark.parametrize("argument", ["cadrumo.exe", "=C:/build/cadrumo.exe", "cadrumo.exe="])
def test_image_arguments_need_both_sides(argument: str) -> None:
    with pytest.raises(ValueError, match="FILE=ARTIFACT"):
        image_artifact(argument)


def _package(tmp_path: Path, *, bundled: bool, startup: list[str] | None = None) -> tuple[Path, dict[str, Any]]:
    root = tmp_path / "package"
    root.mkdir()
    layout = load_layout("windows-x64", root=_checkout(tmp_path / "checkout", [_desktop(), _manager()]))
    files: dict[str, str] = {}
    staged = staged_application_images(layout, user_docs=bundled)
    for image in staged:
        (root / image.package_path).write_bytes(image.name.encode())
        files[image.package_path] = digest(root / image.package_path)
    if bundled:
        (root / "docs/user").mkdir(parents=True)
        (root / "docs/user/manifest.json").write_text('{"files": {}}', encoding="utf-8")
        files["docs/user/manifest.json"] = digest(root / "docs/user/manifest.json")
    manifest = {
        "build": {"version": VERSION},
        "layout": layout,
        "files": files,
        "startup_files": startup or [],
        "delegated_inventories": {"docs/user": "docs/user/manifest.json"} if bundled else {},
        "user_docs": {"directory": "docs/user", "bundled": bundled},
    }
    return root, manifest


def _result(argv: list[str], returncode: int = 0, stdout: str = f"cadrumo {VERSION}\n") -> CommandResult:
    now = datetime.now(UTC)
    return CommandResult(tuple(argv), ".", now, now, 0.0, returncode, stdout, "")


def test_the_verifier_runs_each_staged_image_for_its_version(tmp_path: Path) -> None:
    root, manifest = _package(tmp_path, bundled=True)
    calls: list[list[str]] = []

    def execute(argv: list[str]) -> CommandResult:
        calls.append(argv)
        return _result(argv)

    observed = verify_application_images(root, manifest, execute)

    assert calls == [
        [str(root / "cadrumo.exe"), "--headless", "--", "--version"],
        [str(root / "cadrumo-manager.exe"), "--version"],
    ]
    assert observed["cadrumo.exe"]["sha256"] == manifest["files"]["cadrumo.exe"]
    assert observed["cadrumo.exe"]["startup_file"] is False


def test_the_verifier_requires_the_desktop_image_to_be_absent_without_documentation(tmp_path: Path) -> None:
    root, manifest = _package(tmp_path, bundled=False)

    observed = verify_application_images(root, manifest, _result)

    assert observed["cadrumo.exe"] == {"staged": False}
    (root / "cadrumo.exe").write_bytes(b"shipped anyway")
    with pytest.raises(AssertionError, match=re.escape("cadrumo.exe ships in a package that may not stage it")):
        verify_application_images(root, manifest, _result)


def test_the_verifier_refuses_an_unhashed_or_missing_image(tmp_path: Path) -> None:
    root, manifest = _package(tmp_path, bundled=True)
    (root / "cadrumo.exe").write_bytes(b"replaced after assembly")
    with pytest.raises(AssertionError, match=re.escape("cadrumo.exe is missing or absent from the package manifest")):
        verify_application_images(root, manifest, _result)
    (root / "cadrumo.exe").unlink()
    with pytest.raises(AssertionError, match=re.escape("cadrumo.exe is missing")):
        verify_application_images(root, manifest, _result)


def test_the_verifier_refuses_undeclared_startup_membership(tmp_path: Path) -> None:
    root, manifest = _package(tmp_path, bundled=True, startup=["cadrumo.exe"])

    with pytest.raises(AssertionError, match=re.escape("cadrumo.exe startup membership differs")):
        verify_application_images(root, manifest, _result)


@pytest.mark.parametrize(
    ("returncode", "stdout"),
    [(1, f"cadrumo {VERSION}\n"), (0, "cadrumo 1.2.30\n"), (0, "cadrumo 11.2.3\n"), (0, "")],
)
def test_the_verifier_requires_a_successful_exact_version(tmp_path: Path, returncode: int, stdout: str) -> None:
    root, manifest = _package(tmp_path, bundled=True)

    with pytest.raises(AssertionError, match=f"cadrumo.exe did not report version {VERSION}"):
        verify_application_images(root, manifest, lambda argv: _result(argv, returncode, stdout))

"""Distribution graphs select native formats and retain incremental ZIP receipts."""

from __future__ import annotations

import json
import shutil
import sys
import zipfile
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT
from dev.packaging.command_execution import run_command
from dev.packaging.tests.test_native_installation import payload_fixture

from ..distribution_prepare import refresh
from ..hashing import digest
from ..identity import cmake_projection, identity
from ..windows_msi_build import compile_products, verify_products
from ..windows_msi_database import verify_upgrade_order

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _paths(build: Path) -> dict[str, str]:
    paths = {f"installation_{name}": f"installation/{name}" for name in ("stage", "metadata", "work", "receipts")}
    paths.update(generated="generated", packages="packages")
    build.mkdir()
    (build / "build-paths.json").write_text(json.dumps({"paths": paths}), encoding="utf-8")
    return paths


def _change_payload(payload: Path) -> None:
    (payload / "cadrumo").write_text("changed binary", encoding="utf-8")
    manifest = payload / "data/package-manifest.json"
    value = json.loads(manifest.read_text(encoding="utf-8"))
    value["files"]["cadrumo"] = digest(payload / "cadrumo")
    manifest.write_text(json.dumps(value), encoding="utf-8")


def test_refresh_preserves_previous_receipt_and_rejects_modified_stage(tmp_path: Path) -> None:
    payload, identity_file = payload_fixture(tmp_path, "windows-x86-64")
    build = tmp_path / "build"
    _paths(build)
    refresh(payload, identity_file, build)
    old_receipt = (build / "installation/metadata/installation.json").read_bytes()
    _change_payload(payload)
    refresh(payload, identity_file, build)
    assert (build / "installation/stage/app/cadrumo").read_text(encoding="utf-8") == "changed binary"
    assert old_receipt in [path.read_bytes() for path in (build / "installation/receipts").glob("*.json")]
    (build / "installation/stage/app/cadrumo").write_text("user alteration", encoding="utf-8")
    with pytest.raises(ValueError, match="has changed"):
        refresh(payload, identity_file, build)
    assert (build / "installation/stage/app/cadrumo").read_text(encoding="utf-8") == "user alteration"


def _cmake(source: Path, *arguments: str) -> str:
    cmake = shutil.which("cmake")
    assert cmake is not None
    result = run_command([cmake, *arguments], cwd=source)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def _configure_distribution(tmp_path: Path, target: str, *, manager: bool = False) -> tuple[Path, Path, Path]:
    payload, identity_file = payload_fixture(tmp_path, target, manager=manager)
    source = tmp_path / "source"
    source.mkdir()
    build = tmp_path / "build"
    paths = _paths(build)
    (build / "generated").mkdir()
    shutil.copy2(identity_file, build / "generated/identity.json")
    module = REPO_ROOT / "native/cmake/distribution"
    text = (module / "CMakeLists.txt").read_text(encoding="utf-8")
    # Keep the real distribution graph; substitute only host/bootstrap admission.
    text = text.replace("include(../Identity.cmake)", "include(FixtureIdentity.cmake)")
    text = text.replace(
        "include(../CachedCommand.cmake)", f'include("{(REPO_ROOT / "native/cmake/CachedCommand.cmake").as_posix()}")'
    )
    (source / "CMakeLists.txt").write_text(text, encoding="utf-8")
    shutil.copy2(module / "VerifyInstall.cmake.in", source / "VerifyInstall.cmake.in")
    shutil.copy2(module / "WindowsMsiGate.cmake.in", source / "WindowsMsiGate.cmake.in")
    bootstrap = cmake_projection(identity(target))
    bootstrap += f'set(CADRUMO_SOURCE_ROOT "{REPO_ROOT.as_posix()}")\n'
    bootstrap += f'set(CADRUMO_DEV_PYTHON "{Path(sys.executable).as_posix()}")\n'
    bootstrap += f"set(CADRUMO_TARGET {target})\nadd_custom_target(setup-native-builder)\n"
    bootstrap += f'include("{(REPO_ROOT / "native/cmake/Cleanup.cmake").as_posix()}")\n'
    bootstrap += 'cmake_language(DEFER DIRECTORY "${CMAKE_SOURCE_DIR}" CALL cadrumo_finalize_clean_targets)\n'
    for key, relative in paths.items():
        bootstrap += f'set(CADRUMO_PATH_{key.upper()} "${{CMAKE_BINARY_DIR}}/{relative}")\n'
    (source / "FixtureIdentity.cmake").write_text(bootstrap, encoding="utf-8")

    _cmake(
        source,
        "-G",
        "Ninja",
        "-S",
        str(source),
        "-B",
        str(build),
        "-DCMAKE_BUILD_TYPE=Release",
        f"-DCADRUMO_PAYLOAD={payload}",
    )
    return payload, source, build


def test_distribution_build_presets_are_host_bound() -> None:
    source = REPO_ROOT / "native/cmake/distribution"
    presets = _cmake(source, "--list-presets=build")
    windows = {"distribution-windows-msi"}
    linux = {
        f"distribution-linux-{arch}-{format_name}" for arch in ("x86-64", "aarch64") for format_name in ("deb", "rpm")
    }
    macos = {"distribution-macos-dmg"}
    visible = windows if sys.platform == "win32" else macos if sys.platform == "darwin" else linux
    for name in visible:
        assert f'"{name}"' in presets
    for name in (windows | linux | macos) - visible:
        assert f'"{name}"' not in presets


@pytest.mark.parametrize("manager", [False, True])
def test_distribution_wix_guard_and_authoring_are_in_the_real_graph(tmp_path: Path, manager: bool) -> None:
    _, source, build = _configure_distribution(tmp_path, "windows-x86-64", manager=manager)
    _cmake(source, "--build", str(build), "--target", "msi-author" if manager else "installation_prepare")
    cmake = shutil.which("cmake")
    assert cmake is not None
    result = run_command([cmake, "-DCPACK_GENERATOR=WIX", "-P", str(build / "WindowsMsiGate.cmake")], cwd=source)
    if manager:
        assert result.returncode != 0
        assert "separate version and registration" in result.stdout + result.stderr, result.stdout + result.stderr
        assert len(list((build / "installation/metadata/wix").glob("*.wxs"))) == 4
        result = run_command([cmake, "--build", str(build), "--target", "check-msi-installation"], cwd=source)
        assert result.returncode != 0
        assert "same-version integrity" in result.stdout + result.stderr, result.stdout + result.stderr
        assert "Session 0" in result.stdout + result.stderr
        assert not list((build / "packages").glob("*.msi"))
    else:
        assert result.returncode == 0, result.stdout + result.stderr
    _cmake(source, "--build", str(build), "--target", "zip")
    assert list((build / "packages").glob("*.zip"))


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="Requires the native Windows MSI validator")
def test_cmake_scoped_msi_build_verify_tamper_and_clean(tmp_path: Path) -> None:
    wix = shutil.which("wix")
    assert wix is not None, "Put WiX 5+ on PATH for the native compiler lane"
    _, source, build = _configure_distribution(tmp_path, "windows-x86-64", manager=True)
    _cmake(source, "-S", str(source), "-B", str(build), f"-DCADRUMO_WIX_EXECUTABLE={wix}")
    _cmake(source, "--build", str(build), "--target", "msi-verify")
    directory = build / "packages/msi"
    receipt = json.loads((directory / "compiled.json").read_text(encoding="utf-8"))
    assert receipt["installable"] is False
    assert set(receipt["artifacts"]) == {
        f"{scope}-{role}.msi" for scope in ("user", "machine") for role in ("version", "registration")
    }
    identity_file = build / "generated/identity.json"
    for name, checksum in receipt["artifacts"].items():
        assert digest(directory / name) == checksum
    # Compile a real regression: moving removal outside the transaction must fail
    # the native action-table check even if the WiX decompiler loses scheduling.
    bad_source = tmp_path / "bad-registration.wxs"
    bad_source.write_text(
        (build / "installation/metadata/wix/user-registration.wxs")
        .read_text(encoding="utf-8")
        .replace('Schedule="afterInstallExecute"', 'Schedule="afterInstallFinalize"'),
        encoding="utf-8",
    )
    bad_msi = tmp_path / "bad-registration.msi"
    result = run_command([wix, "build", "-arch", "x64", "-wx", "-o", str(bad_msi), str(bad_source)], cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    with pytest.raises(ValueError, match="transactional upgrade order"):
        verify_upgrade_order(bad_msi, version_product=False)
    (directory / "user-version.msi").write_bytes(b"replaced artifact")
    with pytest.raises(ValueError, match="artifact has changed"):
        verify_products(build, identity_file)
    with pytest.raises(ValueError, match="WiX 5 or newer"):
        compile_products(build, identity_file, Path(sys.executable))
    assert not (directory / "compiled.json").exists()
    _cmake(source, "--build", str(build), "--target", "clean-msi")
    assert not directory.exists()
    assert (build / "installation/metadata/wix/user-version.wxs").is_file()
    assert (build / "installation/stage").is_dir()


def test_cmake_scoped_msi_missing_compiler_fails_without_receipt(tmp_path: Path) -> None:
    _, source, build = _configure_distribution(tmp_path, "windows-x86-64", manager=True)
    _cmake(source, "-S", str(source), "-B", str(build), f"-DCADRUMO_WIX_EXECUTABLE={tmp_path / 'missing-wix'}")
    cmake = shutil.which("cmake")
    assert cmake is not None
    result = run_command([cmake, "--build", str(build), "--target", "msi"], cwd=source)
    assert result.returncode != 0
    assert "CADRUMO_WIX_EXECUTABLE" in result.stdout + result.stderr
    assert not (build / "packages/msi/compiled.json").exists()


@pytest.mark.parametrize(
    ("target", "generators", "formats", "metadata"),
    [
        ("windows-x86-64", "WIX", {"msi": "WIX"}, {"CPACK_WIX_ARCHITECTURE": "x64"}),
        (
            "linux-x86-64",
            "DEB;RPM",
            {"deb": "DEB", "rpm": "RPM"},
            {"CPACK_DEBIAN_PACKAGE_ARCHITECTURE": "amd64", "CPACK_RPM_PACKAGE_ARCHITECTURE": "x86_64"},
        ),
        (
            "linux-aarch64",
            "DEB;RPM",
            {"deb": "DEB", "rpm": "RPM"},
            {"CPACK_DEBIAN_PACKAGE_ARCHITECTURE": "arm64", "CPACK_RPM_PACKAGE_ARCHITECTURE": "aarch64"},
        ),
        ("macos-arm64", "DragNDrop", {"dmg": "DragNDrop"}, {"CPACK_DMG_DISABLE_APPLICATIONS_SYMLINK": "OFF"}),
    ],
)
def test_distribution_native_formats_and_stage_dependencies(
    tmp_path: Path, target: str, generators: str, formats: dict[str, str], metadata: dict[str, str]
) -> None:
    _, source, build = _configure_distribution(tmp_path, target)
    probe = source / "probe.cmake"
    keys = ["CPACK_GENERATOR", *metadata]
    probe.write_text(
        f'include("{(build / "CPackConfig.cmake").as_posix()}")\n'
        + "".join(f'message(STATUS "{key}=${{{key}}}")\n' for key in keys),
        encoding="utf-8",
    )
    projection = _cmake(source, "-P", str(probe))
    for key, value in {"CPACK_GENERATOR": generators, **metadata}.items():
        assert f"-- {key}={value}\n" in projection
    ninja = shutil.which("ninja")
    assert ninja is not None
    for name, generator in formats.items():
        result = run_command([ninja, "-C", str(build), "-t", "commands", name], cwd=source)
        assert result.returncode == 0, result.stdout + result.stderr
        commands = result.stdout.splitlines()
        preparation = next(
            index for index, line in enumerate(commands) if "dev.packaging.native.distribution_prepare" in line
        )
        packaging = next(index for index, line in enumerate(commands) if "CPackConfig.cmake" in line)
        assert preparation < packaging
        assert f" -G {generator}" in commands[packaging]
        assert " -C Release" in commands[packaging]
        assert len([line for line in commands if "CPackConfig.cmake" in line]) == 1
    help_text = _cmake(source, "--build", str(build), "--target", "help")
    for other in {"msi", "deb", "rpm", "dmg"} - formats.keys():
        assert f"{other}: phony" not in help_text


@pytest.mark.parametrize("manager", [False, True])
def test_distribution_cmake_zip_noop_refresh_and_clean_rebuild(tmp_path: Path, manager: bool) -> None:
    payload, source, build = _configure_distribution(tmp_path, "windows-x86-64", manager=manager)
    _cmake(source, "--build", str(build), "--target", "zip")
    if manager:
        assert "Desktop.wxs" in (build / "CPackConfig.cmake").read_text(encoding="utf-8")
        assert (build / "installation/metadata/Desktop.wxs").is_file()
    package = f"versions/{identity('windows-x86-64').version}" if manager else "app"
    archive = next((build / "packages").glob("*.zip"))
    original_time = archive.stat().st_mtime_ns
    _cmake(source, "--build", str(build), "--target", "zip")
    assert archive.stat().st_mtime_ns == original_time
    _change_payload(payload)
    _cmake(source, "--build", str(build), "--target", "zip")
    with zipfile.ZipFile(archive) as zipped:
        binary = next(name for name in zipped.namelist() if name.endswith(f"/{package}/cadrumo"))
        assert zipped.read(binary) == b"changed binary"
    _cmake(source, "--build", str(build), "--target", "clean-installation_prepare")
    assert not (build / "installation/stage").exists()
    assert list((build / "installation/receipts").glob("*.json"))
    _cmake(source, "--build", str(build), "--target", "zip")
    assert (build / "installation/stage" / package / "cadrumo").exists()

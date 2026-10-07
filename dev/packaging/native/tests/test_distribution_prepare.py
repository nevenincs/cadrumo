"""Install-based ZIP stages refresh incrementally and retain prior uninstall receipts."""

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


def test_distribution_cmake_zip_noop_refresh_and_clean_rebuild(tmp_path: Path) -> None:
    cmake = shutil.which("cmake")
    assert cmake is not None
    payload, identity_file = payload_fixture(tmp_path, "windows-x86-64")
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
    bootstrap = cmake_projection(identity("windows-x86-64"))
    bootstrap += f'set(CADRUMO_SOURCE_ROOT "{REPO_ROOT.as_posix()}")\n'
    bootstrap += f'set(CADRUMO_DEV_PYTHON "{Path(sys.executable).as_posix()}")\n'
    bootstrap += "set(CADRUMO_TARGET windows-x86-64)\nadd_custom_target(setup-native-builder)\n"
    bootstrap += f'include("{(REPO_ROOT / "native/cmake/Cleanup.cmake").as_posix()}")\n'
    bootstrap += 'cmake_language(DEFER DIRECTORY "${CMAKE_SOURCE_DIR}" CALL cadrumo_finalize_clean_targets)\n'
    for key, relative in paths.items():
        bootstrap += f'set(CADRUMO_PATH_{key.upper()} "${{CMAKE_BINARY_DIR}}/{relative}")\n'
    (source / "FixtureIdentity.cmake").write_text(bootstrap, encoding="utf-8")

    def command(*arguments: str) -> None:
        result = run_command([cmake, *arguments], cwd=source)
        assert result.returncode == 0, result.stdout + result.stderr

    command(
        "-G", "Ninja", "-S", str(source), "-B", str(build), "-DCMAKE_BUILD_TYPE=Release", f"-DCADRUMO_PAYLOAD={payload}"
    )
    command("--build", str(build), "--target", "zip")
    archive = next((build / "packages").glob("*.zip"))
    original_time = archive.stat().st_mtime_ns
    command("--build", str(build), "--target", "zip")
    assert archive.stat().st_mtime_ns == original_time
    _change_payload(payload)
    command("--build", str(build), "--target", "zip")
    with zipfile.ZipFile(archive) as zipped:
        binary = next(name for name in zipped.namelist() if name.endswith("/app/cadrumo"))
        assert zipped.read(binary) == b"changed binary"
    command("--build", str(build), "--target", "clean-installation_prepare")
    assert not (build / "installation/stage").exists()
    assert list((build / "installation/receipts").glob("*.json"))
    command("--build", str(build), "--target", "zip")
    assert (build / "installation/stage/app/cadrumo").exists()

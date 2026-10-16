"""The source graph builds its payload before configuring the native package owner."""

from __future__ import annotations

import json
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ...command_execution import run_command
from ..hashing import digest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_health_failure_facts_preserve_native_io_codes_without_private_fields(tmp_path: Path) -> None:
    from ..package_launch_smoke import _health_facts

    events = [
        {
            "stage": "manager",
            "failure": {
                "code": "cleanup_failed",
                "operation": "manager",
                "ioKind": "PermissionDenied",
                "osCode": 5,
                "message": "private-payload",
                "path": "private-payload",
            },
        },
        {"stage": ["private-payload"], "failure": {"code": "private-payload", "operation": "private-payload"}},
        {
            "kind": "helper_timing",
            "helperTiming": {"helperKind": "read", "outcome": "completed", "totalMs": 12, "secret": "private-payload"},
        },
    ]
    (tmp_path / "cadrumo-native.jsonl").write_text("\n".join(json.dumps(event) for event in events), encoding="utf-8")
    facts = _health_facts(tmp_path)
    assert facts == {
        "schema": 1,
        "failures": [
            {
                "stage": "manager",
                "code": "cleanup_failed",
                "operation": "manager",
                "ioKind": "PermissionDenied",
                "osCode": 5,
            },
            {"stage": None, "code": "unexpected", "operation": None, "ioKind": None, "osCode": None},
        ],
        "helpers": [{"helperKind": "read", "outcome": "completed", "totalMs": 12}],
    }
    assert "private-payload" not in json.dumps(facts)


def test_health_retains_primary_and_evidence_before_failed_process_settlement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tempfile import TemporaryDirectory

    from .. import package_launch_smoke as health

    executable = tmp_path / "cadrumo.exe"
    executable.write_bytes(b"failure-policy fixture")
    retained = []
    primary = AssertionError("primary startup failure")

    def temporary(**kwargs: object) -> TemporaryDirectory[str]:
        assert kwargs["dir"] == tmp_path
        directory = TemporaryDirectory(prefix="health-test-", dir=tmp_path, delete=False)
        retained.append(Path(directory.name))
        return directory

    class Scope:
        def launch(self, **kwargs: object) -> object:
            return object()

        def terminate(self, *, timeout: int) -> None:
            assert timeout == 10
            assert (retained[0] / "health-failure.json").is_file()
            raise OSError("private cleanup detail")

    def recover(*args: object) -> None:
        raise primary

    monkeypatch.setattr(health, "TemporaryDirectory", temporary)
    monkeypatch.setattr(health, "WindowsProcessScope", Scope)
    monkeypatch.setattr(health, "_recover_runtime", recover)
    with pytest.raises(AssertionError) as caught:
        health.verify_health(executable, "CADRUMO_LOCAL_STORAGE_ROOT", scratch_root=tmp_path)
    assert caught.value is primary
    assert json.loads((retained[0] / "health-failure.json").read_text(encoding="utf-8")) == {
        "schema": 1,
        "failures": [],
        "helpers": [],
    }
    assert any("OSError" in note for note in primary.__notes__)
    assert all("private cleanup detail" not in note for note in primary.__notes__)


@pytest.mark.parametrize(
    "defect", ["missing-kit", "missing-runner", "changed-product", "stale-package", "missing-scope"]
)
def test_desktop_delivery_refuses_incomplete_or_stale_installation_kit(tmp_path: Path, defect: str) -> None:
    package = tmp_path / "app"
    (package / "data").mkdir(parents=True)
    manifest = package / "data/package-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "layout": {
                    "installation": {
                        "bootstrap": {
                            "directory": "services",
                            "manifest": "kit.json",
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    services = tmp_path / "services"
    services.mkdir()
    names = ["runner.exe", "application.msi"]
    artifacts = {}
    for name in names:
        path = services / name
        path.write_bytes(name.encode())
        artifacts[name] = {"path": name, "sha256": digest(path)}
    kit = {
        "schema": 2,
        "runner": artifacts.pop("runner.exe"),
        "maintenance": {"desktop_present": True, "manifest_sha256": digest(manifest)},
        "artifacts": {Path(name).stem: artifact for name, artifact in artifacts.items()},
    }
    descriptor = services / "kit.json"
    descriptor.write_text(json.dumps(kit), encoding="utf-8")
    command = [sys.executable, "-B", "-m", "dev.packaging.native.package_launch_smoke", "--kit", str(package)]
    valid = run_command(command, cwd=REPO_ROOT)
    assert valid.returncode == 0, valid.stdout + valid.stderr
    if defect == "missing-kit":
        descriptor.unlink()
    elif defect == "missing-runner":
        (services / "runner.exe").unlink()
    elif defect == "changed-product":
        (services / "application.msi").write_bytes(b"changed")
    elif defect == "stale-package":
        manifest.write_text(manifest.read_text() + "\n", encoding="utf-8")
    else:
        del kit["artifacts"]["application"]
        descriptor.write_text(json.dumps(kit), encoding="utf-8")
    invalid = run_command(command, cwd=REPO_ROOT)
    assert invalid.returncode != 0, f"Incomplete installation kit was accepted: {defect}"


def test_native_installer_preserves_configuration_and_clears_stale_desktop(tmp_path: Path) -> None:
    cmake = shutil.which("cmake")
    assert cmake is not None
    source = tmp_path / "source with spaces"
    distribution = source / "native/cmake/distribution"
    distribution.mkdir(parents=True)
    shutil.copyfile(REPO_ROOT / "native/package-layout.json", source / "native/package-layout.json")
    (source / "native/CMakeLists.txt").write_text(
        'set(CADRUMO_MSI_ADAPTER "${PROJECT_BINARY_DIR}/adapter.dll")\n'
        'set(CADRUMO_MSI_RUNNER "${PROJECT_BINARY_DIR}/maintenance.exe")\n'
        'add_custom_target(rust_installer COMMAND "${CMAKE_COMMAND}" -E touch '
        '"${CADRUMO_MSI_ADAPTER}" "${CADRUMO_MSI_RUNNER}")\n',
        encoding="utf-8",
    )
    (distribution / "CMakePresets.json").write_text(
        json.dumps(
            {
                "version": 6,
                "configurePresets": [
                    {
                        "name": "native-fixture",
                        "generator": "Ninja Multi-Config",
                        "binaryDir": "${sourceDir}/../../../build/${presetName}",
                        "cacheVariables": {"CADRUMO_TARGET": "fixture"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (distribution / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 4.4)\nproject(Distribution LANGUAGES NONE)\n"
        'if(NOT EXISTS "${CADRUMO_PAYLOAD}/ready")\nmessage(FATAL_ERROR "payload not built")\nendif()\n'
        'if(WIN32 AND (NOT EXISTS "${CADRUMO_MSI_ADAPTER}" OR NOT EXISTS "${CADRUMO_MSI_RUNNER}"))\n'
        'message(FATAL_ERROR "installer not built")\nendif()\n'
        'file(WRITE "${CMAKE_BINARY_DIR}/consumed.txt" '
        '"${CADRUMO_PAYLOAD}\n${CADRUMO_DESKTOP_EXECUTABLE}\n${CADRUMO_CHANNEL}\n")\n'
        'add_custom_target(native-package COMMAND "${CMAKE_COMMAND}" -E touch '
        '"${CMAKE_BINARY_DIR}/packaged-$<CONFIG>")\n',
        encoding="utf-8",
    )
    module = (REPO_ROOT / "native/cmake/InstallerFlow.cmake").as_posix()
    (source / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 4.4)\nproject(Source LANGUAGES NONE)\n"
        "set(CADRUMO_TARGET fixture)\nset(CADRUMO_CHANNEL preview)\n"
        'set(CADRUMO_PATH_STAGE "${PROJECT_BINARY_DIR}/stage")\n'
        "set(image_count 1)\n"
        'set(application_images "[{\\"desktop\\":${FIXTURE_DESKTOP},'
        '\\"package_path\\":\\"desktop executable\\"}]")\n'
        "function(cadrumo_register_clean)\n"
        'cmake_parse_arguments(CLEAN "" "TARGET" "PATHS" ${ARGN})\n'
        'file(GENERATE OUTPUT "${PROJECT_BINARY_DIR}/${CLEAN_TARGET}-clean-$<CONFIG>.txt" '
        'CONTENT "${CLEAN_PATHS}")\nendfunction()\n'
        "add_subdirectory(native)\n"
        "add_custom_target(bundle DEPENDS app-payload)\n"
        'add_custom_target(app-payload COMMAND "${CMAKE_COMMAND}" -E make_directory '
        '"${CADRUMO_PATH_STAGE}/$<CONFIG>/app" COMMAND "${CMAKE_COMMAND}" -E touch '
        '"${CADRUMO_PATH_STAGE}/$<CONFIG>/app/ready")\n'
        f'include("{module}")\n',
        encoding="utf-8",
    )
    binary = tmp_path / "source build"
    nested = source / "build/native-fixture"
    for declared, desktop in [("true", "desktop executable"), ("false", "")]:
        configured = run_command(
            [cmake, "-G", "Ninja Multi-Config", "-S", str(source), "-B", str(binary), f"-DFIXTURE_DESKTOP={declared}"],
            cwd=source,
        )
        assert configured.returncode == 0, configured.stderr
        built = run_command(
            [
                cmake,
                "--build",
                str(binary),
                "--config",
                "Release",
                "--target",
                "bundle" if desktop and sys.platform == "win32" else "native-installer",
            ],
            cwd=source,
        )
        assert built.returncode == 0, built.stdout + built.stderr
        assert (nested / "consumed.txt").read_text().splitlines() == [
            (binary / "stage/Release/app").as_posix(),
            desktop,
            "preview",
        ]
        assert (nested / "packaged-Release").is_file()
        clean_paths = (binary / "native-installer-clean-Release.txt").read_text()
        assert clean_paths == (
            (binary / "stage/Release/services").as_posix() if desktop and sys.platform == "win32" else ""
        )

    # Different source binary directories share the enrolled distribution owner.
    # Its configured payload must not change halfway through the first package.
    (distribution / "check.cmake").write_text(
        'file(WRITE "${BINARY}/entered" "ready")\n'
        'execute_process(COMMAND "${CMAKE_COMMAND}" -E sleep 1)\n'
        'file(STRINGS "${BINARY}/consumed.txt" observed LIMIT_COUNT 1)\n'
        'if(NOT observed STREQUAL EXPECTED)\nmessage(FATAL_ERROR "payload changed during package")\nendif()\n',
        encoding="utf-8",
    )
    with (distribution / "CMakeLists.txt").open("a", encoding="utf-8") as output:
        output.write(
            'add_custom_command(TARGET native-package POST_BUILD COMMAND "${CMAKE_COMMAND}" '
            '"-DBINARY=${CMAKE_BINARY_DIR}" "-DEXPECTED=${CADRUMO_PAYLOAD}" '
            '-P "${CMAKE_SOURCE_DIR}/check.cmake" VERBATIM)\n'
        )
    other_binary = tmp_path / "other source build"
    configured = run_command(
        [cmake, "-G", "Ninja Multi-Config", "-S", str(source), "-B", str(other_binary), "-DFIXTURE_DESKTOP=false"],
        cwd=source,
    )
    assert configured.returncode == 0, configured.stderr

    def build(directory: Path) -> None:
        result = run_command(
            [cmake, "--build", str(directory), "--config", "Release", "--target", "native-installer"], cwd=source
        )
        assert result.returncode == 0, result.stdout + result.stderr

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(build, binary)
        deadline = time.monotonic() + 30
        while not (nested / "entered").exists():
            if first.done():
                first.result()
                pytest.fail("native package did not start")
            assert time.monotonic() < deadline, "native package did not start within its fixture bound"
            time.sleep(0.01)
        second = executor.submit(build, other_binary)
        first.result(timeout=30)
        second.result(timeout=30)
    assert (nested / "consumed.txt").read_text().splitlines()[0] == (other_binary / "stage/Release/app").as_posix()

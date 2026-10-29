"""Verify the ZIP artifact, including relocation, product imports and binary overrides."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from dev._paths import REPO_ROOT

from ..command_execution import run_command
from .archive import extract_bundle
from .build_directory import require_enrolled_build
from .build_log import BuildLog, display_path
from .build_paths import build_paths
from .build_timing import BuildTimings, measure_build
from .cmake_build import reset
from .cpp_abi_inputs import verify_linux_cpp_abi_inputs
from .hashing import digest
from .layout import ApplicationImage, backend, desktop_image, load_layout
from .package_launch_smoke import verify_installation_kit
from .release import verify_release
from .verify import verify


def check(build: Path, configuration: str, application_probe: list[str] | None = None) -> None:
    """Extract a fresh artifact and test the shipped interpreter, not the development venv."""
    build = build.resolve(strict=True)
    with measure_build(build, "artifact-verification") as timings:
        _check(build, configuration, application_probe, timings)


def _check(build: Path, configuration: str, application_probe: list[str] | None, timings: BuildTimings) -> None:
    """Run artifact admission and acceptance against one owned extraction."""
    artifacts = json.loads((build / f"artifacts-{configuration}.json").read_text(encoding="utf-8"))
    archive_path = Path(artifacts["archive"])
    archive_hash = _admit_archive(archive_path, artifacts["archive_sha256"], timings)
    with timings.phase("verification-reset"):
        destination = reset(build, str((build_paths(build)["verification"] / configuration).relative_to(build)))
    extracted = destination / "ZIP espacio á 漢字"
    extracted.mkdir(parents=True)
    with timings.phase("archive-extraction"):
        extract_bundle(archive_path, extracted)
    roots = list(extracted.iterdir())
    if len(roots) != 1 or not roots[0].is_dir():
        raise ValueError("ZIP must contain one named application root")
    package = roots[0]
    external = destination / "external-bin"
    external.mkdir()
    target = artifacts["target"]
    contract = load_layout(target)
    if contract["backend"] == "windows" and (package / "app").is_dir():
        package /= "app"
    environment = dict(os.environ)
    environment.update(CADRUMO_LOCAL_STORAGE_ROOT=str(destination / "state"), CADRUMO_EXTERNAL_BIN_DIRS=str(external))
    manifest_path = package / contract["files"]["package_manifest"]
    if digest(manifest_path) != artifacts["manifest_sha256"]:
        raise AssertionError("ZIP manifest differs from the packaged artifact locator")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    desktop = desktop_image(contract)
    _require_package_identity(package, contract["backend"], desktop, manifest, target)
    expectation = dict(artifacts["release"], manifest_sha256=artifacts["manifest_sha256"])
    verify_release(manifest, expectation)
    linux_cpp_abi = None
    if contract["backend"] == "linux":
        configured = json.loads((build_paths(build)["generated"] / "build-toolchain.json").read_text(encoding="utf-8"))
        linux_cpp_abi = verify_linux_cpp_abi_inputs(package, manifest, configured)
    probe = backend(contract).external_probe(external)
    expectation_path = destination / "release-expectation.json"
    expectation_path.write_text(json.dumps(expectation, indent=2) + "\n", encoding="utf-8")
    expectation_hash = digest(expectation_path)
    development = package / manifest["layout"]["files"]["development_executable"]
    executables = _interpreter_images(development, artifacts["development_binary"], package, manifest)
    _run_interpreter_probes(
        executables, development, package, manifest_path, probe, destination, environment, timings, manifest
    )
    with timings.phase("platform-acceptance"):
        verify(package, target=target, product=True, build_root=destination, already_relocated=True)
    _run_application_probe(application_probe, package, expectation_path, timings)
    _require_verification_inputs_unchanged(
        archive_path, archive_hash, manifest_path, artifacts["manifest_sha256"], expectation_path, expectation_hash
    )
    (destination / "result.json").write_text(
        json.dumps(
            {
                "archive": str(archive_path),
                "archive_sha256": archive_hash,
                "manifest_sha256": digest(manifest_path),
                "release_expectation_sha256": expectation_hash,
                "build": manifest["build"],
                "interpreters": [p.name for p in executables],
                "package_root": str(package.resolve()),
                "application_probe": "passed"
                if (application_probe is not None and application_probe)
                else "not_requested",
                "linux_cpp_abi": linux_cpp_abi,
                "passed": True,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    BuildLog("artifact-verification").status(f"verified {display_path(artifacts['archive'])}")


def _interpreter_images(
    development: Path, development_binary: object, package: Path, manifest: Mapping[str, object]
) -> list[Path]:
    if development.exists() != bool(development_binary):
        raise AssertionError("Development binary inclusion does not match configuration")
    layout = cast("Mapping[str, object]", manifest["layout"])
    paths = cast("Mapping[str, str]", layout["paths"])
    executables = [package / paths["executable"]]
    if development.exists():
        executables.append(development)
    return executables


def _require_package_identity(
    package: Path,
    backend_name: str,
    desktop: ApplicationImage | None,
    manifest: Mapping[str, object],
    target: str,
) -> None:
    if (
        backend_name == "windows"
        and desktop is not None
        and desktop.package_path in cast("Mapping[str, object]", manifest["files"])
    ):
        verify_installation_kit(package)
    if cast("Mapping[str, object]", manifest["build"])["target"] != target:
        raise AssertionError("ZIP target differs from the packaged artifact locator")


def _admit_archive(archive_path: Path, expected_sha256: str, timings: BuildTimings) -> str:
    with timings.phase("archive-admission"):
        archive_hash = digest(archive_path)
        if archive_hash != expected_sha256:
            raise AssertionError("ZIP differs from the packaged artifact locator")
    return archive_hash


def _require_verification_inputs_unchanged(
    archive_path: Path,
    archive_hash: str,
    manifest_path: Path,
    manifest_sha256: str,
    expectation_path: Path,
    expectation_hash: str,
) -> None:
    if digest(archive_path) != archive_hash:
        raise AssertionError("ZIP changed during verification")
    if digest(manifest_path) != manifest_sha256:
        raise AssertionError("ZIP manifest changed during verification")
    if digest(expectation_path) != expectation_hash:
        raise AssertionError("Release expectation changed during verification")


def _run_application_probe(
    application_probe: list[str] | None, package: Path, expectation_path: Path, timings: BuildTimings
) -> None:
    if application_probe is not None and application_probe:
        probe_environment = dict(os.environ)
        probe_environment["CADRUMO_TEST_PACKAGE_ROOT"] = str(package.resolve())
        probe_environment["CADRUMO_TEST_RELEASE_EXPECTATION"] = str(expectation_path.resolve())
        with timings.phase("application-release-probe"):
            result = run_command(application_probe, cwd=REPO_ROOT, environment=probe_environment, timeout_seconds=900)
            if result.returncode:
                raise AssertionError("Rust package compatibility failed:\n" + result.stdout + result.stderr)
        BuildLog("artifact-verification").verbose(result.stdout.strip())


def _run_interpreter_probes(
    executables: list[Path],
    development: Path,
    package: Path,
    manifest_path: Path,
    probe: list[str],
    destination: Path,
    environment: dict[str, str],
    timings: BuildTimings,
    manifest: Mapping[str, object],
) -> None:
    for executable in executables:
        for arguments in (
            ["--version"],
            ["--check-package"],
            [
                "-c",
                f"import sys; sys.exit(bool(sys.cadrumo_build['development']) != {executable == development!r})",
            ],
            [str(REPO_ROOT / "native/tests/package_smoke.py"), str(package), str(manifest_path)],
            [
                "-c",
                f"import subprocess; subprocess.run({probe!r},check=True,capture_output=True)",
            ],
        ):
            _run_interpreter_probe(executable, arguments, destination, environment, timings, manifest)


def _run_interpreter_probe(
    executable: Path,
    arguments: list[str],
    destination: Path,
    environment: dict[str, str],
    timings: BuildTimings,
    manifest: Mapping[str, object],
) -> None:
    with timings.phase("extracted-interpreter-probe"):
        result = run_command(
            [str(executable), *arguments], cwd=destination, environment=environment, timeout_seconds=120
        )
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
    if arguments == ["--version"]:
        # The banner reports the interpreter hosts' own build, not the package's.
        hosts = next(
            item for item in cast("list[dict[str, object]]", manifest["components"]) if item["role"] == "interpreter"
        )
        for key in ("version", "display_version", "build_sequence", "build_id", "build_date"):
            if str(hosts[key]) not in result.stdout:
                raise AssertionError(f"Missing interpreter banner metadata: {key}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=require_enrolled_build, required=True)
    parser.add_argument("--config", choices=("Debug", "Release"), required=True)
    parser.add_argument("--application-probe-command", type=Path, help="CMake-generated JSON argv for the Rust probe")
    args = parser.parse_args()
    command = None
    if args.application_probe_command is not None:
        command = json.loads(args.application_probe_command.read_text(encoding="utf-8"))
        if not isinstance(command, list) or not command or any(not isinstance(arg, str) or not arg for arg in command):
            parser.error("application probe command must be a non-empty JSON array of non-empty strings")
    check(args.build, args.config, command)

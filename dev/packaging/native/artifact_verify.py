"""Verify the ZIP artifact, including relocation, product imports and binary overrides."""

from __future__ import annotations

import argparse
import json
import os
import zipfile
from pathlib import Path

from dev._paths import REPO_ROOT

from ..command_execution import run_command
from .build_paths import build_paths
from .cmake_build import reset
from .hashing import digest
from .layout import backend, load_layout
from .verify import verify


def check(build: Path, configuration: str, application_probe: list[str] | None = None) -> None:
    """Extract a fresh artifact and test the shipped interpreter, not the development venv."""
    build = build.resolve(strict=True)
    artifacts = json.loads((build / f"artifacts-{configuration}.json").read_text(encoding="utf-8"))
    archive_path = Path(artifacts["archive"])
    archive_hash = digest(archive_path)
    if archive_hash != artifacts["archive_sha256"]:
        raise AssertionError("ZIP differs from the packaged artifact locator")
    destination = reset(build, str((build_paths(build)["verification"] / configuration).relative_to(build)))
    extracted = destination / "ZIP espacio á 漢字"
    extracted.mkdir(parents=True)
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.namelist():
            if not (extracted / member).resolve().is_relative_to(extracted):
                raise ValueError("Archive path escapes extraction root")
        archive.extractall(extracted)
    roots = list(extracted.iterdir())
    if len(roots) != 1 or not roots[0].is_dir():
        raise ValueError("ZIP must contain one named application root")
    package = roots[0]
    external = destination / "external-bin"
    external.mkdir()
    contract = load_layout()
    probe = backend(contract).external_probe(external)
    environment = dict(os.environ)
    environment.update(CADRUMO_LOCAL_STORAGE_ROOT=str(destination / "state"), CADRUMO_EXTERNAL_BIN_DIRS=str(external))
    manifest_path = package / contract["files"]["package_manifest"]
    if digest(manifest_path) != artifacts["manifest_sha256"]:
        raise AssertionError("ZIP manifest differs from the packaged artifact locator")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    development = package / manifest["layout"]["files"]["development_executable"]
    if development.exists() != bool(artifacts["development_binary"]):
        raise AssertionError("Development binary inclusion does not match configuration")
    executables = [package / manifest["layout"]["paths"]["executable"]]
    if development.exists():
        executables.append(development)
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
            result = run_command(
                [str(executable), *arguments], cwd=destination, environment=environment, timeout_seconds=120
            )
            if result.returncode:
                raise AssertionError(result.stdout + result.stderr)
            if arguments == ["--version"]:
                for key in ("version", "build_number", "build_date"):
                    if str(manifest["build"][key]) not in result.stdout:
                        raise AssertionError(f"Missing interpreter banner metadata: {key}")
    verify(package, destination=Path("acceptance"), product=True, build_root=destination)
    if application_probe:
        probe_environment = dict(os.environ)
        probe_environment["CADRUMO_TEST_PACKAGE_ROOT"] = str(package.resolve())
        result = run_command(application_probe, cwd=REPO_ROOT, environment=probe_environment, timeout_seconds=900)
        if result.returncode:
            raise AssertionError("Rust package compatibility failed:\n" + result.stdout + result.stderr)
        print(result.stdout)
    if digest(archive_path) != archive_hash:
        raise AssertionError("ZIP changed during verification")
    if digest(manifest_path) != artifacts["manifest_sha256"]:
        raise AssertionError("ZIP manifest changed during verification")
    (destination / "result.json").write_text(
        json.dumps(
            {
                "archive": str(archive_path),
                "archive_sha256": archive_hash,
                "manifest_sha256": digest(manifest_path),
                "build": manifest["build"],
                "interpreters": [p.name for p in executables],
                "package_root": str(package.resolve()),
                "application_probe": "passed" if application_probe else "not_requested",
                "passed": True,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Verified ZIP: {artifacts['archive']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--config", choices=("Debug", "Release"), required=True)
    parser.add_argument("--application-probe-command", type=Path, help="CMake-generated JSON argv for the Rust probe")
    args = parser.parse_args()
    command = None
    if args.application_probe_command is not None:
        command = json.loads(args.application_probe_command.read_text(encoding="utf-8"))
        if not isinstance(command, list) or not command or any(not isinstance(arg, str) or not arg for arg in command):
            parser.error("application probe command must be a non-empty JSON array of non-empty strings")
    check(args.build, args.config, command)

"""Minimal real-byte cohort fixture for plugin materialisation tests."""

from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TestPluginCohort:
    """The complete protocol the production plugin materialiser requires."""

    directory: Path
    source_commit: str
    version: str
    harness_version: str
    root_wheel: Path
    harness_wheel: Path
    runtime_wheelhouse: Path
    runtime_wheelhouse_manifest: dict[str, object]
    manuals_wheel: Path
    official_wheel: Path
    sha256: dict[str, str]


def make_test_plugin_cohort(
    directory: Path,
    *,
    version: str = "1.2.3",
    harness_version: str = "0.1.0",
) -> TestPluginCohort:
    """Write four distinct wheel-shaped byte fixtures and return their authority."""
    directory.mkdir(parents=True)
    artifacts = {
        "cadrumo": directory / f"cadrumo-{version}-py3-none-any.whl",
        "cadrumo-harness": directory / f"cadrumo_harness-{harness_version}-py3-none-any.whl",
        "cadrumo-data-manuals": directory / f"cadrumo_data_manuals-{version}-py3-none-any.whl",
        "cadrumo-data-official": directory / f"cadrumo_data_official-{version}-py3-none-any.whl",
    }
    for name, path in artifacts.items():
        path.write_bytes(f"sealed-test-wheel:{name}\n".encode())
    dependency_name = "mcp-2.0.0-py3-none-any.whl"
    dependency_bytes = b"sealed-test-wheel:mcp\n"
    dependency_sha256 = hashlib.sha256(dependency_bytes).hexdigest()
    platform_floors = {
        "linux-aarch64": "glibc-2.28",
        "linux-x86-64": "glibc-2.28",
        "macos-arm64": "macos-14.0",
        "windows-x86-64": "windows-10",
    }
    platform_rows = {
        target: {"mcp": dependency_name}
        for target in ("linux-aarch64", "linux-x86-64", "macos-arm64", "windows-x86-64")
    }
    wheel_record = {
        dependency_name: {
            "distribution": "mcp",
            "sha256": dependency_sha256,
            "size": len(dependency_bytes),
            "version": "2.0.0",
        }
    }
    wheelhouse_manifest: dict[str, object] = {
        "lock_sha256": "b" * 64,
        "platform_floors": platform_floors,
        "runtimes": {
            runtime: {
                "platforms": platform_rows,
                "python": runtime,
                "status": "ready",
                "wheels": wheel_record,
            }
            for runtime in ("3.13", "3.14")
        },
        "schema": "cadrumo.runtime-wheelhouse.v3",
    }
    runtime_wheelhouse = directory / "cadrumo-runtime-wheelhouse.zip"
    with zipfile.ZipFile(runtime_wheelhouse, "w") as archive:
        archive.writestr(
            "runtime-wheelhouse.json",
            json.dumps(wheelhouse_manifest, sort_keys=True),
        )
        for runtime in ("3.13", "3.14"):
            archive.writestr(f"wheels/{runtime}/{dependency_name}", dependency_bytes)
    sha256 = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in artifacts.items()}
    sha256["runtime-wheelhouse"] = hashlib.sha256(runtime_wheelhouse.read_bytes()).hexdigest()
    return TestPluginCohort(
        directory=directory.resolve(strict=True),
        source_commit="a" * 40,
        version=version,
        harness_version=harness_version,
        root_wheel=artifacts["cadrumo"],
        harness_wheel=artifacts["cadrumo-harness"],
        runtime_wheelhouse=runtime_wheelhouse,
        runtime_wheelhouse_manifest=wheelhouse_manifest,
        manuals_wheel=artifacts["cadrumo-data-manuals"],
        official_wheel=artifacts["cadrumo-data-official"],
        sha256=sha256,
    )

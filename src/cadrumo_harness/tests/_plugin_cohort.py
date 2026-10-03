"""Minimal real-byte cohort fixture for plugin materialisation tests."""

from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PluginTestCohort:
    """Synthetic artifact fields consumed by the plugin workspace tests."""

    directory: Path
    manifest: Path
    source_digest: str
    version: str
    root_wheel: Path
    root_sdist: Path
    source_archive: Path
    runtime_wheelhouse: Path
    runtime_wheelhouse_manifest: dict[str, Any]
    manuals_wheel: Path
    manuals_sdist: Path
    official_wheel: Path
    official_sdist: Path
    sha256: dict[str, str]
    command_spec_attestation: dict[str, object] | None = None

    @property
    def product_wheels(self) -> tuple[Path, Path, Path]:
        """Return the synthetic installable product wheels in stable order."""
        return self.root_wheel, self.manuals_wheel, self.official_wheel


def make_test_plugin_cohort(
    directory: Path,
    *,
    version: str = "1.2.3",
) -> PluginTestCohort:
    """Return a local structural fixture over synthetic artifact bytes."""
    directory.mkdir(parents=True)
    artifacts = {
        "cadrumo": directory / f"cadrumo-{version}-py3-none-any.whl",
        "cadrumo-sdist": directory / f"cadrumo-{version}.tar.gz",
        "source-archive": directory / f"cadrumo-source-{'a' * 64}.zip",
        "cadrumo-data-manuals": directory / f"cadrumo_data_manuals-{version}-py3-none-any.whl",
        "cadrumo-data-manuals-sdist": directory / f"cadrumo_data_manuals-{version}.tar.gz",
        "cadrumo-data-official": directory / f"cadrumo_data_official-{version}-py3-none-any.whl",
        "cadrumo-data-official-sdist": directory / f"cadrumo_data_official-{version}.tar.gz",
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
    manifest = directory / "python-cohort.json"
    manifest.write_text(
        json.dumps(
            {
                "artifacts": {name: path.name for name, path in artifacts.items()}
                | {"runtime-wheelhouse": runtime_wheelhouse.name},
                "sha256": sha256,
                "source_digest": "a" * 64,
                "version": version,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return PluginTestCohort(
        directory=directory.resolve(strict=True),
        manifest=manifest,
        source_digest="a" * 64,
        version=version,
        root_wheel=artifacts["cadrumo"],
        root_sdist=artifacts["cadrumo-sdist"],
        source_archive=artifacts["source-archive"],
        runtime_wheelhouse=runtime_wheelhouse,
        runtime_wheelhouse_manifest=wheelhouse_manifest,
        manuals_wheel=artifacts["cadrumo-data-manuals"],
        manuals_sdist=artifacts["cadrumo-data-manuals-sdist"],
        official_wheel=artifacts["cadrumo-data-official"],
        official_sdist=artifacts["cadrumo-data-official-sdist"],
        sha256=sha256,
    )

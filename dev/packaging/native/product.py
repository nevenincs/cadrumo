"""Build the existing Python product wheels in a stable native-build snapshot."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from cadrumo.core.product_identity import PRODUCT_IDENTITY
from cadrumo.core.toml import parse_toml
from dev._paths import AUTHORITY_ROOT_ENV, REPO_ROOT
from dev.source_tree import repository_files, snapshot

from ..authority_staging import stage_published_authority
from ..command_execution import run_command
from ..google_oauth import GOOGLE_OAUTH_ENV, build_client_json
from ..wheel_metadata import read_wheel_metadata
from .build_toolchain import selected_uv
from .hashing import digest
from .target import uv_environment, uv_platform


def build_product(
    output: Path,
    python: Path,
    dependencies: Path,
    target: str,
    *,
    build_toolchain: Mapping[str, Any] | None = None,
    uv_executable: Path | None = None,
) -> None:
    """Compose existing snapshot, build hooks and wheel metadata owners."""
    client = build_client_json(REPO_ROOT)
    output = output.resolve()
    if output.exists():
        raise FileExistsError("Product build requires a fresh output directory")
    python = python.resolve(strict=True)
    pin = (REPO_ROOT / "dev/packaging/release-python-version").read_text(encoding="utf-8").strip()
    observed = run_command(
        [str(python), "-I", "-c", "import platform; print(platform.python_version())"], cwd=REPO_ROOT
    )
    if observed.returncode or observed.stdout.strip() != pin:
        raise ValueError(f"Product construction requires host CPython {pin}: {observed.stdout.strip()}")
    dependencies = dependencies.resolve(strict=True)
    uv = selected_uv(build_toolchain, executable=uv_executable)
    source = output / "source"
    files = tuple(
        name
        for name in repository_files(REPO_ROOT)
        if not any(
            part.startswith(
                (".aeat-generated-export-transaction-", ".generated-export-backup-", ".generated-export-stage-")
            )
            for part in Path(name).parts
        )
    )
    snapshot(REPO_ROOT, files, source)
    stage_published_authority(REPO_ROOT, source)
    environment = dict(os.environ)
    environment[GOOGLE_OAUTH_ENV] = client.get_secret_value()
    environment[AUTHORITY_ROOT_ENV] = str(source / ".authority")
    project = parse_toml((source / "pyproject.toml").read_text(encoding="utf-8"))
    wheels = output / "wheels"
    projects = [source]
    projects.extend(
        source / project["tool"]["uv"]["sources"][name]["path"] for name in PRODUCT_IDENTITY.companion_distributions
    )
    for directory in projects:
        result = run_command(
            [uv, "build", "--wheel", "--python", str(python), "--project", str(directory), "--out-dir", str(wheels)],
            cwd=REPO_ROOT,
            environment=environment,
        )
        if result.returncode:
            raise RuntimeError(result.stderr)
    artifacts = sorted(wheels.glob("*.whl"))
    metadata = [read_wheel_metadata(wheel) for wheel in artifacts]
    expected = set(PRODUCT_IDENTITY.cohort_distributions)
    if {item["Name"] for item in metadata} != expected or len(artifacts) != len(expected):
        raise ValueError("Incomplete product wheel cohort")
    if {item["Version"] for item in metadata} != {project["project"]["version"]}:
        raise ValueError("Product cohort versions differ")
    root_metadata = next(item for item in metadata if item["Name"] == PRODUCT_IDENTITY.distribution)
    companion_pins = {}
    for value in root_metadata.get_all("Requires-Dist", []):
        requirement = Requirement(value)
        name = canonicalize_name(requirement.name)
        if name in PRODUCT_IDENTITY.companion_distributions:
            if requirement.marker is not None or requirement.url is not None or name in companion_pins:
                raise ValueError(f"Companion requirement is not one unconditional exact pin: {value}")
            companion_pins[name] = str(requirement.specifier)
    if companion_pins != {
        name: f"=={project['project']['version']}" for name in PRODUCT_IDENTITY.companion_distributions
    }:
        raise ValueError("Product companion requirements must match the exact cohort version")
    result = run_command(
        [
            uv,
            "pip",
            "install",
            "--python",
            str(python),
            "--python-version",
            pin,
            "--python-platform",
            uv_platform(target),
            "--no-config",
            "--no-deps",
            "--link-mode",
            "copy",
            "--target",
            str(dependencies),
            *map(str, artifacts),
        ],
        cwd=REPO_ROOT,
        environment=uv_environment(target),
    )
    if result.returncode:
        raise RuntimeError(result.stderr)
    (output / "product-wheels.json").write_text(
        json.dumps({p.name: digest(p) for p in artifacts}, indent=2),
        encoding="utf-8",
    )
    print(f"Installed {len(artifacts)} exact-version product wheels into {dependencies}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--dependencies", type=Path, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--uv", type=Path, help="Explicit uv executable for a standalone invocation")
    parser.add_argument("--build-toolchain", type=Path, help="Explicit admitted builder toolchain JSON")
    args = parser.parse_args()
    configured = None
    if args.build_toolchain is not None:
        configured = json.loads(args.build_toolchain.read_text(encoding="utf-8"))
        if not isinstance(configured, dict):
            parser.error("build toolchain must be a JSON object")
    build_product(
        args.output, args.python, args.dependencies, args.target, build_toolchain=configured, uv_executable=args.uv
    )

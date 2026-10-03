"""Build the existing Python product wheels in a stable native-build snapshot."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

from cadrumo.core.product_identity import PRODUCT_IDENTITY
from cadrumo.core.toml import parse_toml
from dev._paths import AUTHORITY_ROOT_ENV, REPO_ROOT
from dev.source_tree import repository_files, snapshot

from ..authority_staging import stage_published_authority
from ..command_execution import run_command
from ..wheel_metadata import read_wheel_metadata
from .assemble import digest


def build_product(output: Path, python: Path, dependencies: Path) -> None:
    """Compose existing snapshot, build hooks and wheel metadata owners."""
    output = output.resolve()
    if output.exists():
        raise FileExistsError("Product build requires a fresh output directory")
    python = python.resolve(strict=True)
    dependencies = dependencies.resolve(strict=True)
    uv = shutil.which("uv")
    if uv is None:
        raise FileNotFoundError("uv is required")
    source = output / "source"
    snapshot(REPO_ROOT, repository_files(REPO_ROOT), source)
    stage_published_authority(REPO_ROOT, source)
    environment = dict(os.environ)
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
    result = run_command(
        [
            uv,
            "pip",
            "install",
            "--python",
            str(python),
            "--no-deps",
            "--link-mode",
            "copy",
            "--target",
            str(dependencies),
            *map(str, artifacts),
        ],
        cwd=REPO_ROOT,
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
    args = parser.parse_args()
    build_product(args.output, args.python, args.dependencies)

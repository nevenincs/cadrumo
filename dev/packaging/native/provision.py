"""Acquire the pinned official CPython SDK and locked Windows base dependencies."""

from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from pathlib import Path

import httpx

from dev._paths import REPO_ROOT

from ..command_execution import run_command
from ..uv_constraints import export_runtime_constraints
from .assemble import digest


def provision(destination: Path) -> None:
    """Download one verified SDK and install the repository's base closure."""
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    pin = (REPO_ROOT / "dev/packaging/release-python-version").read_text().strip()
    tools = json.loads((REPO_ROOT / "native/toolchain.json").read_text(encoding="utf-8"))
    archive = destination / f"python.{pin}.nupkg"
    url = tools["cpython_source"].format(version=pin)
    if not url.startswith("https://api.nuget.org/"):
        raise ValueError("CPython SDK must come from the pinned HTTPS NuGet origin")
    if not archive.exists():
        with httpx.stream("GET", url, timeout=120) as response, archive.open("wb") as output:
            response.raise_for_status()
            for chunk in response.iter_bytes():
                output.write(chunk)
    if digest(archive) != tools["cpython_sha256"]:
        raise ValueError("CPython SDK SHA256 mismatch")
    sdk = destination / "cpython-nuget"
    if not sdk.exists():
        with zipfile.ZipFile(archive) as package:
            for member in package.namelist():
                if not (sdk / member).resolve().is_relative_to(sdk):
                    raise ValueError("SDK archive contains an escaping path")
            package.extractall(sdk)
    requirements = destination / "requirements.txt"
    requirements.write_text("\n".join(export_runtime_constraints(repo_root=REPO_ROOT)), encoding="utf-8")
    uv = shutil.which("uv")
    if uv is None:
        raise FileNotFoundError("uv is required")
    dependencies = destination / "dependencies"
    if dependencies.exists():
        raise FileExistsError("Use a fresh dependency destination")
    result = run_command(
        [
            uv,
            "pip",
            "install",
            "--python",
            str(sdk / "tools/python.exe"),
            "--target",
            str(dependencies),
            "--only-binary",
            ":all:",
            "--no-deps",
            "--link-mode",
            "copy",
            "-r",
            str(requirements),
        ],
        cwd=REPO_ROOT,
    )
    if result.returncode:
        raise RuntimeError(result.stderr)
    print(result.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    provision(parser.parse_args().destination)

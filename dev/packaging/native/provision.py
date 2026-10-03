"""Acquire the platform runtime and install the locked production dependencies."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from dev._paths import REPO_ROOT

from ..command_execution import run_command
from ..uv_constraints import export_runtime_constraints
from .layout import backend, load_layout


def provision(destination: Path) -> None:
    """Download one verified SDK and install the repository's base closure."""
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    pin = (REPO_ROOT / "dev/packaging/release-python-version").read_text(encoding="utf-8").strip()
    tools = json.loads((REPO_ROOT / "native/toolchain.json").read_text(encoding="utf-8"))
    contract = load_layout()
    sdk = backend(contract).provision_sdk(destination, pin, tools, contract)
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
            str(sdk / contract["sdk"]["executable"]),
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

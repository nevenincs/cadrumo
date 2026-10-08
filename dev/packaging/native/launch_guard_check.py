"""Exercise native interpreter admission before any bundled Python code loads."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path

from ..command_execution import CommandResult, run_command


def check(executable: Path, contract_path: Path) -> None:
    """A structural installation must never fall through to portable launch."""
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    layout = contract["layout"]
    with tempfile.TemporaryDirectory(prefix="cadrumo-launch-admission-") as temporary:
        prefix = Path(temporary).resolve()
        package = prefix / layout["installation"]["versions"] / "1.0.0"
        package.mkdir(parents=True)
        manifest = package / layout["files"]["package_manifest"]
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text("{}", encoding="utf-8")
        target = package / executable.name
        shutil.copy2(executable, target)
        marker_path = prefix / layout["installation"]["marker"]
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        marker = {
            "schema": layout["installation"]["schema"],
            **contract["installation_identity"],
            "platform": layout["platform"],
            "abi": layout["abi"],
            "launch_policy": "native",
            "publication": layout["installation"]["publication"],
        }

        def invoke(*arguments: str) -> CommandResult:
            # SDK loader settings belong to build tools; the application refuses
            # them before package admission, which is the subject of this check.
            environment = {key: value for key, value in os.environ.items() if not key.startswith(("LD_", "DYLD_"))}
            return run_command([str(target), *arguments], cwd=package, environment=environment)

        for present in (True, False):
            if present:
                marker_path.write_text(json.dumps(marker), encoding="utf-8")
            else:
                marker_path.unlink()
            for arguments in (("-c", "raise AssertionError"), ("--version",), ("-V",)):
                result = invoke(*arguments)
                if result.returncode != 120 or "installed package is unavailable for launch" not in result.stderr:
                    raise RuntimeError(f"Native interpreter admission did not refuse {arguments!r}: {result!r}")

        marker.pop("publication")
        marker["launch_policy"] = "portable"
        marker_path.write_text(json.dumps(marker), encoding="utf-8")
        result = invoke("--version")
        if result.returncode != 0 or not result.stdout.startswith("CADRUMO "):
            raise RuntimeError(f"Explicit portable metadata admission failed: {result!r}")


def main() -> None:
    """Check the exact CMake-built host selected by the test graph."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", required=True, type=Path)
    parser.add_argument("--contract", required=True, type=Path)
    arguments = parser.parse_args()
    check(arguments.executable.resolve(strict=True), arguments.contract.resolve(strict=True))


if __name__ == "__main__":
    main()

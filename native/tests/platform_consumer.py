"""Exercise a C ABI consumer with isolated package-location and storage evidence."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path

from dev.packaging.command_execution import run_command
from dev.packaging.native.build_directory import require_enrolled_build
from dev.packaging.native.build_paths import build_paths


def main() -> None:
    """Stage and run the selected consumer without touching an installed package."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", required=True, type=Path)
    parser.add_argument("--consumer", required=True, type=Path)
    parser.add_argument("--dll", type=Path)
    arguments = parser.parse_args()
    build = require_enrolled_build(arguments.build)
    paths = build_paths(build)
    contract = json.loads((paths["generated"] / "contract.json").read_text(encoding="utf-8"))
    paths["testing"].mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="platform-consumer-", dir=paths["testing"]) as temporary:
        scratch = Path(temporary)
        package = scratch / "package"
        package.mkdir()
        consumer = package / arguments.consumer.name
        shutil.copy2(arguments.consumer, consumer)
        if arguments.dll is not None:
            shutil.copy2(arguments.dll, package / arguments.dll.name)
        manifest_member = contract["layout"]["files"]["package_manifest"]
        # A manifest in the working directory must not admit the unrelated image.
        working = scratch / "working"
        working_manifest = working / manifest_member
        working_manifest.parent.mkdir(parents=True)
        working_manifest.write_text("{}", encoding="utf-8")
        environment = {**os.environ, contract["root"]["variable"]: str(scratch / "storage")}
        result = run_command(
            [str(consumer), "--expect-create-refusal"], cwd=working, environment=environment, inherit_output=True
        )
        if result.returncode:
            raise SystemExit(result.returncode)
        manifest = package / manifest_member
        manifest.parent.mkdir(parents=True)
        manifest.write_text("{}", encoding="utf-8")
        expected_package = str(package / contract["layout"]["package_root_from_executable"])
        result = run_command(
            [str(consumer), "--expect-paths", expected_package, environment[contract["root"]["variable"]]],
            cwd=working,
            environment=environment,
            inherit_output=True,
        )
        if result.returncode:
            raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()

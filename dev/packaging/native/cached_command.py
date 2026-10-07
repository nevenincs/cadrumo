"""Content currency for CMake-owned assembly, staging and archive commands."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from dev._paths import REPO_ROOT

from ..command_execution import run_command
from .action_cache import action_lock
from .build_toolchain import sysroot_inventory
from .hashing import digest


def inventory(paths: list[str]) -> dict[str, Any]:
    """Include file membership, bytes, links and executable permissions, never mtimes."""
    result: dict[str, Any] = {}
    for name in sorted(set(paths)):
        path = Path(name)
        if not path.exists():
            raise FileNotFoundError(path)
        if path.is_dir():
            tree = sysroot_inventory(path)
            tree["executable"] = {member: (path / member).stat().st_mode & 0o111 for member in tree["files"]}
            result[name] = tree
        else:
            result[name] = {"sha256": digest(path), "executable": path.stat().st_mode & 0o111}
    return result


def run_cached(build: Path, spec_file: Path, command: list[str]) -> bool:
    """Run one declared action when inputs or outputs differ; return whether it ran."""
    spec = json.loads(spec_file.read_text(encoding="utf-8"))
    root = build.resolve(strict=True)
    marker = Path(spec["marker"])
    for output in [marker, *map(Path, spec["outputs"])]:
        if not output.is_absolute() or not output.resolve().is_relative_to(root) or output.resolve() == root:
            raise ValueError("Cached outputs must be owned children of the CMake binary directory")
    key = hashlib.sha256(json.dumps(sorted(spec["outputs"])).encode()).hexdigest()[:16]
    with action_lock(root, f"cached-{key}"):
        identity = {
            "schema": 1,
            "inputs": inventory(spec["inputs"]),
            "command": command,
            "environment": {name: os.environ.get(name) for name in spec.get("environment", [])},
        }
        try:
            previous = json.loads(marker.read_text(encoding="utf-8"))
            if previous["identity"] == identity and previous["outputs"] == inventory(spec["outputs"]):
                print(f"Reusing {spec['name']}: inputs and output inventory unchanged")
                return False
        except (OSError, ValueError, KeyError):
            pass
        # A failed/interrupted action must never retain a reusable receipt.
        marker.unlink(missing_ok=True)
        result = run_command(command, cwd=REPO_ROOT)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        state = {"identity": identity, "outputs": inventory(spec["outputs"])}
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
        print(f"Built {spec['name']}")
        return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("an executable command is required")
    run_cached(args.build, args.spec, command)

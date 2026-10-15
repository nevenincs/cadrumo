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
from ..google_oauth import build_client_json, client_build_identity
from .action_cache import action_lock
from .build_log import BuildLog, command_line, display_path
from .build_timing import measure_build
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


def _reason(previous: dict[str, Any] | None, identity: dict[str, Any]) -> str:
    """Name what invalidated a receipt, from the parts of its identity."""
    if previous is None:
        return "no completion receipt"
    recorded = previous.get("identity")
    if not isinstance(recorded, dict):
        return "completion receipt is unreadable"
    for key, reason in (
        ("schema", "receipt has an older schema"),
        ("command", "command changed"),
        ("environment", "environment changed"),
        ("publisher_client", "publisher application identity changed"),
    ):
        if recorded.get(key) != identity[key]:
            return reason
    changed = sorted(
        name
        for name in {*recorded.get("inputs", {}), *identity["inputs"]}
        if recorded.get("inputs", {}).get(name) != identity["inputs"].get(name)
    )
    if changed:
        return f"{len(changed)} of {len(identity['inputs'])} inputs changed, first {display_path(changed[0])}"
    return "outputs differ from the completion receipt"


def run_cached(build: Path, spec_file: Path, command: list[str]) -> bool:
    """Run one declared action when inputs or outputs differ; return whether it ran."""
    spec = json.loads(spec_file.read_text(encoding="utf-8"))
    root = build.resolve(strict=True)
    marker = Path(spec["marker"])
    for output in [marker, *map(Path, spec["outputs"])]:
        if not output.is_absolute() or not output.resolve().is_relative_to(root) or output.resolve() == root:
            raise ValueError("Cached outputs must be owned children of the CMake binary directory")
    key = hashlib.sha256(json.dumps(sorted(spec["outputs"])).encode()).hexdigest()[:16]
    log = BuildLog(spec["name"])
    outputs = ", ".join(map(display_path, spec["outputs"]))
    with measure_build(root, spec["name"], log=log) as timings, action_lock(root, f"cached-{key}", timings=timings):
        identity = {
            "schema": 1,
            "inputs": {},
            "command": command,
            "environment": {name: os.environ.get(name) for name in spec.get("environment", [])},
            "publisher_client": (
                client_build_identity("native-contract", build_client_json(REPO_ROOT))
                if spec["name"] == "native_contract"
                else None
            ),
        }
        with timings.phase("input-inventory"):
            identity["inputs"] = inventory(spec["inputs"])
        log.verbose(f"{len(identity['inputs'])} enrolled inputs; receipt {display_path(marker)}")
        try:
            previous: dict[str, Any] | None = json.loads(marker.read_text(encoding="utf-8"))
        except FileNotFoundError:
            previous = None
        except (OSError, ValueError):
            previous = {}
        if isinstance(previous, dict) and previous.get("identity") == identity:
            with timings.phase("existing-output-inventory"):
                try:
                    unchanged = previous.get("outputs") == inventory(spec["outputs"])
                except OSError:
                    unchanged = False
            if unchanged:
                log.status(f"up to date, reusing {outputs}: inputs and output inventory unchanged")
                return False
        # A failed/interrupted action must never retain a reusable receipt.
        marker.unlink(missing_ok=True)
        log.status(f"running ({_reason(previous, identity)}) -> {outputs}")
        log.debug(f"command: {command_line(command)}")
        with timings.phase("producer"):
            result = run_command(command, cwd=REPO_ROOT, inherit_output=True)
            timings.command_completed(result.returncode)
            if result.returncode:
                raise RuntimeError(f"{spec['name']} failed with exit status {result.returncode}; its output is above")
        with timings.phase("input-stability"):
            if identity["inputs"] != inventory(spec["inputs"]):
                raise RuntimeError(f"Inputs changed during {spec['name']}; completion receipt refused")
            if spec["name"] == "native_contract" and identity["publisher_client"] != client_build_identity(
                "native-contract", build_client_json(REPO_ROOT)
            ):
                raise RuntimeError("Publisher application identity changed during native contract generation")
        with timings.phase("output-inventory"):
            produced = inventory(spec["outputs"])
        state = {"identity": identity, "outputs": produced}
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
        log.status(f"built {outputs}")
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

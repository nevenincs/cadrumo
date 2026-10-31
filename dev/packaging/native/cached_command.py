"""Content currency for CMake-owned assembly, staging and archive commands."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, cast

from dev._paths import REPO_ROOT

from ..command_execution import run_command
from ..google_oauth import build_client_json, client_build_identity
from .action_cache import action_lock, receipt_owner
from .build_directory import require_enrolled_build
from .build_log import BuildLog, command_line, display_path
from .build_paths import build_paths
from .build_timing import BuildTimings, measure_build
from .build_toolchain import sysroot_inventory
from .discovered_inputs import DISCOVERED_INPUTS_VARIABLE
from .hashing import digest, digest_cache
from .stage_reuse import package_mismatch, package_records


def _recorded_discovered(previous: Mapping[str, object] | None) -> list[str]:
    recorded = previous.get("discovered") if isinstance(previous, dict) else None
    return [name for name in recorded if isinstance(name, str)] if isinstance(recorded, list) else []


def _action_inputs(declared: list[str], discovered: list[str]) -> list[str]:
    """The declared inputs plus the discovered ones that do not repeat a declared file."""
    known = {os.path.normcase(os.path.abspath(name)) for name in declared}
    extra = [name for name in discovered if os.path.normcase(os.path.abspath(name)) not in known]
    return [*declared, *extra]


def inventory(paths: list[str], *, receipts: Path | None = None) -> dict[str, Any]:
    """Include file membership, bytes, links and executable permissions, never mtimes.

    With ``receipts`` (a binary directory), a directory input that a producer of that
    build owns is represented by the digest of its producer's completion receipt, which
    binds the producer's whole output inventory, instead of by every member's digest.
    """
    result: dict[str, Any] = {}
    for name in sorted(set(paths)):
        path = Path(name)
        if not path.exists():
            raise FileNotFoundError(path)
        owner = receipt_owner(path, receipts) if receipts is not None and path.is_dir() else None
        if owner is not None:
            result[name] = {"receipt": digest(owner / "ready"), "member": path.resolve().relative_to(owner).as_posix()}
        elif path.is_dir():
            tree = sysroot_inventory(path)
            tree["executable"] = {member: (path / member).stat().st_mode & 0o111 for member in tree["files"]}
            result[name] = tree
        else:
            result[name] = {"sha256": digest(path), "executable": path.stat().st_mode & 0o111}
    return result


def _unproven_outputs(build: Path, outputs: list[str], recorded: object) -> str | None:
    """Say why the recorded outputs cannot be taken as they stand, or ``None`` when they can.

    A file output is compared whole. A directory output must be a package that settled build
    records name as staged; it is compared by its own top two levels (manifests and images)
    and by every artifact those records staged. Any other directory is left to the full check.
    """
    if not isinstance(recorded, dict):
        return "no recorded output inventory"
    recorded = cast("dict[str, object]", recorded)
    for name in outputs:
        path = Path(name)
        expected = recorded.get(name)
        if not isinstance(expected, dict) or not path.exists():
            return f"{display_path(path)} is not as recorded"
        if not path.is_dir():
            if inventory([name])[name] != expected:
                return f"{display_path(path)} differs from the completion receipt"
            continue
        issue = _unproven_directory(build, path, cast("dict[str, object]", expected))
        if issue is not None:
            return issue
    return None


def _unproven_directory(build: Path, path: Path, expected: dict[str, object]) -> str | None:
    unsettled = package_mismatch(build, path)
    if unsettled is not None:
        return unsettled
    files = expected.get("files")
    if not isinstance(files, dict):
        return f"{display_path(path)} has no recorded file inventory"
    files = cast("dict[str, str]", files)
    witnesses = {member for member in files if member.count("/") <= 1}
    for _component, record, configuration in package_records(build, path):
        witnesses.update(record["staged"][configuration]["artifacts"])
    for member in sorted(witnesses):
        target = path / member
        if member not in files or not target.is_file() or digest(target) != files[member]:
            return f"{display_path(target)} differs from the completion receipt"
    return None


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
    _require_owned_outputs(marker, spec["outputs"], root)
    key = hashlib.sha256(json.dumps(sorted(spec["outputs"])).encode()).hexdigest()[:16]
    log = BuildLog(spec["name"])
    outputs = ", ".join(map(display_path, spec["outputs"]))
    with (
        measure_build(root, spec["name"], log=log) as timings,
        action_lock(root, f"cached-{key}", timings=timings),
        # The inventories, and the producer this starts, share the binary directory's digest cache.
        digest_cache(root),
    ):
        identity, previous, discover, removed, inputs = _prepare_cached_inputs(spec, command, marker)

        def summarized() -> dict[str, Any]:
            return {**identity, "inputs": inventory(inputs, receipts=root)}

        # The summary keys producer-owned input trees on their completion receipts, so an
        # unchanged action is decided from file metadata the digest cache already holds.
        with timings.phase("input-summary"):
            summary = summarized()
        if not removed and _summary_is_current(previous, summary, root, spec["outputs"], outputs, log, timings):
            return False
        with timings.phase("input-inventory"):
            identity["inputs"] = inventory(inputs)
        log.verbose(f"{len(identity['inputs'])} enrolled inputs; receipt {display_path(marker)}")
        if not removed and _reuse_verified_outputs(
            previous, identity, spec["outputs"], timings, marker, summary, summarized, outputs, log
        ):
            return False
        # A failed/interrupted action must never retain a reusable receipt.
        marker.unlink(missing_ok=True)
        reason = f"discovered input {display_path(Path(removed[0]))} was removed" if removed else None
        log.status(f"running ({reason or _reason(previous, identity)}) -> {outputs}")
        log.debug(f"command: {command_line(command)}")
        discovered_file = marker.with_name(f"{marker.stem}.discovered.json")
        _run_producer(spec["name"], command, discover, discovered_file, timings)
        stable_summary = _inputs_stable(
            spec["name"],
            spec["inputs"],
            inputs,
            identity["inputs"],
            identity["publisher_client"],
            summarized,
            summary,
            timings,
        )
        if stable_summary is None:
            log.status(f"built {outputs}; a discovered input changed while it ran, so the next build reruns it")
            return True
        with timings.phase("output-inventory"):
            produced = inventory(spec["outputs"])
        discovered = _read_discovered(discovered_file, spec["name"]) if discover else None
        # Files first discovered by this run were not inventoried before it, so nothing proves
        # the producer read the bytes they hold now; the next run keys on them and reruns once.
        _write_completed_marker(marker, identity, produced, stable_summary, summary, discovered)
        log.status(f"built {outputs}")
        return True


def _prepare_cached_inputs(
    spec: dict[str, Any], command: list[str], marker: Path
) -> tuple[dict[str, Any], dict[str, object] | None, bool, list[str], list[str]]:
    """Load the prior receipt and select its still-present discovered inputs."""
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
    previous = _read_previous_marker(marker)
    discover = bool(spec.get("discover"))
    recorded = _recorded_discovered(previous) if discover else []
    removed = [name for name in recorded if not Path(name).is_file()]
    inputs = _action_inputs(spec["inputs"], [name for name in recorded if name not in removed])
    return identity, previous, discover, removed, inputs


def _reuse_verified_outputs(
    previous: dict[str, object] | None,
    identity: Mapping[str, object],
    output_paths: list[str],
    timings: BuildTimings,
    marker: Path,
    summary: Mapping[str, object],
    summarized: Callable[[], Mapping[str, object]],
    outputs: str,
    log: BuildLog,
) -> bool:
    """Reuse an exact receipt after independently verifying its outputs."""
    if previous is None or previous.get("identity") != identity:
        return False
    if not _existing_outputs_match(previous, output_paths, timings):
        return False
    if previous.get("summary") != summary and summarized() == summary:
        _write_marker(marker, {**previous, "summary": summary})
    log.status(f"up to date, reusing {outputs}: inputs and output inventory unchanged")
    return True


def _run_producer(name: str, command: list[str], discover: bool, discovered_file: Path, timings: BuildTimings) -> None:
    """Run the producer with an optional input-discovery receipt and check its exit."""
    with timings.phase("producer"):
        if discover:
            discovered_file.unlink(missing_ok=True)
            os.environ[DISCOVERED_INPUTS_VARIABLE] = str(discovered_file)
        try:
            result = run_command(command, cwd=REPO_ROOT, inherit_output=True)
        finally:
            os.environ.pop(DISCOVERED_INPUTS_VARIABLE, None)
        timings.command_completed(result.returncode)
        if result.returncode:
            raise RuntimeError(f"{name} failed with exit status {result.returncode}; its output is above")


def _read_discovered(path: Path, name: str) -> list[str]:
    try:
        discovered = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise RuntimeError(f"{name} did not record the inputs it discovered: {error}") from error
    if not isinstance(discovered, list) or not all(isinstance(entry, str) for entry in discovered):
        raise RuntimeError(f"{name} recorded malformed discovered inputs")
    return cast("list[str]", discovered)


def _write_completed_marker(
    marker: Path,
    identity: Mapping[str, object],
    produced: Mapping[str, object],
    stable_summary: bool,
    summary: Mapping[str, object],
    discovered: list[str] | None = None,
) -> None:
    state: dict[str, object] = {"identity": identity, "outputs": produced}
    if stable_summary:
        state["summary"] = summary
    if discovered is not None:
        state["discovered"] = discovered
    _write_marker(marker, state)


def _inputs_stable(
    name: str,
    declared: list[str],
    inputs: list[str],
    expected_inputs: Mapping[str, object],
    publisher_client: object,
    summarized: Callable[[], Mapping[str, object]],
    summary: Mapping[str, object],
    timings: BuildTimings,
) -> bool | None:
    """Say whether the summary held still, or ``None`` when only a discovered input moved.

    A declared input that changed while the producer ran refuses the receipt and
    fails the action. A discovered input is a file the producer happened to read
    in a shared checkout; its change leaves the action unreceipted rather than
    failed, so the next build reruns it and nothing reuses the torn result.
    """
    with timings.phase("input-stability"):
        known = {os.path.normcase(os.path.abspath(entry)) for entry in declared}
        observed = _inventory_remaining_inputs(inputs, known)
        moved = [entry for entry in inputs if observed.get(entry) != expected_inputs.get(entry)]
        if any(os.path.normcase(os.path.abspath(entry)) in known for entry in moved):
            raise RuntimeError(f"Inputs changed during {name}; completion receipt refused")
        if moved:
            return None
        if name == "native_contract" and publisher_client != client_build_identity(
            "native-contract", build_client_json(REPO_ROOT)
        ):
            raise RuntimeError("Publisher application identity changed during native contract generation")
        return summarized() == summary


def _inventory_remaining_inputs(inputs: list[str], declared: set[str]) -> dict[str, object]:
    """Inventory existing inputs, refusing the disappearance of a declared input."""
    observed: dict[str, object] = {}
    for entry in inputs:
        try:
            observed.update(inventory([entry]))
        except FileNotFoundError:
            if os.path.normcase(os.path.abspath(entry)) in declared:
                raise
    return observed


def _read_previous_marker(marker: Path) -> dict[str, object] | None:
    try:
        return cast("dict[str, object]", json.loads(marker.read_text(encoding="utf-8")))
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        return {}


def _existing_outputs_match(previous: Mapping[str, object], outputs: list[str], timings: BuildTimings) -> bool:
    with timings.phase("existing-output-inventory"):
        try:
            return previous.get("outputs") == inventory(outputs)
        except OSError:
            return False


def _summary_is_current(
    previous: Mapping[str, object] | None,
    summary: Mapping[str, object],
    root: Path,
    output_paths: list[str],
    outputs: str,
    log: BuildLog,
    timings: BuildTimings,
) -> bool:
    if not isinstance(previous, dict) or previous.get("summary") != summary:
        return False
    with timings.phase("record-currency"):
        try:
            unproven = _unproven_outputs(root, output_paths, previous.get("outputs"))
        except OSError as error:
            unproven = str(error)
    if unproven is None:
        log.status(f"up to date, reusing {outputs}: inputs, records and staged artifacts unchanged")
        return True
    log.verbose(f"verifying every input and output: {unproven}")
    return False


def _require_owned_outputs(marker: Path, outputs: list[str], root: Path) -> None:
    for output in [marker, *map(Path, outputs)]:
        if not output.is_absolute() or not output.resolve().is_relative_to(root) or output.resolve() == root:
            raise ValueError("Cached outputs must be owned children of the CMake binary directory")


def _write_marker(marker: Path, state: dict[str, Any]) -> None:
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")


def _configure_temporary(build: Path) -> None:
    """Keep this CMake action and its child process in the build's temporary directory."""
    temporary = build_paths(build)["temporary"]
    temporary.mkdir(parents=True, exist_ok=True)
    os.environ.update(dict.fromkeys(("TEMP", "TMP", "TMPDIR"), str(temporary)))
    tempfile.tempdir = str(temporary)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=require_enrolled_build, required=True)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("an executable command is required")
    _configure_temporary(args.build)
    run_cached(args.build, args.spec, command)

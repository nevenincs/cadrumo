"""Capture a reproducible, side-effect-safe baseline for every live CLI node.

Every enrolled root, group, and leaf is resolved in an independent interpreter.
Invocation is deliberately limited to help rendering: a benchmark must never
turn a destructive, network, browser, filing, or storage-writing command into
an operation merely because it needs a latency observation.
"""

from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from cadrumo.entrypoints.cli._command_suggestions import LiveCommandNode
    from cadrumo.tests.cli_performance import CliPerformanceProfile

SCHEMA = "cadrumo-cli-baseline-v1"
DEFAULT_OUTPUT = Path(__file__).with_name("baseline.json")
CONTROL_PATH: tuple[str, ...] = ()
CONTROL_ARGS = ("--version",)
HELP_ARGS = ("--help",)
_SNAPSHOT_WORKER_ENV = "CADRUMO_BASELINE_SNAPSHOT_WORKER"
_SNAPSHOT_DIGEST_ENV = "CADRUMO_BASELINE_SOURCE_DIGEST"
_SNAPSHOT_ROOT_ENV = "CADRUMO_BASELINE_SOURCE_ROOT"
_ORIGIN_GIT_ENV = "CADRUMO_BASELINE_ORIGIN_GIT"
_ORIGIN_DIRTY_ENV = "CADRUMO_BASELINE_ORIGIN_DIRTY_FINGERPRINT"
_GENERATOR_DIGEST_ENV = "CADRUMO_BASELINE_GENERATOR_DIGEST"
_LOCK_DIGEST_ENV = "CADRUMO_BASELINE_LOCK_DIGEST"


def _command_tokens(node: LiveCommandNode) -> tuple[str, ...]:
    """Remove the executable token from a census path."""
    return node.path[1:]


def _invocation_mode(node: LiveCommandNode) -> tuple[str, tuple[str, ...]]:
    """Return the honest, non-mutating invocation lane for one node."""
    return "help-render", HELP_ARGS


def _observation_payload(profile: CliPerformanceProfile) -> dict[str, Any]:
    phases: dict[str, Any] = {}
    for name in ("resolution", "invocation"):
        observation = getattr(profile, name)
        module_names = tuple(sorted(observation.imported_modules))
        storage_calls = dict(sorted(observation.storage_operation_calls.items()))
        phases[name] = {
            "wall_seconds": observation.wall_seconds,
            "imported_module_count": len(observation.imported_modules),
            "imported_modules": list(module_names),
            "import_families": {
                family: list(sorted(modules)) for family, modules in sorted(observation.import_families.items())
            },
            "pydantic_model_constructions": observation.pydantic_model_constructions,
            "filesystem": {
                "created": list(observation.filesystem_created),
                "modified": list(observation.filesystem_modified),
                "deleted": list(observation.filesystem_deleted),
                "operations": dict(sorted(observation.filesystem_operations.items())),
            },
            "storage_operation_calls": storage_calls,
            "exit_code": observation.exit_code,
            "failure_kind": observation.failure_kind,
        }
    return phases


def _string_sequence_digest(values: Sequence[str]) -> str:
    digest = hashlib.sha256()
    for value in values:
        digest.update(value.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def _compact_storage_calls(calls: Mapping[str, int]) -> dict[str, Any]:
    canonical = tuple(sorted((str(symbol), int(count)) for symbol, count in calls.items()))
    encoded = json.dumps(canonical, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    top = sorted(canonical, key=lambda item: (-item[1], item[0]))[:20]
    return {
        "total_calls": sum(count for _, count in canonical),
        "distinct_symbols": len(canonical),
        "calls_digest": hashlib.sha256(encoded).hexdigest(),
        "top_calls": [{"symbol": symbol, "count": count} for symbol, count in top],
    }


def _compact_existing_observation(observation: dict[str, Any]) -> None:
    imported_modules = observation.pop("imported_modules", None)
    if imported_modules is not None:
        observation["imported_modules_digest"] = _string_sequence_digest(tuple(imported_modules))
    families = observation["import_families"]
    if families and isinstance(next(iter(families.values())), list):
        observation["import_families"] = {
            family: {"count": len(modules), "modules_digest": _string_sequence_digest(tuple(modules))}
            for family, modules in sorted(families.items())
        }
    calls = observation["storage_operation_calls"]
    if "total_calls" not in calls:
        observation["storage_operation_calls"] = _compact_storage_calls(calls)


def compact_existing_baseline(payload: dict[str, Any]) -> None:
    """Mechanically compact raw evidence into its review summary."""
    for sample in payload["control"]["samples"]:
        for phase in ("resolution", "invocation"):
            _compact_existing_observation(sample[phase])
    for command in payload["commands"].values():
        for sample in command["samples"]:
            for phase in ("resolution", "invocation"):
                _compact_existing_observation(sample[phase])


def _median_absolute_deviation(values: Sequence[float]) -> float:
    centre = median(values)
    return float(median(abs(value - centre) for value in values))


def _distribution(samples: Sequence[Mapping[str, Any]], phase: str) -> dict[str, Any]:
    values = tuple(float(sample[phase]["wall_seconds"]) for sample in samples)
    return {
        "samples_seconds": list(values),
        "median_seconds": float(median(values)),
        "median_absolute_deviation_seconds": _median_absolute_deviation(values),
    }


def _summarise_samples(
    samples: Sequence[Mapping[str, Any]],
    *,
    control_resolution_median: float,
    control_invocation_median: float,
) -> dict[str, Any]:
    resolution = _distribution(samples, "resolution")
    invocation = _distribution(samples, "invocation")
    resolution["control_ratio"] = resolution["median_seconds"] / control_resolution_median
    invocation["control_ratio"] = invocation["median_seconds"] / control_invocation_median
    return {"resolution": resolution, "invocation": invocation}


def _policy_payload(node: LiveCommandNode) -> dict[str, Any]:
    policy = node.execution_policy
    if policy is None:
        raise RuntimeError(f"unclassified live command: {' '.join(node.path)}")
    classification = policy.classification
    return {
        "capabilities": sorted(classification.capabilities),
        "expanded_capabilities": sorted(classification.expanded_capabilities),
        "side_effects": sorted(classification.side_effects),
        "performance_class": classification.performance,
        "write_route": policy.write_route,
        "destructive": policy.destructive,
        "handoff": policy.handoff,
        "live_write": policy.live_write,
    }


def _frozen_census_entry(node: LiveCommandNode) -> dict[str, Any]:
    """Retain command identity independently from measured observations."""
    return {
        "kind": node.kind,
        "loader_owner": node.loader_owner,
        "handler_owner": node.handler_owner,
        "policy": _policy_payload(node),
    }


def _measure(
    node: LiveCommandNode,
    *,
    warmups: int,
    samples: int,
    timeout: float,
) -> tuple[str, dict[str, Any]]:
    from cadrumo.tests.cli_performance import profile_cli_path

    mode, args = _invocation_mode(node)
    observations: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="cadrumo-cli-baseline-node-") as directory:
        root = Path(directory)
        for _ in range(warmups):
            profile_cli_path(
                _command_tokens(node),
                invocation_args=args,
                storage_root=root,
                timeout=timeout,
            )
        for _ in range(samples):
            observations.append(
                _observation_payload(
                    profile_cli_path(
                        _command_tokens(node),
                        invocation_args=args,
                        storage_root=root,
                        timeout=timeout,
                    )
                )
            )
    return " ".join(node.path), {
        "kind": node.kind,
        "loader_owner": node.loader_owner,
        "handler_owner": node.handler_owner,
        "policy": _policy_payload(node),
        "invocation_mode": mode,
        "invocation_args": list(args),
        "samples": observations,
    }


def _measure_one_control(*, timeout: float) -> dict[str, Any]:
    from cadrumo.tests.cli_performance import profile_cli_path

    with tempfile.TemporaryDirectory(prefix="cadrumo-cli-baseline-control-") as directory:
        return _observation_payload(
            profile_cli_path(
                CONTROL_PATH,
                invocation_args=CONTROL_ARGS,
                storage_root=Path(directory),
                timeout=timeout,
            )
        )


def _measure_controls(*, samples: int, timeout: float, workers: int) -> list[dict[str, Any]]:
    """Measure controls at the same bounded concurrency as command batches."""
    observations: list[dict[str, Any]] = []
    for offset in range(0, samples, workers):
        lanes = min(workers, samples - offset)
        with ThreadPoolExecutor(max_workers=lanes, thread_name_prefix="cli-baseline-control") as pool:
            futures = [pool.submit(_measure_one_control, timeout=timeout) for _ in range(lanes)]
            observations.extend(future.result() for future in as_completed(futures))
    return observations


def _tool_version(command: Sequence[str]) -> str:
    completed = subprocess.run(  # noqa: S603 - fixed local tool commands supplied by this module.
        list(command),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    return (completed.stdout or completed.stderr).strip().splitlines()[0]


def _git_revision() -> str:
    return _tool_version(("git", "rev-parse", "HEAD"))


def _environment_payload() -> dict[str, str]:
    return {
        "captured_at_utc": datetime.now(UTC).isoformat(),
        "originating_git_revision": os.environ.get(_ORIGIN_GIT_ENV, _git_revision()),
        "originating_dirty_fingerprint": os.environ.get(_ORIGIN_DIRTY_ENV, "unfrozen"),
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "operating_system": platform.system(),
        "os_release": platform.release(),
        "machine": platform.machine(),
        "processor_count": str(os.cpu_count() or "unknown"),
        "uv": _tool_version(("uv", "--version")),
        "source_snapshot_digest": os.environ.get(_SNAPSHOT_DIGEST_ENV, "unfrozen"),
        "generator_digest": os.environ.get(_GENERATOR_DIGEST_ENV, "unfrozen"),
        "dependency_lock_digest": os.environ.get(_LOCK_DIGEST_ENV, "unfrozen"),
    }


def _source_manifest(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    }


def _manifest_digest(manifest: Mapping[str, str]) -> str:
    encoded = json.dumps(dict(sorted(manifest.items())), separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _tree_digest(root: Path) -> str:
    return _manifest_digest(_source_manifest(root))


def _copy_source_snapshot(source: Path, snapshot: Path) -> str:
    """Copy one immutable package tree and return its content identity."""
    if snapshot.exists():
        raise RuntimeError(f"refusing to overwrite existing source snapshot: {snapshot}")
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        source,
        snapshot,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )
    return _tree_digest(snapshot)


def _worktree_fingerprint(repository_root: Path) -> str:
    """Hash tracked, staged, and untracked worktree state without publishing it."""
    digest = hashlib.sha256()
    git_executable = shutil.which("git")
    if git_executable is None:
        raise RuntimeError("git executable is required to fingerprint the worktree")
    commands = (
        (git_executable, "status", "--porcelain=v1", "-z"),
        (git_executable, "diff", "--binary", "HEAD"),
        (git_executable, "diff", "--binary", "--cached", "HEAD"),
    )
    for command in commands:
        completed = subprocess.run(  # noqa: S603 - fixed local Git reads.
            command,
            cwd=repository_root,
            check=True,
            capture_output=True,
        )
        digest.update(completed.stdout)
        digest.update(b"\0")
    untracked = subprocess.run(  # noqa: S603 - resolved local Git executable and fixed arguments.
        (git_executable, "ls-files", "--others", "--exclude-standard", "-z"),
        cwd=repository_root,
        check=True,
        capture_output=True,
    ).stdout.split(b"\0")
    for encoded in sorted(item for item in untracked if item):
        relative = encoded.decode("utf-8", errors="surrogateescape")
        path = repository_root / relative
        digest.update(encoded)
        digest.update(b"\0")
        if path.is_file():
            digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _assert_snapshot_runtime() -> None:
    """Prove this worker and therefore profiler children import the snapshot."""
    import cadrumo

    expected_root = Path(os.environ[_SNAPSHOT_ROOT_ENV]).resolve()
    imported = Path(cadrumo.__file__).resolve()
    if not imported.is_relative_to(expected_root):
        raise RuntimeError(f"baseline worker imported mutable source: {imported}")
    expected_digest = os.environ[_SNAPSHOT_DIGEST_ENV]
    if _tree_digest(expected_root / "cadrumo") != expected_digest:
        raise RuntimeError("baseline source snapshot changed after capture started")


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def _write_bytes_atomic(path: Path, payload: bytes) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, path)


def _reject_unexpected_checkpoint_commands(commands: Mapping[str, Any], expected_paths: Sequence[str]) -> None:
    unexpected = sorted(set(commands) - set(expected_paths))
    if unexpected:
        raise RuntimeError(f"CLI baseline checkpoint contains unexpected commands: {unexpected}")


def _publish_raw_and_summary(output: Path, raw_payload: dict[str, Any]) -> dict[str, Any]:
    census = raw_payload.pop("frozen_census")
    census_payload = {
        "schema": f"{SCHEMA}-frozen-census",
        "source_snapshot_digest": raw_payload["environment"]["source_snapshot_digest"],
        "commands": census,
    }
    canonical_census = json.dumps(census_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    census_path = output.with_name(f"{output.stem}.census.json")
    _write_bytes_atomic(census_path, canonical_census)
    canonical_raw = json.dumps(raw_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    compressed = gzip.compress(canonical_raw, compresslevel=9, mtime=0)
    raw_path = output.with_name(f"{output.stem}.raw.json.gz")
    _write_bytes_atomic(raw_path, compressed)
    summary = copy.deepcopy(raw_payload)
    compact_existing_baseline(summary)
    summary["raw_evidence"] = {
        "filename": raw_path.name,
        "compressed_sha256": hashlib.sha256(compressed).hexdigest(),
        "uncompressed_sha256": hashlib.sha256(canonical_raw).hexdigest(),
        "uncompressed_bytes": len(canonical_raw),
    }
    summary["frozen_census_evidence"] = {
        "filename": census_path.name,
        "sha256": hashlib.sha256(canonical_census).hexdigest(),
        "bytes": len(canonical_census),
    }
    return summary


def _load_frozen_census(payload: Mapping[str, Any], *, baseline_path: Path) -> dict[str, Any]:
    declaration = payload.get("frozen_census_evidence", {})
    filename = declaration.get("filename")
    if not isinstance(filename, str) or Path(filename).name != filename:
        raise RuntimeError("invalid frozen-census filename")
    encoded = baseline_path.with_name(filename).read_bytes()
    if hashlib.sha256(encoded).hexdigest() != declaration.get("sha256"):
        raise RuntimeError("frozen-census digest mismatch")
    if len(encoded) != declaration.get("bytes"):
        raise RuntimeError("frozen-census byte count mismatch")
    census: object = json.loads(encoded)
    if not isinstance(census, dict) or census.get("schema") != f"{SCHEMA}-frozen-census":
        raise RuntimeError("invalid frozen-census evidence")
    if census.get("source_snapshot_digest") != payload["environment"]["source_snapshot_digest"]:
        raise RuntimeError("frozen census belongs to a different source snapshot")
    commands = census.get("commands")
    if not isinstance(commands, dict) or not commands:
        raise RuntimeError("frozen census contains no commands")
    return cast("dict[str, Any]", commands)


def _load_raw_evidence(payload: Mapping[str, Any], *, baseline_path: Path) -> dict[str, Any]:
    declaration = payload.get("raw_evidence", {})
    filename = declaration.get("filename")
    if not isinstance(filename, str) or Path(filename).name != filename:
        raise RuntimeError("invalid raw-evidence filename")
    raw_path = baseline_path.with_name(filename)
    compressed = raw_path.read_bytes()
    if hashlib.sha256(compressed).hexdigest() != declaration.get("compressed_sha256"):
        raise RuntimeError("raw-evidence compressed digest mismatch")
    canonical_raw = gzip.decompress(compressed)
    if hashlib.sha256(canonical_raw).hexdigest() != declaration.get("uncompressed_sha256"):
        raise RuntimeError("raw-evidence content digest mismatch")
    if len(canonical_raw) != declaration.get("uncompressed_bytes"):
        raise RuntimeError("raw-evidence byte count mismatch")
    raw: object = json.loads(canonical_raw)
    if not isinstance(raw, dict):
        raise RuntimeError("raw evidence must be a JSON object")
    return cast("dict[str, Any]", raw)


def capture(
    *,
    warmups: int,
    samples: int,
    timeout: float,
    workers: int,
    checkpoint_path: Path | None = None,
    resume: bool = True,
) -> dict[str, Any]:
    """Capture controls and every dynamically enrolled live command node."""
    from cadrumo.entrypoints.cli import app
    from cadrumo.entrypoints.cli._command_suggestions import walk_live_command_tree

    _assert_snapshot_runtime()
    if samples < 3:
        raise ValueError("baseline requires at least three measured samples")
    if warmups < 1:
        raise ValueError("baseline requires at least one warmup")
    if workers < 1:
        raise ValueError("workers must be positive")
    nodes = walk_live_command_tree(app)
    if not nodes:
        raise RuntimeError("live command census is empty")
    if len({node.path for node in nodes}) != len(nodes):
        raise RuntimeError("live command census contains duplicate paths")
    frozen_census = {" ".join(node.path): _frozen_census_entry(node) for node in nodes}
    expected_paths = list(frozen_census)
    run_config = {
        "warmups": warmups,
        "samples": samples,
        "timeout_seconds": timeout,
        "workers": workers,
        "source_snapshot_digest": os.environ[_SNAPSHOT_DIGEST_ENV],
        "originating_git_revision": os.environ[_ORIGIN_GIT_ENV],
        "originating_dirty_fingerprint": os.environ[_ORIGIN_DIRTY_ENV],
        "generator_digest": os.environ[_GENERATOR_DIGEST_ENV],
        "dependency_lock_digest": os.environ[_LOCK_DIGEST_ENV],
    }

    commands: dict[str, dict[str, Any]] = {}
    controls: list[dict[str, Any]] = []
    if resume and checkpoint_path is not None and checkpoint_path.exists():
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        if checkpoint.get("schema") != f"{SCHEMA}-partial":
            raise RuntimeError("unsupported CLI baseline checkpoint schema")
        if checkpoint.get("run_config") != run_config:
            raise RuntimeError("CLI baseline checkpoint configuration changed")
        if checkpoint.get("expected_paths") != expected_paths:
            raise RuntimeError("CLI baseline checkpoint census changed")
        commands = dict(checkpoint.get("commands", {}))
        _reject_unexpected_checkpoint_commands(commands, expected_paths)
        controls = list(checkpoint.get("controls", []))

    def checkpoint() -> None:
        if checkpoint_path is None:
            return
        _write_json_atomic(
            checkpoint_path,
            {
                "schema": f"{SCHEMA}-partial",
                "run_config": run_config,
                "expected_paths": expected_paths,
                "controls": controls,
                "commands": {path: commands[path] for path in sorted(commands)},
            },
        )

    # Controls bracket the sweep and recur between small deterministic batches.
    # This reveals host drift during a multi-hour run instead of assuming that
    # two endpoint observations represent the whole measurement window.
    control_lane_samples = max(samples, workers)
    if not controls:
        controls.extend(_measure_controls(samples=control_lane_samples, timeout=timeout, workers=workers))
        checkpoint()
    leading_samples = control_lane_samples
    batch_size = workers * 4
    for offset in range(0, len(nodes), batch_size):
        batch = [node for node in nodes[offset : offset + batch_size] if " ".join(node.path) not in commands]
        if not batch:
            continue
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="cli-baseline") as pool:
            futures = {
                pool.submit(_measure, node, warmups=warmups, samples=samples, timeout=timeout): node for node in batch
            }
            for future in as_completed(futures):
                path, payload = future.result()
                commands[path] = payload
        controls.extend(_measure_controls(samples=workers, timeout=timeout, workers=workers))
        checkpoint()
        print(
            f"captured {len(commands)}/{len(nodes)} live CLI nodes; controls={len(controls)}",
            file=sys.stderr,
            flush=True,
        )
    controls.extend(_measure_controls(samples=control_lane_samples, timeout=timeout, workers=workers))
    trailing_samples = control_lane_samples
    if set(commands) != set(frozen_census):
        missing = sorted(set(frozen_census) - set(commands))
        extra = sorted(set(commands) - set(frozen_census))
        raise RuntimeError(f"captured CLI census is incomplete: missing={missing}, extra={extra}")
    control_summary = {
        "resolution": _distribution(controls, "resolution"),
        "invocation": _distribution(controls, "invocation"),
    }
    resolution_control = float(control_summary["resolution"]["median_seconds"])
    invocation_control = float(control_summary["invocation"]["median_seconds"])

    for payload in commands.values():
        payload["distribution"] = _summarise_samples(
            payload["samples"],
            control_resolution_median=resolution_control,
            control_invocation_median=invocation_control,
        )
    ranked_resolution = sorted(
        commands,
        key=lambda path: (-commands[path]["distribution"]["resolution"]["control_ratio"], path),
    )
    ranked_invocation = sorted(
        commands,
        key=lambda path: (-commands[path]["distribution"]["invocation"]["control_ratio"], path),
    )
    failures = sorted(
        path
        for path, payload in commands.items()
        if any(
            phase["failure_kind"] != "none" or phase["exit_code"] != 0
            for sample in payload["samples"]
            for phase in (sample["resolution"], sample["invocation"])
        )
    )
    return {
        "schema": SCHEMA,
        "environment": _environment_payload(),
        "source_snapshot_manifest": _source_manifest(Path(os.environ[_SNAPSHOT_ROOT_ENV]) / "cadrumo"),
        "frozen_census": frozen_census,
        "method": {
            "samples_per_node": samples,
            "warmups_per_node": warmups,
            "control_samples": len(controls),
            "control_cadence_nodes": batch_size,
            "workers": workers,
            "timeout_seconds": timeout,
            "resolution": "fresh-process exact live-path resolution",
            "invocation": "fresh-process help rendering; handlers are never executed",
            "safety": "all nodes use --help, including destructive/network/write nodes",
        },
        "control": {
            "leading_samples": leading_samples,
            "periodic_samples": len(controls) - leading_samples - trailing_samples,
            "trailing_samples": trailing_samples,
            "samples": controls,
            "distribution": control_summary,
        },
        "commands": {path: commands[path] for path in sorted(commands)},
        "ranked_outliers": {
            "resolution_by_control_ratio": ranked_resolution,
            "invocation_by_control_ratio": ranked_invocation,
        },
        "failures_and_timeouts": failures,
    }


def check_baseline(
    payload: Mapping[str, Any],
    *,
    baseline_path: Path = DEFAULT_OUTPUT,
    require_current_source: bool = False,
) -> None:
    """Reject stale, incomplete, unranked, or unsafely labelled evidence."""
    from cadrumo.entrypoints.cli import app
    from cadrumo.entrypoints.cli._command_suggestions import walk_live_command_tree

    if payload.get("schema") != SCHEMA:
        raise RuntimeError("unsupported or missing CLI baseline schema")
    environment = payload.get("environment", {})
    for key in (
        "source_snapshot_digest",
        "originating_dirty_fingerprint",
        "generator_digest",
        "dependency_lock_digest",
    ):
        value = environment.get(key, "")
        if not isinstance(value, str) or len(value) != 64:
            raise RuntimeError(f"missing or invalid baseline source identity: {key}")
    if not environment.get("originating_git_revision"):
        raise RuntimeError("missing baseline originating Git revision")
    manifest = payload.get("source_snapshot_manifest", {})
    if not isinstance(manifest, dict) or not manifest:
        raise RuntimeError("missing baseline source manifest")
    if _manifest_digest(manifest) != environment["source_snapshot_digest"]:
        raise RuntimeError("baseline source manifest disagrees with its digest")
    actual: dict[str, Any] | None = None
    if require_current_source:
        repository_root = Path(__file__).resolve().parents[3]
        current_manifest = _source_manifest(repository_root / "src" / "cadrumo")
        if current_manifest != manifest:
            raise RuntimeError("baseline source snapshot is stale against the current source tree")
        actual = {" ".join(node.path): node for node in walk_live_command_tree(app)}
    recorded = dict(payload.get("commands", {}))
    if not recorded:
        raise RuntimeError("CLI baseline contains no dynamically enrolled commands")
    frozen_census = _load_frozen_census(payload, baseline_path=baseline_path)
    if set(recorded) != set(frozen_census):
        missing = sorted(set(frozen_census) - set(recorded))
        extra = sorted(set(recorded) - set(frozen_census))
        raise RuntimeError(f"frozen CLI baseline exact-set mismatch: missing={missing}, extra={extra}")
    if actual is not None and set(recorded) != set(actual):
        missing = sorted(set(actual) - set(recorded))
        stale = sorted(set(recorded) - set(actual))
        raise RuntimeError(f"stale CLI baseline: missing={missing}, removed={stale}")
    method = payload.get("method", {})
    expected_samples = method.get("samples_per_node")
    if not isinstance(expected_samples, int) or expected_samples < 3:
        raise RuntimeError("invalid baseline sample-count declaration")
    warmups = method.get("warmups_per_node")
    if not isinstance(warmups, int) or warmups < 1:
        raise RuntimeError("invalid baseline warmup declaration")
    control = payload.get("control", {})
    control_samples = control.get("samples", [])
    if method.get("control_samples") != len(control_samples) or len(control_samples) < 3:
        raise RuntimeError("baseline control-count declaration does not match observations")
    for sample in control_samples:
        _validate_observation_sample(sample)
    expected_control_distribution = {
        phase: _distribution(control_samples, phase) for phase in ("resolution", "invocation")
    }
    if control.get("distribution") != expected_control_distribution:
        raise RuntimeError("stored control distribution disagrees with raw observations")
    resolution_control = expected_control_distribution["resolution"]["median_seconds"]
    invocation_control = expected_control_distribution["invocation"]["median_seconds"]
    if resolution_control <= 0 or invocation_control <= 0:
        raise RuntimeError("baseline control median must be positive")

    for path, entry in recorded.items():
        node = actual[path] if actual is not None else None
        identity = frozen_census[path]
        if not isinstance(identity, dict) or any(
            entry.get(key) != identity.get(key) for key in ("kind", "loader_owner", "handler_owner", "policy")
        ):
            raise RuntimeError(f"frozen CLI baseline metadata mismatch: {path}")
        if node is not None and (
            entry["kind"] != node.kind
            or entry["loader_owner"] != node.loader_owner
            or entry["handler_owner"] != node.handler_owner
            or entry["policy"] != _policy_payload(node)
        ):
            raise RuntimeError(f"stale CLI baseline metadata: {path}")
        if entry["invocation_mode"] != "help-render" or entry["invocation_args"] != ["--help"]:
            raise RuntimeError(f"unsafe or dishonest CLI baseline invocation mode: {path}")
        samples = entry.get("samples", [])
        if len(samples) != expected_samples:
            raise RuntimeError(f"insufficient CLI baseline samples: {path}")
        for sample in samples:
            _validate_observation_sample(sample)
        expected_distribution = _summarise_samples(
            samples,
            control_resolution_median=resolution_control,
            control_invocation_median=invocation_control,
        )
        if entry.get("distribution") != expected_distribution:
            raise RuntimeError(f"stored CLI distribution disagrees with raw observations: {path}")
    ranked = payload.get("ranked_outliers", {})
    for phase in ("resolution", "invocation"):
        key = f"{phase}_by_control_ratio"
        expected_order = sorted(
            recorded,
            key=lambda path: (-recorded[path]["distribution"][phase]["control_ratio"], path),
        )
        if ranked.get(key) != expected_order:
            raise RuntimeError(f"ranked outlier order is stale or incomplete: {key}")
    expected_failures = sorted(
        path
        for path, entry in recorded.items()
        if any(
            observation["failure_kind"] != "none" or observation["exit_code"] != 0
            for sample in entry["samples"]
            for observation in (sample["resolution"], sample["invocation"])
        )
    )
    if payload.get("failures_and_timeouts") != expected_failures:
        raise RuntimeError("failure and timeout index is stale or incomplete")
    raw = _load_raw_evidence(payload, baseline_path=baseline_path)
    expected_summary = copy.deepcopy(raw)
    compact_existing_baseline(expected_summary)
    expected_summary["raw_evidence"] = payload["raw_evidence"]
    expected_summary["frozen_census_evidence"] = payload["frozen_census_evidence"]
    if expected_summary != payload:
        raise RuntimeError("compact baseline disagrees with content-addressed raw evidence")


def _validate_observation_sample(sample: Mapping[str, Any]) -> None:
    for phase in ("resolution", "invocation"):
        observation = sample.get(phase, {})
        seconds = observation.get("wall_seconds")
        if not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds < 0:
            raise RuntimeError(f"invalid {phase} latency observation")
        if observation.get("failure_kind") not in {
            "none",
            "timeout",
            "missing-envelope",
            "child-exception",
        }:
            raise RuntimeError(f"invalid {phase} failure kind")
        if not isinstance(observation.get("exit_code"), int):
            raise RuntimeError(f"invalid {phase} exit code")


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--check-fresh", action="store_true")
    parser.add_argument("--no-resume", action="store_true")
    return parser.parse_args(argv)


def _run_snapshot_worker(args: argparse.Namespace) -> int:
    """Run capture in a process whose entire Cadrumo import root is frozen."""
    repository_root = Path(__file__).resolve().parents[3]
    source = repository_root / "src" / "cadrumo"
    snapshot_parent = args.output.parent / ".baseline-source-snapshot"
    snapshot_package = snapshot_parent / "src" / "cadrumo"
    checkpoint_path = args.output.with_suffix(".partial.json")
    if checkpoint_path.exists():
        if not snapshot_package.exists():
            raise RuntimeError("baseline checkpoint exists without its source snapshot")
        snapshot_digest = _tree_digest(snapshot_package)
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        checkpoint_config = checkpoint.get("run_config", {})
        origin_git = str(checkpoint_config["originating_git_revision"])
        origin_dirty = str(checkpoint_config["originating_dirty_fingerprint"])
    else:
        if snapshot_parent.exists():
            resolved = snapshot_parent.resolve()
            if resolved.parent != args.output.parent.resolve():
                raise RuntimeError("refusing to replace source snapshot outside benchmark directory")
            shutil.rmtree(resolved)
        snapshot_digest = _copy_source_snapshot(source, snapshot_package)
        origin_git = _git_revision()
        origin_dirty = _worktree_fingerprint(repository_root)

    env = dict(os.environ)
    env[_SNAPSHOT_WORKER_ENV] = "1"
    env[_SNAPSHOT_DIGEST_ENV] = snapshot_digest
    env[_SNAPSHOT_ROOT_ENV] = str(snapshot_parent / "src")
    env[_ORIGIN_GIT_ENV] = origin_git
    env[_ORIGIN_DIRTY_ENV] = origin_dirty
    env[_GENERATOR_DIGEST_ENV] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    lock_path = repository_root / "uv.lock"
    env[_LOCK_DIGEST_ENV] = hashlib.sha256(lock_path.read_bytes()).hexdigest()
    env["PYTHONPATH"] = os.pathsep.join((str(snapshot_parent / "src"), str(repository_root)))
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(  # noqa: S603 - fixed interpreter/module; original CLI options only.
        [sys.executable, "-P", "-m", "dev.benchmarks.cli.capture_baseline", *sys.argv[1:]],
        cwd=repository_root,
        env=env,
        check=False,
    )
    if completed.returncode == 0:
        resolved = snapshot_parent.resolve()
        if resolved.parent != args.output.parent.resolve():
            raise RuntimeError("refusing to remove source snapshot outside benchmark directory")
        shutil.rmtree(resolved)
    return completed.returncode


def main(argv: Sequence[str] | None = None) -> int:
    """Capture a new baseline or check the committed evidence."""
    args = _parse_args(argv)
    if args.check or args.check_fresh:
        check_baseline(
            json.loads(args.output.read_text(encoding="utf-8")),
            baseline_path=args.output,
            require_current_source=args.check_fresh,
        )
        return 0
    if os.environ.get(_SNAPSHOT_WORKER_ENV) != "1":
        return _run_snapshot_worker(args)
    checkpoint_path = args.output.with_suffix(".partial.json")
    raw_payload = capture(
        warmups=args.warmups,
        samples=args.samples,
        timeout=args.timeout,
        workers=args.workers,
        checkpoint_path=checkpoint_path,
        resume=not args.no_resume,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = _publish_raw_and_summary(args.output, raw_payload)
    _write_json_atomic(args.output, payload)
    check_baseline(payload, baseline_path=args.output)
    checkpoint_path.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

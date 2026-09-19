"""Fresh-process performance observations for the installed Cadrumo CLI.

This module is test infrastructure, but deliberately drives the real CLI.  A
profile consists of two independent interpreters: one resolves the requested
command node through Click's live ``get_command`` protocol, and the other runs
the complete invocation through the public ``main`` entry point.  Keeping the
probes independent prevents resolution from warming imports or model schemas
for invocation.

The child writes its observation to a dedicated JSON file outside the observed
storage root.  CLI stdout and stderr therefore remain byte-for-byte operator
output and cannot corrupt the machine-readable measurement envelope.
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import types
import warnings
from collections import Counter
from collections.abc import Callable, Collection, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from statistics import median
from typing import Any, Literal, Self, cast

from cadrumo.tests.audited_process import run_audited_process

from ....tests.inventory import SRC_CADRUMO
from .subprocess_cli import as_text_completed_process, subprocess_cli_env

__all__ = [
    "CliPerformanceCalibration",
    "CliPerformanceObservation",
    "CliPerformanceProfile",
    "LatencyBudget",
    "LatencyBudgetResult",
    "LatencyDistribution",
    "PerformanceCalibrationPolicy",
    "calibrate_cli_path",
    "evaluate_latency_budget",
    "measure_resolution_costs",
    "profile_cli_invocation",
    "profile_cli_path",
    "verify_cli_profiler_instrumentation",
]

_CHILD_FLAG = "--cadrumo-cli-performance-child"
_STORAGE_MODULE_PREFIX = "cadrumo.adapters.persistence.storage"
IMPORT_FAMILY_PREFIXES: dict[str, tuple[str, ...]] = {
    "registry": ("cadrumo.domain.calculations.registry",),
    "crypto": ("cryptography", "argon2"),
    "custody": (f"{_STORAGE_MODULE_PREFIX}.custody",),
    "keyring": ("keyring", "cadrumo.adapters.persistence.storage.secret_store"),
    "storage": ("cadrumo.adapters.persistence", "sqlalchemy", "sqlite3"),
}
"""Module prefixes that identify each expensive capability family.

Public because the capability gates read the SAME table: a private copy in a
consumer drifts silently, and a family whose prefixes match nothing reports a
clean tree forever rather than failing. ``cadrumo.core.crypto`` was carried
here and matched no module in the tree; the family is covered by the two
third-party prefixes it also names.
"""


DIAGNOSTIC_ONLY_PATHS: frozenset[str] = frozenset({"logs", "logs/cadrumo.log"})
"""Root-relative paths the process-wide diagnostic log channel creates.

Opened by ``get_logger`` at module import, before any command is selected, so
it is a property of running the executable at all rather than of any one leaf
-- and it is plaintext diagnostics, never profile storage.
"""


def is_non_authoritative_artifact(path: str) -> bool:
    """Whether ``path`` is derived or coordination state rather than authority.

    A command declaring no side effects may still leave three kinds of file
    behind, and none of them is the profile-storage topology that the
    side-effect declaration is about:

    * the diagnostic log channel, opened before any command is chosen;
    * the ``cache`` tree -- registry verdicts and corpus text -- which is
      derived, rebuildable, and a byproduct of doing the work that was asked
      for; and
    * a ``.lock`` file, which is coordination rather than content, and which
      lock implementations deliberately do not unlink because deleting a lock
      races the next acquirer.

    Everything else under the root is authoritative state. ``blobs``,
    ``financial``, ``secrets``, ``submissions``, ``drafts`` and the encrypted
    database are NOT excused here, which is what keeps the side-effect gate
    able to fail on the defect it was written for.

    The side-effect taxonomy has no member meaning "writes a derived cache":
    ``local-state`` is bound to profile-scoped write ROUTING by the spec
    invariant, so declaring it on a command that writes a process-wide cache
    would assert something false about where its writes go. That gap is a real
    one and is recorded in the campaign audit rather than papered over by
    widening a declaration.
    """
    if path in DIAGNOSTIC_ONLY_PATHS:
        return True
    if path == "cache" or path.startswith("cache/"):
        return True
    return path.endswith(".lock")


_ENV_PREFIXES = ("AEAT_", "PYTEST_", "CADRUMO_")
_QUIET_CONTROL_PATH: tuple[str, ...] = ()
_QUIET_CONTROL_INVOCATION_ARGS = ("--version",)


@dataclass(frozen=True, slots=True)
class CliPerformanceObservation:
    """One cold-process resolution or invocation observation."""

    phase: Literal["resolution", "invocation", "instrumentation"]
    command_path: tuple[str, ...]
    child_pid: int
    wall_seconds: float
    imported_modules: tuple[str, ...]
    import_families: Mapping[str, tuple[str, ...]]
    pydantic_model_constructions: int
    filesystem_created: tuple[str, ...]
    filesystem_modified: tuple[str, ...]
    filesystem_deleted: tuple[str, ...]
    filesystem_operations: Mapping[str, int]
    storage_operation_calls: Mapping[str, int]
    initial_filesystem_digest: str
    observed_root_identity: str
    exit_code: int
    stdout: str
    stderr: str
    failure_kind: Literal["none", "timeout", "missing-envelope", "child-exception"]

    @classmethod
    def from_json(cls, payload: Mapping[str, Any], *, stdout: str, stderr: str) -> Self:
        """Validate and construct an observation from a child envelope."""
        phase = payload["phase"]
        if phase not in {"resolution", "invocation", "instrumentation"}:
            raise ValueError(f"unknown profiler phase: {phase!r}")
        failure_kind = payload.get("failure_kind", "none")
        if failure_kind not in {"none", "timeout", "missing-envelope", "child-exception"}:
            raise ValueError(f"unknown profiler failure kind: {failure_kind!r}")
        families = {
            str(name): tuple(str(module) for module in modules)
            for name, modules in dict(payload["import_families"]).items()
        }
        return cls(
            phase=phase,
            command_path=tuple(str(token) for token in payload["command_path"]),
            child_pid=int(payload["child_pid"]),
            wall_seconds=float(payload["wall_seconds"]),
            imported_modules=tuple(str(module) for module in payload["imported_modules"]),
            import_families=families,
            pydantic_model_constructions=int(payload["pydantic_model_constructions"]),
            filesystem_created=tuple(str(path) for path in payload["filesystem_created"]),
            filesystem_modified=tuple(str(path) for path in payload["filesystem_modified"]),
            filesystem_deleted=tuple(str(path) for path in payload["filesystem_deleted"]),
            filesystem_operations={
                str(name): int(count) for name, count in dict(payload["filesystem_operations"]).items()
            },
            storage_operation_calls={
                str(name): int(count) for name, count in dict(payload["storage_operation_calls"]).items()
            },
            initial_filesystem_digest=str(payload["initial_filesystem_digest"]),
            observed_root_identity=str(payload["observed_root_identity"]),
            exit_code=int(payload["exit_code"]),
            stdout=stdout,
            stderr=stderr,
            failure_kind=cast(
                "Literal['none', 'timeout', 'missing-envelope', 'child-exception']",
                failure_kind,
            ),
        )


@dataclass(frozen=True, slots=True)
class CliPerformanceProfile:
    """Independent cold observations for one live CLI path."""

    resolution: CliPerformanceObservation
    invocation: CliPerformanceObservation


@dataclass(frozen=True, slots=True)
class PerformanceCalibrationPolicy:
    """Noise-resistant sampling policy for quiet-runner calibration."""

    warmup_runs: int = 1
    sample_count: int = 5

    def __post_init__(self) -> None:
        if self.warmup_runs < 1:
            raise ValueError("calibration requires at least one warmup run")
        if self.sample_count < 3:
            raise ValueError("calibration requires at least three measured samples")


@dataclass(frozen=True, slots=True)
class LatencyDistribution:
    """A measured latency distribution summarized without a lucky-sample pass."""

    samples_seconds: tuple[float, ...]
    median_seconds: float
    median_absolute_deviation_seconds: float

    @classmethod
    def from_samples(cls, samples: Sequence[float]) -> Self:
        values = tuple(float(value) for value in samples)
        if len(values) < 3:
            raise ValueError("latency distribution requires at least three samples")
        if any(not isfinite(value) or value < 0 for value in values):
            raise ValueError("latency samples must be finite and non-negative")
        centre = float(median(values))
        dispersion = float(median(abs(value - centre) for value in values))
        return cls(values, centre, dispersion)


@dataclass(frozen=True, slots=True)
class CliPerformanceCalibration:
    """Paired command and quiet-control distributions from fresh processes."""

    command_profiles: tuple[CliPerformanceProfile, ...]
    control_profiles: tuple[CliPerformanceProfile, ...]
    measured_pair_orders: tuple[Literal["command-first", "control-first"], ...]
    command_resolution: LatencyDistribution
    command_invocation: LatencyDistribution
    control_resolution: LatencyDistribution
    control_invocation: LatencyDistribution

    @property
    def resolution_control_ratio(self) -> float:
        """Median command resolution divided by quiet-control resolution."""
        return self.command_resolution.median_seconds / self.control_resolution.median_seconds

    @property
    def invocation_control_ratio(self) -> float:
        """Median command invocation divided by quiet-control invocation."""
        return self.command_invocation.median_seconds / self.control_invocation.median_seconds


@dataclass(frozen=True, slots=True)
class LatencyBudget:
    """Absolute and quiet-control-relative limits for one latency distribution."""

    maximum_median_seconds: float | None = None
    maximum_control_ratio: float | None = None

    def __post_init__(self) -> None:
        if self.maximum_median_seconds is None and self.maximum_control_ratio is None:
            raise ValueError("latency budget requires an absolute or ratio limit")
        for value in (self.maximum_median_seconds, self.maximum_control_ratio):
            if value is not None and (not isfinite(value) or value <= 0):
                raise ValueError("latency budget limits must be finite and positive")


@dataclass(frozen=True, slots=True)
class LatencyBudgetResult:
    """Typed budget verdict retaining actionable threshold breaches."""

    passed: bool
    observed_median_seconds: float
    control_ratio: float | None
    violations: tuple[Literal["absolute-median", "control-ratio"], ...]
    outlier_samples_seconds: tuple[float, ...]


def evaluate_latency_budget(
    observed: LatencyDistribution,
    budget: LatencyBudget,
    *,
    control: LatencyDistribution | None = None,
) -> LatencyBudgetResult:
    """Evaluate median-based absolute and relative limits without hiding the tail."""
    violations: list[Literal["absolute-median", "control-ratio"]] = []
    thresholds: list[float] = []
    ratio: float | None = None
    if budget.maximum_median_seconds is not None:
        thresholds.append(budget.maximum_median_seconds)
        if observed.median_seconds > budget.maximum_median_seconds:
            violations.append("absolute-median")
    if budget.maximum_control_ratio is not None:
        if control is None:
            raise ValueError("a control distribution is required for a ratio budget")
        if control.median_seconds <= 0:
            raise ValueError("control median must be positive for a ratio budget")
        ratio = observed.median_seconds / control.median_seconds
        thresholds.append(control.median_seconds * budget.maximum_control_ratio)
        if ratio > budget.maximum_control_ratio:
            violations.append("control-ratio")
    strictest_threshold = min(thresholds)
    return LatencyBudgetResult(
        passed=not violations,
        observed_median_seconds=observed.median_seconds,
        control_ratio=ratio,
        violations=tuple(violations),
        outlier_samples_seconds=tuple(value for value in observed.samples_seconds if value > strictest_threshold),
    )


def calibrate_cli_path(
    command_path: Sequence[str],
    *,
    invocation_args: Sequence[str] = (),
    storage_root: Path | None = None,
    extra_env: Mapping[str, str] | None = None,
    stdin_payload: str | None = None,
    timeout: float = 120.0,
    policy: PerformanceCalibrationPolicy | None = None,
) -> CliPerformanceCalibration:
    """Measure a command beside a quiet ``--version`` control in fresh processes."""
    calibration_policy = policy or PerformanceCalibrationPolicy()
    command_profiles: list[CliPerformanceProfile] = []
    control_profiles: list[CliPerformanceProfile] = []
    measured_pair_orders: list[Literal["command-first", "control-first"]] = []
    for index in range(calibration_policy.warmup_runs + calibration_policy.sample_count):

        def measure_command() -> CliPerformanceProfile:
            return profile_cli_path(
                command_path,
                invocation_args=invocation_args,
                storage_root=storage_root,
                extra_env=extra_env,
                stdin_payload=stdin_payload,
                timeout=timeout,
            )

        def measure_control() -> CliPerformanceProfile:
            return profile_cli_path(
                _QUIET_CONTROL_PATH,
                invocation_args=_QUIET_CONTROL_INVOCATION_ARGS,
                storage_root=storage_root,
                extra_env=extra_env,
                timeout=timeout,
            )

        pair_order: Literal["command-first", "control-first"]
        if index % 2 == 0:
            pair_order = "command-first"
            command, control = measure_command(), measure_control()
        else:
            pair_order = "control-first"
            control, command = measure_control(), measure_command()
        _require_successful_profile(command, label="command")
        _require_successful_profile(control, label="control")
        if index >= calibration_policy.warmup_runs:
            command_profiles.append(command)
            control_profiles.append(control)
            measured_pair_orders.append(pair_order)
    return CliPerformanceCalibration(
        command_profiles=tuple(command_profiles),
        control_profiles=tuple(control_profiles),
        measured_pair_orders=tuple(measured_pair_orders),
        command_resolution=_phase_distribution(command_profiles, "resolution"),
        command_invocation=_phase_distribution(command_profiles, "invocation"),
        control_resolution=_phase_distribution(control_profiles, "resolution"),
        control_invocation=_phase_distribution(control_profiles, "invocation"),
    )


def _require_successful_profile(profile: CliPerformanceProfile, *, label: str) -> None:
    for observation in (profile.resolution, profile.invocation):
        if observation.failure_kind != "none" or observation.exit_code != 0:
            raise RuntimeError(
                f"{label} {observation.phase} observation failed: "
                f"failure_kind={observation.failure_kind}, exit_code={observation.exit_code}"
            )


def _phase_distribution(
    profiles: Sequence[CliPerformanceProfile], phase: Literal["resolution", "invocation"]
) -> LatencyDistribution:
    return LatencyDistribution.from_samples(tuple(getattr(profile, phase).wall_seconds for profile in profiles))


def profile_cli_path(
    command_path: Sequence[str],
    *,
    invocation_args: Sequence[str] = (),
    storage_root: Path | None = None,
    extra_env: Mapping[str, str] | None = None,
    stdin_payload: str | None = None,
    timeout: float = 120.0,
) -> CliPerformanceProfile:
    """Profile resolution and invocation of an arbitrary CLI argument vector.

    Args:
        command_path: Exact live command tokens after the ``aeat`` executable.
            Options and positional parameter values do not belong here.
        invocation_args: Synthetic, non-secret options and positional values
            appended only for the real invocation. Values are transported
            through a user-private, permission-restricted request directory,
            deleted by the child immediately after reading, and never returned
            in the observation. Performance probes must never carry real
            passwords, recovery material, access tokens, or taxpayer data.
        storage_root: Empty or pre-populated root to observe. When omitted, a
            private temporary root is created for this profile.
        extra_env: Explicit additional child environment. Cadrumo, AEAT, and
            pytest variables are stripped from the inherited environment first.
        stdin_payload: Optional text delivered to the real invocation.
        timeout: Per-child deterministic wall timeout in seconds.

    Returns:
        The two independent, structured cold-process observations.
    """
    if timeout <= 0:
        raise ValueError("profiler timeout must be positive")
    with _observed_root(storage_root) as root:
        return _profile_with_root(
            tuple(str(token) for token in command_path),
            tuple(str(token) for token in invocation_args),
            root,
            extra_env=extra_env,
            stdin_payload=stdin_payload,
            timeout=timeout,
        )


def profile_cli_invocation(
    command_path: Sequence[str],
    *,
    invocation_args: Sequence[str] = (),
    storage_root: Path | None = None,
    extra_env: Mapping[str, str] | None = None,
    stdin_payload: str | None = None,
    timeout: float = 120.0,
) -> CliPerformanceObservation:
    """Observe only the real invocation of a CLI argument vector.

    The invocation half of :func:`profile_cli_path`, for a caller that never
    reads the resolution observation: it starts one cold child instead of two.
    Arguments mean exactly what they mean there.
    """
    if timeout <= 0:
        raise ValueError("profiler timeout must be positive")
    with (
        _observed_root(storage_root) as root,
        tempfile.TemporaryDirectory(prefix="cadrumo-cli-cold-roots-") as directory,
    ):
        return _invocation_in_clone(
            tuple(str(token) for token in command_path),
            tuple(str(token) for token in invocation_args),
            root,
            Path(directory),
            extra_env=extra_env,
            stdin_payload=stdin_payload,
            timeout=timeout,
        )


@contextmanager
def _observed_root(storage_root: Path | None) -> Iterator[Path]:
    """Yield the root to observe: the caller's, resolved, or a private temporary one."""
    if storage_root is None:
        with tempfile.TemporaryDirectory(prefix="cadrumo-cli-profile-") as directory:
            yield Path(directory)
        return
    storage_root.mkdir(parents=True, exist_ok=True)
    yield storage_root.resolve()


def _invocation_in_clone(
    command_path: tuple[str, ...],
    invocation_args: tuple[str, ...],
    storage_root: Path,
    cold_parent: Path,
    *,
    extra_env: Mapping[str, str] | None,
    stdin_payload: str | None,
    timeout: float,
) -> CliPerformanceObservation:
    invocation_root = cold_parent / "invocation"
    _clone_storage_root(storage_root, invocation_root)
    return _run_child(
        "invocation",
        command_path,
        invocation_args,
        invocation_root,
        extra_env=extra_env,
        stdin_payload=stdin_payload,
        timeout=timeout,
    )


def _profile_with_root(
    command_path: tuple[str, ...],
    invocation_args: tuple[str, ...],
    storage_root: Path,
    *,
    extra_env: Mapping[str, str] | None,
    stdin_payload: str | None,
    timeout: float,
) -> CliPerformanceProfile:
    with tempfile.TemporaryDirectory(prefix="cadrumo-cli-cold-roots-") as directory:
        cold_parent = Path(directory)
        resolution_root = cold_parent / "resolution"
        _clone_storage_root(storage_root, resolution_root)
        resolution = _run_child(
            "resolution",
            command_path,
            (),
            resolution_root,
            extra_env=extra_env,
            timeout=timeout,
        )
        invocation = _invocation_in_clone(
            command_path,
            invocation_args,
            storage_root,
            cold_parent,
            extra_env=extra_env,
            stdin_payload=stdin_payload,
            timeout=timeout,
        )
        return CliPerformanceProfile(resolution=resolution, invocation=invocation)


def _clone_storage_root(source: Path, target: Path) -> None:
    """Clone one starting state without following adversarial links."""
    if source.exists():
        shutil.copytree(source, target, symlinks=True)
    else:
        target.mkdir(parents=True)


def _run_child(
    phase: Literal["resolution", "invocation", "instrumentation"],
    command_path: tuple[str, ...],
    invocation_args: tuple[str, ...],
    storage_root: Path,
    *,
    extra_env: Mapping[str, str] | None,
    timeout: float,
    stdin_payload: str | None = None,
) -> CliPerformanceObservation:
    with tempfile.TemporaryDirectory(prefix="cadrumo-cli-envelope-") as directory:
        result_path = Path(directory) / "observation.json"
        private_directory = Path(directory)
        private_directory.chmod(0o700)
        request_path = private_directory / "request.json"
        request_path.write_text(
            json.dumps(
                {
                    "phase": phase,
                    "command_path": command_path,
                    "invocation_args": invocation_args,
                    "storage_root": str(storage_root),
                    "result_path": str(result_path),
                }
            ),
            encoding="utf-8",
            newline="\n",
        )
        request_path.chmod(0o600)
        env_extra = {
            **dict(extra_env or {}),
            "CADRUMO_LOCAL_STORAGE_ROOT": str(storage_root),
            "CADRUMO_SECRET_STORE_DIR": str(storage_root / "secret-store"),
            "CADRUMO_OUTPUT_LANGUAGE": "en",
        }
        started = time.perf_counter()
        try:
            completed = as_text_completed_process(
                run_audited_process(
                    [
                        sys.executable,
                        "-m",
                        "cadrumo.entrypoints.cli.tests.cli_performance",
                        _CHILD_FLAG,
                        str(request_path),
                    ],
                    cwd=SRC_CADRUMO.parent,
                    env=subprocess_cli_env(strip_prefixes=_ENV_PREFIXES, extra=env_extra),
                    input=stdin_payload,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    capture_output=True,
                    check=False,
                    timeout=timeout,
                ),
            )
        except subprocess.TimeoutExpired:
            return _failed_observation(
                phase,
                command_path,
                wall_seconds=time.perf_counter() - started,
                exit_code=124,
                failure_kind="timeout",
            )
        if not result_path.is_file():
            return _failed_observation(
                phase,
                command_path,
                wall_seconds=time.perf_counter() - started,
                exit_code=completed.returncode,
                failure_kind="missing-envelope",
            )
        raw = json.loads(result_path.read_text(encoding="utf-8"))
        return CliPerformanceObservation.from_json(raw, stdout=completed.stdout, stderr=completed.stderr)


def _failed_observation(
    phase: Literal["resolution", "invocation", "instrumentation"],
    command_path: tuple[str, ...],
    *,
    wall_seconds: float,
    exit_code: int,
    failure_kind: Literal["timeout", "missing-envelope"],
) -> CliPerformanceObservation:
    """Return a secret-free structured outcome when no child envelope survives."""
    return CliPerformanceObservation(
        phase=phase,
        command_path=command_path,
        child_pid=-1,
        wall_seconds=wall_seconds,
        imported_modules=(),
        import_families={family: () for family in IMPORT_FAMILY_PREFIXES},
        pydantic_model_constructions=0,
        filesystem_created=(),
        filesystem_modified=(),
        filesystem_deleted=(),
        filesystem_operations={},
        storage_operation_calls={},
        initial_filesystem_digest="",
        observed_root_identity="",
        exit_code=exit_code,
        stdout="",
        stderr="",
        failure_kind=failure_kind,
    )


def verify_cli_profiler_instrumentation(*, timeout: float = 120.0) -> CliPerformanceObservation:
    """Run planted real operations in a fresh child to prove every counter bites."""
    with tempfile.TemporaryDirectory(prefix="cadrumo-cli-instrumentation-") as directory:
        root = Path(directory) / "storage"
        root.mkdir()
        return _run_child("instrumentation", (), (), root, extra_env=None, timeout=timeout)


def _snapshot(root: Path) -> dict[str, tuple[int, int, str]]:
    """Return path metadata and content fingerprints without following links."""
    if not root.exists():
        return {}
    entries: dict[str, tuple[int, int, str]] = {}
    pending = [root]
    while pending:
        directory = pending.pop()
        try:
            children = tuple(os.scandir(directory))
        except OSError:
            continue
        for entry in children:
            relative = Path(entry.path).relative_to(root).as_posix()
            try:
                stat = entry.stat(follow_symlinks=False)
            except OSError:
                continue
            digest = ""
            if entry.is_file(follow_symlinks=False):
                try:
                    digest = hashlib.sha256(Path(entry.path).read_bytes()).hexdigest()
                except OSError:
                    digest = "<unreadable>"
            entries[relative] = (stat.st_size, stat.st_mtime_ns, digest)
            if entry.is_dir(follow_symlinks=False):
                pending.append(Path(entry.path))
    return entries


def _filesystem_delta(
    before: Mapping[str, tuple[int, int, str]],
    after: Mapping[str, tuple[int, int, str]],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    before_paths = set(before)
    after_paths = set(after)
    created = tuple(sorted(after_paths - before_paths))
    deleted = tuple(sorted(before_paths - after_paths))
    modified = tuple(sorted(path for path in before_paths & after_paths if before[path] != after[path]))
    return created, modified, deleted


def _snapshot_digest(snapshot: Mapping[str, tuple[int, int, str]]) -> str:
    """Fingerprint a starting tree without embedding its absolute location."""
    stable = [(path, size, content_digest) for path, (size, _mtime, content_digest) in sorted(snapshot.items())]
    return hashlib.sha256(json.dumps(stable, separators=(",", ":")).encode()).hexdigest()


def _child_main(payload: Mapping[str, Any]) -> int:
    phase = str(payload["phase"])
    command_path = tuple(str(token) for token in payload["command_path"])
    invocation_args = tuple(str(token) for token in payload["invocation_args"])
    storage_root = Path(str(payload["storage_root"])).resolve()
    result_path = Path(str(payload["result_path"]))
    before_files = _snapshot(storage_root)
    initial_filesystem_digest = _snapshot_digest(before_files)
    observed_root_identity = hashlib.sha256(os.fsencode(storage_root)).hexdigest()
    before_modules = set(sys.modules)
    filesystem_operations: Counter[str] = Counter()
    storage_operations: Counter[str] = Counter()
    pydantic_constructions = 0
    observing_filesystem = True

    def audit(event: str, args: tuple[object, ...]) -> None:
        if not observing_filesystem:
            return
        if event not in {"open", "os.mkdir", "os.remove", "os.rename", "os.rmdir", "os.scandir"} or not args:
            return
        raw_path = args[0]
        if not isinstance(raw_path, (str, os.PathLike)):
            return
        try:
            path = Path(raw_path).resolve(strict=False)
            path.relative_to(storage_root)
        except (OSError, TypeError, ValueError):
            return
        operation = event
        if event == "open" and len(args) > 1:
            mode = args[1]
            native_flags = args[2] if len(args) > 2 else None
            writes = (
                (isinstance(mode, str) and any(flag in mode for flag in "wax+"))
                or (
                    isinstance(mode, int)
                    and bool(mode & (os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC))
                )
                or (
                    isinstance(native_flags, int)
                    and bool(native_flags & (os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC))
                )
            )
            operation = "open.write" if writes else "open.read"
        filesystem_operations[operation] += 1

    def profiler(frame: Any, event: str, arg: object) -> None:
        nonlocal pydantic_constructions
        if event == "c_call":
            qualname = str(getattr(arg, "__qualname__", ""))
            if qualname == "SchemaValidator.validate_python":
                pydantic_constructions += 1
            return
        if event != "call":
            return
        module = str(frame.f_globals.get("__name__", ""))
        name = str(frame.f_code.co_name)
        # A class statement executes its body as a frame named after the class,
        # so an import would otherwise read as a call to the class.
        is_class_body = not frame.f_code.co_flags & inspect.CO_NEWLOCALS
        if module.startswith(_STORAGE_MODULE_PREFIX) and name != "<module>" and not is_class_body:
            storage_operations[f"{module}:{frame.f_code.co_qualname}"] += 1

    sys.addaudithook(audit)
    sys.setprofile(profiler)
    exit_code = 0
    failure_kind = "none"
    started = time.perf_counter()
    try:
        if phase == "resolution":
            _resolve_cli_path(command_path)
        elif phase == "invocation":
            exit_code = _invoke_cli((*command_path, *invocation_args))
        elif phase == "instrumentation":
            _run_instrumentation_probe(storage_root)
        else:
            raise ValueError(f"unknown profiler phase: {phase!r}")
    except SystemExit as exc:
        exit_code = int(exc.code or 0) if isinstance(exc.code, int | None) else 1
    except BaseException:
        exit_code = 1
        failure_kind = "child-exception"
        raise
    finally:
        observing_filesystem = False
        wall_seconds = time.perf_counter() - started
        sys.setprofile(None)
        imported_modules = tuple(sorted(name for name in set(sys.modules) - before_modules if name))
        after_files = _snapshot(storage_root)
        created, modified, deleted = _filesystem_delta(before_files, after_files)
        families = {
            family: tuple(name for name in imported_modules if name.startswith(prefixes))
            for family, prefixes in IMPORT_FAMILY_PREFIXES.items()
        }
        observation = {
            "phase": phase,
            "command_path": command_path,
            "child_pid": os.getpid(),
            "wall_seconds": wall_seconds,
            "imported_modules": imported_modules,
            "import_families": families,
            "pydantic_model_constructions": pydantic_constructions,
            "filesystem_created": created,
            "filesystem_modified": modified,
            "filesystem_deleted": deleted,
            "filesystem_operations": dict(sorted(filesystem_operations.items())),
            "storage_operation_calls": dict(sorted(storage_operations.items())),
            "initial_filesystem_digest": initial_filesystem_digest,
            "observed_root_identity": observed_root_identity,
            "exit_code": exit_code,
            "failure_kind": failure_kind,
        }
        result_path.write_text(json.dumps(observation, sort_keys=True), encoding="utf-8", newline="\n")
    return exit_code


def _resolve_cli_path(command_path: tuple[str, ...]) -> None:
    from typer._click.core import Context
    from typer.main import get_command

    from ..main import app

    command = get_command(app)
    for token in command_path:
        getter = getattr(command, "get_command", None)
        if not callable(getter):
            raise LookupError(f"CLI path traverses through leaf before {token!r}")
        context = Context(command, info_name=command.name)
        try:
            child = getter(context, token)
        finally:
            context.close()
        if child is None:
            raise LookupError(f"unknown CLI command token: {token!r}")
        command = child


_RESOLUTION_REEXECUTED_PREFIX = "cadrumo.entrypoints"
"""Cadrumo modules re-executed for every path of a batched resolution measurement.

The entrypoint layer builds Typer objects that Typer mutates in place and caches
compiled command apps, so a retained copy would answer a later path from the
first path's state. The inner layers are retained once bootstrapped: batched
module sets for every budgeted node were compared, name for name, with sets
taken from one fresh interpreter per node, and agreed.
"""


_MISSING_BINDING = object()

type _Container = dict[Any, Any] | list[Any] | set[Any]


@dataclass(frozen=True, slots=True)
class _RetainedModuleState:
    """One retained module's globals as the bootstrap left them.

    A retained module can memoise work that imported modules the reset later
    drops -- a lazily loaded catalogue kept in a module global, a filled
    ``functools`` cache, a registry dict. Left in place, the next path finds the
    memo, never imports those modules again, and is measured light. Rebinding
    the globals, refilling the plain containers and clearing the caches returns
    every path to the state the first one started from.
    """

    namespace: dict[str, object]
    bindings: dict[str, object]
    containers: tuple[tuple[_Container, _Container], ...]
    caches: tuple[Callable[[], object], ...]


def _capture_module_state(name: str, module: types.ModuleType) -> _RetainedModuleState:
    namespace = vars(module)
    # Submodule attributes belong to the module drop, which deletes them with
    # the submodule; restoring one would let ``from package import submodule``
    # return a dropped module without importing it.
    bindings = {key: value for key, value in namespace.items() if not isinstance(value, types.ModuleType)}
    containers: list[tuple[_Container, _Container]] = []
    caches: list[Callable[[], object]] = []
    for value in bindings.values():
        if isinstance(value, dict | list | set) and type(value) in {dict, list, set}:
            containers.append((value, value.copy()))
            continue
        cache_clear = getattr(value, "cache_clear", None)
        if callable(cache_clear) and getattr(value, "__module__", None) == name:
            caches.append(cache_clear)
    return _RetainedModuleState(
        namespace=namespace,
        bindings=bindings,
        containers=tuple(containers),
        caches=tuple(caches),
    )


def _restore_module_state(state: _RetainedModuleState) -> None:
    namespace = state.namespace
    added = [
        key for key, value in namespace.items() if key not in state.bindings and not isinstance(value, types.ModuleType)
    ]
    for key in added:
        del namespace[key]
    for key, value in state.bindings.items():
        if namespace.get(key, _MISSING_BINDING) is not value:
            namespace[key] = value
    for live, saved in state.containers:
        if isinstance(live, list) and isinstance(saved, list):
            live[:] = saved
        elif isinstance(live, dict) and isinstance(saved, dict):
            live.clear()
            live.update(saved)
        elif isinstance(live, set) and isinstance(saved, set):
            live &= saved
            live |= saved
    for cache_clear in state.caches:
        cache_clear()


@dataclass(frozen=True, slots=True)
class _InterpreterBaseline:
    """Process-global state a resolution may change and a reset must restore."""

    probe_modules: frozenset[str]
    retained_modules: frozenset[str]
    record_factory: Callable[..., logging.LogRecord]
    loggers: dict[str, logging.Logger | logging.PlaceHolder]
    root_handlers: tuple[logging.Handler, ...]
    root_filters: tuple[Any, ...]
    root_level: int
    environ: dict[str, str]
    meta_path: tuple[Any, ...]
    path_hooks: tuple[Callable[[str], Any], ...]
    path: tuple[str, ...]
    module_states: tuple[_RetainedModuleState, ...]


def _cadrumo_modules() -> frozenset[str]:
    return frozenset(name for name in sys.modules if name.startswith("cadrumo"))


def _capture_baseline(probe_modules: frozenset[str]) -> _InterpreterBaseline:
    retained = frozenset(
        name
        for name in _cadrumo_modules()
        if name in probe_modules or not name.startswith(_RESOLUTION_REEXECUTED_PREFIX)
    )
    return _InterpreterBaseline(
        probe_modules=probe_modules,
        retained_modules=retained,
        record_factory=logging.getLogRecordFactory(),
        loggers=dict(logging.Logger.manager.loggerDict),
        root_handlers=tuple(logging.root.handlers),
        root_filters=tuple(logging.root.filters),
        root_level=logging.root.level,
        environ=dict(os.environ),
        meta_path=tuple(sys.meta_path),
        path_hooks=tuple(sys.path_hooks),
        path=tuple(sys.path),
        module_states=tuple(
            _capture_module_state(name, module)
            for name in sorted(retained)
            if isinstance(module := sys.modules.get(name), types.ModuleType)
        ),
    )


def _restore_baseline(baseline: _InterpreterBaseline) -> None:
    for name in _cadrumo_modules() - baseline.retained_modules:
        del sys.modules[name]
        # A retained package keeps its submodule as an attribute, and
        # ``from package import submodule`` would return it without importing.
        parent, _, child = name.rpartition(".")
        owner = sys.modules.get(parent)
        if owner is not None and child in vars(owner):
            delattr(owner, child)
    # Importing the CLI installs a chained record factory whose first log record
    # imports observability modules; a stale chain would charge them to a later path.
    logging.setLogRecordFactory(baseline.record_factory)
    logging.Logger.manager.loggerDict.clear()
    logging.Logger.manager.loggerDict.update(baseline.loggers)
    for handler in logging.root.handlers:
        if handler not in baseline.root_handlers:
            handler.close()
    logging.root.handlers[:] = baseline.root_handlers
    logging.root.filters[:] = baseline.root_filters
    logging.root.setLevel(baseline.root_level)
    os.environ.clear()
    os.environ.update(baseline.environ)
    sys.meta_path[:] = baseline.meta_path
    sys.path_hooks[:] = baseline.path_hooks
    sys.path[:] = baseline.path
    for state in baseline.module_states:
        _restore_module_state(state)


def measure_resolution_costs(
    command_paths: Sequence[Sequence[str]],
    *,
    record_names_for: Collection[str] = (),
) -> list[dict[str, object]]:
    """Measure the Cadrumo modules each path loads, as a fresh interpreter would.

    Meant to run first thing in a dedicated interpreter. The CLI is bootstrapped
    once; before each path the entrypoint layer and everything loaded since the
    bootstrap is dropped and the process-global import and logging state is
    restored. A path that finds any leftover module is reported as an error
    rather than measured, so a broken reset cannot pass as a small count.

    Args:
        command_paths: The paths to measure, in order.
        record_names_for: ``/``-joined paths whose records also carry the
            sorted module names, so a disagreement can be reported as a diff.

    Returns:
        One record per requested path, in order: ``path``, ``modules`` (the
        Cadrumo module count), ``digest`` (a fingerprint of the sorted module
        names, for comparing against a fresh interpreter), ``names`` (those
        names for a path in ``record_names_for``, else ``None``) and ``error``.
    """
    probe_modules = _cadrumo_modules()
    from typer.main import get_command

    from ..main import app

    get_command(app)
    baseline = _capture_baseline(probe_modules)
    _restore_baseline(baseline)
    records: list[dict[str, object]] = []
    for command_path in command_paths:
        path = tuple(str(token) for token in command_path)
        record: dict[str, object] = {
            "path": "/".join(path),
            "modules": None,
            "digest": None,
            "names": None,
            "error": None,
        }
        leftover = sorted(_cadrumo_modules() ^ baseline.retained_modules)
        if leftover:
            record["error"] = f"interpreter was not reset before this path; differing modules: {leftover[:10]}"
        else:
            try:
                with warnings.catch_warnings():
                    _resolve_cli_path(path)
            except Exception:
                record["error"] = traceback.format_exc()
            else:
                loaded = sorted(_cadrumo_modules())
                record["modules"] = len(loaded)
                record["digest"] = hashlib.sha256("\n".join(loaded).encode()).hexdigest()
                if record["path"] in record_names_for:
                    record["names"] = loaded
        records.append(record)
        _restore_baseline(baseline)
    return records


def _invoke_cli(argv: tuple[str, ...]) -> int:
    from ..main import main

    sys.argv = ["aeat", *argv]
    try:
        result = main()
    except SystemExit as exc:
        return int(exc.code or 0) if isinstance(exc.code, int | None) else 1
    return int(result) if isinstance(result, int) else 0


def _run_instrumentation_probe(storage_root: Path) -> None:
    """Exercise real aliased/native boundaries for the permanent bite test."""
    from os import close as aliased_close
    from os import open as aliased_open
    from pathlib import Path as AliasedPath

    from pydantic import BaseModel

    from ....adapters.persistence.storage.path_safety import safe_repository_id as aliased_storage_call

    class ProbeModel(BaseModel):
        value: int

    ProbeModel(value=1)
    ProbeModel.model_validate({"value": 2})
    aliased_storage_call("probe", context="cli_performance")
    AliasedPath(storage_root / "aliased-pathlib.txt").write_text("probe", encoding="utf-8", newline="\n")
    descriptor = aliased_open(storage_root / "aliased-native.bin", os.O_CREAT | os.O_WRONLY, 0o600)
    aliased_close(descriptor)


def _parse_child_payload() -> Mapping[str, Any] | None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(_CHILD_FLAG, dest="payload")
    namespace, unknown = parser.parse_known_args()
    if namespace.payload is None:
        return None
    if unknown:
        raise ValueError(f"unexpected profiler child arguments: {unknown!r}")
    request_path = Path(namespace.payload)
    decoded = json.loads(request_path.read_text(encoding="utf-8"))
    request_path.unlink(missing_ok=True)
    if not isinstance(decoded, dict):
        raise TypeError("profiler child payload must be a JSON object")
    return decoded


if __name__ == "__main__":
    child_payload = _parse_child_payload()
    if child_payload is None:
        raise SystemExit("cli_performance is a library; use profile_cli_path()")
    raise SystemExit(_child_main(child_payload))

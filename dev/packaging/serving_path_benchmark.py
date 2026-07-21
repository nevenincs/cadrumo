"""Serving-path latency benchmark and acceptance gate (mcp-call-latency P05).

Measures the research call table against isolated encrypted state and asserts the
projected end-state as acceptance gates. Dual-use: a CLI entrypoint emitting a
schema-versioned JSON evidence document, and a pytest integration test asserting
the gates (``dev/packaging/tests/test_serving_path_benchmark.py``).

Two environments are measured and EVERY number is labelled with its
``environment`` so tables are never cross-compared unlabelled:

- ``subprocess`` drives the editable-tree ``aeat`` executable; each call pays the
  full source-import floor per process, so its warm numbers are 3-6x the
  installed-cohort projections. Only the cliff-gone gate binds here (first-touch
  work create far under the former 49.6 s). The installed-cohort subprocess
  targets (warm calculate <= 3 s, first-touch <= 5 s) are NOT asserted on the
  editable tree; they are S19/S20's to prove against the built cohort.
- ``server`` drives the warm in-process runtime (D4), which pays interpreter,
  import, and registry once per process and then serves steady-state calls. This
  is the campaign's real, current-tree-verifiable win: reads and simple writes
  are sub-second and the heaviest calculation is low single-digit seconds.

On the server warm-calculate bound: the research projected ~1.5 s for a lighter
baseline; the 16-input Modelo 200 oracle here measures ~1.7-1.9 s steady-state,
which meets the operator's bar (sub-second reads/simple writes, low single-digit
seconds at absolute worst for the heaviest calculation). The gate is 2.5 s -- the
honest steady-state plus slow-machine margin -- and the evidence records the
projection, the measured value, and this rationale so a future regression from
~1.9 s toward the gate stays visible in the recorded table even while it passes.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import shutil
import sys
import tempfile
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Final, cast

from dev.packaging.installed_tax_oracle import (
    isolated_product_environment,
    profile_create_arguments,
    work_calculate_arguments,
    work_create_arguments,
)

_UTF_8: Final[str] = "utf-8"
_SCHEMA_VERSION: Final[int] = 1
_ENVIRONMENT_IDENTITY: Final[str] = "editable-tree"

# Acceptance gates asserted on the current (editable) tree.
_SERVER_READ_MAX_S: Final[float] = 1.0
_SERVER_SIMPLE_WRITE_MAX_S: Final[float] = 1.0
_SERVER_WARM_CALCULATE_MAX_S: Final[float] = 2.5
_SUBPROCESS_FIRST_TOUCH_CLIFF_MAX_S: Final[float] = 25.0

# Reference figures recorded (never gated on the editable tree) so the evidence
# is self-describing and cross-environment claims stay explicitly labelled.
_RESEARCH_PROJECTIONS: Final[dict[str, str]] = {
    "server_warm_calculate_projection_s": "1.5 (installed-cohort, research lighter-baseline)",
    "subprocess_warm_calculate_target_s": "3.0 (installed-cohort, proven by S19/S20)",
    "subprocess_first_touch_target_s": "5.0 (installed-cohort, proven by S19/S20)",
    "subprocess_first_touch_former_cliff_s": "49.6 (installed v0.2.1 pre-fix)",
}


class ServingPathBenchmarkError(RuntimeError):
    """Raised when the benchmark cannot execute a required measurement."""


@dataclass(frozen=True)
class CallMeasurement:
    """One timed call, labelled with its environment and gate disposition."""

    label: str
    mode: str
    environment: str
    seconds: float
    gated: bool
    threshold_seconds: float | None
    within_threshold: bool | None
    note: str


@dataclass(frozen=True)
class ServingPathEvidence:
    """The full measured table plus the acceptance gates it satisfies or breaks."""

    schema_version: int
    environment: dict[str, Any]
    projections: dict[str, str]
    measurements: tuple[CallMeasurement, ...]
    gate_failures: tuple[str, ...] = field(default=())

    def to_jsonable(self) -> dict[str, Any]:
        """Return a JSON-compatible evidence mapping."""
        return {
            "schema_version": self.schema_version,
            "environment": self.environment,
            "projections": self.projections,
            "measurements": [asdict(measurement) for measurement in self.measurements],
            "gate_failures": list(self.gate_failures),
        }


def _timed_subprocess(argv: tuple[str, ...], *, env: dict[str, str], cwd: Path, timeout_s: float) -> tuple[float, str]:
    import subprocess

    started = time.monotonic()
    completed = subprocess.run(  # noqa: S603 - fixed resolved executable and declarative argv
        argv,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding=_UTF_8,
        errors="strict",
        timeout=timeout_s,
        check=False,
    )
    elapsed = time.monotonic() - started
    if completed.returncode != 0:
        raise ServingPathBenchmarkError(
            f"subprocess call failed ({completed.returncode}): {argv!r}\n{completed.stdout}\n{completed.stderr}",
        )
    return elapsed, completed.stdout


def measure_subprocess(cli: Path, *, work_dir: Path, storage_root: Path, timeout_s: float) -> list[CallMeasurement]:
    """Measure the research call table through the editable-tree ``aeat`` executable.

    The isolated product environment (and its fresh passphrase) is built ONCE so
    every call resolves the same encrypted storage root; only the first-touch
    cliff-gone gate binds here.
    """
    env = isolated_product_environment(storage_root)
    base = (str(cli), "--format", "json")
    out: list[CallMeasurement] = []

    version_seconds, _ = _timed_subprocess((str(cli), "--version"), env=env, cwd=work_dir, timeout_s=timeout_s)
    out.append(CallMeasurement("version", "subprocess", _ENVIRONMENT_IDENTITY, version_seconds, False, None, None, ""))

    profile_seconds, _ = _timed_subprocess(
        (*base, *profile_create_arguments()), env=env, cwd=work_dir, timeout_s=timeout_s
    )
    out.append(
        CallMeasurement("profile create", "subprocess", _ENVIRONMENT_IDENTITY, profile_seconds, False, None, None, "")
    )

    first_touch_seconds, create_stdout = _timed_subprocess(
        (*base, *work_create_arguments()), env=env, cwd=work_dir, timeout_s=timeout_s
    )
    out.append(
        CallMeasurement(
            "work create (first-touch, fresh state)",
            "subprocess",
            _ENVIRONMENT_IDENTITY,
            first_touch_seconds,
            True,
            _SUBPROCESS_FIRST_TOUCH_CLIFF_MAX_S,
            first_touch_seconds <= _SUBPROCESS_FIRST_TOUCH_CLIFF_MAX_S,
            "cliff-gone gate (was 49.6 s); the installed-cohort <= 5 s target is proven by S19/S20",
        )
    )
    work_unit_id = str(json.loads(create_stdout)["result"]["work_unit_id"])

    warm_create_seconds, _ = _timed_subprocess(
        (*base, *work_create_arguments()), env=env, cwd=work_dir, timeout_s=timeout_s
    )
    out.append(
        CallMeasurement(
            "work create (warm)",
            "subprocess",
            _ENVIRONMENT_IDENTITY,
            warm_create_seconds,
            False,
            None,
            None,
            "editable-tree per-process import floor; installed-cohort target proven by S19/S20",
        )
    )

    calculate_seconds, _ = _timed_subprocess(
        (*base, *work_calculate_arguments(work_unit_id)), env=env, cwd=work_dir, timeout_s=timeout_s
    )
    out.append(
        CallMeasurement(
            "work calculate (warm)",
            "subprocess",
            _ENVIRONMENT_IDENTITY,
            calculate_seconds,
            False,
            None,
            None,
            "editable-tree per-process import floor; installed-cohort <= 3 s target proven by S19/S20",
        )
    )

    list_seconds, _ = _timed_subprocess((*base, "app", "modelo", "list"), env=env, cwd=work_dir, timeout_s=timeout_s)
    out.append(
        CallMeasurement("modelo list (warm)", "subprocess", _ENVIRONMENT_IDENTITY, list_seconds, False, None, None, "")
    )
    return out


@contextmanager
def _server_environment(storage_root: Path) -> Iterator[None]:
    """Point the in-process runtime at a fresh env-isolated encrypted root.

    The warm runtime runs the CLI in a worker thread that inherits ``os.environ``
    (not context-var overrides), so isolation is env-based; the values are
    restored on exit so the benchmark process leaves no ambient state behind.
    """
    from cadrumo.core.config import DEV_TEST_DATABASE_PASSWORD

    overrides = {
        "CADRUMO_LOCAL_STORAGE_ROOT": str((storage_root / "storage").resolve()),
        "CADRUMO_SECRET_STORE_BACKEND": "file",
        "CADRUMO_SECRET_STORE_DIR": str((storage_root / "secrets").resolve()),
        "CADRUMO_SECRET_PASSPHRASE": DEV_TEST_DATABASE_PASSWORD,
        "CADRUMO_OUTPUT_LANGUAGE": "en",
        "CADRUMO_CLI_REVEAL_IDENTIFIERS": "1",
    }
    previous = {key: os.environ.get(key) for key in overrides}
    os.environ.update(overrides)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _run_in_process(argv_tail: Sequence[str], *, acquire_timeout_s: float) -> tuple[float, dict[str, object]]:
    from cadrumo.entrypoints.mcp._inprocess import parse_cli_envelope, run_cli_in_process

    started = time.monotonic()
    run = run_cli_in_process(["--format", "json", *argv_tail], acquire_timeout_s=acquire_timeout_s)
    elapsed = time.monotonic() - started
    if run is None:
        raise ServingPathBenchmarkError(f"in-process capture lock not acquired for {argv_tail!r}")
    envelope, is_error = parse_cli_envelope(run)
    if is_error:
        raise ServingPathBenchmarkError(f"in-process call errored for {argv_tail!r}: {envelope!r}")
    return elapsed, envelope


def _timed_build_server_read(command_key: str, *, timeout_s: float) -> float:
    """Measure one warm read through the real MCP surface (SDK memory transport)."""
    from mcp.shared.memory import create_connected_server_and_client_session as connect

    from cadrumo.entrypoints.mcp._dispatch import tool_name_for_command
    from cadrumo.entrypoints.mcp._harness_tools import WHOAMI_TOOL
    from cadrumo.entrypoints.mcp._server import build_server
    from cadrumo.entrypoints.mcp._tools import build_tool_descriptors

    async def _drive() -> float:
        server = build_server(build_tool_descriptors())
        async with connect(server) as session:
            # Clear the first-change identity gate, then warm the tool once so the
            # measured call is steady-state, not the session's first dispatch.
            await session.call_tool(WHOAMI_TOOL, {})
            tool_name = tool_name_for_command(command_key)
            await session.call_tool(tool_name, {})
            started = time.monotonic()
            result = await session.call_tool(tool_name, {})
            elapsed = time.monotonic() - started
            if result.isError:
                raise ServingPathBenchmarkError(f"MCP-surface read errored for {command_key!r}: {result.content!r}")
            return elapsed

    return asyncio.run(asyncio.wait_for(_drive(), timeout=timeout_s))


def measure_server_mode(*, storage_root: Path, acquire_timeout_s: float) -> list[CallMeasurement]:
    """Measure warm server-mode calls through the D4 in-process runtime.

    One process pays interpreter, import, and registry once; the reads, simple
    write, and steady-state calculation are then the campaign's real serving
    cost. A final read is driven through the full ``build_server`` memory
    transport to confirm the MCP-surface framing overhead is negligible.
    """
    out: list[CallMeasurement] = []
    with _server_environment(storage_root):
        # Warm the process: provision a profile and a work unit (the first
        # registry touch validates once in-process).
        _run_in_process(profile_create_arguments(), acquire_timeout_s=acquire_timeout_s)
        _, create_envelope = _run_in_process(work_create_arguments(), acquire_timeout_s=acquire_timeout_s)
        create_result = create_envelope["result"]
        if not isinstance(create_result, dict):
            raise ServingPathBenchmarkError(f"work create result is not an object: {create_envelope!r}")
        work_unit_id = str(cast("dict[str, object]", create_result)["work_unit_id"])

        read_seconds, _ = _run_in_process(["app", "modelo", "list"], acquire_timeout_s=acquire_timeout_s)
        out.append(
            CallMeasurement(
                "modelo list read",
                "server",
                _ENVIRONMENT_IDENTITY,
                read_seconds,
                True,
                _SERVER_READ_MAX_S,
                read_seconds <= _SERVER_READ_MAX_S,
                "sub-second read bar",
            )
        )

        write_seconds, _ = _run_in_process(work_create_arguments(), acquire_timeout_s=acquire_timeout_s)
        out.append(
            CallMeasurement(
                "work create (simple write, idempotent re-touch)",
                "server",
                _ENVIRONMENT_IDENTITY,
                write_seconds,
                True,
                _SERVER_SIMPLE_WRITE_MAX_S,
                write_seconds <= _SERVER_SIMPLE_WRITE_MAX_S,
                "sub-second simple-write bar",
            )
        )

        first_calc_seconds, _ = _run_in_process(
            work_calculate_arguments(work_unit_id), acquire_timeout_s=acquire_timeout_s
        )
        out.append(
            CallMeasurement(
                "work calculate (first in-process)",
                "server",
                _ENVIRONMENT_IDENTITY,
                first_calc_seconds,
                False,
                None,
                None,
                "one-time lazy calc-engine import; recorded, not gated",
            )
        )

        steady_calc_seconds, _ = _run_in_process(
            work_calculate_arguments(work_unit_id), acquire_timeout_s=acquire_timeout_s
        )
        out.append(
            CallMeasurement(
                "work calculate (warm steady-state)",
                "server",
                _ENVIRONMENT_IDENTITY,
                steady_calc_seconds,
                True,
                _SERVER_WARM_CALCULATE_MAX_S,
                steady_calc_seconds <= _SERVER_WARM_CALCULATE_MAX_S,
                "research ~1.5 s was a lighter baseline; the 16-input M200 oracle measures ~1.7-1.9 s "
                "steady-state, meeting the low-single-digit-seconds bar; 2.5 s = honest steady-state + "
                "slow-machine margin, so a regression toward it stays visible in this table",
            )
        )

        mcp_read_seconds = _timed_build_server_read("review.queue", timeout_s=acquire_timeout_s)
        out.append(
            CallMeasurement(
                "review.queue read (MCP memory transport)",
                "server",
                _ENVIRONMENT_IDENTITY,
                mcp_read_seconds,
                True,
                _SERVER_READ_MAX_S,
                mcp_read_seconds <= _SERVER_READ_MAX_S,
                "full build_server SDK memory transport round-trip; sub-second read bar",
            )
        )
    return out


def _environment_block(cli: Path) -> dict[str, Any]:
    return {
        "identity": _ENVIRONMENT_IDENTITY,
        "editable_install": True,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "aeat_executable": str(cli),
    }


def run_serving_path_benchmark(
    *,
    cli: Path | None = None,
    work_dir: Path | None = None,
    subprocess_timeout_s: float = 120.0,
    acquire_timeout_s: float = 120.0,
) -> ServingPathEvidence:
    """Run the full benchmark and return the measured table plus gate failures."""
    resolved_cli = (cli or _resolve_cli()).expanduser().resolve(strict=True)
    resolved_work_dir = (work_dir or Path(tempfile.mkdtemp(prefix="serving-benchmark-"))).resolve()
    resolved_work_dir.mkdir(parents=True, exist_ok=True)

    measurements: list[CallMeasurement] = []
    measurements.extend(
        measure_subprocess(
            resolved_cli,
            work_dir=resolved_work_dir,
            storage_root=resolved_work_dir / "subprocess-state",
            timeout_s=subprocess_timeout_s,
        )
    )
    measurements.extend(
        measure_server_mode(
            storage_root=resolved_work_dir / "server-state",
            acquire_timeout_s=acquire_timeout_s,
        )
    )

    gate_failures = tuple(
        f"{measurement.label} [{measurement.mode}/{measurement.environment}] "
        f"{measurement.seconds:.3f}s exceeds {measurement.threshold_seconds}s"
        for measurement in measurements
        if measurement.gated and measurement.within_threshold is False
    )
    return ServingPathEvidence(
        schema_version=_SCHEMA_VERSION,
        environment=_environment_block(resolved_cli),
        projections=_RESEARCH_PROJECTIONS,
        measurements=tuple(measurements),
        gate_failures=gate_failures,
    )


def assert_acceptance(evidence: ServingPathEvidence) -> None:
    """Raise if any current-tree acceptance gate is broken."""
    if evidence.gate_failures:
        raise ServingPathBenchmarkError(
            "serving-path acceptance gate(s) failed:\n"
            + "\n".join(f" - {failure}" for failure in evidence.gate_failures)
        )


def _resolve_cli() -> Path:
    resolved = shutil.which("aeat")
    if resolved is None:
        raise ServingPathBenchmarkError("no `aeat` executable on PATH; pass --cli")
    return Path(resolved)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", type=Path, help="aeat executable to benchmark (default: resolved on PATH).")
    parser.add_argument("--work-dir", type=Path, help="Execution cwd + isolated state root (default: a temp dir).")
    parser.add_argument("--subprocess-timeout-seconds", type=float, default=120.0)
    parser.add_argument("--acquire-timeout-seconds", type=float, default=120.0)
    parser.add_argument("--output", type=Path, help="Optional JSON evidence destination.")
    parser.add_argument("--assert-gates", action="store_true", help="Exit non-zero if any acceptance gate fails.")
    return parser


def main() -> int:
    """Run the benchmark from the command line and emit the JSON evidence."""
    args = _parser().parse_args()
    evidence = run_serving_path_benchmark(
        cli=args.cli,
        work_dir=args.work_dir,
        subprocess_timeout_s=args.subprocess_timeout_seconds,
        acquire_timeout_s=args.acquire_timeout_seconds,
    )
    rendered = json.dumps(evidence.to_jsonable(), ensure_ascii=False, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{rendered}\n", encoding=_UTF_8)
    print(rendered)
    if args.assert_gates:
        assert_acceptance(evidence)
    return 0


if __name__ == "__main__":
    sys.exit(main())

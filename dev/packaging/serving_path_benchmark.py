"""Serving-path latency benchmark and acceptance gate for MCP call latency.

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
  editable tree; the installed-cohort acquisition lanes prove those against the
  built cohort.
- ``server`` drives the harness's warm runtime, the path an MCP call takes. The
  acceptance bar is that reads and simple writes are sub-second and the
  heaviest calculation is low single-digit seconds. That runtime now executes
  each call in an installed-CLI command process, so every server row is charged
  for that child as well as for this process.

On the server warm-calculate bound: the research projected ~1.5 s for a lighter
baseline; the 16-input Modelo 200 oracle here measures ~1.7-1.9 s steady-state,
which meets the operator's bar (sub-second reads/simple writes, low single-digit
seconds at absolute worst for the heaviest calculation). The evidence records
the projection, the measured value, and this rationale so a future regression
toward a gate stays visible in the recorded table even while it passes.

Gate basis (perf-gate-honesty, 2026-07-21): the ACCEPTANCE gates assert
PROCESS CPU-TIME, not wall-clock. The fleet runs three jobs per physical
machine, so co-resident load steals wall-clock from a compute-bound
measurement while its CPU seconds stay constant — a wall gate flakes under
load without measuring any regression. Server rows gate on this process's CPU
plus that of every command process the call ran
(:func:`dev.ci.perf_measurement.process_tree_cpu`); the subprocess first-touch
cliff gates on the child TREE's CPU time, measured by the shared
:func:`dev.ci.perf_measurement.timed_subprocess` (``getrusage(RUSAGE_CHILDREN)``
on POSIX; a Job Object's aggregate accounting on Windows, where the ``aeat``
exe shim spawns the real interpreter as a grandchild that per-process times
would miss). Wall-clock stays MEASURED and RECORDED on every row — and printed
as an advisory by the pytest gate — but is never asserted. Caveat stated
honestly: CPU-time excludes wait-time but SMT/cache contention still inflates
it (the loaded-machine steady-state measured 3.23 CPU-s vs ~1.97 quiet), so
ceilings carry that margin.
"""

from __future__ import annotations

import argparse
import asyncio
import atexit
import json
import os
import platform
import secrets
import shutil
import sys
import tempfile
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Final, cast

from cadrumo.domain.calculations.registry.authority_store import AuthorityDescriptor, AuthorityStoreError
from dev._paths import REPO_ROOT, UTF_8
from dev.ci.perf_measurement import ProcessTreeCpu, process_tree_cpu, timed_subprocess

from .authority_staging import AUTHORITY_ROOT_ENV, selected_published_authority
from .installed_tax_oracle import (
    PROFILE_AUTHENTICATION_SECRETS_OPTION,
    PROFILE_CREATION_SECRETS_OPTION,
    complete_setup_arguments,
    isolated_product_environment,
    profile_authentication_secrets,
    profile_create_arguments,
    profile_creation_secrets,
    work_calculate_arguments,
    work_create_arguments,
)

_UTF_8: Final[str] = UTF_8
_SCHEMA_VERSION: Final[int] = 3
_ENVIRONMENT_IDENTITY: Final[str] = "editable-tree"

# Acceptance gates asserted on the current (editable) tree, in PROCESS
# CPU-SECONDS (load-immune; see the module docstring). Ceilings are the
# freshly measured baseline plus margin; the baseline is stated beside each
# gate and in the pytest module's docstring.
_SERVER_READ_MAX_CPU_S: Final[float] = 1.0
_SERVER_SIMPLE_WRITE_MAX_CPU_S: Final[float] = 1.0
# Measured 3.23 CPU-s under FULL co-resident load (SMT contention inflates
# CPU-time even though wait-time is excluded); quiet-machine steady-state is
# ~1.7-1.9 s. The ceiling is the loaded measurement plus margin — still an
# order of magnitude under the regression class this gate exists to catch.
_SERVER_WARM_CALCULATE_MAX_CPU_S: Final[float] = 4.5
# Measured 21.6 child-CPU-s (quiet-ish run; wall 106 s under heavy disk load —
# exactly the divergence CPU gating exists for). 35 = baseline + SMT margin,
# still clearly under the ~50 s compute cliff this gate guards against.
_SUBPROCESS_FIRST_TOUCH_CLIFF_MAX_CPU_S: Final[float] = 35.0

# Reference figures recorded (never gated on the editable tree) so the evidence
# is self-describing and cross-environment claims stay explicitly labelled.
_RESEARCH_PROJECTIONS: Final[dict[str, str]] = {
    "server_warm_calculate_projection_s": "1.5 (installed-cohort, research lighter-baseline)",
    "subprocess_warm_calculate_target_s": "3.0 (installed-cohort, proven by the acquisition lanes)",
    "subprocess_first_touch_target_s": "5.0 (installed-cohort, proven by the acquisition lanes)",
    "subprocess_first_touch_former_cliff_s": "49.6 (installed v0.2.1 pre-fix)",
}


class ServingPathBenchmarkError(RuntimeError):
    """Raised when the benchmark cannot execute a required measurement."""


@dataclass(frozen=True)
class CallMeasurement:
    """One timed call, labelled with its environment and gate disposition.

    ``seconds`` is wall-clock (recorded, advisory, never asserted);
    ``cpu_seconds`` is the load-immune measurement the acceptance gates bind
    (``threshold_cpu_seconds`` / ``within_threshold``). ``child_cpu_seconds`` is
    the part of ``cpu_seconds`` spent in child processes, so the remainder is
    the measuring process's own share.
    """

    label: str
    mode: str
    environment: str
    seconds: float
    cpu_seconds: float | None
    gated: bool
    threshold_cpu_seconds: float | None
    within_threshold: bool | None
    note: str
    child_cpu_seconds: float | None = None


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


def subprocess_failure_message(returncode: int, argv: tuple[str, ...], stdout: str, stderr: str) -> str:
    """Name the product's own refusal ahead of the raw child detail.

    A measured child that refuses returns the typed CLI envelope, and that
    envelope is the diagnosis. Reported as a bare return code in front of a
    full argv dump, a named boundary refusal reads instead as an unexplained
    subprocess failure -- and because the caller runs under a module-scoped
    fixture, that same unreadable text is what EVERY test in the module
    reports at setup, none of them naming a cause.

    BOTH streams are read, because a refusal is written to stderr while a
    successful envelope is written to stdout. Reading only stdout finds an
    empty string on exactly the failures this exists to explain.

    The summary is added, never substituted: argv, stdout, and stderr all
    survive behind it, so a failure carrying no envelope loses nothing.
    """
    summary = f"subprocess call failed ({returncode})"
    for stream in (stderr, stdout):
        try:
            error = json.loads(stream).get("error")
        except (ValueError, AttributeError):
            continue
        if isinstance(error, dict) and (error.get("code") or error.get("message")):
            named = error.get("code") or "unnamed refusal"
            detail = error.get("message") or "no message"
            summary = f"{summary}: {named} - {detail}"
            break
    return f"{summary}\nargv: {argv!r}\n{stdout}\n{stderr}"


def _timed_subprocess(
    argv: tuple[str, ...], *, env: dict[str, str], cwd: Path, timeout_s: float, input_text: str | None = None
) -> tuple[float, float, str]:
    """Run one child and return (wall seconds, child CPU seconds, stdout).

    Thin domain adapter over the shared
    :func:`dev.ci.perf_measurement.timed_subprocess`, which owns the
    platform-specific child-TREE CPU accounting. What is added here is only the
    benchmark's failure vocabulary: a non-zero child is a benchmark error.
    """
    timing = timed_subprocess(argv, env=env, cwd=cwd, timeout_s=timeout_s, input_text=input_text)
    if timing.returncode != 0:
        raise ServingPathBenchmarkError(
            subprocess_failure_message(timing.returncode, argv, timing.stdout, timing.stderr),
        )
    return timing.wall_seconds, timing.cpu_seconds, timing.stdout


def measure_subprocess(
    cli: Path, *, work_dir: Path, storage_root: Path, authority_root: Path, timeout_s: float
) -> list[CallMeasurement]:
    """Measure the research call table through the editable-tree ``aeat`` executable.

    The isolated product environment (and its fresh passphrase) is built ONCE so
    every call resolves the same encrypted storage root; only the first-touch
    cliff-gone gate binds here. That environment drops every inherited Cadrumo
    setting, and an editable tree carries no packaged authority, so the
    published authority the server mode also reads is named explicitly.

    Every profile-scoped call authenticates through the CLI's stdin secret
    channel, the only one a command process accepts, so the measured cost
    includes the profile unlock a real caller pays.
    """
    env = isolated_product_environment(storage_root)
    env[AUTHORITY_ROOT_ENV] = str(authority_root)
    base = (str(cli), "--format", "json")
    authenticated = (*base, PROFILE_AUTHENTICATION_SECRETS_OPTION)
    passphrase = secrets.token_urlsafe(32)
    authentication = profile_authentication_secrets(passphrase)
    out: list[CallMeasurement] = []

    def ungated(label: str, wall: float, cpu: float, note: str = "") -> CallMeasurement:
        return CallMeasurement(
            label, "subprocess", _ENVIRONMENT_IDENTITY, wall, cpu, False, None, None, note, child_cpu_seconds=cpu
        )

    version_wall, version_cpu, _ = _timed_subprocess(
        (str(cli), "--version"), env=env, cwd=work_dir, timeout_s=timeout_s
    )
    out.append(ungated("version", version_wall, version_cpu))

    profile_wall, profile_cpu, _ = _timed_subprocess(
        (*base, *profile_create_arguments(), PROFILE_CREATION_SECRETS_OPTION),
        env=env,
        cwd=work_dir,
        timeout_s=timeout_s,
        input_text=profile_creation_secrets(passphrase),
    )
    out.append(ungated("profile create", profile_wall, profile_cpu))

    setup_wall, setup_cpu, _ = _timed_subprocess(
        (*authenticated, *complete_setup_arguments()),
        env=env,
        cwd=work_dir,
        timeout_s=timeout_s,
        input_text=authentication,
    )
    out.append(ungated("profile complete-setup", setup_wall, setup_cpu))

    first_touch_wall, first_touch_cpu, create_stdout = _timed_subprocess(
        (*authenticated, *work_create_arguments()),
        env=env,
        cwd=work_dir,
        timeout_s=timeout_s,
        input_text=authentication,
    )
    out.append(
        CallMeasurement(
            "work create (first-touch, fresh state)",
            "subprocess",
            _ENVIRONMENT_IDENTITY,
            first_touch_wall,
            first_touch_cpu,
            True,
            _SUBPROCESS_FIRST_TOUCH_CLIFF_MAX_CPU_S,
            first_touch_cpu <= _SUBPROCESS_FIRST_TOUCH_CLIFF_MAX_CPU_S,
            "cliff-gone gate in child CPU seconds (the 49.6 s cliff was compute, not waiting); "
            "the installed-cohort <= 5 s target is proven by the acquisition lanes",
            child_cpu_seconds=first_touch_cpu,
        )
    )
    work_unit_id = str(json.loads(create_stdout)["result"]["work_unit_id"])

    warm_create_wall, warm_create_cpu, _ = _timed_subprocess(
        (*authenticated, *work_create_arguments()),
        env=env,
        cwd=work_dir,
        timeout_s=timeout_s,
        input_text=authentication,
    )
    out.append(
        ungated(
            "work create (warm)",
            warm_create_wall,
            warm_create_cpu,
            "editable-tree per-process import floor; installed-cohort target proven by the acquisition lanes",
        )
    )

    calculate_wall, calculate_cpu, _ = _timed_subprocess(
        (*authenticated, *work_calculate_arguments(work_unit_id)),
        env=env,
        cwd=work_dir,
        timeout_s=timeout_s,
        input_text=authentication,
    )
    out.append(
        ungated(
            "work calculate (warm)",
            calculate_wall,
            calculate_cpu,
            "editable-tree per-process import floor; installed-cohort <= 3 s target proven by the lanes",
        )
    )

    list_wall, list_cpu, _ = _timed_subprocess(
        (*base, "app", "modelo", "list"), env=env, cwd=work_dir, timeout_s=timeout_s
    )
    out.append(ungated("modelo list (warm)", list_wall, list_cpu))
    return out


@contextmanager
def _server_environment(storage_root: Path, authority_root: Path) -> Generator[None]:
    """Point the in-process runtime at a fresh env-isolated encrypted root.

    The warm runtime runs the CLI in a worker thread that inherits ``os.environ``
    (not context-var overrides), so isolation is env-based; the values are
    restored on exit so the benchmark process leaves no ambient state behind.
    """
    from cadrumo.core.config import DEV_TEST_DATABASE_PASSWORD

    # An explicit secret-store override is the operator's to provision: the CLI
    # validates the directory on every command and never creates it.
    (storage_root / "secrets").mkdir(parents=True, exist_ok=True)
    overrides = {
        "CADRUMO_LOCAL_STORAGE_ROOT": str((storage_root / "storage").resolve()),
        "CADRUMO_SECRET_STORE_DIR": str((storage_root / "secrets").resolve()),
        "CADRUMO_SECRET_PASSPHRASE": DEV_TEST_DATABASE_PASSWORD,
        "CADRUMO_OUTPUT_LANGUAGE": "en",
        "CADRUMO_CLI_REVEAL_IDENTIFIERS": "1",
        AUTHORITY_ROOT_ENV: str(authority_root),
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


def _run_in_process(
    argv_tail: Sequence[str], *, acquire_timeout_s: float, stdin_payload: str | None = None
) -> tuple[ProcessTreeCpu, dict[str, object]]:
    """Return the measured cost and the envelope of one warm-runtime call.

    The warm runtime hands each call to an installed-CLI command process, so the
    cost is this process's CPU plus that child's (:func:`process_tree_cpu`);
    ``time.process_time`` alone would read the waiting parent only.
    ``stdin_payload`` is the machine secret the command reads, framed exactly as
    a subprocess pipe carries it.
    """
    from cadrumo_harness.mcp.inprocess import parse_cli_envelope, run_cli_in_process

    with process_tree_cpu() as measured:
        run = run_cli_in_process(
            ["--format", "json", *argv_tail],
            acquire_timeout_s=acquire_timeout_s,
            stdin_payload=stdin_payload,
        )
    if run is None:
        raise ServingPathBenchmarkError(f"in-process capture lock not acquired for {argv_tail!r}")
    envelope, is_error = parse_cli_envelope(run)
    if is_error:
        raise ServingPathBenchmarkError(f"in-process call errored for {argv_tail!r}: {envelope!r}")
    return measured, envelope


def _timed_build_server_read(command_key: str, *, timeout_s: float) -> ProcessTreeCpu:
    """Measure one warm read through the real MCP surface (SDK memory transport).

    The memory transport runs inside this process and the dispatched command in
    the child the runtime spawns, so both are measured.
    """
    from cadrumo_harness.mcp.dispatch import tool_name_for_command
    from cadrumo_harness.mcp.harness_tools import WHOAMI_TOOL
    from cadrumo_harness.mcp.server import build_server
    from cadrumo_harness.mcp.tests.session import connected_server_and_client_session as connect
    from cadrumo_harness.mcp.tools import build_tool_descriptors

    async def _drive() -> ProcessTreeCpu:
        server = build_server(build_tool_descriptors())
        async with connect(server) as session:
            # Clear the first-change identity gate, then warm the tool once so the
            # measured call is steady-state, not the session's first dispatch.
            await session.call_tool(WHOAMI_TOOL, {})
            tool_name = tool_name_for_command(command_key)
            await session.call_tool(tool_name, {})
            with process_tree_cpu() as measured:
                result = await session.call_tool(tool_name, {})
            if result.is_error:
                raise ServingPathBenchmarkError(f"MCP-surface read errored for {command_key!r}: {result.content!r}")
            return measured

    return asyncio.run(asyncio.wait_for(_drive(), timeout=timeout_s))


def _server_row(label: str, measured: ProcessTreeCpu, *, threshold_cpu_s: float | None, note: str) -> CallMeasurement:
    """Record one server row; a row without a threshold is measured but not gated."""
    cpu = measured.cpu_seconds
    return CallMeasurement(
        label,
        "server",
        _ENVIRONMENT_IDENTITY,
        measured.wall_seconds,
        cpu,
        threshold_cpu_s is not None,
        threshold_cpu_s,
        None if threshold_cpu_s is None else cpu <= threshold_cpu_s,
        note,
        child_cpu_seconds=measured.child_cpu_seconds,
    )


def measure_server_mode(*, storage_root: Path, authority_root: Path, acquire_timeout_s: float) -> list[CallMeasurement]:
    """Measure warm server-mode calls through the harness runtime.

    Every row is charged for the command process the runtime spawns as well as
    for this process, so a row measures what the call costs. A final read is
    driven through the full ``build_server`` memory transport, beside the same
    read without it, so the MCP framing overhead is visible.
    """
    out: list[CallMeasurement] = []
    passphrase = secrets.token_urlsafe(32)
    authentication = profile_authentication_secrets(passphrase)

    def authenticated(argv_tail: Sequence[str]) -> tuple[ProcessTreeCpu, dict[str, object]]:
        return _run_in_process(
            (PROFILE_AUTHENTICATION_SECRETS_OPTION, *argv_tail),
            acquire_timeout_s=acquire_timeout_s,
            stdin_payload=authentication,
        )

    with _server_environment(storage_root, authority_root):
        # Warm the process: provision a ready profile and a work unit (the
        # first registry touch validates once).
        _run_in_process(
            (*profile_create_arguments(), PROFILE_CREATION_SECRETS_OPTION),
            acquire_timeout_s=acquire_timeout_s,
            stdin_payload=profile_creation_secrets(passphrase),
        )
        authenticated(complete_setup_arguments())
        _, create_envelope = authenticated(work_create_arguments())
        create_result = create_envelope["result"]
        if not isinstance(create_result, dict):
            raise ServingPathBenchmarkError(f"work create result is not an object: {create_envelope!r}")
        work_unit_id = str(cast("dict[str, object]", create_result)["work_unit_id"])

        read, _ = _run_in_process(["app", "modelo", "list"], acquire_timeout_s=acquire_timeout_s)
        out.append(
            _server_row(
                "modelo list read",
                read,
                threshold_cpu_s=_SERVER_READ_MAX_CPU_S,
                note="sub-second read bar in CPU seconds",
            )
        )

        write, _ = authenticated(work_create_arguments())
        out.append(
            _server_row(
                "work create (simple write, idempotent re-touch)",
                write,
                threshold_cpu_s=_SERVER_SIMPLE_WRITE_MAX_CPU_S,
                note="sub-second simple-write bar in CPU seconds",
            )
        )

        first_calculation, _ = authenticated(work_calculate_arguments(work_unit_id))
        out.append(
            _server_row(
                "work calculate (first in-process)",
                first_calculation,
                threshold_cpu_s=None,
                note="one-time lazy calc-engine import; recorded, not gated",
            )
        )

        steady_calculation, _ = authenticated(work_calculate_arguments(work_unit_id))
        out.append(
            _server_row(
                "work calculate (warm steady-state)",
                steady_calculation,
                threshold_cpu_s=_SERVER_WARM_CALCULATE_MAX_CPU_S,
                note=(
                    "research ~1.5 s was a lighter baseline; the 16-input M200 oracle measures ~1.7-1.9 "
                    "CPU-seconds steady-state, meeting the low-single-digit-seconds bar; 2.5 CPU-s = honest "
                    "steady-state + margin, load-immune by construction"
                ),
            )
        )

        # The same registry read as the direct row above, so the delta is the
        # MCP framing alone. A profile-scoped read would add session custody,
        # and its secret channel is loaded only by the stdio launcher.
        out.append(
            _server_row(
                "modelo list read (MCP memory transport)",
                _timed_build_server_read("modelo.list", timeout_s=acquire_timeout_s),
                threshold_cpu_s=_SERVER_READ_MAX_CPU_S,
                note="full build_server SDK memory transport round-trip; sub-second read bar in CPU seconds",
            )
        )
    return out


def _published_authority() -> tuple[Path, AuthorityDescriptor]:
    """Return the checkout's published authority root and the generation it selects.

    Both measured environments serve this one generation, so a run is
    reproducible against the recorded identity instead of whichever copy a
    child happens to resolve. A checkout that has not published refuses here,
    before any measurement, rather than as a runtime refusal inside a child.
    """
    try:
        descriptor_path, _ = selected_published_authority(REPO_ROOT)
        descriptor = AuthorityDescriptor.read(descriptor_path)
    except (FileNotFoundError, AuthorityStoreError) as exc:
        raise ServingPathBenchmarkError(f"the serving-path benchmark needs a published authority: {exc}") from exc
    return descriptor_path.parent.resolve(), descriptor


def _environment_block(cli: Path, *, authority_root: Path, authority: AuthorityDescriptor) -> dict[str, Any]:
    return {
        "identity": _ENVIRONMENT_IDENTITY,
        "editable_install": True,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "aeat_executable": str(cli),
        "authority_root": str(authority_root),
        "authority_logical_generation": authority.logical_generation,
        "authority_database_sha256": authority.database_sha256,
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
    if work_dir is None:
        # Reclaimed at exit and named under the swept `cadrumo-` stem, because
        # neither held here before: the family was invisible to the scratch
        # gate (whose subject it fell outside) and disposed of by nothing, so
        # every benchmark run left a work tree of measured state behind.
        minted = Path(tempfile.mkdtemp(prefix="cadrumo-serving-benchmark-"))
        atexit.register(shutil.rmtree, minted, ignore_errors=True)
        resolved_work_dir = minted.resolve()
    else:
        resolved_work_dir = work_dir.resolve()
    resolved_work_dir.mkdir(parents=True, exist_ok=True)
    authority_root, authority = _published_authority()

    measurements: list[CallMeasurement] = []
    measurements.extend(
        measure_subprocess(
            resolved_cli,
            work_dir=resolved_work_dir,
            storage_root=resolved_work_dir / "subprocess-state",
            authority_root=authority_root,
            timeout_s=subprocess_timeout_s,
        )
    )
    measurements.extend(
        measure_server_mode(
            storage_root=resolved_work_dir / "server-state",
            authority_root=authority_root,
            acquire_timeout_s=acquire_timeout_s,
        )
    )

    gate_failures = tuple(
        f"{measurement.label} [{measurement.mode}/{measurement.environment}] "
        f"{measurement.cpu_seconds:.3f} CPU-s exceeds {measurement.threshold_cpu_seconds} CPU-s "
        f"(wall {measurement.seconds:.3f}s, advisory)"
        for measurement in measurements
        if measurement.gated and measurement.within_threshold is False
    )
    return ServingPathEvidence(
        schema_version=_SCHEMA_VERSION,
        environment=_environment_block(resolved_cli, authority_root=authority_root, authority=authority),
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
        args.output.write_text(f"{rendered}\n", encoding=_UTF_8, newline="\n")
    print(rendered)
    if args.assert_gates:
        assert_acceptance(evidence)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""The sole contributor-facing import-quality gate implementation.

The driver has one fixed order:

1. read and preflight the closed classification declared by Import Linter;
2. run Import Linter's complete native graph/contracts;
3. prove every governed non-test module loads;
4. run the subordinate syntax/canonical/dynamic source checker.

Import Linter remains the only dependency-direction authority.  The
subordinate component is deliberately invoked here rather than exposed as a
second contributor verdict.

Each subprocess step runs under a :class:`StepBudget` measured in the CPU its
process tree consumes, not in wall-clock seconds; see the budget constants
below for why.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import time
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

import psutil

from cadrumo.core.storage_environment import resolve_storage_path
from dev._paths import REPO_ROOT, UTF_8, prepare_temporary_directory
from dev.exit_codes import FAILED, TOOL_BROKEN, TOOL_MISSING

from .import_authority import read_authority
from .import_check_models import Authority, CheckResult, Finding, ImportOccurrence
from .import_diagnostics import has_architectural_warning
from .import_health import build_import_health
from .import_health_rendering import render_import_health, unavailable_import_health

_ROOT_ENV: Final[str] = "CADRUMO_IMPORT_GATE_ROOT"
_LINTER_ENV: Final[str] = "CADRUMO_IMPORT_GATE_LINT_IMPORTS"
_CHECKER_ENV: Final[str] = "CADRUMO_IMPORT_GATE_CHECKER"
_FORCE_CHECKER_EXCEPTION_ENV: Final[str] = "CADRUMO_IMPORT_GATE_FORCE_CHECKER_EXCEPTION"
_CHECKER_PATH: Final[Path] = Path(__file__).with_name("import_checker.py").resolve()
_LOAD_PROBE_MODULE: Final[str] = "dev.quality.import_load_probe"
_LOAD_HARNESS_PACKAGES: Final[tuple[str, ...]] = ("dev", "cadrumo")

# Why the steps are bounded by CPU consumed rather than by wall-clock time.
#
# Every step is a finite computation over the governed tree: Import Linter
# builds one graph, the probe imports each non-test module once, and the
# subordinate checker parses every governed file and walks the trees.  None of
# them waits on a network, a lock or another process.  A profile of the
# checker over the full tree (95 MiB of source, 9.6 million AST nodes) put all
# of its time in ``ast.parse`` and repeated ``ast.walk`` traversals; its cost is
# linear in the governed source.  Wall-clock time for that same fixed work
# measured 147-307 s depending only on what else the machine was running, so a
# wall-clock limit turned the same tree into different verdicts.  CPU consumed
# by the step's process tree is a property of the work, so it is the quantity
# bounded here; a budget still exists so that a runaway step (an evaluator that
# never terminates) is reported as unavailable rather than waited on forever.
#
# The budget scales with the governed source because the work does.  Measured
# full-tree consumption at 95 MiB, on a loaded machine: checker 161 CPU-s
# (1.7 per MiB) while its wall time was 235 s, isolated import worker 45 CPU-s
# (0.5 per MiB), Import Linter 7 CPU-s.  The rate below is about 3.5 times the
# costliest step, so growth and contention-inflated CPU time stay inside it; the
# floor covers the fixed interpreter and tool start-up that dominates small
# fixture trees.
_CPU_SECONDS_FLOOR: Final[float] = 120.0
_CPU_SECONDS_PER_MIB: Final[float] = 6.0
# A live step whose whole process tree consumes no CPU for this long is not
# computing: it is blocked or deadlocked, and no amount of waiting completes it.
_STALL_SECONDS: Final[float] = 120.0
_MIB: Final[int] = 1024 * 1024
# Sampling is dense at start-up so a short overrun is still observed, then
# relaxed so that supervising a long step costs little CPU of its own.
_FAST_POLL_SECONDS: Final[float] = 0.05
_SLOW_POLL_SECONDS: Final[float] = 0.5
_FAST_POLL_WINDOW_SECONDS: Final[float] = 2.0
_POST_KILL_WAIT_SECONDS: Final[float] = 10.0


def _linter_component_result(completed: BudgetedRun) -> ComponentResult:
    """Linter component result."""
    output = _combined_output(completed.stdout, completed.stderr)
    if completed.returncode == 0:
        returncode = FAILED if has_architectural_warning(output) else 0
    elif completed.returncode == FAILED:
        returncode = FAILED
    else:
        returncode = TOOL_BROKEN
    return ComponentResult("import-linter", returncode, output, completed.cpu_seconds)


def _subordinate_component_result(
    completed: BudgetedRun, checker_result: CheckResult, authority: Authority
) -> tuple[ComponentResult, CheckResult]:
    """Subordinate component result."""
    output = _combined_output(completed.stdout, completed.stderr)
    cpu_seconds = completed.cpu_seconds
    if any(finding.fatal for finding in checker_result.findings):
        return (
            ComponentResult(
                "subordinate-checker",
                TOOL_BROKEN,
                output or checker_result.render(authority.repository),
                cpu_seconds,
            ),
            checker_result,
        )
    if completed.returncode == 0:
        return (
            ComponentResult(
                "subordinate-checker",
                0,
                output or "subordinate import checker completed without diagnostics",
                cpu_seconds,
            ),
            checker_result,
        )
    if completed.returncode == FAILED:
        return ComponentResult("subordinate-checker", FAILED, output, cpu_seconds), checker_result
    return (
        ComponentResult(
            "subordinate-checker",
            TOOL_BROKEN,
            f"[TOOL_BROKEN] subordinate checker exited unexpectedly with {completed.returncode}\n{output}".rstrip(),
            cpu_seconds,
        ),
        checker_result,
    )


@dataclass(frozen=True)
class StepBudget:
    """Work-based bounds for one supervised gate step.

    ``cpu_seconds`` caps the CPU (user plus system) the step's whole process
    tree may consume; ``stall_seconds`` caps how long that tree may stay alive
    without consuming any.
    """

    cpu_seconds: float
    stall_seconds: float = _STALL_SECONDS

    def as_dict(self) -> dict[str, float]:
        """Return the budget as stable report data."""
        return {"cpu_seconds": round(self.cpu_seconds, 3), "stall_seconds": round(self.stall_seconds, 3)}


class StepBudgetExceededError(Exception):
    """A supervised step overran its CPU budget or stopped making progress."""


@dataclass(frozen=True)
class BudgetedRun:
    """The observable result of one step that completed inside its budget."""

    returncode: int
    stdout: str
    stderr: str
    cpu_seconds: float


@dataclass(frozen=True)
class ComponentResult:
    """Outcome of one ordered import-gate component."""

    name: str
    returncode: int
    output: str = ""
    cpu_seconds: float | None = None


def step_budget_for_source(governed_bytes: int) -> StepBudget:
    """Derive the per-step budget from the size of the governed source."""
    return StepBudget(_CPU_SECONDS_FLOOR + _CPU_SECONDS_PER_MIB * governed_bytes / _MIB)


def step_budget_for(authority: Authority) -> StepBudget:
    """Derive the per-step budget for *authority*'s governed tree as it stands."""
    return step_budget_for_source(_source_snapshot(authority).governed_bytes)


def run_within_budget(
    argv: Sequence[str],
    *,
    cwd: Path,
    environment: Mapping[str, str] | None,
    budget: StepBudget,
) -> BudgetedRun:
    """Run one step, killing its process tree if it exceeds *budget*.

    Raises :class:`StepBudgetExceededError` after the tree is killed.  Output
    goes to temporary files rather than pipes so a step that writes a large
    report can never block on an undrained pipe and be mistaken for a stalled
    one.
    """
    if budget.cpu_seconds <= 0 or budget.stall_seconds <= 0:
        raise StepBudgetExceededError(
            f"has no work budget ({budget.cpu_seconds:g} CPU-s, {budget.stall_seconds:g} s stall limit)"
        )
    with (
        tempfile.TemporaryFile(dir=prepare_temporary_directory()) as stdout_file,
        tempfile.TemporaryFile(dir=prepare_temporary_directory()) as stderr_file,
    ):
        returncode, cpu_seconds = asyncio.run(
            _supervise(
                tuple(argv),
                cwd=cwd,
                environment=environment,
                budget=budget,
                stdout_fileno=stdout_file.fileno(),
                stderr_fileno=stderr_file.fileno(),
            )
        )
        stdout_file.seek(0)
        stderr_file.seek(0)
        return BudgetedRun(
            returncode=returncode,
            stdout=_decode_output(stdout_file.read()),
            stderr=_decode_output(stderr_file.read()),
            cpu_seconds=cpu_seconds,
        )


async def _supervise(
    argv: tuple[str, ...],
    *,
    cwd: Path,
    environment: Mapping[str, str] | None,
    budget: StepBudget,
    stdout_fileno: int,
    stderr_fileno: int,
) -> tuple[int, float]:
    """Sample the step's process-tree CPU until it exits or overruns *budget*."""
    started = time.monotonic()
    process = await asyncio.create_subprocess_exec(
        *argv,
        cwd=str(cwd),
        env=dict(environment) if environment is not None else None,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=stdout_fileno,
        stderr=stderr_fileno,
    )
    try:
        tree: psutil.Process | None = psutil.Process(process.pid)
    except psutil.Error:
        tree = None
    consumed: dict[tuple[int, float], float] = {}
    cpu_seconds = 0.0
    progress_cpu = 0.0
    progress_at = started
    try:
        while True:
            elapsed = time.monotonic() - started
            interval = _FAST_POLL_SECONDS if elapsed < _FAST_POLL_WINDOW_SECONDS else _SLOW_POLL_SECONDS
            try:
                returncode = await asyncio.wait_for(process.wait(), interval)
            except TimeoutError:
                pass
            else:
                return returncode, cpu_seconds
            cpu_seconds, progress_cpu, progress_at = _enforce_step_budget(
                tree, consumed, cpu_seconds, progress_cpu, progress_at, budget, started
            )
    finally:
        if process.returncode is None:
            _kill_tree(tree)
            with suppress(ProcessLookupError):
                process.kill()
            with suppress(TimeoutError):
                await asyncio.wait_for(process.wait(), _POST_KILL_WAIT_SECONDS)


def _tree_cpu_seconds(tree: psutil.Process, consumed: dict[tuple[int, float], float]) -> float:
    """Accumulate the CPU of every process the step has started so far.

    A launcher such as the virtual-environment interpreter shim hands the work
    to a child, and the loadability probe starts its own worker, so the root
    process alone measures almost nothing.  A member that has exited keeps its
    last observed consumption.
    """
    for member in (tree, *_descendants(tree)):
        try:
            with member.oneshot():
                identity = (member.pid, member.create_time())
                times = member.cpu_times()
        except psutil.Error:
            continue
        consumed[identity] = max(consumed.get(identity, 0.0), times.user + times.system)
    return sum(consumed.values())


def _descendants(tree: psutil.Process) -> tuple[psutil.Process, ...]:
    """Return every live process *tree* has started, directly or not."""
    try:
        children = tree.children(recursive=True)
    except psutil.Error:
        return ()
    return tuple(child for child in children if isinstance(child, psutil.Process))


def _kill_tree(tree: psutil.Process | None) -> None:
    """Kill the step's descendants and then the step itself, and reap them."""
    if tree is None:
        return
    members = (*_descendants(tree), tree)
    for member in members:
        with suppress(psutil.Error):
            member.kill()
    psutil.wait_procs(members, timeout=_POST_KILL_WAIT_SECONDS)


def _decode_output(payload: bytes) -> str:
    """Decode captured output with universal newlines, replacing undecodable bytes."""
    return payload.decode(UTF_8, errors="replace").replace("\r\n", "\n").replace("\r", "\n")


def run_import_linter(
    authority: Authority,
    executable: str | None = None,
    budget: StepBudget | None = None,
) -> ComponentResult:
    """Run Import Linter's complete native graph/contracts once."""
    requested = executable or "lint-imports"
    resolved = shutil.which(requested)
    if resolved is None:
        return ComponentResult(
            "import-linter",
            TOOL_MISSING,
            f"[TOOL_MISSING] Import Linter executable {requested!r} is unavailable",
        )
    step_budget = budget or step_budget_for(authority)

    environment = os.environ.copy()
    import_paths = [str(root.source_root) for root in authority.roots]
    existing = environment.get("PYTHONPATH")
    if existing:
        import_paths.append(existing)
    environment["PYTHONPATH"] = os.pathsep.join(dict.fromkeys(import_paths))
    environment["PYTHONIOENCODING"] = UTF_8
    command = (
        resolved,
        "--config",
        str(authority.config_path),
        "--no-cache",
        "--no-logo",
    )
    try:
        completed = run_within_budget(
            command,
            cwd=authority.repository,
            environment=environment,
            budget=step_budget,
        )
    except FileNotFoundError:
        return ComponentResult(
            "import-linter",
            TOOL_MISSING,
            f"[TOOL_MISSING] Import Linter executable {requested!r} disappeared before execution",
        )
    except StepBudgetExceededError as exc:
        return ComponentResult("import-linter", TOOL_BROKEN, f"[TOOL_BROKEN] Import Linter {exc}")
    except OSError as exc:
        return ComponentResult("import-linter", TOOL_BROKEN, f"[TOOL_BROKEN] Import Linter could not run: {exc}")
    except Exception as exc:  # broad: a graph component exception must fail closed
        return ComponentResult("import-linter", TOOL_BROKEN, f"[TOOL_BROKEN] Import Linter aborted: {exc}")

    return _linter_component_result(completed)


def run_subordinate(
    authority: Authority,
    force_exception: bool = False,
    *,
    budget: StepBudget | None = None,
) -> tuple[ComponentResult, CheckResult]:
    """Run the subordinate checker as the final ordered component."""
    try:
        if force_exception:
            raise RuntimeError("forced subordinate checker exception")
        step_budget = budget or step_budget_for(authority)
        requested = os.environ.get(_CHECKER_ENV) or sys.executable
        resolved = shutil.which(requested)
        if resolved is None:
            return (
                ComponentResult(
                    "subordinate-checker",
                    TOOL_MISSING,
                    f"[TOOL_MISSING] subordinate checker executable {requested!r} is unavailable",
                ),
                CheckResult((), 0),
            )
        environment = _subordinate_environment(authority)
        with tempfile.TemporaryDirectory(
            prefix="cadrumo-import-checker-", dir=prepare_temporary_directory()
        ) as temporary:
            report_path = Path(temporary) / "checker.json"
            command = (
                resolved,
                str(_CHECKER_PATH),
                "--internal",
                "--root",
                str(authority.repository),
                "--config",
                str(authority.config_path),
                "--report",
                str(report_path),
            )
            completed = run_within_budget(
                command,
                cwd=authority.repository,
                environment=environment,
                budget=step_budget,
            )
            checker_result = _read_checker_report(report_path, authority)
    except Exception as exc:  # broad: component boundary must fail closed
        if isinstance(exc, StepBudgetExceededError):
            message = f"[TOOL_BROKEN] subordinate checker {exc}"
        elif isinstance(exc, FileNotFoundError):
            message = f"[TOOL_MISSING] subordinate checker interpreter is unavailable: {exc}"
            return ComponentResult("subordinate-checker", TOOL_MISSING, message), CheckResult((), 0)
        elif force_exception:
            message = f"[INTERNAL_CHECKER] subordinate checker aborted: {exc}"
        else:
            message = f"[TOOL_BROKEN] subordinate checker could not run: {exc}"
        return ComponentResult(
            "subordinate-checker",
            TOOL_BROKEN,
            message,
        ), CheckResult((), 0)
    return _subordinate_component_result(completed, checker_result, authority)


def run_loadability(
    authority: Authority,
    *,
    budget: StepBudget | None = None,
) -> tuple[ComponentResult, dict[str, object]]:
    """Import every governed non-test module in an isolated process."""
    unavailable: dict[str, object] = {
        "attempted": 0,
        "failed": 0,
        "failures": [],
        "loaded": 0,
        "operational_error": "loadability evidence is unavailable",
        "root_cause_count": 0,
        "root_causes": [],
        "scope": "unavailable",
        "target_digest": None,
    }
    step_budget = budget or step_budget_for(authority)
    harness_roots = _load_harness_import_roots()
    if isinstance(harness_roots, str):
        unavailable["operational_error"] = harness_roots
        return ComponentResult("loadability", TOOL_BROKEN, f"[TOOL_BROKEN] {harness_roots}"), unavailable
    # The harness is tool code and must resolve from the tool tree; the audited
    # targets are imported by the probe's own isolated worker, so no audited
    # source root belongs on this path.
    environment = os.environ.copy()
    import_paths = list(harness_roots)
    existing = environment.get("PYTHONPATH")
    if existing:
        import_paths.append(existing)
    environment["PYTHONPATH"] = os.pathsep.join(dict.fromkeys(import_paths))
    environment["PYTHONIOENCODING"] = UTF_8

    artifact_directory = os.environ.get("CADRUMO_DEV_ARTIFACTS_DIR")
    try:
        with tempfile.TemporaryDirectory(
            prefix="cadrumo-import-loadability-", dir=prepare_temporary_directory()
        ) as temporary:
            if artifact_directory:
                report_path = resolve_storage_path(artifact_directory) / "import-loadability.json"
                report_path.parent.mkdir(parents=True, exist_ok=True)
            else:
                report_path = Path(temporary) / "import-loadability.json"
            command = (
                sys.executable,
                "-P",
                "-m",
                _LOAD_PROBE_MODULE,
                "--root",
                str(authority.repository),
                "--config",
                str(authority.config_path),
                "--report",
                str(report_path),
            )
            # The probe sets no limit of its own on its worker: the worker is in
            # this step's process tree, so the step budget already bounds it.
            completed = run_within_budget(
                command,
                cwd=authority.repository,
                environment=environment,
                budget=step_budget,
            )
            decoded_payload = _loadability_report_object(report_path)
            payload = _validate_loadability_report(decoded_payload)
            if artifact_directory:
                payload["artifact"] = str(report_path)
    except StepBudgetExceededError as exc:
        unavailable["operational_error"] = f"loadability probe {exc}"
        return ComponentResult(
            "loadability", TOOL_BROKEN, f"[TOOL_BROKEN] {unavailable['operational_error']}"
        ), unavailable
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        unavailable["operational_error"] = f"loadability evidence is unusable: {exc}"
        return ComponentResult(
            "loadability", TOOL_BROKEN, f"[TOOL_BROKEN] {unavailable['operational_error']}"
        ), unavailable

    output = _combined_output(completed.stdout, completed.stderr)
    cpu_seconds = completed.cpu_seconds
    if completed.returncode == 0:
        return ComponentResult("loadability", 0, output, cpu_seconds), payload
    if completed.returncode == FAILED:
        return ComponentResult("loadability", FAILED, output, cpu_seconds), payload
    payload.setdefault("operational_error", f"loadability probe exited unexpectedly with {completed.returncode}")
    diagnostic = str(payload["operational_error"])
    return ComponentResult("loadability", TOOL_BROKEN, _combined_output(output, diagnostic), cpu_seconds), payload


def _load_harness_import_roots() -> tuple[str, ...] | str:
    """Return the tool-tree directories providing the probe's own packages, or a refusal."""
    roots: list[str] = []
    for package in _LOAD_HARNESS_PACKAGES:
        spec = importlib.util.find_spec(package)
        if spec is None or spec.origin is None or not spec.submodule_search_locations:
            return f"loadability harness package {package!r} is not a regular package in the tool environment"
        roots.append(str(Path(spec.origin).resolve().parents[1]))
    return tuple(dict.fromkeys(roots))


def _read_checker_report(path: Path, authority: Authority) -> CheckResult:
    """Load the complete child evidence or fail closed when it is unusable."""
    try:
        payload = json.loads(path.read_text(encoding=UTF_8))
        if payload.get("schema_version") != 2:
            raise ValueError("unsupported checker report schema")
        findings = tuple(
            Finding(
                category=str(item["category"]),
                message=str(item["message"]),
                path=(authority.repository / str(item["path"])).resolve() if item.get("path") else None,
                lineno=int(item["line"]) if item.get("line") is not None else None,
                fatal=bool(item.get("fatal", False)),
                advisory=bool(item.get("advisory", False)),
            )
            for item in payload.get("findings", ())
        )
        occurrences = tuple(
            ImportOccurrence(
                fingerprint=str(item["fingerprint"]),
                source_module=str(item["source_module"]),
                target_module=str(item["target_module"]),
                imported_symbols=tuple(str(symbol) for symbol in item.get("imported_symbols", ())),
                import_form=str(item["import_form"]),
                lexical_scope=str(item["lexical_scope"]),
                contract=str(item["contract"]),
                path=(authority.repository / str(item["location"]["path"])).resolve(),
                lineno=int(item["location"]["line"]),
            )
            for item in payload.get("occurrences", ())
        )
        files_scanned = int(payload["files_scanned"])
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        return CheckResult(
            (Finding("INTERNAL_CHECKER", f"checker evidence report is unusable: {exc}", fatal=True),),
            0,
        )
    return CheckResult(findings, files_scanned, occurrences)


def run_import_gate(
    repository: Path,
    config_path: Path | None = None,
    lint_executable: str | None = None,
    budget: StepBudget | None = None,
) -> int:
    """Run the ordered authority, graph, and subordinate components.

    *budget* bounds each step; by default it is derived from the governed
    source measured before the first step.
    """
    try:
        read = read_authority(repository, config_path)
    except Exception as exc:  # broad: authority preflight must fail closed
        message = f"[AUTHORITY_PREFLIGHT] authority preflight aborted: {exc}"
        _emit_failure(
            [
                ComponentResult(
                    "authority-preflight",
                    TOOL_BROKEN,
                    message,
                )
            ]
        )
        _emit_health_payload(unavailable_import_health(message))
        return TOOL_BROKEN
    if read.authority is None:
        message = "\n".join(read.findings)
        _emit_failure(
            [ComponentResult("authority-preflight", TOOL_BROKEN, message)],
        )
        _emit_health_payload(unavailable_import_health(message))
        return TOOL_BROKEN

    authority = read.authority
    components: list[ComponentResult] = []
    if read.findings:
        components.append(ComponentResult("authority-preflight", TOOL_BROKEN, "\n".join(read.findings)))

    source_snapshot_before = _source_snapshot(authority)
    step_budget = budget or step_budget_for_source(source_snapshot_before.governed_bytes)
    linter_started = time.perf_counter()
    linter = run_import_linter(authority, lint_executable, step_budget)
    linter_seconds = time.perf_counter() - linter_started
    components.append(linter)
    load_started = time.perf_counter()
    load_component, loadability = run_loadability(authority, budget=step_budget)
    load_seconds = time.perf_counter() - load_started
    components.append(load_component)
    checker_started = time.perf_counter()
    subordinate, subordinate_result = run_subordinate(
        authority,
        force_exception=os.environ.get(_FORCE_CHECKER_EXCEPTION_ENV) == "1",
        budget=step_budget,
    )
    checker_seconds = time.perf_counter() - checker_started
    components.append(subordinate)
    source_snapshot_after = _source_snapshot(authority)

    component_cpu_seconds = {
        key: component.cpu_seconds
        for key, component in (
            ("import_linter", linter),
            ("loadability", load_component),
            ("subordinate_checker", subordinate),
        )
        if component.cpu_seconds is not None
    }
    health, exit_status = build_import_health(
        authority=authority,
        authority_findings=read.findings,
        linter_returncode=linter.returncode,
        linter_output=linter.output,
        checker=subordinate_result,
        loadability=loadability,
        load_returncode=load_component.returncode,
        source_snapshot_before=source_snapshot_before.digest,
        source_snapshot_after=source_snapshot_after.digest,
        component_durations={
            "import_linter": linter_seconds,
            "loadability": load_seconds,
            "subordinate_checker": checker_seconds,
        },
        component_cpu_seconds=component_cpu_seconds,
        step_budget=step_budget.as_dict(),
    )
    _emit_component_evidence(components)
    _emit_health_payload(health)
    return exit_status


def _combined_output(stdout: str | None, stderr: str | None) -> str:
    """Combine native streams without changing their text or encoding."""
    return "\n".join(part for part in (stdout or "", stderr or "") if part).strip()


@dataclass(frozen=True)
class _SourceSnapshot:
    """Fingerprint of the governed inputs plus the size of the governed source."""

    digest: str
    governed_bytes: int


def _source_snapshot(authority: Authority) -> _SourceSnapshot:
    """Fingerprint the governed inputs so concurrent mutation fails closed."""
    digest = hashlib.sha256()
    governed_bytes = 0
    paths: set[Path] = {authority.config_path}
    for root in authority.roots:
        paths.update(root.path.rglob("*.py"))
    ratchet = authority.repository / "dev" / "quality" / "metadata" / "import_boundary_ratchet.json"
    if ratchet.is_file():
        paths.add(ratchet)
    quality_metadata = authority.repository / "dev" / "quality" / "metadata"
    if quality_metadata.is_dir():
        paths.update(quality_metadata.glob("*.json"))
    for path in sorted(paths, key=lambda item: item.as_posix()):
        try:
            stat = path.stat()
            relative = path.relative_to(authority.repository).as_posix()
        except (OSError, ValueError) as exc:
            digest.update(f"unavailable:{path}:{exc}".encode(UTF_8))
            continue
        digest.update(f"{relative}\0{stat.st_size}\0{stat.st_mtime_ns}\n".encode(UTF_8))
        if path.suffix == ".py":
            governed_bytes += stat.st_size
    return _SourceSnapshot(digest.hexdigest(), governed_bytes)


def _emit_failure(components: list[ComponentResult]) -> None:
    """Replay only failing component diagnostics, retaining native output."""
    print("check-import-boundaries: failed")
    for component in components:
        if component.returncode == 0 or not component.output:
            continue
        label = {
            "authority-preflight": "AUTHORITY_PREFLIGHT",
            "import-linter": "GRAPH_AUTHORITY",
            "loadability": "LOADABILITY",
            "subordinate-checker": "SUBORDINATE_CHECKER",
        }.get(component.name, component.name.upper().replace("-", "_"))
        print(f"[{label}] exit {component.returncode}")
        print(component.output.rstrip())


def _emit_component_evidence(components: list[ComponentResult]) -> None:
    """Replay complete component evidence; the outer runner keeps it in the log."""
    for component in components:
        if not component.output:
            continue
        label = {
            "authority-preflight": "AUTHORITY_PREFLIGHT",
            "import-linter": "GRAPH_AUTHORITY",
            "loadability": "LOADABILITY",
            "subordinate-checker": "SUBORDINATE_CHECKER",
        }.get(component.name, component.name.upper().replace("-", "_"))
        print(f"[{label}] exit {component.returncode}")
        print(component.output.rstrip())


def _emit_health_payload(payload: dict[str, object]) -> None:
    """Emit the stable human and machine contracts together."""
    print(render_import_health(payload))
    print(json.dumps({"event": "import_health", **payload}, sort_keys=True, separators=(",", ":")))


def main(argv: list[str] | None = None) -> int:
    """Run the one import-quality verdict."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=None, help="repository/source root for isolated proofs")
    parser.add_argument("--config", type=Path, default=None, help="Import Linter configuration path")
    parser.add_argument(
        "--lint-imports",
        dest="lint_executable",
        default=None,
        help="internal executable override used by failure-path tests",
    )
    parser.add_argument(
        "--cpu-budget",
        type=float,
        default=None,
        help="CPU-seconds each step's process tree may consume (default: derived from the governed source size)",
    )
    parser.add_argument(
        "--stall-seconds",
        type=float,
        default=_STALL_SECONDS,
        help="seconds a step may stay alive without consuming CPU before it is reported unavailable",
    )
    args = parser.parse_args(argv)
    env_root = os.environ.get(_ROOT_ENV)
    repository = args.root or (Path(env_root) if env_root else REPO_ROOT)
    lint_executable = args.lint_executable or os.environ.get(_LINTER_ENV)
    budget = StepBudget(args.cpu_budget, args.stall_seconds) if args.cpu_budget is not None else None
    if budget is None and args.stall_seconds != _STALL_SECONDS:
        parser.error("--stall-seconds requires --cpu-budget")
    return run_import_gate(repository, args.config, lint_executable, budget)


__all__ = [
    "BudgetedRun",
    "ComponentResult",
    "StepBudget",
    "StepBudgetExceededError",
    "main",
    "run_import_gate",
    "run_import_linter",
    "run_loadability",
    "run_subordinate",
    "run_within_budget",
    "step_budget_for",
    "step_budget_for_source",
]


def _enforce_step_budget(
    tree: psutil.Process | None,
    consumed: dict[tuple[int, float], float],
    cpu_seconds: float,
    progress_cpu: float,
    progress_at: float,
    budget: StepBudget,
    started: float,
) -> tuple[float, float, float]:
    """Check the unchanged process CPU and stall budgets after a polling interval."""
    if tree is not None:
        cpu_seconds = _tree_cpu_seconds(tree, consumed)
    now = time.monotonic()
    if cpu_seconds > budget.cpu_seconds:
        raise StepBudgetExceededError(
            f"consumed {cpu_seconds:.2f} CPU-s, over its {budget.cpu_seconds:g} CPU-s work budget, "
            f"after {now - started:.1f} s"
        )
    if cpu_seconds > progress_cpu:
        progress_cpu, progress_at = cpu_seconds, now
    elif now - progress_at > budget.stall_seconds:
        raise StepBudgetExceededError(
            f"consumed no CPU for {now - progress_at:.1f} s (stall limit {budget.stall_seconds:g} s) "
            f"after {cpu_seconds:.2f} CPU-s"
        )
    return cpu_seconds, progress_cpu, progress_at


def _loadability_report_object(report_path: Path) -> object:
    """Loadability report object."""
    decoded_payload: object = json.loads(report_path.read_text(encoding=UTF_8))
    return decoded_payload


def _validate_loadability_report(decoded_payload: object) -> dict[str, object]:
    """Validate loadability report."""
    if not isinstance(decoded_payload, dict):
        raise ValueError("loadability report must be a JSON object")
    payload: dict[str, object] = {}
    for key, value in cast("dict[object, object]", decoded_payload).items():
        if not isinstance(key, str):
            raise ValueError("loadability report object keys must be strings")
        payload[key] = value
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported loadability report schema")
    return payload


def _set_subordinate_environment(environment: dict[str, str], import_paths: list[str]) -> None:
    """Set subordinate environment."""
    environment["PYTHONPATH"] = os.pathsep.join(dict.fromkeys(import_paths))
    environment["PYTHONIOENCODING"] = UTF_8


def _subordinate_environment(authority: Authority) -> dict[str, str]:
    """Subordinate environment."""
    environment = os.environ.copy()
    import_paths = [str(_CHECKER_PATH.parents[2]), *(str(root.source_root) for root in authority.roots)]
    existing = environment.get("PYTHONPATH")
    if existing:
        import_paths.append(existing)
    _set_subordinate_environment(environment, import_paths)
    return environment


if __name__ == "__main__":
    sys.exit(main())

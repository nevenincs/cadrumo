#!/usr/bin/env python
"""Consolidated blocking code-quality dashboard for the build harness.

Runs its selected quality gates to completion (not fail-fast), then reports:

* One line per gate, in the declared order: ``passed``, ``failed`` or
  ``reused`` and its wall seconds.
* On any failure: a compact dashboard naming each failing gate and replaying
  its actionable output, then the first failing gate's status (in declared
  order) as the exit status.

``--jobs N`` runs up to N gates at once; each gate's output is still captured
on its own and reported in the declared order. The default is one, the
sequential behaviour, because several gates are themselves multi-process (the
type checkers run three analysers at eight threads, the import gate runs its
own process pools) and the caller that runs this suite beside other work owns
the machine's budget. The two native gates both configure the same CMake build
tree and never run at the same time as each other.

``--verdict-dir PATH`` enables clean-verdict reuse (see
:mod:`dev.quality.suite_verdicts`): a gate whose declared inputs have the
content key of its last clean run, with its positive control passed under that
key, is reported ``reused`` and not run. Without it every gate runs.
``--report PATH`` writes the per-gate record as JSON.

Python gates invoke their underlying tools directly: this process is already started via ``uv run --no-sync
python -m dev.quality.suite``, so the active venv's console scripts
(``ruff`` and ``deptry``) resolve by bare name; the import-quality row calls
the authoritative Python driver, which resolves Import Linter itself, and
``sys.executable`` names the venv interpreter for the Python-module gates.
The optional native rows call their existing just recipes to preserve CMake's
configured build ownership and platform selection. This script aggregates
pass/fail and surfaces the failing detail.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import time
from collections.abc import Generator, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Final

from cadrumo.core.atomic_write import atomic_write_text
from dev.ci.lane_recipe_commands import resolve_just_executable
from dev.exit_codes import TOOL_BROKEN, TOOL_MISSING
from dev.first_party_source import DEPENDENCY_DECLARATION_ROOTS
from dev.paths import REPO_ROOT, UTF_8

from .suite_verdicts import (
    REUSE,
    Environment,
    KeyRefusal,
    ReuseDeclaration,
    TreeSnapshot,
    VerdictKey,
    current_environment,
    positive_control_command,
    publish_verdict,
    read_verdict,
    reusable,
    take_tree_snapshot,
    verdict_key,
    verdict_record,
)

_UTF_8: Final[str] = UTF_8

#: The shared CMake build tree both native gates configure.
CMAKE_CONFIGURE: Final[str] = "cmake-configure"
REPORT_SCHEMA: Final[str] = "cadrumo-quality-suite-report/v1"

# Each gate's underlying command, kept byte-identical to the tool invocation
# the matching `just check-*` recipe wraps (see justfile). Direct invocation
# here is deliberately independent of the recipe wrapper (`dev.quality.quiet`
# for the bare-tool gates): that wrapper's job — stay silent on success,
# replay on failure — is already `main()`'s job for the dashboard, so
# duplicating it here would be redundant, not protective.
GATES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("check-style", ("ruff", "check", ".")),
    ("check-format", ("ruff", "format", "--check", ".")),
    ("check-data-format", (sys.executable, "-m", "dev.quality.data_files", "check")),
    ("check-types", (sys.executable, "-m", "dev.quality.types")),
    ("complexity-gate", (sys.executable, "-m", "dev.audit.complexity", "--gate")),
    ("check-module-size", (sys.executable, "-m", "dev.quality.typescript_module_size")),
    ("check-year-literals", (sys.executable, "-m", "dev.quality.year_literals")),
    ("check-surface-redeclaration", (sys.executable, "-m", "dev.quality.surface_redeclaration")),
    ("check-import-boundaries", (sys.executable, "-m", "dev.quality.import_gate")),
    (
        "check-dependency-declarations",
        (
            "deptry",
            # The harness package ships its own console script and is where the
            # MCP and anyio dependencies are actually imported. Leaving it out
            # reported both as declared-but-unused: a scan-scope artefact, not
            # a real unused dependency.
            *DEPENDENCY_DECLARATION_ROOTS,
            "--known-first-party",
            "cadrumo",
            "--known-first-party",
            "cadrumo_mcp",
            "--known-first-party",
            "cadrumo_agent_service",
            "--known-first-party",
            "cadrumo_client",
            "--known-first-party",
            "cadrumo_runtime",
            "--known-first-party",
            "dev",
            "--non-dev-dependency-groups",
            "registry",
            "--extend-exclude",
            r"(?:^|[\\/])test_.*[.]py$",
            "--extend-exclude",
            r"(?:^|[\\/])_test_.*[.]py$",
            "--extend-exclude",
            r".*[\\/]tests[\\/].*",
            "--extend-exclude",
            r"(?:^|[\\/])_data[\\/]",
            "--extend-exclude",
            r"(?:^|[\\/])conftest[.]py$",
        ),
    ),
    (
        "check-module-reachability",
        (sys.executable, "-m", "dev.quality.unreachable_module_coverage"),
    ),
    (
        "check-symbol-usage",
        (sys.executable, "-m", "dev.quality.unused_symbol_coverage"),
    ),
    (
        "check-export-consumption",
        (sys.executable, "-m", "dev.quality.unconsumed_export_coverage"),
    ),
    (
        "check-secure-store-write-paths",
        (sys.executable, "-m", "dev.quality.secure_store_write_path"),
    ),
    (
        "check-persistence-write-paths",
        (sys.executable, "-m", "dev.quality.write_path_coverage"),
    ),
    ("check-docstring-references", (sys.executable, "-m", "dev.quality.docstring_reference_targets")),
    (
        "check-operation-contract-manifest",
        (sys.executable, "-m", "dev.operation_contract_manifest.generate", "--check"),
    ),
)


@dataclass(frozen=True)
class GateResult:
    """Outcome of one gate run."""

    name: str
    returncode: int
    output: str
    seconds: float = 0.0
    reused: bool = False
    note: str = ""

    @property
    def status(self) -> str:
        """``reused`` for a reused clean verdict, else ``passed`` or ``failed`` by exit status."""
        if self.reused:
            return "reused"
        return "passed" if self.returncode == 0 else "failed"


@dataclass(frozen=True)
class Gate:
    """One gate to run: its name, command and the exclusive resources it holds while running."""

    name: str
    command: tuple[str, ...]
    resources: frozenset[str] = field(default_factory=frozenset)


def run_gate(name: str, command: tuple[str, ...], *, cwd: Path | None = None) -> GateResult:
    """Run a single gate's underlying tool command, capturing combined output and wall seconds."""
    started = time.perf_counter()
    # Decode explicitly: `text=True` alone uses the locale preferred encoding,
    # which on a Windows console is cp1252. The wrapped gates emit UTF-8, so the
    # reader thread died on the first non-cp1252 byte and the dashboard lost the
    # whole run rather than reporting the gate's verdict.
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding=_UTF_8,
            errors="replace",
            check=False,
            cwd=cwd,
        )
    except FileNotFoundError as error:
        return GateResult(name, TOOL_MISSING, f"cannot run {command[0]}: {error}", _since(started))
    except OSError as error:
        return GateResult(name, TOOL_BROKEN, f"cannot run {command[0]}: {error}", _since(started))
    return GateResult(
        name=name,
        returncode=result.returncode,
        output=((result.stdout or "") + (result.stderr or "")).strip(),
        seconds=_since(started),
    )


def _since(started: float) -> float:
    return time.perf_counter() - started


def native_gates(configuration: str = "Debug") -> tuple[list[Gate], list[GateResult]]:
    """Return the platform-owned gates to run, or their unavailability when ``just`` cannot be resolved."""
    names = ("check-frontend", "check-rust")
    try:
        executable = resolve_just_executable()
    except RuntimeError as error:
        return [], [GateResult(name, TOOL_MISSING, str(error)) for name in names]
    return [Gate(name, (executable, name, configuration), frozenset({CMAKE_CONFIGURE})) for name in names], []


class _Resources:
    """One lock per named exclusive resource, always taken in name order so two gates cannot deadlock."""

    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._locks: dict[str, threading.Lock] = {}

    @contextmanager
    def held(self, names: frozenset[str]) -> Generator[None]:
        with ExitStack() as stack:
            for name in sorted(names):
                with self._guard:
                    lock = self._locks.setdefault(name, threading.Lock())
                stack.enter_context(lock)
            yield


@dataclass(frozen=True)
class _Reuse:
    """The verdict store and the inputs as they stood when the suite started."""

    directory: Path
    root: Path
    snapshot: TreeSnapshot
    environment: Environment


@dataclass(frozen=True)
class GateOutcome:
    """One gate's result, the input key it was judged under, and the clean verdict to record, if any."""

    result: GateResult
    key: VerdictKey | KeyRefusal | None = None
    record: dict[str, object] | None = None


def _start_reuse(directory: Path, root: Path) -> _Reuse:
    declarations = list(REUSE.values())
    return _Reuse(
        directory=directory,
        root=root,
        snapshot=take_tree_snapshot(root, declarations),
        environment=current_environment(name for item in declarations for name in item.executables),
    )


def _execute(gate: Gate, resources: _Resources, reuse: _Reuse | None) -> GateOutcome:
    """Run one gate, or reuse its recorded clean verdict when its input key matches."""
    declaration = REUSE.get(gate.name) if reuse is not None else None
    if reuse is None or declaration is None:
        with resources.held(gate.resources):
            return GateOutcome(run_gate(gate.name, gate.command))
    key = verdict_key(gate.name, gate.command, declaration, reuse.snapshot, reuse.environment)
    if isinstance(key, VerdictKey) and reusable(read_verdict(reuse.directory, gate.name), gate.name, key, declaration):
        return GateOutcome(GateResult(gate.name, 0, "", reused=True, note="clean verdict reused"), key)
    with resources.held(gate.resources):
        result = run_gate(gate.name, gate.command)
    return _checked(gate, result, key, declaration, reuse)


def _checked(
    gate: Gate, result: GateResult, key: VerdictKey | KeyRefusal, declaration: ReuseDeclaration, reuse: _Reuse
) -> GateOutcome:
    """Refuse a gate that read nothing, and prove a clean one can fail before its verdict may be kept."""
    if key.scanned_files == 0:
        empty = "the gate's declared input set resolved to zero files, so its verdict measured nothing"
        return GateOutcome(
            replace(result, returncode=result.returncode or TOOL_BROKEN, output=f"{empty}\n{result.output}".strip()),
            key,
        )
    if result.returncode != 0:
        return GateOutcome(result, key)
    if isinstance(key, KeyRefusal):
        return GateOutcome(replace(result, note=f"not recorded: {key.reason}"), key)
    control = run_gate(f"{gate.name} positive control", positive_control_command(declaration), cwd=reuse.root)
    seconds = result.seconds + control.seconds
    if control.returncode != 0:
        output = f"positive control failed, so a clean result cannot be trusted:\n{control.output}"
        return GateOutcome(replace(result, returncode=TOOL_BROKEN, output=output, seconds=seconds), key)
    record = verdict_record(gate.name, key.key, declaration, scanned_files=key.scanned_files, seconds=seconds)
    return GateOutcome(replace(result, seconds=seconds, note="positive control passed"), key, record)


def _publish_unchanged(outcomes: list[GateOutcome], gates: Sequence[Gate], reuse: _Reuse) -> list[GateOutcome]:
    """Record each clean verdict whose inputs still have the key they were checked under."""
    if not any(outcome.record is not None for outcome in outcomes):
        return outcomes
    after = _start_reuse(reuse.directory, reuse.root)
    published: list[GateOutcome] = []
    for gate, outcome in zip(gates, outcomes, strict=True):
        if outcome.record is None or not isinstance(outcome.key, VerdictKey):
            published.append(outcome)
            continue
        again = verdict_key(gate.name, gate.command, REUSE[gate.name], after.snapshot, after.environment)
        if not isinstance(again, VerdictKey) or again.key != outcome.key.key:
            note = "not recorded: its inputs changed while the suite ran"
            published.append(replace(outcome, result=replace(outcome.result, note=note), record=None))
            continue
        try:
            publish_verdict(reuse.directory, gate.name, outcome.record)
        except OSError as error:
            note = f"not recorded: {error}"
            published.append(replace(outcome, result=replace(outcome.result, note=note), record=None))
            continue
        published.append(replace(outcome, result=replace(outcome.result, note="clean verdict recorded")))
    return published


def run_gates(
    gates: Sequence[Gate], *, jobs: int = 1, verdict_dir: Path | None = None, root: Path = REPO_ROOT
) -> list[GateOutcome]:
    """Run ``gates`` at most ``jobs`` at a time and return their outcomes in the declared order."""
    if jobs < 1:
        raise ValueError(f"jobs must be at least 1, got {jobs}")
    reuse = _start_reuse(verdict_dir, root) if verdict_dir is not None else None
    resources = _Resources()
    if jobs == 1:
        outcomes = [_execute(gate, resources, reuse) for gate in gates]
    else:
        with ThreadPoolExecutor(max_workers=jobs, thread_name_prefix="quality-gate") as pool:
            futures = [pool.submit(_execute, gate, resources, reuse) for gate in gates]
            outcomes = [future.result() for future in futures]
    return outcomes if reuse is None else _publish_unchanged(outcomes, gates, reuse)


def main(
    *,
    native: bool = False,
    native_only: bool = False,
    configuration: str = "Debug",
    jobs: int = 1,
    verdict_dir: Path | None = None,
    report: Path | None = None,
) -> int:
    """Run every gate and emit the consolidated dashboard.

    Every gate runs even after one fails, because an aggregate is asked for a
    complete picture and fail-fast costs a CI round-trip per defect. The status
    returned is the FIRST non-zero one in declared order: the earliest failure is
    the one that may explain the rest, and its actual value distinguishes a gate
    that found something (1) from a gate that could not run at all (127). See
    ``dev/EXIT-CODES.md``.
    """
    started = time.perf_counter()
    gates = [] if native_only else [Gate(name, command) for name, command in GATES]
    unavailable: list[GateResult] = []
    if native or native_only:
        native_rows, unavailable = native_gates(configuration)
        gates.extend(native_rows)
    outcomes = run_gates(gates, jobs=jobs, verdict_dir=verdict_dir)
    results = [outcome.result for outcome in outcomes] + unavailable
    name = "check-native-code" if native_only else "check-code" if native else "check-python"
    if report is not None:
        keys = {outcome.result.name: outcome.key for outcome in outcomes}
        _write_report(report, name, results, keys, jobs=jobs, verdict_dir=verdict_dir, seconds=_since(started))
    _emit_timings(results)
    return _report_results(name, results)


def _write_report(
    path: Path,
    name: str,
    results: Sequence[GateResult],
    keys: Mapping[str, VerdictKey | KeyRefusal | None],
    *,
    jobs: int,
    verdict_dir: Path | None,
    seconds: float,
) -> None:
    rows: list[dict[str, object]] = []
    for result in results:
        key = keys.get(result.name)
        rows.append(
            {
                "name": result.name,
                "status": result.status,
                "returncode": result.returncode,
                "seconds": round(result.seconds, 3),
                "reuse_enabled": result.name in REUSE,
                "input_key": key.key if isinstance(key, VerdictKey) else None,
                "scanned_files": key.scanned_files if key is not None else None,
                "note": key.reason if isinstance(key, KeyRefusal) and not result.note else result.note,
            }
        )
    payload = {
        "schema": REPORT_SCHEMA,
        "suite": name,
        "jobs": jobs,
        "verdict_dir": str(verdict_dir) if verdict_dir is not None else None,
        "wall_seconds": round(seconds, 3),
        "exit_status": next((result.returncode for result in results if result.returncode != 0), 0),
        "gates": rows,
    }
    atomic_write_text(path, json.dumps(payload, indent=2) + "\n", encoding=_UTF_8)


def _emit_timings(results: Sequence[GateResult]) -> None:
    for result in results:
        note = f"  ({result.note})" if result.note else ""
        _emit(f"{result.status:<7} {result.seconds:9.1f}s  {result.name}{note}")


def _report_results(name: str, results: list[GateResult]) -> int:
    """Render every failure while retaining the first gate's actual exit status."""
    failed = [r for r in results if r.returncode != 0]

    if not failed:
        return 0

    _emit(f"\n{name}: {len(failed)} of {len(results)} gates failed\n")
    _emit_failed_gates(failed)
    return failed[0].returncode


def _emit(line: str) -> None:
    """Print a dashboard line without tripping a narrow console encoding.

    The replay carries the wrapped tools' UTF-8, which a cp1252 console
    cannot encode, so printing the dashboard raised instead of reporting
    which gate failed.
    """
    encoding = sys.stdout.encoding or ""
    if encoding.lower().replace("-", "") != "utf8":
        sys.stdout.buffer.write(f"{line}\n".encode(errors="replace"))
        sys.stdout.flush()
        return
    print(line)


def _emit_failed_gates(failed: list[GateResult]) -> None:
    """Emit failed gates."""
    for result in failed:
        _emit(f"FAIL  {result.name}")
        if result.output:
            _emit(result.output)
        _emit("")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--all-languages", action="store_true", help="Include frontend and Rust gates.")
    scope.add_argument("--native-only", action="store_true", help="Run only frontend and Rust gates.")
    parser.add_argument("--configuration", choices=("Debug", "Release"), default="Debug")
    parser.add_argument("--jobs", type=int, default=1, help="Run up to this many gates at once (default 1).")
    parser.add_argument(
        "--verdict-dir",
        type=Path,
        default=None,
        help="Reuse and record clean verdicts keyed on each gate's declared input content.",
    )
    parser.add_argument("--report", type=Path, default=None, help="Write the per-gate record as JSON.")
    options = parser.parse_args()
    if options.jobs < 1:
        parser.error("--jobs must be at least 1")
    sys.exit(
        main(
            native=options.all_languages,
            native_only=options.native_only,
            configuration=options.configuration,
            jobs=options.jobs,
            verdict_dir=options.verdict_dir,
            report=options.report,
        )
    )

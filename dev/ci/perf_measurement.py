"""Load-immune process CPU-time measurement for performance gates.

The `.github` control plane's honest-perf-gate invariant requires every
performance benchmark to ASSERT process CPU-time and to print wall-clock as an
advisory only. The reason is measured, not theoretical: the fleet runs several
jobs per physical machine and the workstation additionally hosts the
developer's own agent fleet, so wall-clock on a compute-bound measurement is
dominated by co-resident load. A bare ``python -c "import sys"`` spawn measured
1.63-5.00 s WALL on that box while its CPU stayed at 0.08 s -- a 20x spread in
the quantity a wall gate would bind, and a 1.4x spread in the quantity a CPU
gate binds.

This module is the single home for that measurement so no benchmark grows its
own copy. Two shapes are covered:

* **In-process** work is measured with :func:`time.process_time` directly at
  the call site -- it is a stdlib one-liner and needs no wrapper.
* **Subprocess** work needs :func:`timed_subprocess`, because reading a child's
  CPU time is genuinely platform-specific: POSIX takes an ``RUSAGE_CHILDREN``
  delta around the reaped child, while Windows needs a Job Object to aggregate
  a process TREE (a console-script shim spawns the real interpreter as a
  grandchild that per-process times would miss entirely).

Caveat stated honestly: CPU-time excludes wait-time, but SMT and cache
contention still inflate it. The measured inflation on the workstation is
~1.64x (a steady-state calculation measuring 1.97 CPU-s quiet and 3.23 CPU-s
under full co-resident load), so ceilings derived from a baseline must carry
that margin rather than pretending CPU-time is perfectly load-invariant.

That same exclusion of wait-time is a HOLE as well as a virtue, which is why
:func:`wall_advisory_message` also lives here. A test blocked on a wedged
network mount burns almost no CPU, so converting a gate to CPU-time removes
the only instrument that could ever notice it stalling. The conversions keep
their wall threshold as a non-failing advisory rather than deleting it, and
this module owns that emission for the same reason it owns the measurement:
so the two sites cannot drift into two conventions.
"""

from __future__ import annotations

import subprocess
import sys
import time
import warnings
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from .._paths import UTF_8

_UTF_8: Final[str] = UTF_8

#: Measured SMT/cache-contention inflation of CPU-time on the shared
#: workstation (3.23 CPU-s loaded against 1.97 CPU-s quiet for one
#: steady-state calculation). A ceiling derived from a baseline measurement
#: multiplies by this rather than assuming CPU-time is perfectly load-invariant.
CPU_CONTENTION_MARGIN: Final[float] = 1.64


class WallClockAdvisory(UserWarning):
    """A CPU-gated benchmark's WALL time looks wedged rather than merely loaded.

    Never a failure. It is raised on the warnings channel rather than printed
    because the channel is the only one that reaches a reader on a PASSING
    test: the broad serial pass runs ``pytest -q ... -n0`` with no ``-s``, so
    fd-level capture swallows every ``print`` from a test that passes, which is
    exactly the run this signal exists for. pytest renders its warnings summary
    by default, including under ``-q``.
    """


def wall_advisory_message(
    label: str,
    *,
    wall_seconds: float,
    cpu_seconds: float,
    wall_advisory_seconds: float,
    hang_wall_to_cpu_ratio: float,
) -> str | None:
    """Return a wedge advisory for ``label``, or ``None`` when nothing is wrong.

    Moving a perf gate from wall-clock to CPU-time is the correct instrument
    choice for the co-residency this fleet has (see the module docstring), but
    a straight conversion DELETES the only bound that can see a share hang: a
    test blocked on a wedged network mount burns almost no CPU, so a CPU
    ceiling can never fire on it however long it stalls. This keeps the wall
    threshold as the trigger and hands the reader both clocks.

    The ratio is what stops the retained bound decaying into noise. On a box
    this loaded the wall threshold alone is crossed constantly by tests that
    are merely queued behind co-resident work, and an advisory that fires on
    every run is one every reader learns to skip. Load inflates BOTH clocks;
    a block inflates only wall. So the advisory needs both conditions, and
    ``hang_wall_to_cpu_ratio`` is per-site rather than global because the
    ratio a healthy site runs at depends on how much of its wall time is
    spawn-wait: an in-process aggregation sits near 1, while a subprocess cold
    start pays process creation the SUT is not answerable for.

    Args:
        label: Benchmark identity, quoted verbatim into the advisory.
        wall_seconds: Measured wall-clock seconds (the advisory's trigger).
        cpu_seconds: Measured process CPU seconds (the asserted gate's figure).
        wall_advisory_seconds: Retained wall threshold; at or below it the site
            is healthy by definition and nothing is emitted.
        hang_wall_to_cpu_ratio: Wall-to-CPU ratio above which a crossing is
            wedge-shaped rather than load-shaped, derived per site from that
            site's own measured loaded maximum.

    Returns:
        The advisory text when it fired, so a caller can also route it
        somewhere durable; ``None`` when it did not.
    """
    if wall_seconds <= wall_advisory_seconds:
        return None
    # A zero-CPU sample is the wedge in its purest form, not a division to
    # guard around: it is what a fully-blocked test measures.
    ratio = float("inf") if cpu_seconds <= 0.0 else wall_seconds / cpu_seconds
    if ratio <= hang_wall_to_cpu_ratio:
        return None

    message = (
        f"{label}: wall {wall_seconds:.3f}s crossed its {wall_advisory_seconds:.3f}s advisory "
        f"threshold on {cpu_seconds:.3f} CPU-s (ratio {ratio:.1f}x, wedge above "
        f"{hang_wall_to_cpu_ratio:.1f}x). CPU is the asserted gate and it is unaffected, so "
        f"this is NOT a performance regression — it is wall time spent not computing, which "
        f"is what a blocked mount or a wedged child looks like and what a CPU ceiling can "
        f"never see. A merely loaded box inflates both clocks and does not reach here."
    )
    warnings.warn(message, WallClockAdvisory, stacklevel=2)
    return message


class ProcessCpuMeasurementError(RuntimeError):
    """Raised when a child process's CPU time cannot be measured."""


class WindowsJobCpuAccounting:
    """Total CPU seconds of a child AND its descendants via a Job Object.

    A console-script launcher on Windows is an exe shim that spawns the real
    python interpreter as a grandchild, so per-process ``GetProcessTimes``
    reads only the shim (~0 CPU). A Job Object aggregates the whole tree: the
    shim is assigned right after spawn, its descendants inherit membership, and
    the job's basic accounting keeps the FINAL user + kernel totals (100 ns
    units) queryable after every member exits.
    """

    def __init__(self) -> None:
        """Create the job object every measured child will be assigned to."""
        import ctypes

        self._ctypes = ctypes
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._job = self._kernel32.CreateJobObjectW(None, None)
        if not self._job:
            raise ProcessCpuMeasurementError(f"CreateJobObject failed (error {ctypes.get_last_error()})")

    def assign(self, process: Any) -> None:
        """Enrol a live child (and, by inheritance, its descendants) in the job."""
        # The private Popen handle is the point: assignment must target the
        # live child before it spawns the interpreter grandchild.
        if not self._kernel32.AssignProcessToJobObject(self._job, int(process._handle)):
            raise ProcessCpuMeasurementError(
                f"AssignProcessToJobObject failed for pid {process.pid} (error {self._ctypes.get_last_error()})",
            )

    def cpu_seconds(self) -> float:
        """Return the job's total user + kernel CPU seconds across every member."""
        ctypes = self._ctypes

        class _JobBasicAccounting(ctypes.Structure):
            _fields_ = (
                ("TotalUserTime", ctypes.c_longlong),
                ("TotalKernelTime", ctypes.c_longlong),
                ("ThisPeriodTotalUserTime", ctypes.c_longlong),
                ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
                ("TotalPageFaultCount", ctypes.c_uint32),
                ("TotalProcesses", ctypes.c_uint32),
                ("ActiveProcesses", ctypes.c_uint32),
                ("TotalTerminatedProcesses", ctypes.c_uint32),
            )

        accounting = _JobBasicAccounting()
        job_object_basic_accounting_information = 1
        ok = self._kernel32.QueryInformationJobObject(
            self._job,
            job_object_basic_accounting_information,
            ctypes.byref(accounting),
            ctypes.sizeof(accounting),
            None,
        )
        if not ok:
            raise ProcessCpuMeasurementError(
                f"QueryInformationJobObject failed (error {ctypes.get_last_error()})",
            )
        return (accounting.TotalUserTime + accounting.TotalKernelTime) / 10_000_000

    def close(self) -> None:
        """Release the job handle."""
        self._kernel32.CloseHandle(self._job)


@dataclass(frozen=True)
class SubprocessTiming:
    """One timed child run: CPU seconds gate, wall seconds are advisory."""

    wall_seconds: float
    cpu_seconds: float
    returncode: int
    stdout: str
    stderr: str


def timed_subprocess(
    argv: Sequence[str],
    *,
    env: Mapping[str, str] | None = None,
    cwd: Path | None = None,
    timeout_s: float,
) -> SubprocessTiming:
    """Run one child and return its wall time, TREE CPU time, and captured output.

    CPU seconds is the load-immune figure a perf gate binds. POSIX reads the
    ``RUSAGE_CHILDREN`` delta around the reaped child; Windows aggregates the
    child and every descendant through a :class:`WindowsJobCpuAccounting` job,
    which stays queryable after the members exit.

    The return code is REPORTED, never raised on: a benchmark and a structural
    gate want different failure vocabulary for a non-zero child, so that choice
    stays with the caller.
    """
    argv_list = [str(part) for part in argv]
    run_env = None if env is None else dict(env)
    run_cwd = None if cwd is None else str(cwd)

    if sys.platform.startswith("win"):
        accounting = WindowsJobCpuAccounting()
        try:
            started = time.monotonic()
            process = subprocess.Popen(  # noqa: S603 - fixed resolved executable and declarative argv
                argv_list,
                cwd=run_cwd,
                env=run_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding=_UTF_8,
                errors="strict",
            )
            accounting.assign(process)
            try:
                stdout, stderr = process.communicate(timeout=timeout_s)
            except subprocess.TimeoutExpired:
                process.kill()
                raise
            elapsed = time.monotonic() - started
            cpu_seconds = accounting.cpu_seconds()
            returncode = process.returncode
        finally:
            accounting.close()
    else:
        import resource

        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        started = time.monotonic()
        completed = subprocess.run(  # noqa: S603 - fixed resolved executable and declarative argv
            argv_list,
            cwd=run_cwd,
            env=run_env,
            capture_output=True,
            text=True,
            encoding=_UTF_8,
            errors="strict",
            timeout=timeout_s,
            check=False,
        )
        elapsed = time.monotonic() - started
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        cpu_seconds = (after.ru_utime - before.ru_utime) + (after.ru_stime - before.ru_stime)
        stdout, stderr, returncode = completed.stdout, completed.stderr, completed.returncode

    return SubprocessTiming(
        wall_seconds=elapsed,
        cpu_seconds=cpu_seconds,
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def min_subprocess_cpu_seconds(
    argv: Sequence[str],
    *,
    samples: int,
    env: Mapping[str, str] | None = None,
    cwd: Path | None = None,
    timeout_s: float,
) -> tuple[float, float, SubprocessTiming]:
    """Spawn ``argv`` ``samples`` times; return (min CPU s, min wall s, last run).

    ``min`` is the conservative cold-start estimate on a shared machine:
    contention only ever ADDS CPU (SMT and cache pressure) and wall time, so the
    minimum is the closest available reading of the unloaded cost and filters
    transient scheduler spikes. Taking the minimum of each clock independently
    is deliberate -- the two are reported separately and never subtracted from
    one another.
    """
    if samples < 1:
        raise ProcessCpuMeasurementError(f"samples must be >= 1, got {samples}")
    runs = [timed_subprocess(argv, env=env, cwd=cwd, timeout_s=timeout_s) for _ in range(samples)]
    return (
        min(run.cpu_seconds for run in runs),
        min(run.wall_seconds for run in runs),
        runs[-1],
    )

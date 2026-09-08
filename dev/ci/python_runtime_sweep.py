"""Drive the source and binary compatibility probes across every declared runtime.

The probes themselves already lived in `dev/`: this module replaced only the
SWEEP around them, which was written twice - 44 lines of bash and 32 of
PowerShell - and reached into the inventory through a `python -c` one-liner
that re-serialised it as tab-separated text on one platform and as JSON on the
other. Two serialisations of one in-process object, parsed by two shells, to
answer a question this module can simply ask.

The release cohort is built ONCE and its sealed bytes are consumed by every
binary row; no runtime rebuilds it.

Evidence is written beneath `var/python-runtime-compatibility/runs/` and stays
there. Nothing is uploaded: this repository deliberately produces no Actions
artifacts, and the `::error::`/`::warning::` lines below are workflow log
annotations, which is the whole of its CI reporting surface.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from dev._paths import REPO_ROOT
from dev.ci.python_runtime_matrix import RuntimeRecord, load_runtime_inventory

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

#: Where a sweep's evidence tree is rooted.
RUNS_ROOT = REPO_ROOT / "var" / "python-runtime-compatibility" / "runs"

#: The two probe modes every runtime is exercised in, in order. `source`
#: installs from the tree; `binary` consumes the sealed release cohort.
MODES = ("source", "binary")

#: The evidence document each probe writes.
EVIDENCE_NAME = "compatibility-evidence.json"


@dataclass(frozen=True)
class ProbeOutcome:
    """One probe's result.

    Args:
        runtime_id: The inventory row's identifier.
        mode: Either ``source`` or ``binary``.
        status: The probe's exit code.
        blocking: Whether a failure fails the sweep. A prerelease canary is
            advisory: it stays visible as evidence without gating.
    """

    runtime_id: str
    mode: str
    status: int
    blocking: bool

    @property
    def failed(self) -> bool:
        """Whether this probe did not succeed."""
        return self.status != 0


def _run(argv: Sequence[str]) -> int:
    """Run a subprocess and return its exit code.

    Args:
        argv: The argument vector to execute.

    Returns:
        The child's exit code, or 127 when it could not be started.
    """
    print(f"$ {' '.join(argv)}", flush=True)
    try:
        return subprocess.run(list(argv), check=False).returncode
    except OSError as exc:
        print(f"{argv[0]} could not be executed: {exc}", file=sys.stderr, flush=True)
        return 127


def _uv_run(*argv: str) -> list[str]:
    """Build an argument vector running a module from the existing environment."""
    return ["uv", "run", "--no-sync", "python", *argv]


def allocate_run_root(now: datetime | None = None) -> Path:
    """Return a fresh, collision-resistant evidence root for one sweep.

    Args:
        now: Clock override for testing.

    Returns:
        The run directory, already created.
    """
    started = now or datetime.now(tz=UTC)
    run_id = f"{started:%Y%m%dT%H%M%S}Z-{os.getpid()}"
    run_root = RUNS_ROOT / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    return run_root


def _head_commit() -> str | None:
    """Return the checked-out commit, or ``None`` when git cannot answer."""
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def _build_cohort(cohort: Path, commit: str) -> int:
    """Build the release cohort once, for every binary row to share.

    Args:
        cohort: Where the sealed cohort is written.
        commit: The commit the cohort must attest to.

    Returns:
        The builder's exit code.
    """
    return _run(
        _uv_run(
            "-m",
            "dev.packaging.release_cohort",
            "build",
            "--output",
            str(cohort),
            "--expected-commit",
            commit,
        )
    )


def _probe_argv(row: RuntimeRecord, mode: str, evidence_dir: Path, cohort: Path) -> list[str]:
    """Build one probe invocation.

    Args:
        row: The inventory row being probed.
        mode: ``source`` or ``binary``.
        evidence_dir: Where this probe writes its working files and evidence.
        cohort: The sealed cohort, passed only for the binary mode.

    Returns:
        The argument vector to execute.
    """
    argv = _uv_run(
        "-m",
        "dev.ci.python_runtime_compatibility",
        "--mode",
        mode,
        "--python",
        row.selector,
        "--runtime-id",
        row.identifier,
        "--stability",
        row.phase.value,
        "--repo-root",
        str(REPO_ROOT),
        "--work-dir",
        str(evidence_dir),
        "--evidence",
        str(evidence_dir / EVIDENCE_NAME),
    )
    if mode == "binary":
        argv += ["--cohort-dir", str(cohort)]
    return argv


def _probe_rows(rows: Sequence[RuntimeRecord], run_root: Path, cohort: Path) -> Iterator[ProbeOutcome]:
    """Run every mode against every row, yielding each outcome.

    Args:
        rows: The inventory rows.
        run_root: The sweep's evidence root.
        cohort: The sealed release cohort.

    Yields:
        One :class:`ProbeOutcome` per row and mode.
    """
    for row in rows:
        for mode in MODES:
            evidence_dir = run_root / row.identifier / mode
            evidence_dir.mkdir(parents=True, exist_ok=True)
            status = _run(_probe_argv(row, mode, evidence_dir, cohort))
            yield ProbeOutcome(
                runtime_id=row.identifier,
                mode=mode,
                status=status,
                blocking=bool(row.blocking),
            )


def _report(outcome: ProbeOutcome) -> None:
    """Annotate a failed probe in the workflow log.

    Args:
        outcome: The probe result to report.
    """
    severity = "error" if outcome.blocking else "warning"
    kind = "blocking" if outcome.blocking else "advisory"
    print(
        f"::{severity}::{kind} {outcome.mode} compatibility probe failed for {outcome.runtime_id}",
        file=sys.stderr,
        flush=True,
    )


def sweep() -> int:
    """Probe every declared runtime in both modes and report the verdict.

    Returns:
        1 when any BLOCKING probe failed, otherwise 0. An advisory failure is
        annotated and does not gate - that is what makes the inventory's
        prerelease canary visible without making it fatal.
    """
    inventory = load_runtime_inventory()
    rows = list(inventory.rows)
    if not rows:
        print("runtime inventory produced no rows", file=sys.stderr, flush=True)
        return 1

    commit = _head_commit()
    if commit is None:
        print(
            "could not resolve HEAD - the release cohort must attest to a commit",
            file=sys.stderr,
            flush=True,
        )
        return 1

    run_root = allocate_run_root()
    cohort = run_root / "cohort"
    code = _build_cohort(cohort, commit)
    if code != 0:
        return code

    failed = False
    for outcome in _probe_rows(rows, run_root, cohort):
        if not outcome.failed:
            continue
        _report(outcome)
        if outcome.blocking:
            failed = True

    print(f"\ncompatibility evidence: {run_root}", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(sweep())

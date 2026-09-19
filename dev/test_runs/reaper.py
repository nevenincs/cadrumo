"""Liveness-gated reclamation of repository-local test-run directories.

A run directory is command output. It is written by one invocation, it is read
back by nothing, and it carries no meaning the next run needs -- so the only
question this module asks is whether the run that owns it has finished writing.
A finished run's directory is reclaimable immediately.

There is deliberately no retention window. One stood here for seven days on the
reasoning that a completed run's output was evidence worth keeping, and the
reasoning was wrong in both directions: it let 2,354 run directories and 9.3 GB
accumulate at the repository root, and it invited exactly one consumer to grow
against it -- a dead-weight baseline that globbed a previous run's signal file
and reported a delta from it. That consumer is gone, and no age threshold
replaces it, because a threshold is the mechanism by which run output starts
being treated as history.
"""

from __future__ import annotations

import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.link_safety import is_link_like
from cadrumo.tests.collection_storage_root import process_is_live

INTERRUPTED_GRACE_SECONDS = 10 * 60
"""Mtime silence after which a run with no owner and no ``run.json`` is reclaimed.

The one threshold left, and it measures liveness rather than age: a directory
with no completion record may still be being written, and a run whose name does
not carry a readable PID cannot be resolved against the OS. Ten minutes of
silence is what stands in for the observation that is unavailable there. It is
not a retention period -- it never applies to a run that finished.
"""


@dataclass(frozen=True)
class RunVerdict:
    """Reclamation decision for one test-run directory."""

    directory: Path
    reclaimable: bool
    reason: str


def _owner_pid(directory: Path) -> int | None:
    parts = directory.name.rsplit("-", 2)
    if len(parts) != 3 or not parts[1].isdigit():
        return None
    return int(parts[1])


def assess_run_directories(root: Path, *, now: float | None = None) -> tuple[RunVerdict, ...]:
    """Classify run directories without deleting: finished output goes, live work stays.

    A ``run.json`` is the completion record its own invocation writes last, so its
    presence answers the only question here. Its absence does not prove the
    opposite -- the run may have been killed before writing one -- which is what
    :data:`INTERRUPTED_GRACE_SECONDS` and the owning PID are for.
    """
    reference = time.time() if now is None else now
    verdicts: list[RunVerdict] = []
    try:
        date_directories = scan_directory(root, require_root=True)
    except OSError:
        return ()
    for date_directory in date_directories:
        if is_link_like(date_directory) or not date_directory.is_dir():
            continue
        try:
            runs = scan_directory(date_directory, require_root=True)
        except OSError:
            continue
        for run in runs:
            if is_link_like(run) or not run.is_dir():
                continue
            try:
                age = reference - run.stat().st_mtime
            except OSError:
                continue
            if (run / "run.json").is_file():
                reclaimable = True
                reason = "completed run output, which nothing reads back"
            else:
                pid = _owner_pid(run)
                owner_live = pid is None or process_is_live(pid)
                reclaimable = not owner_live and age > INTERRUPTED_GRACE_SECONDS
                reason = "interrupted owner is gone" if reclaimable else "owner is running or unknown"
            verdicts.append(RunVerdict(run, reclaimable, reason))
    return tuple(verdicts)


def reclaim_run_directories(verdicts: tuple[RunVerdict, ...]) -> int:
    """Remove only directories already classified as reclaimable."""
    removed = 0
    for verdict in verdicts:
        if not verdict.reclaimable or is_link_like(verdict.directory):
            continue
        shutil.rmtree(verdict.directory, ignore_errors=True)
        if not verdict.directory.exists():
            removed += 1
    return removed

"""Conservative retention for repository-local test-run directories."""

from __future__ import annotations

import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.link_safety import is_link_like
from cadrumo.tests.collection_storage_root import process_is_live

COMPLETED_RETENTION_SECONDS = 7 * 24 * 60 * 60
INTERRUPTED_GRACE_SECONDS = 10 * 60


@dataclass(frozen=True)
class RunVerdict:
    """Retention decision for one test-run directory."""

    directory: Path
    reclaimable: bool
    reason: str


def _owner_pid(directory: Path) -> int | None:
    parts = directory.name.rsplit("-", 2)
    if len(parts) != 3 or not parts[1].isdigit():
        return None
    return int(parts[1])


def assess_run_directories(root: Path, *, now: float | None = None) -> tuple[RunVerdict, ...]:
    """Classify completed and interrupted run directories without deleting."""
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
                reclaimable = age > COMPLETED_RETENTION_SECONDS
                reason = "completed evidence passed retention" if reclaimable else "completed evidence is retained"
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

"""Canonical paths for date-partitioned development run output.

Run output is transient by construction: one invocation writes a directory
under the configured Cadrumo storage root, nothing reads it back, and every
base below is reclaimed. The word "evidence" does not appear in this module's
vocabulary on purpose -- a finding that must outlive its run belongs in durable
evidence, not in a path under ``.logs``.
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final
from uuid import uuid4

from cadrumo.core.storage_environment import prepare_temporary_directory, resolve_storage_path, storage_directory
from dev._paths import REPO_ROOT

LOGS_STEM = ".logs"
"""The one directory name every run family lives under, whatever the base."""

TEST_RUNS_FAMILY = "test-runs"
"""The family a pytest controller invocation writes."""


def run_log_bases() -> tuple[Path, ...]:
    """Return every base directory that can hold a ``.logs`` run family.

    The configured storage root is the active base. The repository and current
    OS temp roots remain in the list so the reaper can find output made by older
    versions while new writers use the overrideable root.
    """
    current = test_log_root()
    # Keep old bases in the reaper population while new writers use the
    # configured Cadrumo log root.
    return tuple(dict.fromkeys((current, REPO_ROOT, Path(tempfile.gettempdir()))))


def test_log_root() -> Path:
    """Return the operator-controlled base for test and development run logs."""
    return storage_directory("CADRUMO_TEST_LOG_ROOT", "development")


def run_log_roots(family: str, *, bases: tuple[Path, ...] | None = None) -> tuple[Path, ...]:
    """Return every existing ``.logs/<family>`` root across ``bases``.

    Absent bases are filtered out rather than reported: a checkout that has never
    run the audit tooling simply has no such root, and that is not a condition a
    reclamation report should raise. ``bases`` is injectable so a caller can be
    tested against a tree it controls without substituting this module.
    """
    candidates = run_log_bases() if bases is None else bases
    roots = tuple(dict.fromkeys(base / LOGS_STEM / family for base in candidates))
    return tuple(root for root in roots if root.is_dir())


def run_log_families(*, bases: tuple[Path, ...] | None = None) -> tuple[str, ...]:
    """Return every run family that exists under any ``.logs`` base.

    DISCOVERED, never enumerated. A family named in a constant list is a list
    someone has to remember to extend, and the cost of forgetting is not
    symmetric: a family the reaper does not know about is reaped by name alone
    elsewhere, with no owner check, so a run still writing into it is deleted
    mid-write. ``audit-runs`` and ``lane-runs`` reached the tree exactly that
    way, both allocated by :func:`allocate_run_directory` with a live owner's
    pid in the marker, and neither was ever assessed.

    Returns:
        Each family's directory name, sorted and deduplicated across bases.
    """
    candidates = run_log_bases() if bases is None else bases
    families: dict[str, None] = {}
    for base in candidates:
        root = base / LOGS_STEM
        try:
            children = sorted(root.iterdir())
        except OSError:
            continue
        for child in children:
            if child.is_dir() and not child.is_symlink():
                families[child.name] = None
    return tuple(sorted(families))


SCRATCH_BASE_ENV = "CADRUMO_SCRATCH_BASE"
"""Pins the directory every nested run's scratch is allocated beside.

A run redirects ``TEMP`` into its own scratch, so a child run that derived its
base from ``TEMP`` would nest one scratch inside another and grow the path with
every level. Exporting the base keeps every run's scratch a direct child of the
original temp directory, however deeply runs nest.
"""

SCRATCH_PREFIX = "cr"
"""Leading token of a run scratch directory name: ``cr_<pid>_<token>``."""

SCRATCH_SEPARATOR = "_"
"""Joins a scratch name's parts; an underscore, never a hyphen.

Scratch paths appear in command output, and output redaction hashes anything
shaped like an intra-EU VAT number: two letters, then digits and letters,
joined by hyphens, dots or spaces. ``cr-60168-a06524`` is that shape, so the
reported path came back as ``sha256:...`` and every test comparing it failed.
An underscore is a word character, which leaves the name no boundary for the
pattern to start at.
"""

SCRATCH_NAME: Final = re.compile(
    rf"{re.escape(SCRATCH_PREFIX)}{SCRATCH_SEPARATOR}(?P<pid>\d+){SCRATCH_SEPARATOR}[0-9a-f]+"
)
"""A run scratch name: prefix, owning PID, random token."""


def scratch_base() -> Path:
    """Return the controlled base for run scratch allocations."""
    inherited = os.environ.get(SCRATCH_BASE_ENV, "").strip()
    return resolve_storage_path(inherited) if inherited else prepare_temporary_directory()


def allocate_scratch_directory() -> Path:
    """Create this process's run scratch beneath the configured scratch base.

    The name carries the owning PID in the same position a run marker does, so
    the run reaper resolves its owner against the OS exactly as it does for run
    directories.

    """
    scratch = scratch_base() / SCRATCH_SEPARATOR.join((SCRATCH_PREFIX, str(os.getpid()), uuid4().hex[:6]))
    scratch.mkdir(parents=True)
    return scratch


def scratch_environment(scratch: Path) -> dict[str, str]:
    """Return the variables that make ``scratch`` a process's temporary directory."""
    return {
        SCRATCH_BASE_ENV: str(scratch.parent),
        "TEMP": str(scratch),
        "TMP": str(scratch),
        "TMPDIR": str(scratch),
    }


class ScratchOwnershipError(RuntimeError):
    """A scratch removal was asked for a path that is not the caller's own allocation."""


@dataclass(frozen=True)
class ScratchAllocation:
    """One run scratch as it was minted: its path, its owner, and the directory's identity.

    The identity is what lets removal prove it is deleting the directory this
    process created rather than whatever now answers to the same name.
    """

    path: Path
    owner_pid: int
    identity: tuple[int, int]

    @classmethod
    def record(cls, scratch: Path) -> ScratchAllocation:
        """Record ``scratch``, just allocated by this process, for a later verified removal.

        Raises:
            ScratchOwnershipError: When ``scratch`` is not named as this process's scratch.
        """
        match = SCRATCH_NAME.fullmatch(scratch.name)
        if match is None or int(match.group("pid")) != os.getpid():
            raise ScratchOwnershipError(f"{scratch} is not a scratch directory named for process {os.getpid()}")
        status = os.stat(scratch, follow_symlinks=False)
        return cls(path=scratch, owner_pid=os.getpid(), identity=(status.st_dev, status.st_ino))


def remove_scratch_directory(allocation: ScratchAllocation) -> None:
    """Remove this process's own run scratch, refusing any path that is not that allocation.

    Every check runs before anything is deleted. The allocation must belong to
    this process, and its name must still carry that owner, so a process that
    inherited another run's scratch through the environment -- an xdist worker,
    a nested pytest -- can never remove it. The path itself must not be a link
    or junction, must resolve to exactly where it is written, and must still be
    the directory recorded at allocation rather than a replacement of the same
    name.

    Removal never follows a link out of the tree: ``shutil.rmtree`` unlinks a
    symlink or junction it meets inside the scratch instead of descending into
    it. A read-only member has the attribute cleared and is retried once, since
    Windows refuses to unlink one. Whatever still cannot be removed -- a file
    this process holds open, on Windows -- is left for the run reaper, and
    everything else is removed regardless.

    Raises:
        ScratchOwnershipError: When the path is not this process's recorded allocation.
        OSError: When the scratch cannot be inspected, or entries in it could not be removed.
    """
    # Imported here for the reason ``run_log_bases`` gives: this module loads
    # before the root conftest has prepared the process environment.
    from cadrumo.core.link_safety import is_link_like

    scratch = allocation.path
    if allocation.owner_pid != os.getpid():
        raise ScratchOwnershipError(f"{scratch} belongs to process {allocation.owner_pid}, not {os.getpid()}")
    match = SCRATCH_NAME.fullmatch(scratch.name)
    if match is None or int(match.group("pid")) != allocation.owner_pid:
        raise ScratchOwnershipError(f"{scratch} is not named as the scratch of process {allocation.owner_pid}")
    if is_link_like(scratch):
        raise ScratchOwnershipError(f"{scratch} is a link, not the scratch directory it names")
    status = os.stat(scratch, follow_symlinks=False)
    if not stat.S_ISDIR(status.st_mode) or (status.st_dev, status.st_ino) != allocation.identity:
        raise ScratchOwnershipError(f"{scratch} is no longer the directory this run allocated")
    if scratch.resolve(strict=True) != scratch.parent.resolve(strict=True) / scratch.name:
        raise ScratchOwnershipError(f"{scratch} resolves to {scratch.resolve(strict=True)}, outside its allocation")

    failures: list[OSError] = []

    def _clear_read_only_and_retry(action: Callable[..., object], path: str, error: BaseException) -> None:
        if action in (os.unlink, os.rmdir):
            try:
                os.chmod(path, stat.S_IWRITE)
                action(path)
            except OSError as retry_error:
                failures.append(retry_error)
            return
        failures.append(error if isinstance(error, OSError) else OSError(str(error)))

    shutil.rmtree(scratch, onexc=_clear_read_only_and_retry)
    if failures:
        raise OSError(f"{len(failures)} entries under {scratch} could not be removed; first: {failures[0]}")


def allocate_run_directory(
    repository: Path,
    *,
    family: str,
    label: str,
    now: datetime | None = None,
) -> Path:
    """Return a collision-resistant run path below ``repository``'s ``.logs``.

    The PID in the marker is load-bearing rather than decorative: it is what lets
    the reaper resolve a directory's owner against the OS and so distinguish a run
    still being written from output that can go.
    """
    started = now or datetime.now(tz=UTC)
    marker = f"{started:%Y%m%dT%H%M%S.%fZ}-{label}-{os.getpid()}-{uuid4().hex[:8]}"
    return repository / LOGS_STEM / family / f"{started:%Y-%m-%d}" / marker

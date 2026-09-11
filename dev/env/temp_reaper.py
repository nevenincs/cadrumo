"""Operator-invoked reaper for temporary agent and test-run storage.

On 2026-08-07 ``C:`` reached 2.9 MB free of 931 GB and broke the agent fleet:
spurious ``OSError: could not create numbered dir``, collection timeouts, and a
run of non-reproducing registry failures that were all initially blamed on the
``Y:`` share. Two families accounted for essentially all of it -- pytest's
``tmp_path`` factory and Claude Code's per-session scratchpads -- and neither is
bounded by anything that runs.

Both are the same problem shape: reclaim abandoned scratch without ever
touching a live session's store. They differ in exactly one respect, and that
difference decides everything else about how each is handled:

**pytest numbered directories carry their owner.** Each one holds a ``.lock``
file whose entire contents are the owning session's PID, so liveness is
*observed*: the PID goes to the OS and the answer is about that process. That
family is reclaimed automatically at every pytest session start (see
``cadrumo.tests.collection_storage_root.reap_abandoned_numbered_dirs``); this module only reports on it,
so an operator running one command sees both.

**Claude Code session scratchpads carry no owner at all.** The directory name is
a session UUID, no lock file exists, and the ``claude.exe`` command line names
no session, so nothing available *observes* whether a session is running. Only
activity records remain, and activity is not liveness: a session sitting idle
while its user is away writes nothing and is indistinguishable from an
abandoned one by any signal on disk. That family is therefore reported by
default and reclaimed only under an explicit ``--apply``, because automating a
deletion decided by inference is a different risk from automating one decided
by observation.

This module is a library. Its operator surface is ``just clean`` (report) and
``just clean-apply`` (act), which drive :func:`report_temporary_storage` as one
section of the wider reclamation report.
"""

from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from tempfile import gettempdir
from typing import TextIO

from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.link_safety import is_link_like
from cadrumo.tests.collection_storage_root import (
    pytest_numbered_dir_root,
    reap_abandoned_numbered_dirs,
)
from dev._paths import REPO_ROOT
from dev.test_runs.reaper import assess_run_directories, reclaim_run_directories

CLAUDE_TEMP_STEM = "claude"
"""Claude Code's root under the OS temp directory.

Below it, one directory per project (the working directory with separators
flattened), and below that one directory per session, named for the session's
UUID and holding that session's ``scratchpad/`` and ``tasks/`` trees.
"""

SESSION_TRANSCRIPT_ROOT = Path.home() / ".claude" / "projects"
"""Where Claude Code keeps per-session transcripts, under the same project slug.

``<session-uuid>.jsonl``, appended on every turn of the conversation. This is
the second, independent activity signal: it lives on a different volume path,
is written by a different part of the tool, and keeps moving through stretches
where a session happens to touch no scratchpad file at all.
"""

IDLE_CEILING_SECONDS = 72 * 60 * 60
"""How long a session must show no activity on EITHER signal before it is reaped.

Not a staleness estimate, and not the ten-minute grace its pytest counterpart
uses. That grace is short because it applies only AFTER the owner has been
confirmed gone, so it needs to cover nothing but clock skew and an exiting
process still finishing its own cleanup. Here there is no owner to confirm, so
this number has to do the whole job alone: it must out-wait the longest period a
LIVE session can plausibly stay silent.

Three days is chosen against the observed shape of that silence rather than
against how much disk it recovers. An interactive session left open when its
user stops for the evening resumes the next morning; one left open on a Friday
resumes on a Monday, and that span is a little over sixty hours. Anything
appreciably shorter reclaims a session someone is coming back to; anything much
longer stops bounding the accrual it exists to bound.

Both signals must clear it. One writer stalling -- an agent whose work has moved
entirely into the repository, a transcript flushed in large batches -- is
common; both going quiet together for three days is what abandonment looks
like.
"""


_LISTED_FLOOR = 1_000_000
"""Bytes a reaped session must hold to earn its own report line.

Purely presentational: everything above and below it is reaped identically.
It exists because the reaped population is long-tailed -- most abandoned
sessions wrote nothing -- and a screen of zero-byte lines hides the few that
actually account for the space.
"""

SESSION_ID_VARIABLE = "CLAUDE_CODE_SESSION_ID"
"""Environment variable naming the session this process is running inside.

The one exact answer this family has. Everything else here is inference over
activity records, but a reaper invoked from inside a session knows that
session's UUID for certain, and can refuse to consider it at all rather than
work out from timestamps that it should be spared. The same belt-and-braces
reasoning as the pytest sweep's ``exclude``: the general rule already covers it,
and depending on the general rule for the one case with a definite answer is a
needless bet.

It says nothing about any OTHER session -- it names one process's own id, not a
registry -- so it narrows the population by exactly one and the inference still
has to carry the rest.
"""


@dataclass(frozen=True)
class SessionVerdict:
    """One session scratchpad, its evidence, and the decision that evidence supports."""

    directory: Path
    scratchpad_idle_seconds: float | None
    transcript_idle_seconds: float | None
    total_bytes: int | None
    reclaimable: bool
    reason: str

    @property
    def session_id(self) -> str:
        """The session UUID this directory is named for."""
        return self.directory.name


def claude_session_root(temproot: Path | None = None) -> Path:
    """Return Claude Code's per-project session root under the OS temp directory."""
    root = temproot if temproot is not None else Path(gettempdir())
    return root / CLAUDE_TEMP_STEM


def newest_activity(directory: Path) -> tuple[float, int]:
    """Return ``(newest mtime, total bytes)`` for everything under ``directory``.

    The directory's OWN mtime is not the answer and cannot be substituted for
    it. A directory's timestamp moves when an entry is added to or removed from
    that directory, not when anything below it is written, so a session whose
    top level was laid down once and written through ever after reads as
    untouched for as long as it has been running. Measured on the live session
    that wrote this module: its scratchpad root read 22.7 hours idle while it
    was actively writing files. Any reaper keyed on that number deletes the
    session it is running inside.

    It is used as the fallback for a directory holding no files at all, where
    it is the only timestamp that exists.

    A file that cannot be stat'd is an unanswered question, and this module
    answers those by sparing. Dropping it silently would take it out of the
    maximum below, so an unreadable NEWEST entry makes a live session read as
    idle: measured on a tree written five seconds earlier, the walk reported
    100000 seconds of silence once its newest file refused to stat, which is
    past every ceiling this reaper runs with. A refusal therefore reports the
    current time, exactly as the empty-directory fallback below does. The byte
    total still omits the unread file, because under-reporting what can be
    reclaimed is the safe direction for that number.
    """
    newest = 0.0
    total = 0
    refused = False
    for parent, _directories, files in os.walk(directory):
        for name in files:
            try:
                stat = os.stat(os.path.join(parent, name))
            except OSError:
                refused = True
                continue
            total += stat.st_size
            newest = max(newest, stat.st_mtime)
    if refused:
        return time.time(), total
    if newest == 0.0:
        try:
            newest = directory.stat().st_mtime
        except OSError:
            newest = time.time()
    return newest, total


def transcript_mtime(
    session_id: str, project_slug: str, transcript_root: Path = SESSION_TRANSCRIPT_ROOT
) -> float | None:
    """Return the mtime of ``session_id``'s transcript, or ``None`` if there is none.

    ``None`` is the answer that spares. A transcript this reaper cannot find is
    a question it cannot answer, and the one rule the whole module holds to is
    that an unanswered question leaves the directory alone.
    """
    transcript = transcript_root / project_slug / f"{session_id}.jsonl"
    try:
        return transcript.stat().st_mtime
    except OSError:
        return None


def assess_session(
    directory: Path,
    project_slug: str,
    *,
    now: float,
    ceiling: float,
    measure_spared: bool = False,
    transcript_root: Path = SESSION_TRANSCRIPT_ROOT,
) -> SessionVerdict:
    """Judge one session scratchpad against both activity signals.

    Reclaimable requires all three of: the transcript exists, the transcript has
    been silent past the ceiling, and the scratchpad tree has been silent past
    the ceiling too. Every other combination spares, and the verdict records
    which one, so the report says why rather than only what.

    The transcript is consulted FIRST, and a live or unfindable one short-cuts
    the walk. That is an ordering with teeth, not just a speed choice: these
    trees reach hundreds of thousands of files, and a reaper that must walk a
    live session's whole scratchpad before deciding to spare it is one that gets
    turned off. ``measure_spared`` forces the walk anyway, for the report that
    wants to say how much a spare is costing.
    """
    stamp = transcript_mtime(directory.name, project_slug, transcript_root)
    transcript_idle = None if stamp is None else now - stamp

    if transcript_idle is None:
        reason = "no transcript was found, so the session's own activity cannot be checked"
    elif transcript_idle <= ceiling:
        reason = "the session transcript was appended within the idle ceiling"
    else:
        reason = ""

    if reason and not measure_spared:
        return SessionVerdict(
            directory=directory,
            scratchpad_idle_seconds=None,
            transcript_idle_seconds=transcript_idle,
            total_bytes=None,
            reclaimable=False,
            reason=reason,
        )

    newest, total = newest_activity(directory)
    scratchpad_idle = now - newest
    if not reason:
        reason = (
            "both the scratchpad tree and the session transcript have been silent past the ceiling"
            if scratchpad_idle > ceiling
            else "the scratchpad tree was written within the idle ceiling"
        )

    return SessionVerdict(
        directory=directory,
        scratchpad_idle_seconds=scratchpad_idle,
        transcript_idle_seconds=transcript_idle,
        total_bytes=total,
        reclaimable=reason.startswith("both"),
        reason=reason,
    )


def assess_claude_sessions(
    root: Path,
    *,
    now: float | None = None,
    ceiling: float = IDLE_CEILING_SECONDS,
    measure_spared: bool = False,
    transcript_root: Path = SESSION_TRANSCRIPT_ROOT,
    own_session_id: str | None = None,
) -> list[SessionVerdict]:
    """Judge every session scratchpad under ``root``, deleting nothing.

    Separated from the removal so the decision is inspectable on its own: an
    operator can read the verdicts, and a test can assert them, without anything
    being at risk while they do.

    ``own_session_id`` is dropped from consideration entirely, defaulting to
    whatever :data:`SESSION_ID_VARIABLE` names. Passed explicitly rather than
    read at the decision point so a test can supply one without touching the
    environment.

    Symbolic links are skipped entirely rather than judged, on the same reasoning
    the pytest family skips ``pytest-current``: a link is not the thing it names,
    and following one turns a link removal into the removal of whatever it points
    at.
    """
    reference = time.time() if now is None else now
    mine = own_session_id if own_session_id is not None else os.environ.get(SESSION_ID_VARIABLE, "")
    verdicts: list[SessionVerdict] = []
    try:
        projects = scan_directory(root, require_root=True)
    except OSError:
        if root.exists():
            # An ABSENT root is a legitimate empty and stays absorbed. A root
            # that exists and cannot be scanned is not: returning [] here
            # prints 'spared: 0 of 0 sessions', which is exactly what a
            # genuinely clean box prints, so a failed scan would read as
            # nothing to reclaim.
            raise
        return verdicts
    for project in projects:
        if is_link_like(project) or not project.is_dir():
            continue
        try:
            sessions = scan_directory(project, require_root=True)
        except OSError:
            continue
        for session in sessions:
            if is_link_like(session) or not session.is_dir() or (mine and session.name == mine):
                continue
            verdicts.append(
                assess_session(
                    session,
                    project.name,
                    now=reference,
                    ceiling=ceiling,
                    measure_spared=measure_spared,
                    transcript_root=transcript_root,
                ),
            )
    return verdicts


def reclaim(verdicts: list[SessionVerdict]) -> int:
    """Remove every reclaimable directory among ``verdicts`` and return the byte total.

    Best-effort per directory: a file another process still holds open makes
    ``shutil.rmtree`` fail partway, and that failure is absorbed rather than
    raised. A partially removed abandoned scratchpad is not a state anything
    reads, and the next run finishes the job.
    """
    reclaimed = 0
    for verdict in verdicts:
        if not verdict.reclaimable:
            continue
        if not verdict.directory.exists():
            continue
        shutil.rmtree(verdict.directory, ignore_errors=True)
        if verdict.directory.exists():
            # The absorbed failure above is deliberate, but its bytes are
            # not reclaimed and must not be counted: this total is printed
            # to the operator as 'removed'. A partial removal therefore
            # under-reports rather than overstating, which is the only
            # safe direction for that claim.
            continue
        reclaimed += verdict.total_bytes or 0
    return reclaimed


def _gigabytes(value: int | None) -> str:
    return "not measured" if value is None else f"{value / 1_000_000_000:.3f} GB"


def _hours(value: float | None) -> str:
    return "not measured" if value is None else f"{value / 3600:6.1f}h"


def _report(
    verdicts: list[SessionVerdict], *, applying: bool, stream: TextIO, verbose: bool = False
) -> tuple[int, int]:
    """Print the session verdicts and return ``(reclaimable bytes, spared count)``.

    Reaped sessions are always listed, because those are the lines an operator
    is being asked to sanction. Spared ones are summarised by reason unless
    ``verbose`` asks for the inventory: this machine carries several hundred
    sessions, and printing one line each buries every other section of the
    report it now forms part of.
    """
    reclaimable = 0
    reaped: list[SessionVerdict] = []
    spared: list[SessionVerdict] = []
    for verdict in sorted(verdicts, key=lambda item: -(item.total_bytes or 0)):
        if verdict.reclaimable:
            reclaimable += verdict.total_bytes or 0
            reaped.append(verdict)
        else:
            spared.append(verdict)

    # Sorted by size above, so the tail is the sessions holding nothing. They
    # are still reaped -- an empty abandoned scratchpad is still a directory --
    # but naming each one costs a screen to report zero bytes.
    listed = reaped if verbose else [verdict for verdict in reaped if (verdict.total_bytes or 0) >= _LISTED_FLOOR]
    for verdict in listed:
        print(
            f"  REAP  {verdict.session_id}"
            f"  scratchpad {_hours(verdict.scratchpad_idle_seconds)}"
            f"  transcript {_hours(verdict.transcript_idle_seconds)}"
            f"  {_gigabytes(verdict.total_bytes)}",
            file=stream,
        )
    folded = len(reaped) - len(listed)
    if folded:
        print(f"  REAP  {folded} further abandoned sessions holding under 1 MB each", file=stream)
    if verbose:
        for verdict in spared:
            print(f"  SPARE {verdict.session_id}  {verdict.reason}", file=stream)
    else:
        for reason in dict.fromkeys(verdict.reason for verdict in spared):
            count = sum(1 for verdict in spared if verdict.reason == reason)
            print(f"  SPARE {count:4d} sessions  {reason}", file=stream)

    verb = "reclaimed" if applying else "reclaimable"
    print(f"  {verb}: {_gigabytes(reclaimable)}   spared: {len(spared)} of {len(verdicts)} sessions", file=stream)
    return reclaimable, len(spared)


def report_temporary_storage(
    stream: TextIO,
    *,
    apply: bool,
    idle_hours: float = IDLE_CEILING_SECONDS / 3600,
    measure_spared: bool = False,
    verbose: bool = False,
) -> int:
    """Report all three temporary-storage families and return the bytes reclaimed.

    The operator surface for this module is ``just clean``, which drives this
    function as one section of a wider report. Keeping the section here rather
    than in the caller keeps each family's rules with the module that reasons
    about them: the liveness probes, the idle ceiling and the reasons the
    verdicts carry are this file's subject, and a caller that re-derived any of
    them would be a second opinion about who owns a scratch directory.

    Args:
        stream: Where the section is written.
        apply: Whether to remove what the verdicts judge abandoned.
        idle_hours: Silence required on BOTH session signals before reaping.
        measure_spared: Walk spared sessions to report what sparing them costs.
        verbose: List every spared session instead of summarising them by reason.

    Returns:
        Bytes reclaimed from the session scratchpads, or 0 when reporting only.
    """
    ceiling = idle_hours * 3600

    numbered_root = pytest_numbered_dir_root()
    print(f"\npytest numbered directories under {numbered_root}", file=stream)
    if apply:
        removed, kept = reap_abandoned_numbered_dirs(numbered_root)
        print(
            f"  reclaimed {removed} abandoned, spared {kept} whose owner is running or unknown",
            file=stream,
        )
    else:
        # Report mode must not delete. This family's only entry point reaps as
        # it counts, so there is no count to print without acting, and acting
        # here would make the report's own promise false: it is reached from a
        # command documented as deleting nothing until --apply. Nothing is lost
        # by waiting, because every pytest session start already reaps it.
        print(
            "  reaped at every pytest session start; not counted here, because counting this"
            " family means reaping it and a report deletes nothing",
            file=stream,
        )

    run_root = REPO_ROOT / ".logs" / "test-runs"
    run_verdicts = assess_run_directories(run_root)
    print(f"\nRepository test runs under {run_root}", file=stream)
    for verdict in run_verdicts:
        if verdict.reclaimable or verbose:
            print(
                f"  {'REAP ' if verdict.reclaimable else 'SPARE'} {verdict.directory.name}  {verdict.reason}",
                file=stream,
            )
    kept_runs = [verdict for verdict in run_verdicts if not verdict.reclaimable]
    if kept_runs and not verbose:
        # One line for the retained population rather than one per directory.
        # This tree holds a run per pytest invocation and reaches the high
        # hundreds on a busy day; listing every retained run pushes the reaped
        # ones -- the only lines an operator is being asked to sanction -- off
        # the screen, which is the failure mode a report has instead of a bug.
        for reason in dict.fromkeys(verdict.reason for verdict in kept_runs):
            count = sum(1 for verdict in kept_runs if verdict.reason == reason)
            print(f"  SPARE {count:4d} run directories  {reason}", file=stream)
    if apply:
        print(f"  removed {reclaim_run_directories(run_verdicts)} run directories", file=stream)

    session_root = claude_session_root()
    print(f"\nClaude Code session scratchpads under {session_root}", file=stream)
    print(
        f"  idle ceiling {idle_hours:.0f}h on both the scratchpad tree and the session transcript",
        file=stream,
    )
    verdicts = assess_claude_sessions(session_root, ceiling=ceiling, measure_spared=measure_spared)
    _report(verdicts, applying=apply, stream=stream, verbose=verbose)
    if not apply:
        return 0
    reclaimed = reclaim(verdicts)
    print(f"  removed {_gigabytes(reclaimed)}", file=stream)
    return reclaimed

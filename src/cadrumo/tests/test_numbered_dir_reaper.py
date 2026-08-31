"""pytest's numbered temp directories are bounded by their owner, not by age.

pytest already garbage-collects them, but only under two conditions it cannot
relax: the directory must fall outside the retained-session count, and its
``.lock`` must have aged past ``_pytest.pathlib.LOCK_TIMEOUT`` -- three days, a
module constant with no ini override. Nothing refreshes that lock's mtime, so
the comparison is against the directory's creation time and a session killed
one minute in holds its entire tree for three days. On this box a numbered
directory is minted roughly every twenty seconds and the larger ones carry
upwards of a thousand entries, which is how a 39 GB pile formed while the
system volume ran down to single-digit megabytes free.

The lock file holds the owning session's PID as its entire contents, so the
question pytest approximates with age can be asked directly. These tests pin
that: what is reclaimed, and -- the ones that matter -- what is spared.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from _pytest.pathlib import LOCK_TIMEOUT, ensure_deletable, make_numbered_dir_with_cleanup

from ..core.directory_scan import scan_directory
from .collection_storage_root import (
    _ABANDONED_AFTER_SECONDS,
    _LOCK_NAME,
    _STALE_AFTER_SECONDS,
    pytest_numbered_dir_root,
    reap_abandoned_numbered_dirs,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SUBPROCESS_TIMEOUT_SECONDS = 60


def _age(directory: Path, seconds: float) -> None:
    """Backdate ``directory``'s mtime so the reaper sees it as that old."""
    stamp = directory.stat().st_mtime - seconds
    os.utime(directory, (stamp, stamp))


def _a_genuinely_dead_pid() -> int:
    """Run a real process to completion and return its now-unused identifier.

    A real reaped process rather than a fabricated number: an arbitrary large
    integer would also read as dead, but it would prove only that the probe
    dislikes unfamiliar numbers. Closing the handle matters on Windows, where
    an open handle keeps the identifier reserved.
    """
    with subprocess.Popen([sys.executable, "-c", "pass"]) as child:  # fixed interpreter argv, no external input.
        child.wait(timeout=_SUBPROCESS_TIMEOUT_SECONDS)
        pid = child.pid
    return pid


def _numbered_dir(root: Path, number: int, *, owner: int | None, entries: int = 3) -> Path:
    """Build a numbered directory shaped the way pytest builds one.

    ``owner`` is written verbatim into the ``.lock`` file, exactly as
    ``_pytest.pathlib.create_cleanup_lock`` writes ``os.getpid()``; ``None``
    leaves no lock at all, which is both what a cleanly-exited session leaves
    behind and what a directory observed between its creation and its lock's
    creation looks like.
    """
    directory = root / f"pytest-{number}"
    directory.mkdir(parents=True)
    for index in range(entries):
        (directory / f"payload-{index}").write_text("x" * 512, encoding="utf-8")
    if owner is not None:
        (directory / _LOCK_NAME).write_text(str(owner), encoding="utf-8")
    return directory


def test_the_lock_file_names_its_owner_and_never_refreshes_its_mtime(tmp_path: Path) -> None:
    """The premise the whole reaper rests on, read off the real pytest code.

    Two claims, and the design is wrong if either fails. First, the lock's
    contents are the owning session's PID -- that is the direct liveness signal
    this family has, and if pytest ever stopped writing it the reaper would
    silently fall back to the mtime ceiling. Second, the mtime is a creation
    stamp and not a heartbeat, which is why pytest's own three-day
    ``LOCK_TIMEOUT`` measures from creation and holds a crashed session's tree
    for three days regardless of when it actually died.

    Exercised against the real ``make_numbered_dir_with_cleanup``, not a
    re-implementation of it, so a pytest upgrade that changed the protocol
    fails here rather than somewhere subtler.
    """
    root = tmp_path / "pytest-of-probe"
    root.mkdir()
    created = make_numbered_dir_with_cleanup(
        root=root,
        prefix="pytest-",
        mode=0o700,
        keep=3,
        lock_timeout=LOCK_TIMEOUT,
        register=lambda *_args, **_kwargs: None,
    )
    lock = created / _LOCK_NAME

    assert lock.is_file(), "pytest no longer writes a lock file; the owner signal is gone"
    assert lock.read_text(encoding="utf-8").strip() == str(os.getpid())

    written_at = lock.stat().st_mtime
    time.sleep(0.05)
    (created / "work-happens-here").write_text("a live session doing work", encoding="utf-8")

    assert lock.stat().st_mtime == written_at, (
        "the lock mtime moved; if pytest has started refreshing it as a heartbeat, "
        "reading the PID is no longer the only way to tell a live session from a dead one"
    )
    assert LOCK_TIMEOUT == 60 * 60 * 24 * 3


def test_pytest_cannot_reclaim_a_crashed_sessions_directory_but_the_reaper_can(tmp_path: Path) -> None:
    """The gap, stated as a comparison against pytest's own decision function.

    This is the reason the reaper exists rather than a tuning knob on pytest.
    ``ensure_deletable`` is asked the same question about the same directory
    and refuses, because the lock is young in wall-clock terms even though its
    owner is provably gone. Without this pairing the reclaim test below would
    show only that something removed a directory, not that it removed one
    nothing else would have.
    """
    root = tmp_path / "pytest-of-probe"
    abandoned = _numbered_dir(root, 1, owner=_a_genuinely_dead_pid())
    _age(abandoned, _ABANDONED_AFTER_SECONDS + 60)
    consider_lock_dead_if_created_before = time.time() - LOCK_TIMEOUT

    assert not ensure_deletable(abandoned, consider_lock_dead_if_created_before), (
        "pytest would already reclaim this, so the reaper is redundant here"
    )

    removed, spared = reap_abandoned_numbered_dirs(root)

    assert (removed, spared) == (1, 0)
    assert not abandoned.exists()


def test_a_running_sessions_directory_is_spared(tmp_path: Path) -> None:
    """The load-bearing guarantee: a live session's tmp_path tree is never taken.

    Dozens of pytest sessions share one numbered-directory root on this box --
    several agents at once, each with xdist workers underneath -- and every one
    of them runs this reaper at its own startup. A reaper that mistook a
    running session for a crashed one would delete the fixtures out from under
    a peer's tests mid-run, which is a far worse outcome than the disk pressure
    it exists to relieve.

    The directory is aged well past the abandonment grace, so age cannot save
    it and only the liveness answer can. Its lock names a process that is
    definitively alive: this one.
    """
    root = tmp_path / "pytest-of-probe"
    live = _numbered_dir(root, 1, owner=os.getpid())
    _age(live, _ABANDONED_AFTER_SECONDS * 6)

    removed, spared = reap_abandoned_numbered_dirs(root)

    assert (removed, spared) == (0, 1)
    assert (live / "payload-0").read_text(encoding="utf-8") == "x" * 512


def test_a_directory_whose_lock_is_not_yet_written_is_spared(tmp_path: Path) -> None:
    """A missing lock is ambiguous, and ambiguity resolves to sparing.

    pytest creates the numbered directory and writes its lock in two separate
    steps, so a directory observed between them belongs to a session that is
    starting up right now and carries no owner to ask about. Treating "no lock"
    as "no owner" would delete a session's tmp_path in the first milliseconds
    of its run -- the one moment it is guaranteed to still need it.
    """
    root = tmp_path / "pytest-of-probe"
    mid_creation = _numbered_dir(root, 1, owner=None)
    _age(mid_creation, _ABANDONED_AFTER_SECONDS * 6)

    removed, spared = reap_abandoned_numbered_dirs(root)

    assert (removed, spared) == (0, 1)
    assert mid_creation.is_dir()


def test_a_directory_with_an_unreadable_lock_is_spared(tmp_path: Path) -> None:
    """A lock that does not parse as a PID answers nothing, so it spares.

    The uncertainty direction the whole module is built on, at the one place a
    caller could plausibly be tempted to guess: a corrupt or truncated lock is
    a reason to know less, never a licence to delete more.
    """
    root = tmp_path / "pytest-of-probe"
    unreadable = _numbered_dir(root, 1, owner=None)
    (unreadable / _LOCK_NAME).write_bytes(b"\xff\xfe not a pid at all")
    _age(unreadable, _ABANDONED_AFTER_SECONDS * 6)

    removed, spared = reap_abandoned_numbered_dirs(root)

    assert (removed, spared) == (0, 1)
    assert unreadable.is_dir()


def test_a_lockless_directory_is_reclaimed_once_the_mtime_ceiling_passes(tmp_path: Path) -> None:
    """Sparing the ambiguous case must not mean keeping it forever.

    A cleanly-exited session unlinks its own lock, leaving a directory that is
    indistinguishable from one caught mid-creation. The day-long ceiling
    separates them in the only way available: a directory that has been
    untouched for a day was not created a moment ago.
    """
    root = tmp_path / "pytest-of-probe"
    finished = _numbered_dir(root, 1, owner=None)
    _age(finished, _STALE_AFTER_SECONDS + 60)

    removed, spared = reap_abandoned_numbered_dirs(root)

    assert (removed, spared) == (1, 0)
    assert not finished.exists()


def test_a_just_crashed_directory_is_spared_until_the_grace_elapses(tmp_path: Path) -> None:
    """Death alone is not licence; the grace absorbs the exit-race window.

    pytest registers its own ``cleanup_numbered_dir`` as an exit hook, so a
    process that has just gone may still be mid-removal inside it, and an mtime
    read can disagree with a liveness read by a little clock skew. The grace
    covers both. It is a margin for those two races, not an estimate of how
    long a directory stays interesting.
    """
    root = tmp_path / "pytest-of-probe"
    just_gone = _numbered_dir(root, 1, owner=_a_genuinely_dead_pid())

    removed, spared = reap_abandoned_numbered_dirs(root)

    assert (removed, spared) == (0, 1)
    assert just_gone.is_dir()


def test_the_interrupted_removal_leftovers_are_reclaimed_too(tmp_path: Path) -> None:
    """``garbage-*`` is the same leak wearing pytest's own rename.

    pytest reclaims a numbered directory by renaming it to ``garbage-<uuid>``
    and then removing it, so an interrupted reclaim leaves the tree behind
    under a different prefix with the same lock inside. Covering only the
    ``pytest-*`` prefix would leave exactly the directories a crash mid-cleanup
    produces, which is the population most likely to be large.
    """
    root = tmp_path / "pytest-of-probe"
    root.mkdir()
    leftover = root / "garbage-4b6081a2-a9d9-4441-bdc1-87c0b879bca1"
    leftover.mkdir()
    (leftover / _LOCK_NAME).write_text(str(_a_genuinely_dead_pid()), encoding="utf-8")
    _age(leftover, _ABANDONED_AFTER_SECONDS + 60)

    removed, spared = reap_abandoned_numbered_dirs(root)

    assert (removed, spared) == (1, 0)
    assert not leftover.exists()


def test_the_current_session_symlink_is_neither_removed_nor_followed(tmp_path: Path) -> None:
    """``pytest-current`` points at the newest run, so following it is fatal.

    pytest maintains this link on every session. Its name matches the swept
    prefix, and it is not itself a numbered directory, so a reaper that treated
    it as one would either delete a live session's tree through it or judge it
    by the target's properties. Neither is a decision this reaper is entitled
    to make about a name it does not own.
    """
    root = tmp_path / "pytest-of-probe"
    root.mkdir()
    target = tmp_path / "outside-the-root"
    target.mkdir()
    (target / "held").write_text("a live session's tree", encoding="utf-8")
    link = root / "pytest-current"
    link.symlink_to(target, target_is_directory=True)
    _age(target, _STALE_AFTER_SECONDS * 30)

    assert reap_abandoned_numbered_dirs(root) == (0, 0), "the link was judged rather than skipped"
    assert link.is_symlink(), "the reaper removed the current-session link"
    assert (target / "held").read_text(encoding="utf-8") == "a live session's tree"


def test_directories_the_reaper_does_not_own_are_left_alone(tmp_path: Path) -> None:
    """Age is not licence: the prefix decides what is the reaper's to remove."""
    root = tmp_path / "pytest-of-probe"
    root.mkdir()
    foreign = root / "some-other-tools-workspace"
    foreign.mkdir()
    _age(foreign, _STALE_AFTER_SECONDS * 30)

    removed, spared = reap_abandoned_numbered_dirs(root)

    assert (removed, spared) == (0, 0)
    assert foreign.is_dir()


def test_the_reap_is_safe_to_run_concurrently(tmp_path: Path) -> None:
    """Every pytest session on the box runs this at startup, often at once.

    Nothing the reaper removes belongs to a live session, so two reapers
    reaching one directory together can each partially remove it without any
    run observing the difference. What must hold is that no invocation raises
    and that the live directory survives all of them.
    """
    root = tmp_path / "pytest-of-probe"
    dead_pid = _a_genuinely_dead_pid()
    for index in range(12):
        abandoned = _numbered_dir(root, index + 1, owner=dead_pid + index * 100000)
        _age(abandoned, _ABANDONED_AFTER_SECONDS + 60)
    live = _numbered_dir(root, 99, owner=os.getpid())
    _age(live, _ABANDONED_AFTER_SECONDS * 6)

    failures: list[BaseException] = []

    def _reap() -> None:
        try:
            reap_abandoned_numbered_dirs(root)
        except BaseException as error:  # the assertion under test is that none escapes.
            failures.append(error)

    workers = [threading.Thread(target=_reap) for _ in range(8)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=_SUBPROCESS_TIMEOUT_SECONDS)

    assert not failures, f"concurrent reaps raised: {failures}"
    survivors = scan_directory(root, pattern="pytest-*")
    assert {path.name for path in survivors} == {live.name}
    assert (live / "payload-0").read_text(encoding="utf-8") == "x" * 512


def test_a_missing_root_is_not_an_error(tmp_path: Path) -> None:
    """The reaper runs before pytest has ever created its root on a fresh box."""
    assert reap_abandoned_numbered_dirs(tmp_path / "never-created") == (0, 0)


def test_the_reaped_root_is_where_a_real_pytest_run_puts_its_directories(tmp_path: Path) -> None:
    """The derivation is checked against a real run, not against itself.

    A literal ``pytest-of-hello`` satisfies any self-comparison and reaps
    nothing whatsoever on a box with a different user -- the failure mode that
    leaves a disk filling silently while the reaper reports a clean zero. This
    starts an actual pytest process, with its own minimal ini so this
    repository's ``addopts`` do not reach it and no ``--basetemp`` override is
    in force, and asks it where it put its numbered directory.
    """
    probe = tmp_path / "test_where.py"
    report = tmp_path / "basetemp.txt"
    probe.write_text(
        "def test_report(tmp_path_factory):\n"
        f"    open({str(report)!r}, 'w').write(str(tmp_path_factory.getbasetemp().parent))\n",
        encoding="utf-8",
    )
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    completed = subprocess.run(  # noqa: S603 - fixed interpreter argv; the probe is a test-local literal.
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "-c",
            str(tmp_path / "pytest.ini"),
            str(probe),
        ],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS * 4,
        check=False,
    )

    assert completed.returncode == 0, f"probe run failed:\n{completed.stdout}\n{completed.stderr}"
    where_pytest_put_it = Path(report.read_text(encoding="utf-8"))

    assert pytest_numbered_dir_root(where_pytest_put_it.parent) == where_pytest_put_it

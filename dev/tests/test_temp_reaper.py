"""A Claude Code session scratchpad is reaped only when nothing says it is alive.

This family is the harder of the two the reaper covers, and the tests are
weighted accordingly. pytest's numbered directories name their owner in a lock
file, so liveness there is observed. These carry no owner anywhere -- a UUID for
a name, no lock, and a ``claude.exe`` command line that names no session -- so
every signal available is an activity record, and activity is not liveness.

The load-bearing tests here are therefore the negative ones. Removing an old
directory is easy and proves nothing; the property worth pinning is that a live
session's store survives, including the specific way a live session looks dead.
That way is real and was measured, not imagined: the session that wrote this
module had a scratchpad root whose own mtime read 22.7 hours old while it was
actively writing into it, because a directory's timestamp tracks changes to its
entry list and not to anything below.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from ..env.temp_reaper import (
    IDLE_CEILING_SECONDS,
    assess_claude_sessions,
    assess_session,
    claude_session_root,
    newest_activity,
    reclaim,
    transcript_mtime,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PROJECT = "Y--code-aeat-worktrees-main"
# Every call below passes own_session_id explicitly. These fixtures use real
# session UUIDs from the box this was built on, one of which is the session that
# built it, so leaving the exclusion to read the ambient environment would make
# the results depend on who is running the suite.
_SESSION = "29c15b00-3e98-4c2a-baf5-ec0a404242c0"
_OTHER_SESSION = "4b6081a2-a9d9-4441-bdc1-87c0b879bca1"


def _stamp(path: Path, seconds_ago: float, *, now: float) -> None:
    """Set ``path``'s mtime to ``seconds_ago`` before ``now``."""
    when = now - seconds_ago
    os.utime(path, (when, when))


def _session_tree(
    root: Path,
    session_id: str,
    *,
    now: float,
    root_idle: float,
    content_idle: float,
    payload: bytes = b"scratch",
) -> Path:
    """Build a session scratchpad whose root and contents carry separate ages.

    The two ages are set independently on purpose: the whole liveness question
    for this family turns on which of them is read, and a fixture that moved
    them together could not tell a correct reaper from one keyed on the wrong
    timestamp.
    """
    session = root / _PROJECT / session_id
    (session / "scratchpad").mkdir(parents=True)
    written = session / "scratchpad" / "work.txt"
    written.write_bytes(payload)
    _stamp(written, content_idle, now=now)
    _stamp(session / "scratchpad", root_idle, now=now)
    _stamp(session, root_idle, now=now)
    return session


def _transcript(root: Path, session_id: str, *, now: float, idle: float) -> Path:
    """Write a session transcript at a chosen age under the same project slug."""
    project = root / _PROJECT
    project.mkdir(parents=True, exist_ok=True)
    transcript = project / f"{session_id}.jsonl"
    transcript.write_text('{"type":"user"}\n', encoding="utf-8")
    _stamp(transcript, idle, now=now)
    return transcript


def test_a_session_root_can_read_stale_while_its_contents_are_being_written(tmp_path: Path) -> None:
    """The trap this whole family's rule is built around, reproduced on real files.

    A directory's mtime tracks its own entry list, so a scratchpad laid down
    once and written through afterwards keeps a stale root timestamp for as long
    as the session runs. This is the measured shape of a live session, and any
    reaper that read the root would delete it. The assertion is not about the
    reaper at all -- it is about the filesystem behaviour the reaper must not be
    caught by, and it fails if that behaviour ever changes.
    """
    now = time.time()
    session = _session_tree(tmp_path, _SESSION, now=now, root_idle=22.7 * 3600, content_idle=1.0)

    root_age = now - session.stat().st_mtime
    newest, total = newest_activity(session)

    assert root_age > 20 * 3600, "the fixture no longer reproduces a stale-looking live session"
    assert now - newest < 60, "the recursive read must find the file written a moment ago"
    assert total == len(b"scratch")


def test_an_entry_the_walk_cannot_stat_leaves_the_tree_reading_active(tmp_path: Path) -> None:
    """An unreadable entry spares the tree instead of ageing it.

    ``os.walk`` lists a dangling symlink and ``os.stat`` then refuses it, which
    is the real shape of the race this guard covers: an entry present in the
    listing and gone, locked, or unreadable by the time it is measured. Dropping
    it from the maximum silently takes the newest file out of the answer, so a
    tree written moments ago reads as untouched. Measured before the guard: five
    seconds of real activity reported as 100000 seconds of silence, past every
    ceiling the reaper runs with, which is the state that makes a live session
    reclaimable. The byte total still omits the unread entry, because
    under-reporting what can be reclaimed is the safe direction for that number.
    """
    now = time.time()
    stale = tmp_path / "stale.txt"
    stale.write_bytes(b"old")
    os.utime(stale, (now - 100000, now - 100000))
    os.symlink(tmp_path / "no_such_target.txt", tmp_path / "vanished.txt")

    with pytest.raises(OSError):
        os.stat(tmp_path / "vanished.txt")

    newest, total = newest_activity(tmp_path)

    assert now - newest < 60, "a tree holding an unreadable entry must not read as idle"
    assert total == len(b"old")


def test_a_live_session_is_spared_even_though_its_root_looks_abandoned(tmp_path: Path) -> None:
    """The load-bearing guarantee: an active session's scratchpad is never taken.

    Root aged past the ceiling, contents written seconds ago, transcript being
    appended right now -- which is exactly the state of every session on this box
    while it works. There were about twenty of them running concurrently when
    this reaper was written, several writing at the same time.
    """
    now = time.time()
    temp = tmp_path / "temp"
    transcripts = tmp_path / "transcripts"
    session = _session_tree(temp, _SESSION, now=now, root_idle=IDLE_CEILING_SECONDS * 3, content_idle=5)
    _transcript(transcripts, _SESSION, now=now, idle=5)

    verdicts = assess_claude_sessions(
        temp, now=now, transcript_root=transcripts, measure_spared=True, own_session_id=""
    )

    assert [verdict.reclaimable for verdict in verdicts] == [False]
    assert (session / "scratchpad" / "work.txt").read_bytes() == b"scratch"


def test_a_session_still_writing_is_spared_when_only_the_walk_can_tell(tmp_path: Path) -> None:
    """The case where the recursive read is the sole thing standing between a live
    session and deletion.

    The test above has a moving transcript, so the transcript alone spares it and
    the walk is never consulted -- which means it cannot detect a reaper keyed on
    the wrong timestamp. Here the transcript has gone quiet past the ceiling and
    the only remaining evidence of life is a file written a moment ago, deep
    under a root whose own mtime is days old. Read the root and this session is
    condemned; read the tree and it is spared.
    """
    now = time.time()
    temp = tmp_path / "temp"
    transcripts = tmp_path / "transcripts"
    over = IDLE_CEILING_SECONDS + 7200
    session = _session_tree(temp, _SESSION, now=now, root_idle=over, content_idle=5)
    _transcript(transcripts, _SESSION, now=now, idle=over)

    verdicts = assess_claude_sessions(temp, now=now, transcript_root=transcripts, own_session_id="")

    assert [verdict.reclaimable for verdict in verdicts] == [False]
    assert "written within the idle ceiling" in verdicts[0].reason
    reclaim(verdicts)
    assert (session / "scratchpad" / "work.txt").read_bytes() == b"scratch"


def test_a_session_whose_transcript_is_live_is_spared_without_reading_its_tree(tmp_path: Path) -> None:
    """A moving transcript ends the question before the scratchpad is even walked.

    The independence of the two signals is the point. A session can go a long
    while touching no scratchpad file -- its work moved into the repository, or
    it is reading rather than writing -- while its transcript advances on every
    turn. Requiring both signals to be silent means neither one stalling can
    condemn a session on its own.
    """
    now = time.time()
    temp = tmp_path / "temp"
    transcripts = tmp_path / "transcripts"
    _session_tree(temp, _SESSION, now=now, root_idle=IDLE_CEILING_SECONDS * 3, content_idle=IDLE_CEILING_SECONDS * 3)
    _transcript(transcripts, _SESSION, now=now, idle=60)

    verdict = assess_claude_sessions(temp, now=now, transcript_root=transcripts, own_session_id="")[0]

    assert not verdict.reclaimable
    assert "transcript was appended" in verdict.reason
    assert verdict.scratchpad_idle_seconds is None, "the tree was walked despite the question being settled"


def test_a_session_with_no_transcript_is_spared_however_old_it_looks(tmp_path: Path) -> None:
    """An unanswerable question spares, and this is the only place one arises.

    A missing transcript means the reaper cannot check the session's own
    activity at all. Treating absence as evidence of abandonment would invert
    the module's one rule at precisely the point where it knows least.
    """
    now = time.time()
    temp = tmp_path / "temp"
    ancient = IDLE_CEILING_SECONDS * 100
    session = _session_tree(temp, _SESSION, now=now, root_idle=ancient, content_idle=ancient)

    verdict = assess_claude_sessions(
        temp, now=now, transcript_root=tmp_path / "no-transcripts-here", own_session_id=""
    )[0]

    assert not verdict.reclaimable
    assert "no transcript was found" in verdict.reason
    assert session.is_dir()


def test_a_session_silent_on_both_signals_past_the_ceiling_is_reclaimed(tmp_path: Path) -> None:
    """The positive case, without which every sparing test above passes vacuously.

    A reaper that spared everything would satisfy all four negatives. This is
    the control that makes them mean something.
    """
    now = time.time()
    temp = tmp_path / "temp"
    transcripts = tmp_path / "transcripts"
    over = IDLE_CEILING_SECONDS + 3600
    session = _session_tree(temp, _SESSION, now=now, root_idle=over, content_idle=over, payload=b"x" * 4096)
    _transcript(transcripts, _SESSION, now=now, idle=over)

    verdicts = assess_claude_sessions(temp, now=now, transcript_root=transcripts, own_session_id="")

    assert [verdict.reclaimable for verdict in verdicts] == [True]
    assert verdicts[0].total_bytes == 4096
    assert reclaim(verdicts) == 4096
    assert not session.exists()


def test_the_ceiling_is_a_boundary_and_not_a_direction(tmp_path: Path) -> None:
    """Just inside the ceiling spares; just outside reclaims.

    Pins the comparison itself. A rule that reclaimed everything past some age
    and a rule that reclaimed everything at all differ only at this boundary,
    and the sparing tests above sit far from it by design.
    """
    now = time.time()
    temp = tmp_path / "temp"
    transcripts = tmp_path / "transcripts"
    for session_id, idle in ((_SESSION, IDLE_CEILING_SECONDS - 600), (_OTHER_SESSION, IDLE_CEILING_SECONDS + 600)):
        _session_tree(temp, session_id, now=now, root_idle=idle, content_idle=idle)
        _transcript(transcripts, session_id, now=now, idle=idle)

    verdicts = {
        v.session_id: v.reclaimable
        for v in assess_claude_sessions(temp, now=now, transcript_root=transcripts, own_session_id="")
    }

    assert verdicts == {_SESSION: False, _OTHER_SESSION: True}


def test_only_the_matching_sessions_transcript_is_consulted(tmp_path: Path) -> None:
    """A sibling session's activity must not vouch for an abandoned one.

    The transcripts sit together in one project directory, so a lookup that
    matched loosely -- newest in the directory, any file for the project -- would
    let one busy session keep every abandoned sibling alive forever, and the
    family would never be bounded at all. This is the same shape as comparing a
    name without its namespace.
    """
    now = time.time()
    temp = tmp_path / "temp"
    transcripts = tmp_path / "transcripts"
    over = IDLE_CEILING_SECONDS + 3600
    _session_tree(temp, _SESSION, now=now, root_idle=over, content_idle=over)
    _transcript(transcripts, _SESSION, now=now, idle=over)
    _transcript(transcripts, _OTHER_SESSION, now=now, idle=5)

    verdict = assess_claude_sessions(temp, now=now, transcript_root=transcripts, own_session_id="")[0]

    assert verdict.reclaimable, "a busy sibling's transcript was read as this session's activity"


def test_a_session_directory_symlink_is_neither_judged_nor_followed(tmp_path: Path) -> None:
    """A link is not the tree it names, and following one widens the blast radius."""
    now = time.time()
    temp = tmp_path / "temp"
    transcripts = tmp_path / "transcripts"
    over = IDLE_CEILING_SECONDS + 3600
    target = tmp_path / "outside"
    target.mkdir()
    (target / "held").write_bytes(b"someone else's tree")
    (temp / _PROJECT).mkdir(parents=True)
    link = temp / _PROJECT / _SESSION
    link.symlink_to(target, target_is_directory=True)
    _stamp(target / "held", over, now=now)
    _transcript(transcripts, _SESSION, now=now, idle=over)

    verdicts = assess_claude_sessions(temp, now=now, transcript_root=transcripts, own_session_id="")

    assert verdicts == []
    assert link.is_symlink()
    assert (target / "held").read_bytes() == b"someone else's tree"


def test_a_missing_session_root_is_not_an_error(tmp_path: Path) -> None:
    """A box where Claude Code has never run has no root, and that is not a failure."""
    assert assess_claude_sessions(tmp_path / "never-created") == []


def test_reclaim_touches_nothing_a_verdict_spared(tmp_path: Path) -> None:
    """The decision and the deletion are separable, and only the decision decides.

    ``reclaim`` is the one function in the module that removes anything, so it
    must consult the verdict and never re-derive it. A mixed batch proves it
    walks past the spared entries rather than acting on position or count.
    """
    now = time.time()
    temp = tmp_path / "temp"
    transcripts = tmp_path / "transcripts"
    over = IDLE_CEILING_SECONDS + 3600
    abandoned = _session_tree(temp, _OTHER_SESSION, now=now, root_idle=over, content_idle=over)
    live = _session_tree(temp, _SESSION, now=now, root_idle=over, content_idle=5)
    _transcript(transcripts, _OTHER_SESSION, now=now, idle=over)
    _transcript(transcripts, _SESSION, now=now, idle=5)

    reclaim(assess_claude_sessions(temp, now=now, transcript_root=transcripts, own_session_id=""))

    assert not abandoned.exists()
    assert (live / "scratchpad" / "work.txt").is_file()


def test_the_invoking_sessions_own_scratchpad_is_never_even_considered(tmp_path: Path) -> None:
    """The one exact answer this family has, used rather than inferred around.

    A reaper is most likely to be run from inside a session that has been
    working for days, which is precisely the shape its own inference would
    condemn: root long stale, transcript flushed some time ago. Its own id is
    known for certain, so it is dropped from the population outright instead of
    being argued out of it by timestamps.
    """
    now = time.time()
    temp = tmp_path / "temp"
    transcripts = tmp_path / "transcripts"
    over = IDLE_CEILING_SECONDS + 3600
    for session_id in (_SESSION, _OTHER_SESSION):
        _session_tree(temp, session_id, now=now, root_idle=over, content_idle=over)
        _transcript(transcripts, session_id, now=now, idle=over)

    verdicts = assess_claude_sessions(
        temp,
        now=now,
        transcript_root=transcripts,
        own_session_id=_SESSION,
    )

    assert [verdict.session_id for verdict in verdicts] == [_OTHER_SESSION]
    reclaim(verdicts)
    assert (temp / _PROJECT / _SESSION).is_dir(), "the reaper deleted the session it was running inside"
    assert not (temp / _PROJECT / _OTHER_SESSION).exists()


def test_the_transcript_is_looked_up_under_its_own_project_slug(tmp_path: Path) -> None:
    """The layout contract: ``<root>/<project slug>/<session uuid>.jsonl``.

    Pinned because getting it wrong has no symptom. A derivation that missed
    would find no transcript for any session, every one would read as
    unanswerable, and the reaper would report a permanently clean zero while the
    disk filled -- indistinguishable from a box with nothing to reclaim.

    The negative half is the load-bearing one: the same file under a different
    project must not answer, or one project's activity would vouch for another's
    abandoned sessions.
    """
    (tmp_path / _PROJECT).mkdir()
    (tmp_path / _PROJECT / f"{_SESSION}.jsonl").write_text("{}\n", encoding="utf-8")

    assert transcript_mtime(_SESSION, _PROJECT, tmp_path) is not None
    assert transcript_mtime(_SESSION, "A--different-project", tmp_path) is None
    assert transcript_mtime(_OTHER_SESSION, _PROJECT, tmp_path) is None
    assert claude_session_root(tmp_path) == tmp_path / "claude"


def test_the_verdict_records_the_evidence_it_decided_on(tmp_path: Path) -> None:
    """Every verdict carries the ages it was decided from, so a report can be audited.

    A reaper that printed only its conclusions would be unreviewable in exactly
    the situation review matters -- an operator deciding whether to pass
    ``--apply`` on a machine full of other people's sessions.
    """
    now = time.time()
    temp = tmp_path / "temp"
    transcripts = tmp_path / "transcripts"
    over = IDLE_CEILING_SECONDS + 7200
    _session_tree(temp, _SESSION, now=now, root_idle=over, content_idle=over)
    _transcript(transcripts, _SESSION, now=now, idle=over + 3600)

    verdict = assess_session(
        temp / _PROJECT / _SESSION,
        _PROJECT,
        now=now,
        ceiling=IDLE_CEILING_SECONDS,
        transcript_root=transcripts,
    )

    assert verdict.session_id == _SESSION
    assert verdict.scratchpad_idle_seconds == pytest.approx(over, abs=5)
    assert verdict.transcript_idle_seconds == pytest.approx(over + 3600, abs=5)
    assert verdict.reason

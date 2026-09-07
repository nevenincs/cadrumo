"""Gates for the temp reaper's sparing decisions.

This module deletes directories, and every one of its safety invariants fails
toward deleting a scratchpad that belongs to a running session. Nothing
exercised them: the reaper shipped with no test module at all, so an edit that
inverted any single condition below would have been caught by nothing.

Each test here drives the real functions over a real temporary tree. Nothing
under the operator's actual temp directory is read or written, and no session
store outside the test's own ``tmp_path`` is reachable from any of them.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from dev.env.temp_reaper import (
    assess_claude_sessions,
    assess_session,
    newest_activity,
    reclaim,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_CEILING = 72 * 60 * 60
_STALE = _CEILING + 3600
_FRESH = 60.0


def _age(path: Path, seconds: float) -> None:
    """Backdate ``path`` by ``seconds``, so idle time is stated, not waited for."""
    stamp = time.time() - seconds
    os.utime(path, (stamp, stamp))


def _session(sessions_root: Path, project: str, session_id: str, *, idle: float) -> Path:
    """Create one session scratchpad whose newest file is ``idle`` seconds old."""
    directory = sessions_root / project / session_id / "scratchpad"
    directory.mkdir(parents=True)
    note = directory / "note.txt"
    note.write_text("scratch", encoding="utf-8")
    _age(note, idle)
    _age(directory, idle)
    return sessions_root / project / session_id


def _transcript(transcript_root: Path, project: str, session_id: str, *, idle: float) -> Path:
    """Create the session transcript the reaper reads as its second signal."""
    project_root = transcript_root / project
    project_root.mkdir(parents=True, exist_ok=True)
    transcript = project_root / f"{session_id}.jsonl"
    transcript.write_text("{}", encoding="utf-8")
    _age(transcript, idle)
    return transcript


def test_a_session_whose_transcript_is_live_is_spared_without_walking_its_tree(
    tmp_path: Path,
) -> None:
    """A live transcript short-cuts the walk, so the spare costs no traversal."""
    sessions, transcripts = tmp_path / "temp", tmp_path / "projects"
    directory = _session(sessions, "proj", "live-session", idle=_STALE)
    _transcript(transcripts, "proj", "live-session", idle=_FRESH)

    verdict = assess_session(
        directory,
        "proj",
        now=time.time(),
        ceiling=_CEILING,
        transcript_root=transcripts,
    )

    assert verdict.reclaimable is False
    assert verdict.scratchpad_idle_seconds is None, "the tree was walked despite a live transcript"
    assert verdict.total_bytes is None


def test_a_session_with_no_transcript_at_all_is_spared(tmp_path: Path) -> None:
    """An unanswerable question spares: no transcript is not evidence of absence."""
    sessions, transcripts = tmp_path / "temp", tmp_path / "projects"
    directory = _session(sessions, "proj", "orphan-session", idle=_STALE)
    transcripts.mkdir(parents=True)

    verdict = assess_session(directory, "proj", now=time.time(), ceiling=_CEILING, transcript_root=transcripts)

    assert verdict.reclaimable is False
    assert verdict.transcript_idle_seconds is None


def test_a_session_silent_on_the_transcript_but_written_recently_is_spared(
    tmp_path: Path,
) -> None:
    """Both signals must clear the ceiling; one stale signal is not abandonment."""
    sessions, transcripts = tmp_path / "temp", tmp_path / "projects"
    directory = _session(sessions, "proj", "working-session", idle=_FRESH)
    _transcript(transcripts, "proj", "working-session", idle=_STALE)

    verdict = assess_session(directory, "proj", now=time.time(), ceiling=_CEILING, transcript_root=transcripts)

    assert verdict.reclaimable is False
    assert verdict.scratchpad_idle_seconds is not None


def test_a_session_silent_on_both_signals_is_reclaimable(tmp_path: Path) -> None:
    """The positive control: without it every test above passes on a reaper that never reaps."""
    sessions, transcripts = tmp_path / "temp", tmp_path / "projects"
    directory = _session(sessions, "proj", "abandoned-session", idle=_STALE)
    _transcript(transcripts, "proj", "abandoned-session", idle=_STALE)

    verdict = assess_session(directory, "proj", now=time.time(), ceiling=_CEILING, transcript_root=transcripts)

    assert verdict.reclaimable is True
    assert verdict.total_bytes is not None and verdict.total_bytes > 0


def test_the_verdict_agrees_with_the_two_idle_figures_it_reports(tmp_path: Path) -> None:
    """The decision must follow the evidence, not the wording that describes it.

    ``reclaimable`` is derived from the reason prose, so a copy-edit to an
    operator-facing sentence can move it. Recomputing the rule from the two
    reported figures catches that drift, which reading the sentence cannot.
    """
    sessions, transcripts = tmp_path / "temp", tmp_path / "projects"
    cases = ((_STALE, _STALE), (_STALE, _FRESH), (_FRESH, _STALE), (_FRESH, _FRESH))
    reclaimed = 0
    for index, (tree_idle, transcript_idle) in enumerate(cases):
        name = f"session-{index}"
        directory = _session(sessions, "proj", name, idle=tree_idle)
        _transcript(transcripts, "proj", name, idle=transcript_idle)
        verdict = assess_session(
            directory,
            "proj",
            now=time.time(),
            ceiling=_CEILING,
            measure_spared=True,
            transcript_root=transcripts,
        )
        expected = (
            verdict.transcript_idle_seconds is not None
            and verdict.transcript_idle_seconds > _CEILING
            and verdict.scratchpad_idle_seconds is not None
            and verdict.scratchpad_idle_seconds > _CEILING
        )
        assert verdict.reclaimable is expected, (
            f"{name}: reported {verdict.reclaimable} but its own figures say {expected} ({verdict.reason!r})"
        )
        reclaimed += int(verdict.reclaimable)
    assert reclaimed == 1, f"exactly one of the four combinations reaps, got {reclaimed}"


def test_the_running_session_is_dropped_from_consideration_entirely(tmp_path: Path) -> None:
    """The one session with a definite answer is excluded, not merely judged safe."""
    sessions, transcripts = tmp_path / "temp", tmp_path / "projects"
    _session(sessions, "proj", "mine", idle=_STALE)
    _transcript(transcripts, "proj", "mine", idle=_STALE)
    _session(sessions, "proj", "theirs", idle=_STALE)
    _transcript(transcripts, "proj", "theirs", idle=_STALE)

    verdicts = assess_claude_sessions(sessions, ceiling=_CEILING, transcript_root=transcripts, own_session_id="mine")

    assert [item.session_id for item in verdicts] == ["theirs"]


def test_a_root_that_exists_but_cannot_be_scanned_refuses_rather_than_reporting_nothing(
    tmp_path: Path,
) -> None:
    """A failed scan must not print the same 'nothing to reclaim' a clean box prints."""
    not_a_directory = tmp_path / "temp"
    not_a_directory.write_text("this is a file", encoding="utf-8")

    with pytest.raises(OSError):
        assess_claude_sessions(not_a_directory, ceiling=_CEILING, transcript_root=tmp_path)


def test_an_absent_root_is_a_legitimate_empty(tmp_path: Path) -> None:
    """The other direction: a box that never ran the tool reports no sessions, quietly."""
    verdicts = assess_claude_sessions(tmp_path / "never-created", ceiling=_CEILING, transcript_root=tmp_path)

    assert verdicts == []


def test_an_entry_that_refuses_to_stat_reports_the_tree_as_active(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unreadable newest entry must not make a live tree read as silent.

    There is no portable way to make ``os.stat`` refuse one real file on this
    host, so the refusal is injected at the boundary the reaper calls rather
    than simulated in the reaper itself. Everything else here is the real walk.
    """
    tree = tmp_path / "session"
    tree.mkdir()
    unreadable = tree / "newest.txt"
    unreadable.write_text("recent", encoding="utf-8")
    _age(unreadable, _STALE)
    # A second entry that stats cleanly and is old. Without it the tree holds
    # nothing readable, `newest` stays 0.0, and the empty-directory fallback
    # returns the current time too -- so a reaper that dropped the refusal
    # silently would produce the same answer and this test could not tell the
    # two apart. The stale companion is what forces them to differ.
    readable = tree / "older.txt"
    readable.write_text("stale", encoding="utf-8")
    _age(readable, _STALE)

    real_stat = os.stat

    def refusing_stat(path, *args, **kwargs):  # type: ignore[no-untyped-def]
        if str(path).endswith("newest.txt"):
            raise OSError("refused")
        return real_stat(path, *args, **kwargs)

    monkeypatch.setattr("dev.env.temp_reaper.os.stat", refusing_stat)
    newest, total = newest_activity(tree)

    assert time.time() - newest < 60, "a refused stat left the tree looking idle"
    assert total == readable.stat().st_size, "the byte total must omit what it could not read"


def test_reclaim_does_not_count_bytes_for_a_directory_that_survived_removal(
    tmp_path: Path,
) -> None:
    """A partial removal under-reports; it must never claim bytes it did not free."""
    sessions, transcripts = tmp_path / "temp", tmp_path / "projects"
    directory = _session(sessions, "proj", "held-session", idle=_STALE)
    _transcript(transcripts, "proj", "held-session", idle=_STALE)
    verdicts = assess_claude_sessions(sessions, ceiling=_CEILING, transcript_root=transcripts, own_session_id="none")
    assert [item.reclaimable for item in verdicts] == [True]

    held = directory / "scratchpad" / "note.txt"
    with held.open("r", encoding="utf-8"):
        reclaimed = reclaim(verdicts)
        survived = directory.exists()

    if survived:
        assert reclaimed == 0, "bytes were reported freed while the directory still stands"
    else:
        assert reclaimed > 0


def test_reclaim_leaves_every_spared_directory_untouched(tmp_path: Path) -> None:
    """The invariant the whole module exists to hold."""
    sessions, transcripts = tmp_path / "temp", tmp_path / "projects"
    spared = _session(sessions, "proj", "spared-session", idle=_FRESH)
    _transcript(transcripts, "proj", "spared-session", idle=_FRESH)
    doomed = _session(sessions, "proj", "doomed-session", idle=_STALE)
    _transcript(transcripts, "proj", "doomed-session", idle=_STALE)

    verdicts = assess_claude_sessions(sessions, ceiling=_CEILING, transcript_root=transcripts, own_session_id="none")
    reclaim(verdicts)

    assert spared.exists(), "a session written one minute ago was removed"
    assert not doomed.exists(), "the abandoned session was not reclaimed"

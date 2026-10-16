"""The desktop's sign-in watch reads only when something moved and writes only what changed."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from datetime import timedelta
from threading import Thread
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from cadrumo.core.time.clock import now
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.sign_in import SignInPresence, SignInStatus

from .. import session_watch

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_ABSENT = SignInStatus(presence=SignInPresence.ABSENT)


class _Runtime:
    """Stand in for the runtime connection; the loop under test is the real one."""

    def __init__(self) -> None:
        self.status = _ABSENT
        self.reads = 0
        self.connections: list[UUID] = []
        self.cue: Callable[[], None] | None = None
        self.lost = False

    async def open(self, *, profile_id: UUID, frontend: object) -> _Runtime:
        self.connections.append(profile_id)
        self.lost = False
        return self

    def _reply(self) -> SimpleNamespace:
        self.reads += 1
        if self.lost:
            raise RefusalError(RefusalCode.CONNECTION_CLOSED)
        return SimpleNamespace(status=self.status)

    def watch_sign_in(self, receive: Callable[[], None]) -> SimpleNamespace:
        self.cue = receive
        return self._reply()

    def sign_in_status(self) -> SimpleNamespace:
        return self._reply()

    def close(self) -> None:
        pass


def _until(condition: Callable[[], bool], what: str) -> None:
    deadline = time.monotonic() + 5
    while not condition():
        assert time.monotonic() < deadline, what
        time.sleep(0.01)


def test_the_watch_follows_cues_pointer_moves_deadlines_and_reconnects(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = _Runtime()
    lines: list[dict[str, object]] = []
    first, second = uuid4(), uuid4()
    selection: list[tuple[UUID | None, str | None]] = [(first, "Primero")]
    monkeypatch.setattr(session_watch, "open_installed_client", runtime.open)
    monkeypatch.setattr(session_watch, "_selection", lambda: selection[0])
    monkeypatch.setattr(session_watch, "_emit", lambda document: lines.append(json.loads(json.dumps(document))))
    monkeypatch.setattr(session_watch, "_RECONNECT_SECONDS", (0.1,))
    wakes = session_watch._Wakes()
    watching = Thread(target=session_watch._watch, args=(wakes,), daemon=True)
    watching.start()
    try:
        _until(lambda: len(lines) == 1, "the first observation")
        assert lines[0] == {
            "kind": "sign_in",
            "active_profile": "Primero",
            "profile_id": str(first),
            "presence": "absent",
            "refusal": None,
        }
        time.sleep(0.5)
        assert runtime.reads == 1, "an idle watch must not read again"

        runtime.status = SignInStatus(
            presence=SignInPresence.PRESENT,
            idle_deadline=now() + timedelta(seconds=0.3),
            absolute_deadline=now() + timedelta(hours=1),
        )
        assert runtime.cue is not None
        runtime.cue()
        _until(lambda: len(lines) == 2, "the cued observation")
        assert lines[1]["presence"] == "present"
        # The idle deadline passes with no cue: the watch reads once at it.
        runtime.status = _ABSENT
        _until(lambda: len(lines) == 3, "the observation at the deadline")
        assert lines[2]["presence"] == "absent"

        reads = runtime.reads
        runtime.cue()
        _until(lambda: runtime.reads == reads + 1, "the cued read")
        time.sleep(0.2)
        assert len(lines) == 3, "an unchanged observation is not written again"
        # After a sign-in or sign-out of its own the parent asks, and hears, even when nothing changed.
        wakes.refresh()
        _until(lambda: len(lines) == 4, "the requested observation")
        assert lines[3] == lines[2]
        del lines[3]

        reads = runtime.reads
        wakes.pointer_moved()
        time.sleep(0.2)
        assert runtime.reads == reads, "a pointer change that selects the same profile reads nothing"

        selection[0] = (second, "Segundo")
        wakes.pointer_moved()
        _until(lambda: len(lines) == 4, "the newly selected profile")
        assert runtime.connections == [first, second]
        assert (lines[3]["profile_id"], lines[3]["active_profile"]) == (str(second), "Segundo")

        runtime.lost = True
        runtime.cue()
        _until(lambda: len(lines) == 5, "the lost connection")
        assert lines[4]["refusal"] == "runtime_unavailable"
        assert lines[4]["presence"] == "unknown"
        _until(lambda: len(runtime.connections) == 3, "the reconnection")
        _until(lambda: len(lines) == 6, "the observation after reconnecting")
        assert lines[5]["refusal"] is None
    finally:
        wakes.stop()
        watching.join(timeout=5)
    assert not watching.is_alive()


def test_no_selected_profile_is_absent_until_the_pointer_moves(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = _Runtime()
    lines: list[dict[str, object]] = []
    selection: list[tuple[UUID | None, str | None]] = [(None, None)]
    monkeypatch.setattr(session_watch, "open_installed_client", runtime.open)
    monkeypatch.setattr(session_watch, "_selection", lambda: selection[0])
    monkeypatch.setattr(session_watch, "_emit", lines.append)
    wakes = session_watch._Wakes()
    watching = Thread(target=session_watch._watch, args=(wakes,), daemon=True)
    watching.start()
    try:
        _until(lambda: len(lines) == 1, "the first observation")
        assert lines[0]["presence"] == "absent" and lines[0]["profile_id"] is None
        assert runtime.connections == []
        profile = uuid4()
        selection[0] = (profile, "Nuevo")
        wakes.pointer_moved()
        _until(lambda: len(lines) == 2, "the selected profile")
        assert runtime.connections == [profile]
    finally:
        wakes.stop()
        watching.join(timeout=5)
    assert not watching.is_alive()


def test_the_watch_ends_when_its_parent_closes_standard_input() -> None:
    import os

    reader, writer = os.pipe()
    wakes = session_watch._Wakes()
    parent = Thread(target=session_watch._watch_parent, args=(reader, wakes), daemon=True)
    parent.start()
    try:
        os.write(writer, b"\n")
        assert not wakes.stopping.wait(0.2)
        assert wakes.take_forced(), "a newline from the parent asks for a fresh line"
        os.close(writer)
        assert wakes.stopping.wait(5)
    finally:
        parent.join(timeout=5)
        os.close(reader)


def test_a_cue_and_a_pointer_change_are_each_taken_once() -> None:
    wakes = session_watch._Wakes()
    wakes.cue()
    wakes.pointer_moved()
    assert wakes.wait(0) == (True, True)
    assert wakes.wait(0) == (False, False)
    wakes.stop()
    assert wakes.stopping.is_set()

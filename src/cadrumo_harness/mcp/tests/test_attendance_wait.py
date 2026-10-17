"""The attendance wait reads its ask again only when the runtime cues an answer, bounded by its deadline.

Whether an ask is approved is the runtime's decision and is proven against the
real runtime there; this connection double only answers when it was told to.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import timedelta
from threading import Lock, Timer
from typing import cast
from uuid import uuid4

import pytest

from cadrumo.application.user_profile.access_contracts import AccessDenialCode
from cadrumo.core.time.clock import now
from cadrumo_client.contracts.attendance import AttendancePending
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

from .. import runtime_admission
from ..runtime_admission import attend_held_sign_in

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class _Asker:
    """One asking connection whose ask the person declines when ``decline`` runs."""

    def __init__(self) -> None:
        self.attendance_id = uuid4()
        self.status_reads = 0
        self._declined = False
        self._lock = Lock()
        self._receivers: list[Callable[[], None]] = []

    def subscribe_attendance_answers(self, receive: Callable[[], None]) -> Callable[[], None]:
        with self._lock:
            self._receivers.append(receive)

        def unsubscribe() -> None:
            with self._lock:
                self._receivers.remove(receive)

        return unsubscribe

    @property
    def subscribed(self) -> int:
        with self._lock:
            return len(self._receivers)

    def request_attendance(self) -> AttendancePending:
        return self._pending()

    def attendance_status(self, attendance_id: object) -> AttendancePending:
        assert attendance_id == self.attendance_id
        with self._lock:
            self.status_reads += 1
            declined = self._declined
        if declined:
            raise FrontendRefusedError(AccessDenialCode.AUTHENTICATION_REQUIRED.value)
        return self._pending()

    def decline(self) -> None:
        with self._lock:
            self._declined = True
            receivers = tuple(self._receivers)
        for receive in receivers:
            receive()

    def _pending(self) -> AttendancePending:
        return AttendancePending(
            request_id=uuid4(),
            runtime_boot_id=uuid4(),
            connection_id=uuid4(),
            attendance_id=self.attendance_id,
            expires_at=now() + timedelta(minutes=2),
        )


def _refusal(asker: _Asker) -> str:
    with pytest.raises(FrontendRefusedError) as refused:
        attend_held_sign_in(cast(FrontendClient, asker), profile_id=uuid4())
    return refused.value.reason


def test_the_answer_cue_alone_reads_the_ask_again() -> None:
    asker = _Asker()
    decision = Timer(1.0, asker.decline)
    decision.start()
    started = time.monotonic()
    try:
        assert _refusal(asker) == AccessDenialCode.AUTHENTICATION_REQUIRED.value
    finally:
        decision.cancel()
    # One read, after the answer: a timer would have read the pending ask several times first.
    assert asker.status_reads == 1
    assert time.monotonic() - started < 10
    assert asker.subscribed == 0


def test_without_an_answer_the_ask_is_not_read_again_before_the_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime_admission, "ATTENDANCE_WAIT_SECONDS", 1.0)
    asker = _Asker()
    started = time.monotonic()
    assert _refusal(asker) == AccessDenialCode.AUTHENTICATION_REQUIRED.value
    assert asker.status_reads == 0
    assert time.monotonic() - started >= 1.0
    assert asker.subscribed == 0

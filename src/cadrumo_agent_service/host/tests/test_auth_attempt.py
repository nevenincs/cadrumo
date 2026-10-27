"""A revoked request never reaches native process creation."""

import io
import json
import time
from collections.abc import Buffer
from pathlib import Path
from queue import Queue
from threading import Event, Lock, Thread
from typing import override
from uuid import uuid4

import pytest

from ..auth_attempt import AuthAttempt
from ..auth_protocol import AuthEvent, AuthProtocol, snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_revoked_attempt_closes_without_creating_a_process_or_profile(tmp_path: Path) -> None:
    settled = Event()
    attempt = AuthAttempt(
        provider="example",
        lane="example_cli",
        executable=tmp_path / "absent.exe",
        arguments=(),
        directory=tmp_path / "absent",
        environment={},
        valid=lambda: False,
        settled=settled.set,
    )
    attempt.close()
    assert not attempt.active
    assert settled.is_set()
    assert attempt.observe() == {"attempt_id": attempt.id, "provider": "example_cli", "event": "cancelled"}
    assert list(tmp_path.iterdir()) == []


def _exchange_attempt(valid: Event) -> AuthAttempt:
    attempt = AuthAttempt.__new__(AuthAttempt)
    attempt.id = str(uuid4())
    attempt._lane = "example_cli"
    attempt._protocol = AuthProtocol("example")
    attempt._valid = valid.is_set
    attempt._lock = Lock()
    attempt._cancel = Event()
    attempt._observed = time.monotonic()
    attempt._deadline = time.monotonic() + 305
    attempt._snapshot = snapshot(attempt.id, attempt._lane, "starting")
    return attempt


def _frame(attempt: str, event: str, **fields: str) -> bytes:
    return (
        json.dumps({"version": 1, "attempt_id": attempt, "provider": "example", "event": event, **fields}) + "\n"
    ).encode()


def test_code_submission_uses_same_pipe_once_and_does_not_expose_the_code() -> None:
    valid = Event()
    valid.set()
    attempt = _exchange_attempt(valid)
    stream = io.BytesIO()
    attempt._input = stream
    queue: Queue[bytes | None] = Queue()
    helper_id = str(uuid4())
    for event in ("ready", "started"):
        queue.put(_frame(helper_id, event))
    queue.put(_frame(helper_id, "browser_action", url="https://example.org/login?state=opaque"))
    queue.put(_frame(helper_id, "authorization_code_required"))
    outcomes: list[tuple[str, str | None]] = []
    worker = Thread(target=lambda: outcomes.append(attempt._exchange(stream, queue)))
    worker.start()
    try:
        deadline = time.monotonic() + 3
        while attempt.observe()["event"] != "authorization_code_required" and time.monotonic() < deadline:
            time.sleep(0.01)
        before = attempt.observe()
        assert before["event"] == "authorization_code_required"
        assert before["url"] == "https://example.org/login?state=opaque"
        for invalid in (b"", b"contains space", b"\xff", b"x" * 2049, b'"' * 2048):
            with pytest.raises(ValueError, match="invalid_request"):
                attempt.submit_code(bytearray(invalid))
        code = bytearray(b'synthetic-"\\-code')
        answer = attempt.submit_code(code)
        assert answer["event"] == "started" and "url" not in answer
        assert code.decode() not in str(answer)
        with pytest.raises(ValueError, match="invalid_request"):
            attempt.submit_code(code)
        lines = stream.getvalue().splitlines()
        assert json.loads(lines[0]) == {"version": 1, "action": "start"}
        assert json.loads(lines[1]) == {"version": 1, "action": "auth_code", "code": code.decode()}
        queue.put(_frame(helper_id, "succeeded"))
        worker.join(3)
        assert outcomes == [("succeeded", None)]
    finally:
        attempt.cancel()
        worker.join(3)


@pytest.mark.parametrize("state", ["revoked", "cancelled", "wrong_state", "timeout", "disconnected"])
def test_code_submission_refuses_revoked_cancelled_or_out_of_state(state: str) -> None:
    valid = Event()
    valid.set()
    attempt = _exchange_attempt(valid)
    attempt._input = io.BytesIO()
    attempt._snapshot = snapshot(attempt.id, attempt._lane, "authorization_code_required")
    if state == "revoked":
        valid.clear()
    elif state == "cancelled":
        attempt.cancel()
    elif state == "timeout":
        attempt._deadline = time.monotonic() - 1
    elif state == "disconnected":
        attempt._observed = time.monotonic() - 16
    else:
        attempt._snapshot = snapshot(attempt.id, attempt._lane, "browser_action")
    with pytest.raises(ValueError, match="invalid_request"):
        attempt.submit_code(bytearray(b"synthetic-code"))
    assert attempt._input.getvalue() == b""


def test_partial_write_consumes_attempt_and_cancels_without_replay() -> None:
    class ShortWrite(io.BytesIO):
        @override
        def write(self, data: Buffer, /) -> int:
            return super().write(bytes(data)[:1])

    valid = Event()
    valid.set()
    attempt = _exchange_attempt(valid)
    attempt._input = ShortWrite()
    attempt._snapshot = snapshot(attempt.id, attempt._lane, "authorization_code_required")
    with pytest.raises(ValueError, match="invalid_request"):
        attempt.submit_code(bytearray(b"synthetic-code"))
    assert attempt._cancel.is_set()
    with pytest.raises(ValueError, match="invalid_request"):
        attempt.submit_code(bytearray(b"synthetic-code"))
    assert len(attempt._input.getvalue()) == 1


def test_cancel_and_submission_are_serialized() -> None:
    writing, release = Event(), Event()

    class BlockingWrite(io.BytesIO):
        @override
        def write(self, data: Buffer, /) -> int:
            writing.set()
            assert release.wait(3)
            return super().write(data)

    valid = Event()
    valid.set()
    attempt = _exchange_attempt(valid)
    attempt._input = BlockingWrite()
    attempt._snapshot = snapshot(attempt.id, attempt._lane, "authorization_code_required")
    submitted = Thread(target=attempt.submit_code, args=(bytearray(b"synthetic-code"),))
    cancelled = Thread(target=attempt.cancel)
    submitted.start()
    try:
        assert writing.wait(3)
        cancelled.start()
        assert not attempt._cancel.is_set()
    finally:
        release.set()
        submitted.join(3)
        if cancelled.ident is not None:
            cancelled.join(3)
    assert not submitted.is_alive() and not cancelled.is_alive()
    assert attempt._cancel.is_set()
    with pytest.raises(ValueError, match="invalid_request"):
        attempt.submit_code(bytearray(b"synthetic-code"))


def test_terminal_event_withdraws_code_state_before_a_waiting_submission() -> None:
    terminal_read, release = Event(), Event()

    class PausedProtocol(AuthProtocol):
        @override
        def read(self, raw: bytes) -> AuthEvent:
            event = super().read(raw)
            if event.event == "failed":
                terminal_read.set()
                assert release.wait(3)
            return event

    valid = Event()
    valid.set()
    attempt = _exchange_attempt(valid)
    attempt._protocol = PausedProtocol("example")
    stream = io.BytesIO()
    attempt._input = stream
    queue: Queue[bytes | None] = Queue()
    helper_id = str(uuid4())
    for event in ("ready", "started"):
        queue.put(_frame(helper_id, event))
    queue.put(_frame(helper_id, "browser_action", url="https://example.org/login"))
    queue.put(_frame(helper_id, "authorization_code_required"))
    outcomes: list[tuple[str, str | None]] = []
    worker = Thread(target=lambda: outcomes.append(attempt._exchange(stream, queue)))
    worker.start()
    submitting = Event()
    submissions: list[str] = []

    def submit() -> None:
        submitting.set()
        try:
            attempt.submit_code(bytearray(b"synthetic-code"))
            submissions.append("accepted")
        except ValueError:
            submissions.append("refused")

    submitter = Thread(target=submit)
    try:
        deadline = time.monotonic() + 3
        while attempt.observe()["event"] != "authorization_code_required" and time.monotonic() < deadline:
            time.sleep(0.01)
        assert attempt.observe()["event"] == "authorization_code_required"
        queue.put(_frame(helper_id, "failed"))
        assert terminal_read.wait(3)
        submitter.start()
        assert submitting.wait(3)
    finally:
        release.set()
        worker.join(3)
        if submitter.ident is not None:
            submitter.join(3)
    assert outcomes == [("failed", None)]
    assert submissions == ["refused"]
    assert len(stream.getvalue().splitlines()) == 1  # only the start command


@pytest.mark.parametrize("raw", [b"untrusted output\n", None], ids=["malformed", "eof"])
def test_bad_stream_withdraws_code_state_before_a_waiting_submission(raw: bytes | None) -> None:
    invalid_read, release = Event(), Event()

    class PausedProtocol(AuthProtocol):
        @override
        def read(self, raw: bytes) -> AuthEvent:
            try:
                return super().read(raw)
            except ValueError:
                invalid_read.set()
                assert release.wait(3)
                raise

    valid = Event()
    valid.set()
    attempt = _exchange_attempt(valid)
    attempt._protocol = PausedProtocol("example")
    stream = io.BytesIO()
    attempt._input = stream
    queue: Queue[bytes | None] = Queue()
    helper_id = str(uuid4())
    for event in ("ready", "started"):
        queue.put(_frame(helper_id, event))
    queue.put(_frame(helper_id, "browser_action", url="https://example.org/login"))
    queue.put(_frame(helper_id, "authorization_code_required"))
    failures: list[str] = []

    def exchange() -> None:
        try:
            attempt._exchange(stream, queue)
        except ValueError as error:
            failures.append(str(error))

    worker = Thread(target=exchange)
    worker.start()
    submitting = Event()
    submissions: list[str] = []

    def submit() -> None:
        submitting.set()
        try:
            attempt.submit_code(bytearray(b"synthetic-code"))
            submissions.append("accepted")
        except ValueError:
            submissions.append("refused")

    submitter = Thread(target=submit)
    try:
        deadline = time.monotonic() + 3
        while attempt.observe()["event"] != "authorization_code_required" and time.monotonic() < deadline:
            time.sleep(0.01)
        assert attempt.observe()["event"] == "authorization_code_required"
        queue.put(raw)
        assert invalid_read.wait(3)
        submitter.start()
        assert submitting.wait(3)
    finally:
        release.set()
        worker.join(3)
        if submitter.ident is not None:
            submitter.join(3)
    assert failures == ["invalid_auth_event"]
    assert submissions == ["refused"]
    assert attempt._cancel.is_set()
    assert len(stream.getvalue().splitlines()) == 1

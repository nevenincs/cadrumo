"""Upgrade notices are coalesced and written before a bounded idle stop."""

import time
from collections.abc import Callable
from concurrent.futures import Future
from pathlib import Path
from threading import Event, Thread
from types import SimpleNamespace
from typing import Literal, cast, override
from uuid import uuid4

import pytest
from pydantic import BaseModel, ConfigDict

from cadrumo_client.contracts.contracts import ByteChannel, ClientHello, ExitReason, Peer, RefusalError
from cadrumo_client.contracts.login import LoginEvidence
from cadrumo_client.contracts.session_events import LifecycleNotice
from cadrumo_client.contracts.transport import ConnectionContext
from cadrumo_client.transport.frame_io import decode_document, document_frame
from cadrumo_client.transport.native_wake import NativeWake

from .. import notice_observation
from ..profile_connections import RuntimeProfileConnections
from ..session_events import RuntimeSessionEvents
from ..shutdown import RuntimeStop

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_SETTLED = 30.0
"""A ceiling for an awaited event that a passing run never reaches; no assertion depends on its size."""


class _WriterWake(NativeWake):
    """The native wake a connection's frame writer waits on, observable from a test thread."""

    def __init__(self) -> None:
        super().__init__()
        self.raised = Event()

    @override
    def set(self) -> None:
        super().set()
        self.raised.set()


def _write_one_notice(profiles: RuntimeProfileConnections, context: ConnectionContext, wake: _WriterWake) -> None:
    """Act as the connection's sole writer: wait for a queued event, take it and record its flush."""
    while True:
        assert wake.raised.wait(_SETTLED)
        # Cleared before the take, so an event queued after it raises the wake again.
        wake.raised.clear()
        wake.clear()
        events = profiles.take_events(context)
        if events:
            (notice,) = events
            assert isinstance(notice, LifecycleNotice)
            profiles.event_flushed(context, notice)
            return


def _in_thread(call: Callable[[], bool]) -> Future[bool]:
    result: Future[bool] = Future()

    def run() -> None:
        try:
            result.set_result(call())
        except BaseException as error:
            result.set_exception(error)

    Thread(target=run, name="test-idle-stop", daemon=True).start()
    return result


def _context(*, capable: bool = True) -> ConnectionContext:
    return ConnectionContext(uuid4(), uuid4(), Peer(os_owner_id="fixture", process_id=1), capable)


def test_legacy_hello_omits_capability_and_legacy_connection_gets_no_notice() -> None:
    hello = ClientHello(product_version="1.0.0", storage_identity="a" * 64)
    assert b"lifecycle_notices" not in document_frame(hello)
    events = RuntimeSessionEvents()
    legacy = _context(capable=False)
    events.connect(legacy)
    assert events.upgrade_pending(legacy) is None
    assert events.take(legacy) == ()


class LegacyHello(BaseModel):
    """Frozen pre-notice protocol-4 schema, exposing the one-way compatibility limit."""

    model_config = ConfigDict(extra="forbid", strict=True)
    kind: Literal["client_hello"]
    protocol_version: Literal[4]
    product_version: str
    storage_identity: str
    authority_generation: str | None


def test_opt_in_refuses_on_prior_strict_server_without_silent_downgrade() -> None:
    legacy = ClientHello(product_version="1.0.0", storage_identity="a" * 64)
    assert decode_document(document_frame(legacy)[5:], LegacyHello).protocol_version == 4
    opted_in = legacy.model_copy(update={"lifecycle_notices": "v1"})
    with pytest.raises(RefusalError):
        decode_document(document_frame(opted_in)[5:], LegacyHello)
    assert ClientHello.model_validate_json(document_frame(legacy)[5:]).lifecycle_notices is None


def test_only_exact_successful_write_acknowledges_notice_and_retries_coalesce() -> None:
    events = RuntimeSessionEvents()
    context = _context()
    events.connect(context)
    flushed = events.upgrade_pending(context)
    assert flushed is not None and not flushed.is_set()
    assert events.upgrade_pending(context) is flushed
    (notice,) = events.take(context)
    assert isinstance(notice, LifecycleNotice)
    assert not flushed.is_set()  # Taking/queueing is not delivery.
    events.flushed(_context(), notice)
    assert not flushed.is_set()
    events.flushed(context, notice)
    assert flushed.is_set()
    assert events.upgrade_pending(context) is flushed
    assert events.take(context) == ()


@pytest.mark.parametrize(
    ("opted_in", "unlocked"),
    [(True, True), (False, True), (True, False)],
    ids=["opted-in-attended", "not-opted-in", "opted-in-locked"],
)
def test_idle_stop_waits_only_for_attended_opted_in_connections(tmp_path: Path, opted_in: bool, unlocked: bool) -> None:
    # A connection carries no frontend here: every frontend's client opts in, and only the offer counts.
    stop = RuntimeStop()
    context = _context(capable=opted_in)
    profiles = RuntimeProfileConnections(
        storage_root=tmp_path, storage_identity="a" * 64, runtime_boot_id=context.runtime_boot_id, stop=stop
    )
    login = cast(
        LoginEvidence,
        SimpleNamespace(
            observe=lambda **_: SimpleNamespace(active=True, unlocked=unlocked, os_owner_id=context.peer.os_owner_id)
        ),
    )
    profiles._capture = lambda _: login
    wake = _WriterWake()
    profiles.connect_events(context, cast(ByteChannel, SimpleNamespace(peer=context.peer)), queued=wake)
    assert not profiles._connections  # No profile login or session is required for presentation.
    if not (opted_in and unlocked):
        # Nothing waits for a flush: a stop that waited would refuse at the deadline instead.
        assert profiles.stop_if_idle(ExitReason.SUPERVISOR_STOP, timeout=_SETTLED)
        assert stop.is_set()
        assert profiles.take_events(context) == ()
        return
    # An unflushed notice refuses at the bound, whether or not the observation finished in it: returning
    # while nothing has written the notice is the proof that the wait is bounded.
    assert not profiles.stop_if_idle(ExitReason.SUPERVISOR_STOP, timeout=0.02)
    assert not stop.is_set()
    assert profiles._admitting()
    # An attempt refuses while an earlier one's observation still runs; the next one starts after it.
    earlier = profiles._notice_observation
    assert earlier is not None
    earlier.result(timeout=_SETTLED)
    stopping = _in_thread(lambda: profiles.stop_if_idle(ExitReason.SUPERVISOR_STOP, timeout=_SETTLED))
    _write_one_notice(profiles, context, wake)
    assert stopping.result(timeout=_SETTLED)
    assert stop.is_set()


def test_slow_native_observation_is_bounded_retained_and_cannot_publish_late(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stop = RuntimeStop()
    context = _context()
    profiles = RuntimeProfileConnections(
        storage_root=tmp_path, storage_identity="a" * 64, runtime_boot_id=context.runtime_boot_id, stop=stop
    )
    entered, release = Event(), Event()
    calls: list[int] = []
    blocking = False

    def observe(**_: object) -> SimpleNamespace:
        if blocking:
            calls.append(1)
            entered.set()
            assert release.wait(_SETTLED)
        return SimpleNamespace(active=True, unlocked=True, os_owner_id=context.peer.os_owner_id)

    def observation_clock() -> float:
        # The first attempt's thread may start after its short deadline under load and then skip the query;
        # until the query has begun, the observation reads a clock that has not reached any deadline.
        return time.monotonic() if entered.is_set() else float("-inf")

    monkeypatch.setattr(notice_observation, "time", SimpleNamespace(monotonic=observation_clock))
    profiles._capture = lambda _: cast(LoginEvidence, SimpleNamespace(observe=observe))
    wake = _WriterWake()
    profiles.connect_events(context, cast(ByteChannel, SimpleNamespace(peer=context.peer)), queued=wake)
    blocking = True
    try:
        # Returning at all while the observation cannot finish is the proof that the attempt is bounded.
        assert not profiles.stop_if_idle(ExitReason.SUPERVISOR_STOP, timeout=0.01)
        assert entered.wait(_SETTLED)
        retained = profiles._notice_observation
        assert retained is not None and not retained.done()
        # Retry storms cannot accumulate OS queries or reuse a timed-out task.
        for _ in range(20):
            assert not profiles.stop_if_idle(ExitReason.SUPERVISOR_STOP, timeout=0.01)
            assert profiles._notice_observation is retained
        assert len(calls) == 1
        assert not stop.is_set() and profiles._admitting()
        assert profiles.take_events(context) == ()
    finally:
        release.set()
    # The late result belongs to an expired attempt: it is None and queues nothing.
    assert retained.result(timeout=_SETTLED) is None
    assert profiles.take_events(context) == () and not stop.is_set()
    # A later attempt requires a fresh native observation and a real frame flush.
    stopping = _in_thread(lambda: profiles.stop_if_idle(ExitReason.SUPERVISOR_STOP, timeout=_SETTLED))
    _write_one_notice(profiles, context, wake)
    assert len(calls) == 2
    assert stopping.result(timeout=_SETTLED)
    assert stop.is_set()

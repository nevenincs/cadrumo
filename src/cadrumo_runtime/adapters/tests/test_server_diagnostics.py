"""Diagnostic interruption never prevents the listener's owned resource drain."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from typing import override

import pytest

from cadrumo_client.contracts.contracts import (
    ByteChannel,
    ChannelWake,
    RefusalCode,
    RefusalError,
    ShutdownIncompleteError,
)
from cadrumo_runtime.contracts.profile_host import ProfileDrainResult

from .. import server as runtime_server
from ..server import RuntimeTransportServer

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


class _Listener:
    storage_identity = "a" * 64

    def __init__(self) -> None:
        self.closed = False

    def listen(self) -> None:
        pass

    def accept(self, *, timeout: float | None, wakes: tuple[ChannelWake, ...] = ()) -> ByteChannel:
        raise AssertionError("the test server owns its bounded accept driver")

    def close(self) -> None:
        self.closed = True


class _Server(RuntimeTransportServer):
    def __init__(self, listener: _Listener, primary: BaseException | None, *, incomplete: bool = False) -> None:
        super().__init__(listener, product_version="diagnostic-test", stop=Event())
        self.primary = primary
        self.incomplete = incomplete
        self.drained = False

    @override
    def _accept_connections(self, workers: ThreadPoolExecutor) -> None:
        if self.primary is not None:
            raise self.primary

    @override
    def _drain_owned_resources(self, *, deadline: float) -> ProfileDrainResult | None:
        self.drained = True
        if self.incomplete:
            raise ShutdownIncompleteError()
        return None


class _DiagnosticFailure(logging.Handler):
    def __init__(self, event: str, failure: BaseException) -> None:
        super().__init__()
        self.event, self.failure = event, failure

    @override
    def emit(self, record: logging.LogRecord) -> None:
        if record.getMessage() == self.event:
            raise self.failure


@pytest.fixture
def logger(monkeypatch: pytest.MonkeyPatch) -> logging.Logger:
    """A server logger whose handler faults surface on the calling thread.

    A registered project logger hands its records to the background dispatch,
    which contains every handler fault by design, so an interruption raised by
    a handler there could never reach the serving thread. This logger sits
    outside that dispatch.
    """
    selected = logging.Logger(runtime_server.__name__, level=logging.DEBUG)
    selected.propagate = False
    monkeypatch.setattr(runtime_server, "_LOGGER", selected)
    return selected


@pytest.mark.parametrize("event", ["runtime_listener_ready", "runtime_listener_drain_started"])
@pytest.mark.parametrize("active_caller_error", [False, True])
def test_diagnostic_interrupt_still_drains_before_listener_release(
    logger: logging.Logger, event: str, active_caller_error: bool
) -> None:
    listener = _Listener()
    server = _Server(listener, None)
    interruption = KeyboardInterrupt("synthetic diagnostic interruption")
    handler = _DiagnosticFailure(event, interruption)
    logger.addHandler(handler)
    try:
        if active_caller_error:
            try:
                raise ValueError("unrelated caller exception")
            except ValueError:
                with pytest.raises(KeyboardInterrupt) as caught:
                    server.serve()
        else:
            with pytest.raises(KeyboardInterrupt) as caught:
                server.serve()
    finally:
        logger.removeHandler(handler)

    assert caught.value is interruption
    assert server.drained and listener.closed
    assert server.stop.is_set() and not server.ready.is_set()


def test_drain_diagnostic_interrupt_does_not_replace_accept_refusal(logger: logging.Logger) -> None:
    listener = _Listener()
    primary = RefusalError(RefusalCode.UNAVAILABLE)
    server = _Server(listener, primary)
    handler = _DiagnosticFailure("runtime_listener_drain_started", KeyboardInterrupt("synthetic sink interrupt"))
    logger.addHandler(handler)
    try:
        with pytest.raises(RefusalError) as caught:
            server.serve()
    finally:
        logger.removeHandler(handler)

    assert caught.value is primary
    assert server.drained and listener.closed


def test_drain_diagnostic_interrupt_cannot_release_an_incompletely_drained_listener(logger: logging.Logger) -> None:
    listener = _Listener()
    server = _Server(listener, None, incomplete=True)
    handler = _DiagnosticFailure("runtime_listener_drain_started", KeyboardInterrupt("synthetic sink interrupt"))
    logger.addHandler(handler)
    try:
        with pytest.raises(ShutdownIncompleteError):
            server.serve()
        assert not listener.closed
    finally:
        logger.removeHandler(handler)
        listener.close()

    assert server.drained
    assert not server._listener_owner.released

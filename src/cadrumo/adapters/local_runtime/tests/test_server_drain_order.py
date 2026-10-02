"""Transport shutdown contains profile custody before waiting on blocked handlers."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Thread
from typing import cast, override
from uuid import uuid4

import pytest

from cadrumo.application.runtime.contracts import RuntimeShutdownIncompleteError
from cadrumo.application.runtime.profile_access import RuntimeProfileDrainResult, RuntimeProfileHandler

from ..server import RuntimeListener, RuntimeTransportServer

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


class _Listener:
    storage_identity = "0" * 64

    def __init__(self) -> None:
        self.listening = Event()
        self.closed = Event()

    def listen(self) -> None:
        self.listening.set()

    def close(self) -> None:
        self.closed.set()


class _Profiles:
    def __init__(self, release: Event, result: RuntimeProfileDrainResult | None = None) -> None:
        self.release = release
        self.drained = Event()
        self.result = result or RuntimeProfileDrainResult((), (), (), ())

    def drain(self, *, deadline: float) -> RuntimeProfileDrainResult:
        assert time.monotonic() < deadline
        self.drained.set()
        self.release.set()
        return self.result


class _ProfilesWithoutRelease(_Profiles):
    @override
    def drain(self, *, deadline: float) -> RuntimeProfileDrainResult:
        self.drained.set()
        return self.result


class _BlockedRequestServer(RuntimeTransportServer):
    def __init__(
        self, listener: RuntimeListener, *, stop: Event, profiles: RuntimeProfileHandler, entered: Event, release: Event
    ) -> None:
        super().__init__(listener, product_version="drain-order-test", stop=stop, profiles=profiles)
        self._entered, self._release = entered, release

    @override
    def _accept_connections(self, workers: ThreadPoolExecutor) -> None:
        def blocked() -> None:
            self._entered.set()
            self._release.wait()

        future = workers.submit(blocked)
        self._requests.add(future)
        future.add_done_callback(self._forget_request)
        self._entered.wait(timeout=2)
        self.stop.wait(timeout=2)


def test_profile_drain_releases_blocked_handler_before_executor_wait() -> None:
    stop, entered, release = Event(), Event(), Event()
    listener = _Listener()
    profiles = _Profiles(release)
    server = _BlockedRequestServer(
        cast("RuntimeListener", listener),
        stop=stop,
        profiles=cast("RuntimeProfileHandler", profiles),
        entered=entered,
        release=release,
    )
    failures: list[BaseException] = []

    def serve() -> None:
        try:
            server.serve()
        except BaseException as error:
            failures.append(error)

    running = Thread(target=serve, daemon=True)
    running.start()
    try:
        assert entered.wait(timeout=2)
        stop.set()
        assert profiles.drained.wait(timeout=2)
        running.join(timeout=2)
        assert not running.is_alive()
        assert listener.closed.is_set()
        assert failures == []
    finally:
        release.set()
        stop.set()
        running.join(timeout=5)


def test_incomplete_profile_drain_retains_listener_ownership() -> None:
    stop, entered, release = Event(), Event(), Event()
    listener = _Listener()
    profiles = _Profiles(release, RuntimeProfileDrainResult((), (), (uuid4(),), ()))
    server = _BlockedRequestServer(
        cast("RuntimeListener", listener),
        stop=stop,
        profiles=cast("RuntimeProfileHandler", profiles),
        entered=entered,
        release=release,
    )
    failures: list[BaseException] = []

    def serve() -> None:
        try:
            server.serve()
        except BaseException as error:
            failures.append(error)

    running = Thread(target=serve, daemon=True)
    running.start()
    try:
        assert entered.wait(timeout=2)
        stop.set()
        running.join(timeout=2)
        assert not running.is_alive()
        assert len(failures) == 1 and isinstance(failures[0], RuntimeShutdownIncompleteError)
        assert listener.listening.is_set() and not listener.closed.is_set()
    finally:
        release.set()
        stop.set()
        listener.close()
        running.join(timeout=5)


def test_pending_transport_request_retains_listener_ownership() -> None:
    stop, entered, release = Event(), Event(), Event()
    listener = _Listener()
    profiles = _ProfilesWithoutRelease(release)
    server = _BlockedRequestServer(
        cast("RuntimeListener", listener),
        stop=stop,
        profiles=cast("RuntimeProfileHandler", profiles),
        entered=entered,
        release=release,
    )
    server.DRAIN_SECONDS = 0.1
    failures: list[BaseException] = []

    def serve() -> None:
        try:
            server.serve()
        except BaseException as error:
            failures.append(error)

    running = Thread(target=serve, daemon=True)
    running.start()
    try:
        assert entered.wait(timeout=2)
        stop.set()
        running.join(timeout=2)
        assert not running.is_alive()
        assert len(failures) == 1 and isinstance(failures[0], RuntimeShutdownIncompleteError)
        assert profiles.drained.is_set() and not listener.closed.is_set()
    finally:
        release.set()
        stop.set()
        listener.close()
        running.join(timeout=5)

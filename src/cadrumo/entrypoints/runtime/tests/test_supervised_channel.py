"""Supervisor commands and announcements over real pipes, with an idle-only stop fence."""

from __future__ import annotations

import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
from pydantic import TypeAdapter

from cadrumo.adapters.local_runtime.boot_record import (
    RuntimeBootRecord,
    RuntimeBootRecordPublication,
    RuntimeBootRecordUnavailable,
    read_runtime_boot_record,
)
from cadrumo.application.runtime.contracts import RuntimeExitReason, RuntimeRefusalError
from cadrumo.core.logging import get_logger

from ..profile_connections import RuntimeProfileConnections
from ..profile_host import RuntimeProfileHost
from ..shutdown import RuntimeStop
from ..supervised_channel import SupervisedRuntime, SupervisorChannel, SupervisorStreams
from ..supervised_protocol import (
    RuntimeAnnouncement,
    RuntimeBusy,
    RuntimeHeartbeat,
    RuntimeReady,
    RuntimeRefused,
    RuntimeStopping,
    SupervisorLineRefusal,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_LOGGER = get_logger(__name__)
_ANNOUNCEMENTS: TypeAdapter[RuntimeAnnouncement] = TypeAdapter(RuntimeAnnouncement)


class _Serving:
    """Transport facts as a heartbeat reads them; the server owns its own tests."""

    def __init__(self) -> None:
        self.ready = Event()

    def accept_tick_age(self) -> float | None:
        return 0.25

    def open_connection_count(self) -> int:
        return 2


class _Pipes:
    """Two real pipes: supervisor-to-runtime commands and runtime-to-supervisor announcements."""

    def __init__(self) -> None:
        commands, supervisor_writes = os.pipe()
        supervisor_reads, announcements = os.pipe()
        self._open = {
            "commands": commands,
            "supervisor_writes": supervisor_writes,
            "supervisor_reads": supervisor_reads,
            "announcements": announcements,
        }
        self._reader = ThreadPoolExecutor(max_workers=1)
        self._buffer = b""

    def streams(self) -> SupervisorStreams:
        return SupervisorStreams(commands=self._open["commands"], announcements=self._open["announcements"])

    def send(self, line: bytes) -> None:
        os.write(self._open["supervisor_writes"], line)

    def _next_line(self) -> bytes:
        while b"\n" not in self._buffer:
            chunk = os.read(self._open["supervisor_reads"], 4096)
            if not chunk:
                return b""
            self._buffer += chunk
        line, self._buffer = self._buffer.split(b"\n", 1)
        return line + b"\n"

    def next_line(self) -> bytes:
        return self._reader.submit(self._next_line).result(timeout=5)

    def receive(self) -> RuntimeAnnouncement:
        line = self.next_line()
        assert line.endswith(b"\n"), line
        return _ANNOUNCEMENTS.validate_json(line[:-1], strict=True)

    def close(self, name: str) -> None:
        descriptor = self._open.pop(name, None)
        if descriptor is not None:
            os.close(descriptor)

    def close_all(self, gone: Event | None) -> None:
        # End the runtime's command reader before its descriptor is released.
        self.close("supervisor_writes")
        if gone is not None:
            assert gone.wait(5)
        for name in tuple(self._open):
            self.close(name)
        self._reader.shutdown(wait=False)


@contextmanager
def _channel(stop: RuntimeStop | None = None) -> Iterator[tuple[_Pipes, SupervisorChannel]]:
    pipes = _Pipes()
    channel = SupervisorChannel(pipes.streams(), logger=_LOGGER)
    try:
        yield pipes, channel
    finally:
        channel.close(timeout=5)
        if stop is not None:
            # Release the stop announcer of a runtime that never stopped.
            stop.set()
        pipes.close_all(channel.supervisor_gone if channel._writer.ident is not None else None)


def _profiles(root: Path, stop: RuntimeStop) -> RuntimeProfileConnections:
    return RuntimeProfileConnections(storage_root=root, storage_identity="a" * 64, runtime_boot_id=uuid4(), stop=stop)


def _ready() -> RuntimeReady:
    return RuntimeReady(boot_id=uuid4(), pid=os.getpid(), version="test", storage_identity="b" * 64, admission="native")


def _publication(root: Path, ready: RuntimeReady) -> RuntimeBootRecordPublication:
    record = RuntimeBootRecord(
        boot_id=ready.boot_id,
        pid=ready.pid,
        process_created=1,
        version=ready.version,
        package_directory=None,
        admission=ready.admission,
    )
    return RuntimeBootRecordPublication(storage_root=root, record=record)


def _host(count: int | None) -> RuntimeProfileHost:
    return cast(RuntimeProfileHost, SimpleNamespace(owner=SimpleNamespace(in_flight_operation_count=lambda **_: count)))


@pytest.mark.parametrize("count", [0, 1, 3, None])
def test_idle_probe_observes_operations_not_host_count(tmp_path: Path, count: int | None) -> None:
    stop = RuntimeStop()
    profiles = _profiles(tmp_path, stop)
    profiles._profiles[uuid4()] = _host(count)
    assert profiles.in_flight_operation_count(timeout=1) == count
    assert profiles.stop_if_idle(RuntimeExitReason.SUPERVISOR_STOP, timeout=1) is (count == 0)
    assert stop.is_set() is (count == 0)
    if count != 0:
        assert profiles._admitting()


def test_idle_fence_retains_requests_that_have_not_reached_the_worker(tmp_path: Path) -> None:
    stop = RuntimeStop()
    profiles = _profiles(tmp_path, stop)
    with profiles.operation_admission():
        assert not profiles.stop_if_idle(RuntimeExitReason.SUPERVISOR_STOP, timeout=1)
        assert profiles._admitting()
    assert profiles.stop_if_idle(RuntimeExitReason.SUPERVISOR_STOP, timeout=1)


def test_idle_fence_rejects_new_requests_without_revoking_existing_authority(tmp_path: Path) -> None:
    stop = RuntimeStop()
    profiles = _profiles(tmp_path, stop)

    def observe(*, deadline: float) -> int:
        assert profiles._private_work_available()
        with pytest.raises(RuntimeRefusalError), profiles.operation_admission():
            raise AssertionError("new request crossed the idle fence")
        return 1

    profiles._profiles[uuid4()] = cast(
        RuntimeProfileHost, SimpleNamespace(owner=SimpleNamespace(in_flight_operation_count=observe))
    )
    assert not profiles.stop_if_idle(RuntimeExitReason.SUPERVISOR_STOP, timeout=1)
    assert profiles._admitting() and profiles._private_work_available()


def test_heartbeat_sums_operations_across_workers(tmp_path: Path) -> None:
    profiles = _profiles(tmp_path, RuntimeStop())
    profiles._profiles[uuid4()] = _host(2)
    profiles._profiles[uuid4()] = _host(3)
    assert profiles.in_flight_operation_count(timeout=1) == 5
    profiles._profiles[uuid4()] = _host(None)
    assert profiles.in_flight_operation_count(timeout=1) is None


def test_idle_fence_stops_only_without_operations(tmp_path: Path) -> None:
    stop = RuntimeStop()
    profiles = _profiles(tmp_path, stop)
    profile_id = uuid4()
    # A hosted worker with unknown activity cannot prove idle.
    profiles._profiles[profile_id] = _host(None)
    assert profile_id in profiles._profiles
    assert not profiles.stop_if_idle(RuntimeExitReason.SUPERVISOR_STOP, timeout=1)
    assert not stop.is_set() and profiles._admitting()
    profiles._profiles.pop(profile_id)
    assert not profiles._profiles
    # An accepted bootstrap transaction can own work without any profile worker.
    profiles._custody_mutations.add(profile_id)
    assert not profiles.stop_if_idle(RuntimeExitReason.SUPERVISOR_STOP, timeout=1)
    assert not stop.is_set()
    profiles._custody_mutations.remove(profile_id)
    assert profiles.stop_if_idle(RuntimeExitReason.SUPERVISOR_STOP, timeout=1)
    assert stop.reason is RuntimeExitReason.SUPERVISOR_STOP and not profiles._admitting()


def test_idle_fence_counts_a_busy_admission_guard_as_possible_work(tmp_path: Path) -> None:
    stop = RuntimeStop()
    profiles = _profiles(tmp_path, stop)
    held, release = Event(), Event()

    def hold_admission() -> None:
        with profiles._guard:
            held.set()
            release.wait(5)

    with ThreadPoolExecutor(max_workers=1) as pool:
        holder = pool.submit(hold_admission)
        assert held.wait(5)
        try:
            assert not profiles.stop_if_idle(RuntimeExitReason.SUPERVISOR_STOP, timeout=0.1)
        finally:
            release.set()
        holder.result(timeout=5)
    assert not stop.is_set()


def test_supervisor_commands_drive_ready_heartbeat_busy_and_stop(tmp_path: Path) -> None:
    stop = RuntimeStop()
    profiles = _profiles(tmp_path, stop)
    with _channel(stop) as (pipes, channel):
        runtime = SupervisedRuntime(stop, channel)
        runtime.start()
        serving = _Serving()
        ready = _ready()
        runtime.attach(
            serving, profiles=profiles, ready=ready, publish_boot_record=_publication(tmp_path, ready).publish
        )
        assert read_runtime_boot_record(storage_root=tmp_path) is RuntimeBootRecordUnavailable.ABSENT
        serving.ready.set()
        assert pipes.receive() == ready
        # The record was published before the line that announced readiness.
        published = read_runtime_boot_record(storage_root=tmp_path)
        assert isinstance(published, RuntimeBootRecord) and published.boot_id == ready.boot_id

        profile_id = uuid4()
        profiles._profiles[profile_id] = _host(2)
        pipes.send(b'{"type":"stop-if-idle"}\n')
        assert pipes.receive() == RuntimeBusy()
        assert not stop.is_set()
        pipes.send(b'{"type":"ping","seq":3}\n')
        assert pipes.receive() == RuntimeHeartbeat(seq=3, tick_age_ms=250, frontends=2, in_flight_operations=2)
        pipes.send(b'{"type":"ping","seq":3,"tick":1}\n')
        assert pipes.receive() == RuntimeRefused(code=SupervisorLineRefusal.MALFORMED)

        profiles._profiles.pop(profile_id)
        pipes.send(b'{"type":"stop-if-idle"}\n')
        assert pipes.receive() == RuntimeStopping(reason=RuntimeExitReason.SUPERVISOR_STOP)
        assert stop.reason is RuntimeExitReason.SUPERVISOR_STOP
        # The final exit reason does not repeat a stop that was already announced.
        runtime.finish(int(RuntimeExitReason.DRAIN_WATCHDOG))
        pipes.close("announcements")
        assert pipes.next_line() == b""


def test_an_unpublished_boot_record_ends_the_runtime_without_ready(tmp_path: Path) -> None:
    stop = RuntimeStop()
    profiles = _profiles(tmp_path, stop)
    with _channel(stop) as (pipes, channel):
        runtime = SupervisedRuntime(stop, channel)
        runtime.start()
        serving = _Serving()
        ready = _ready()
        # A storage root that does not exist cannot hold the record.
        publication = _publication(tmp_path / "missing", ready)
        runtime.attach(serving, profiles=profiles, ready=ready, publish_boot_record=publication.publish)
        serving.ready.set()
        assert pipes.receive() == RuntimeStopping(reason=RuntimeExitReason.UNEXPECTED_FAILURE)
        assert stop.reason is RuntimeExitReason.UNEXPECTED_FAILURE
        runtime.finish(int(RuntimeExitReason.UNEXPECTED_FAILURE))
        pipes.close("announcements")
        assert pipes.next_line() == b""


def test_a_withdrawn_boot_record_is_never_published_or_announced(tmp_path: Path) -> None:
    stop = RuntimeStop()
    profiles = _profiles(tmp_path, stop)
    with _channel(stop) as (pipes, channel):
        runtime = SupervisedRuntime(stop, channel)
        runtime.start()
        serving = _Serving()
        ready = _ready()
        publication = _publication(tmp_path, ready)
        publication.withdraw()
        attempted = Event()

        def publish() -> bool:
            try:
                return publication.publish()
            finally:
                attempted.set()

        runtime.attach(serving, profiles=profiles, ready=ready, publish_boot_record=publish)
        serving.ready.set()
        assert attempted.wait(5)
        stop.request(RuntimeExitReason.SUPERVISOR_STOP)
        assert pipes.receive() == RuntimeStopping(reason=RuntimeExitReason.SUPERVISOR_STOP)
        assert read_runtime_boot_record(storage_root=tmp_path) is RuntimeBootRecordUnavailable.ABSENT


def test_heartbeat_before_serving_has_no_tick_and_session_end_names_its_reason() -> None:
    stop = RuntimeStop()
    with _channel(stop) as (pipes, channel):
        SupervisedRuntime(stop, channel).start()
        pipes.send(b'{"type":"ping","seq":0}\n')
        assert pipes.receive() == RuntimeHeartbeat(seq=0, tick_age_ms=None, frontends=0, in_flight_operations=0)
        pipes.send(b'{"type":"session-end"}\n')
        assert pipes.receive() == RuntimeStopping(reason=RuntimeExitReason.SESSION_END_SETTLE)
        assert stop.reason is RuntimeExitReason.SESSION_END_SETTLE


def test_a_stop_without_reason_takes_the_final_exit_reason_once() -> None:
    stop = RuntimeStop()
    with _channel(stop) as (pipes, channel):
        runtime = SupervisedRuntime(stop, channel)
        runtime.start()
        stop.set()
        runtime.finish(int(RuntimeExitReason.UNEXPECTED_FAILURE))
        assert pipes.receive() == RuntimeStopping(reason=RuntimeExitReason.UNEXPECTED_FAILURE)
        pipes.close("announcements")
        assert pipes.next_line() == b""


def test_end_of_input_marks_the_supervisor_gone_without_stopping() -> None:
    stop = RuntimeStop()
    with _channel(stop) as (pipes, channel):
        SupervisedRuntime(stop, channel).start()
        pipes.close("supervisor_writes")
        assert channel.supervisor_gone.wait(5)
        assert not stop.is_set()


def test_a_broken_announcement_pipe_disables_the_channel_without_raising() -> None:
    with _channel() as (pipes, channel):
        channel.start(lambda _command: None)
        pipes.close("supervisor_reads")
        channel.announce(RuntimeBusy())
        channel.close(timeout=5)
        assert not channel._enabled.is_set()
        # Later announcements are dropped rather than queued or raised.
        channel.announce(RuntimeBusy())
        assert channel._queue.empty()


def test_a_launch_without_announcement_stream_drops_announcements() -> None:
    commands, supervisor_writes = os.pipe()
    channel = SupervisorChannel(SupervisorStreams(commands=commands, announcements=None), logger=_LOGGER)
    try:
        channel.start(lambda _command: None)
        channel.announce(RuntimeBusy())
        assert channel._queue.empty()
        channel.close(timeout=5)
    finally:
        os.close(supervisor_writes)
        assert channel.supervisor_gone.wait(5)
        os.close(commands)

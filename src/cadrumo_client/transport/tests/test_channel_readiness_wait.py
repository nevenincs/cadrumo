"""An idle channel blocks on input and a wake together, and loses nothing it read while waiting."""

from __future__ import annotations

import sys
import time
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event, Thread
from uuid import uuid4

import pytest

from ...contracts.contracts import ChannelWake, ClientHello, Peer, RefusalCode, RefusalError, ServerHello
from ...contracts.session_events import SignInChanged
from ..frame_io import DOCUMENT_FRAME_KIND, read_frame_payload, write_document, write_session_event
from ..framing import VerifiedConnection
from ..native_wake import NativeWake
from ..windows import WindowsEndpoint
from ..windows_channel import WindowsChannel

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_inbound_adapter,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires the native Windows transport"),
]

_IDENTITY = "a" * 64


@pytest.fixture
def pair(tmp_path: Path) -> Generator[tuple[WindowsChannel, WindowsChannel]]:
    """A runtime-side and a client-side channel over one real named pipe."""
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsEndpoint(storage_root=root)
    endpoint.listen()
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            accepted = pool.submit(endpoint.accept, timeout=5)
            client = endpoint.connect(timeout=5)
            server = accepted.result(timeout=5)
        try:
            yield server, client
        finally:
            client.close()
            server.close()
    finally:
        endpoint.close()


class _Wait:
    """One readiness wait on its own thread, as a connection's loop runs it."""

    def __init__(self, channel: WindowsChannel, *wakes: ChannelWake) -> None:
        self.done = Event()
        self.result: bool | BaseException | None = None
        Thread(target=self._run, args=(channel, wakes), daemon=True).start()

    def _run(self, channel: WindowsChannel, wakes: tuple[NativeWake, ...]) -> None:
        try:
            self.result = channel.wait_readable(*wakes)
        except BaseException as error:
            self.result = error
        finally:
            self.done.set()


class _Counted:
    """The real channel, counting how often its reader starts a readiness wait."""

    def __init__(self, channel: WindowsChannel) -> None:
        self.channel = channel
        self.waits = 0

    @property
    def peer(self) -> Peer:
        return self.channel.peer

    def read_exact(self, count: int, *, deadline: float) -> bytes:
        return self.channel.read_exact(count, deadline=deadline)

    def read_ready(self) -> bool:
        return self.channel.read_ready()

    def wait_readable(self, *wakes: ChannelWake) -> bool:
        self.waits += 1
        return self.channel.wait_readable(*wakes)

    def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
        self.channel.write_all(payload, deadline=deadline)

    def close(self) -> None:
        self.channel.close()


def test_a_wake_ends_an_idle_wait_and_later_input_is_read_whole(pair: tuple[WindowsChannel, WindowsChannel]) -> None:
    server, client = pair
    wake = NativeWake()
    waiting = _Wait(server, wake)
    assert not waiting.done.wait(0.3), "an idle wait ends only for input or a wake"
    wake.set()
    assert waiting.done.wait(2)
    assert waiting.result is False
    wake.clear()
    client.write_all(b"abc", deadline=time.monotonic() + 5)
    assert server.wait_readable(wake) is True
    assert server.read_exact(3, deadline=time.monotonic() + 5) == b"abc"
    assert not server.read_ready()


def test_input_ends_the_wait_and_the_byte_it_read_comes_first(pair: tuple[WindowsChannel, WindowsChannel]) -> None:
    server, client = pair
    waiting = _Wait(server, NativeWake())
    assert not waiting.done.wait(0.2)
    client.write_all(b"xyz", deadline=time.monotonic() + 5)
    assert waiting.done.wait(2)
    assert waiting.result is True
    assert server.read_ready()
    assert server.read_exact(1, deadline=time.monotonic() + 5) == b"x"
    assert server.read_exact(2, deadline=time.monotonic() + 5) == b"yz"
    assert not server.read_ready()


def test_waiting_input_wins_over_a_set_wake(pair: tuple[WindowsChannel, WindowsChannel]) -> None:
    server, client = pair
    wake = NativeWake()
    wake.set()
    assert server.wait_readable(wake) is False
    client.write_all(b"q", deadline=time.monotonic() + 5)
    deadline = time.monotonic() + 5
    while not server.read_ready():
        assert time.monotonic() < deadline
        time.sleep(0.01)
    assert server.wait_readable(wake) is True
    assert server.read_exact(1, deadline=time.monotonic() + 5) == b"q"


def test_a_closed_peer_ends_the_wait_as_a_closed_connection(pair: tuple[WindowsChannel, WindowsChannel]) -> None:
    server, client = pair
    waiting = _Wait(server, NativeWake())
    assert not waiting.done.wait(0.2)
    client.close()
    assert waiting.done.wait(2)
    result = waiting.result
    with pytest.raises(RefusalError) as caught:
        # The wait refuses at once, or reports input that the read then refuses.
        if isinstance(result, BaseException):
            raise result
        assert result is True
        server.read_exact(1, deadline=time.monotonic() + 5)
    assert caught.value.reason is RefusalCode.CONNECTION_CLOSED


def test_an_idle_subscription_waits_once_and_an_exchange_claims_the_connection_at_once(
    pair: tuple[WindowsChannel, WindowsChannel],
) -> None:
    server, client = pair
    counted = _Counted(client)
    boot = uuid4()
    with ThreadPoolExecutor(max_workers=1) as pool:
        connecting = pool.submit(
            VerifiedConnection,
            counted,
            expected=ClientHello(product_version="test", storage_identity=_IDENTITY),
            deadline=time.monotonic() + 5,
        )
        read_frame_payload(server, kind=DOCUMENT_FRAME_KIND, deadline=time.monotonic() + 5)
        write_document(
            server,
            ServerHello(product_version="test", storage_identity=_IDENTITY, boot_id=boot),
            deadline=time.monotonic() + 5,
        )
        connection = connecting.result(timeout=5)
    try:
        heard = Event()
        connection.subscribe_session_events(lambda _event: heard.set())
        time.sleep(0.3)
        assert counted.waits == 1, "an idle subscription is one blocked wait, not a timer"
        connection_id = uuid4()
        write_session_event(
            server, SignInChanged(runtime_boot_id=boot, connection_id=connection_id), deadline=time.monotonic() + 5
        )
        assert heard.wait(2)
        started = time.monotonic()
        assert connection.connection_id == connection_id
        assert time.monotonic() - started < 1, "a claim wakes the idle wait instead of waiting out a timer"
        time.sleep(0.3)
        # The event's read, the claim's wake, and the wait that followed it.
        assert counted.waits == 3
    finally:
        connection.close()

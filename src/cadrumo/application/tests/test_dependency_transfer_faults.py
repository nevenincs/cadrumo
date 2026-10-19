"""Transfer faults produced by real local HTTP and TLS servers.

Setup downloads gigabytes over networks that reset, stall, throttle, cut a body
short or crawl. The fault server below produces each of those faults on a real
loopback socket, scripted per request, and records what every request asked
for, so a retry or resume claim is checked against what actually went over the
wire rather than against a substituted client.

The first group of tests proves each fault is real: an unmodified HTTP client
observes exactly the failure the fault names. A transfer test that ran against
a fault which never materialised would pass by testing nothing.
"""

from __future__ import annotations

import asyncio
import errno
import hashlib
import shutil
import socket
import ssl
import struct
import threading
import time
from collections.abc import AsyncGenerator, Awaitable, Callable, Generator, Iterator, Sequence
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ipaddress import IPv4Address
from pathlib import Path
from typing import Final, override

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

from ..dependency_contracts import DependencySetupStep
from ..dependency_transfer import (
    DEPENDENCY_RETRY_POLICY,
    DependencyRetryPolicy,
    DependencyTransferError,
    require_free_space,
    run_with_retry,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

PAYLOAD: Final = bytes(range(256)) * 256
"""A 64 KiB body whose every byte position is distinguishable, so a spliced or restarted body shows."""

PAYLOAD_DIGEST: Final = hashlib.sha256(PAYLOAD).hexdigest()
_STALL_CEILING_S: Final = 30.0
_CLIENT_TIMEOUT_S: Final = 0.5


class Fault(StrEnum):
    """What the server does with one request."""

    SERVE = "serve"
    """Answer in full, or from the requested offset when the request carries a byte range."""

    RESET = "reset"
    """Abort the connection with a TCP reset before any response."""

    STALL = "stall"
    """Accept the request and never answer until the server stops."""

    SERVER_ERROR = "server_error"
    """Answer 503."""

    TOO_MANY_REQUESTS = "too_many_requests"
    """Answer 429 with a one-second ``Retry-After``."""

    FORBIDDEN = "forbidden"
    """Answer 403, which a network filter or proxy also answers."""

    NOT_FOUND = "not_found"
    """Answer 404, a permanent client error."""

    TRUNCATE = "truncate"
    """Promise the full length, send half the body, then close."""

    SLOW = "slow"
    """Send the full body in small chunks with a pause between them."""


@dataclass(frozen=True, slots=True)
class ObservedRequest:
    """One request as the server received it."""

    method: str
    path: str
    byte_range: str | None
    fault: Fault


@dataclass(slots=True)
class FaultScript:
    """The faults to apply to successive requests; once spent, every request is served."""

    faults: list[Fault]
    slow_chunk_bytes: int = 4096
    slow_pause_s: float = 0.02
    observed: list[ObservedRequest] = field(default_factory=list)
    stopping: threading.Event = field(default_factory=threading.Event)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def next_fault(self, method: str, path: str, byte_range: str | None) -> Fault:
        """Take the next scripted fault and record the request it applies to."""
        with self._lock:
            fault = self.faults.pop(0) if self.faults else Fault.SERVE
            self.observed.append(ObservedRequest(method=method, path=path, byte_range=byte_range, fault=fault))
            return fault


def _requested_offset(byte_range: str | None) -> int:
    if byte_range is None:
        return 0
    unit, _, spec = byte_range.partition("=")
    start, _, end = spec.partition("-")
    if unit.strip() != "bytes" or end.strip() or not start.strip().isdigit():
        raise ValueError(f"unsupported byte range {byte_range!r}")
    return int(start)


class _FaultHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    @override
    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:
        self._answer(with_body=True)

    def do_HEAD(self) -> None:
        self._answer(with_body=False)

    def _script(self) -> FaultScript:
        server = self.server
        assert isinstance(server, _FaultHttpServer)
        return server.script

    def _answer(self, *, with_body: bool) -> None:
        byte_range = self.headers.get("Range")
        script = self._script()
        fault = script.next_fault(self.command, self.path, byte_range)
        match fault:
            case Fault.RESET:
                self._reset()
            case Fault.STALL:
                script.stopping.wait(_STALL_CEILING_S)
                self.close_connection = True
            case Fault.SERVER_ERROR:
                self._status_only(503)
            case Fault.TOO_MANY_REQUESTS:
                self._status_only(429, retry_after="1")
            case Fault.FORBIDDEN:
                self._status_only(403)
            case Fault.NOT_FOUND:
                self._status_only(404)
            case Fault.TRUNCATE:
                self._body(PAYLOAD, status=200, with_body=with_body, send=PAYLOAD[: len(PAYLOAD) // 2])
                self.close_connection = True
            case Fault.SLOW:
                self._body(PAYLOAD, status=200, with_body=with_body, slow=True)
            case Fault.SERVE:
                offset = _requested_offset(byte_range)
                remainder = PAYLOAD[offset:]
                status = 206 if byte_range is not None else 200
                extra = {"Content-Range": f"bytes {offset}-{len(PAYLOAD) - 1}/{len(PAYLOAD)}"} if status == 206 else {}
                self._body(remainder, status=status, with_body=with_body, extra=extra)

    def _reset(self) -> None:
        self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
        self.connection.close()
        self.close_connection = True

    def _status_only(self, status: int, *, retry_after: str | None = None) -> None:
        self.send_response(status)
        if retry_after is not None:
            self.send_header("Retry-After", retry_after)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _body(
        self,
        body: bytes,
        *,
        status: int,
        with_body: bool,
        send: bytes | None = None,
        slow: bool = False,
        extra: dict[str, str] | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Accept-Ranges", "bytes")
        for name, value in (extra or {}).items():
            self.send_header(name, value)
        self.end_headers()
        if not with_body:
            return
        outgoing = body if send is None else send
        if not slow:
            self.wfile.write(outgoing)
            return
        script = self._script()
        for start in range(0, len(outgoing), script.slow_chunk_bytes):
            self.wfile.write(outgoing[start : start + script.slow_chunk_bytes])
            self.wfile.flush()
            if script.stopping.wait(script.slow_pause_s):
                return

    @override
    def finish(self) -> None:
        try:
            super().finish()
        except OSError:
            # A reset or a client that gave up leaves nothing to flush to.
            return


class _FaultHttpServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, script: FaultScript, tls: ssl.SSLContext | None) -> None:
        super().__init__(("127.0.0.1", 0), _FaultHandler)
        self.script = script
        self._tls = tls

    @override
    def get_request(self) -> tuple[socket.socket, object]:
        connection, address = super().get_request()
        if self._tls is None:
            return connection, address
        return self._tls.wrap_socket(connection, server_side=True), address

    @override
    def handle_error(self, request: object, client_address: object) -> None:
        # Faults abort connections on purpose; their errors are the point, not noise.
        return


@dataclass(frozen=True, slots=True)
class RunningFaultServer:
    """A started fault server: where to reach it, which certificate to trust, and what it saw."""

    url: str
    script: FaultScript
    trust_file: Path | None

    @property
    def observed(self) -> Sequence[ObservedRequest]:
        """Every request the server received, in arrival order."""
        return tuple(self.script.observed)


def _self_signed_tls(directory: Path) -> tuple[ssl.SSLContext, Path]:
    """Return a server context for ``127.0.0.1`` and the certificate a client must trust to reach it."""
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "cadrumo-dependency-transfer-faults")])
    now = datetime.now(UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.SubjectAlternativeName([x509.IPAddress(IPv4Address("127.0.0.1")), x509.DNSName("localhost")]),
            critical=False,
        )
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .sign(key, hashes.SHA256())
    )
    certificate_path = directory / "fault-server.crt"
    key_path = directory / "fault-server.key"
    certificate_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    )
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certificate_path, key_path)
    return context, certificate_path


@contextmanager
def fault_server(faults: Sequence[Fault], *, tls_directory: Path | None = None) -> Generator[RunningFaultServer]:
    """Serve :data:`PAYLOAD` on loopback, applying ``faults`` to successive requests.

    With ``tls_directory`` the server speaks TLS over a throwaway self-signed
    certificate written there; a client reaches it only by trusting that file.
    """
    script = FaultScript(faults=list(faults))
    tls, trust_file = _self_signed_tls(tls_directory) if tls_directory is not None else (None, None)
    server = _FaultHttpServer(script, tls)
    thread = threading.Thread(
        target=server.serve_forever,
        kwargs={"poll_interval": 0.05},
        name="dependency-fault-server",
        daemon=True,
    )
    thread.start()
    scheme = "https" if tls is not None else "http"
    host, port = server.server_address[:2]
    try:
        yield RunningFaultServer(url=f"{scheme}://{host!s}:{port}/payload", script=script, trust_file=trust_file)
    finally:
        script.stopping.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _client(server: RunningFaultServer, *, timeout_s: float = _CLIENT_TIMEOUT_S) -> httpx.Client:
    verify: ssl.SSLContext | bool = True
    if server.trust_file is not None:
        verify = ssl.create_default_context(cafile=str(server.trust_file))
    return httpx.Client(timeout=timeout_s, verify=verify)


# --------------------------------------------------------------------------
# Each fault is real on the wire
# --------------------------------------------------------------------------


def test_served_payload_arrives_whole_over_plain_http() -> None:
    """The baseline: an unfaulted request returns the whole payload with its length."""
    with fault_server([]) as server, _client(server) as client:
        response = client.get(server.url)
    assert response.status_code == 200
    assert hashlib.sha256(response.content).hexdigest() == PAYLOAD_DIGEST
    assert [request.fault for request in server.observed] == [Fault.SERVE]


def test_reset_aborts_the_connection_before_any_response() -> None:
    """A reset reaches the client as a transport error, never as an HTTP status."""
    with fault_server([Fault.RESET]) as server, _client(server) as client, pytest.raises(httpx.TransportError):
        client.get(server.url)


def test_stall_exhausts_the_client_read_timeout() -> None:
    """A stalled server answers nothing, so the client's own read deadline is what ends the wait."""
    with fault_server([Fault.STALL]) as server, _client(server) as client:
        started = time.monotonic()
        with pytest.raises(httpx.ReadTimeout):
            client.get(server.url)
        elapsed = time.monotonic() - started
    assert _CLIENT_TIMEOUT_S <= elapsed < _STALL_CEILING_S


@pytest.mark.parametrize(
    ("fault", "status"),
    [(Fault.SERVER_ERROR, 503), (Fault.TOO_MANY_REQUESTS, 429), (Fault.FORBIDDEN, 403), (Fault.NOT_FOUND, 404)],
)
def test_status_faults_answer_their_status_with_no_body(fault: Fault, status: int) -> None:
    """Each status fault answers exactly its status; throttling also says when to come back."""
    with fault_server([fault]) as server, _client(server) as client:
        response = client.get(server.url)
    assert response.status_code == status
    assert response.content == b""
    assert response.headers.get("Retry-After") == ("1" if fault is Fault.TOO_MANY_REQUESTS else None)


def test_truncation_promises_the_full_length_and_delivers_half() -> None:
    """A cut-short body is a protocol error on read, after half the bytes have already arrived."""
    received = bytearray()
    with (
        fault_server([Fault.TRUNCATE]) as server,
        _client(server) as client,
        pytest.raises(httpx.RemoteProtocolError),
        client.stream("GET", server.url) as response,
    ):
        assert response.headers["Content-Length"] == str(len(PAYLOAD))
        for chunk in response.iter_bytes():
            received.extend(chunk)
    assert bytes(received) == PAYLOAD[: len(PAYLOAD) // 2]


def test_slow_transfer_completes_but_only_across_many_pauses() -> None:
    """A crawling transfer is not a failure: the whole body arrives, just slowly and in pieces."""
    with fault_server([Fault.SLOW]) as server, _client(server) as client:
        started = time.monotonic()
        chunks: list[bytes] = []
        with client.stream("GET", server.url) as response:
            chunks.extend(response.iter_bytes())
        elapsed = time.monotonic() - started
    pauses = len(PAYLOAD) // server.script.slow_chunk_bytes - 1
    assert hashlib.sha256(b"".join(chunks)).hexdigest() == PAYLOAD_DIGEST
    assert elapsed >= pauses * server.script.slow_pause_s


def test_interrupted_transfer_resumes_from_its_offset_rather_than_restarting() -> None:
    """After a cut, a ranged request receives exactly the missing bytes, and the server saw the offset."""
    received = bytearray()
    with fault_server([Fault.TRUNCATE]) as server, _client(server) as client:
        with pytest.raises(httpx.RemoteProtocolError), client.stream("GET", server.url) as response:
            for chunk in response.iter_bytes():
                received.extend(chunk)
        resumed = client.get(server.url, headers={"Range": f"bytes={len(received)}-"})
    assert resumed.status_code == 206
    received.extend(resumed.content)
    assert hashlib.sha256(received).hexdigest() == PAYLOAD_DIGEST
    assert [request.byte_range for request in server.observed] == [None, f"bytes={len(PAYLOAD) // 2}-"]


def test_head_requests_take_their_fault_like_a_download_does() -> None:
    """A reachability check meets the same faults as the transfer it precedes."""
    with fault_server([Fault.FORBIDDEN, Fault.SERVE]) as server, _client(server) as client:
        refused = client.head(server.url)
        reachable = client.head(server.url)
    assert (refused.status_code, reachable.status_code) == (403, 200)
    assert reachable.headers["Content-Length"] == str(len(PAYLOAD))
    assert [request.method for request in server.observed] == ["HEAD", "HEAD"]


def test_tls_server_is_reached_only_by_a_client_that_trusts_its_certificate(tmp_path: Path) -> None:
    """The TLS fault server serves a trusting client and fails a client using the default trust store."""
    with fault_server([], tls_directory=tmp_path) as server:
        with _client(server) as trusting:
            response = trusting.get(server.url)
        with httpx.Client(timeout=_CLIENT_TIMEOUT_S) as default_trust, pytest.raises(httpx.ConnectError) as refused:
            default_trust.get(server.url)
    assert hashlib.sha256(response.content).hexdigest() == PAYLOAD_DIGEST
    assert any(isinstance(cause, ssl.SSLCertVerificationError) for cause in _causes(refused.value))


def _causes(error: BaseException) -> Iterator[BaseException]:
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = current.__cause__ or current.__context__


def test_tls_faults_apply_after_the_handshake(tmp_path: Path) -> None:
    """Over TLS, a reset still surfaces as a transport error and throttling still as its status."""
    with fault_server([Fault.RESET, Fault.TOO_MANY_REQUESTS], tls_directory=tmp_path) as server:
        with _client(server) as client, pytest.raises(httpx.TransportError):
            client.get(server.url)
        with _client(server) as client:
            throttled = client.get(server.url)
    assert throttled.status_code == 429


# --------------------------------------------------------------------------
# The transfer owner's retry, classification, free-space and resume rules
# --------------------------------------------------------------------------


class _RecordedEvents:
    """The setup event port, recording what the retry runner reports."""

    def __init__(self, *, cancel_after_retries: int | None = None) -> None:
        self.retries: list[tuple[int, float]] = []
        self._cancel_after = cancel_after_retries

    async def step(self, step: DependencySetupStep) -> None:
        del step

    async def transferred(self, *, completed: int, total: int | None) -> None:
        del completed, total

    async def retrying(self, *, attempt: int, delay_s: float) -> None:
        self.retries.append((attempt, delay_s))

    @property
    def cancellation_requested(self) -> bool:
        return self._cancel_after is not None and len(self.retries) >= self._cancel_after

    @asynccontextmanager
    async def irreversible(self) -> AsyncGenerator[None]:
        yield


class _VirtualClock:
    """Time the retry runner waits on, advanced by its own sleeps rather than by the wall."""

    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds

    def monotonic(self) -> float:
        return self.now


def _download_attempt(server: RunningFaultServer, destination: Path) -> Callable[[], Awaitable[int]]:
    """One real download attempt that continues from whatever earlier attempts left on disk."""

    async def attempt() -> int:
        offset = destination.stat().st_size if destination.exists() else 0
        headers = {"Range": f"bytes={offset}-"} if offset else {}
        verify: ssl.SSLContext | bool = True
        if server.trust_file is not None:
            verify = ssl.create_default_context(cafile=str(server.trust_file))
        async with (
            httpx.AsyncClient(timeout=_CLIENT_TIMEOUT_S, verify=verify) as client,
            client.stream("GET", server.url, headers=headers) as response,
        ):
            response.raise_for_status()
            with destination.open("ab") as sink:
                async for chunk in response.aiter_bytes():
                    sink.write(chunk)
        return destination.stat().st_size

    return attempt


async def _retried(
    server: RunningFaultServer,
    destination: Path,
    *,
    policy: DependencyRetryPolicy = DEPENDENCY_RETRY_POLICY,
    events: _RecordedEvents | None = None,
    clock: _VirtualClock | None = None,
) -> int:
    ticking = clock or _VirtualClock()
    return await run_with_retry(
        _download_attempt(server, destination),
        events=events or _RecordedEvents(),
        policy=policy,
        sleep=ticking.sleep,
        monotonic=ticking.monotonic,
        jitter=lambda: 0.0,
    )


def test_the_shipped_policy_is_the_decided_budget() -> None:
    """Backoff starts at 2 s, doubles to at most 60 s, for at most 6 attempts within 15 minutes."""
    assert (
        DependencyRetryPolicy(initial_delay_s=2.0, max_delay_s=60.0, max_attempts=6, window_s=900.0)
        == DEPENDENCY_RETRY_POLICY
    )
    ceilings = [DEPENDENCY_RETRY_POLICY.delay_s(retry, jitter=1.0) for retry in range(1, 8)]
    assert ceilings == [2.0, 4.0, 8.0, 16.0, 32.0, 60.0, 60.0]
    assert DEPENDENCY_RETRY_POLICY.delay_s(3, jitter=0.0) == 4.0


@pytest.mark.parametrize("transient", [Fault.RESET, Fault.SERVER_ERROR, Fault.TOO_MANY_REQUESTS, Fault.STALL])
def test_a_transient_fault_is_retried_with_backoff_until_the_transfer_succeeds(
    tmp_path: Path, transient: Fault
) -> None:
    """Two transient faults cost two reported retries at the backoff schedule, then the payload arrives whole."""
    destination = tmp_path / "archive.bin"
    events, clock = _RecordedEvents(), _VirtualClock()
    with fault_server([transient, transient]) as server:
        size = asyncio.run(_retried(server, destination, events=events, clock=clock))
        observed = [request.fault for request in server.observed]
    assert size == len(PAYLOAD)
    assert hashlib.sha256(destination.read_bytes()).hexdigest() == PAYLOAD_DIGEST
    assert observed == [transient, transient, Fault.SERVE]
    assert events.retries == [(2, 1.0), (3, 2.0)]
    assert sum(clock.slept) == pytest.approx(3.0)


@pytest.mark.parametrize(
    ("permanent", "category"),
    [
        (Fault.FORBIDDEN, DependencyFailureCategory.BLOCKED_BY_NETWORK),
        (Fault.NOT_FOUND, DependencyFailureCategory.UNEXPECTED),
    ],
)
def test_a_permanent_fault_is_final_on_the_first_attempt(
    tmp_path: Path, permanent: Fault, category: DependencyFailureCategory
) -> None:
    """A refusal no retry can change is reported at once, with exactly one request on the wire."""
    events = _RecordedEvents()
    with fault_server([permanent, permanent]) as server:
        with pytest.raises(DependencyTransferError) as failure:
            asyncio.run(_retried(server, tmp_path / "archive.bin", events=events))
        requests = len(server.observed)
    assert failure.value.category is category
    assert failure.value.transient is False
    assert failure.value.facts["attempts"] == 1
    assert requests == 1
    assert events.retries == []


def test_an_untrusted_certificate_is_never_retried(tmp_path: Path) -> None:
    """A secure-connection failure is final: retrying cannot make an untrusted certificate trusted."""
    with fault_server([], tls_directory=tmp_path) as server:
        untrusted = RunningFaultServer(url=server.url, script=server.script, trust_file=None)
        with pytest.raises(DependencyTransferError) as failure:
            asyncio.run(_retried(untrusted, tmp_path / "archive.bin"))
        requests = len(server.observed)
    assert failure.value.category is DependencyFailureCategory.SECURE_CONNECTION_FAILED
    assert failure.value.facts["attempts"] == 1
    assert requests == 0


def test_transient_faults_stop_at_the_attempt_budget_and_stay_transient_in_kind(tmp_path: Path) -> None:
    """A fault that never clears ends after the last attempt, still named as an unreachable host."""
    policy = DependencyRetryPolicy(initial_delay_s=2.0, max_delay_s=60.0, max_attempts=3, window_s=900.0)
    events = _RecordedEvents()
    with fault_server([Fault.SERVER_ERROR] * 10) as server:
        with pytest.raises(DependencyTransferError) as failure:
            asyncio.run(_retried(server, tmp_path / "archive.bin", policy=policy, events=events))
        requests = len(server.observed)
    assert failure.value.category is DependencyFailureCategory.HOST_UNREACHABLE
    assert failure.value.facts == {"http_status": 503, "attempts": 3}
    assert requests == 3
    assert [attempt for attempt, _delay in events.retries] == [2, 3]


def test_no_retry_starts_after_the_time_window_closes(tmp_path: Path) -> None:
    """A retry whose wait would end past the window is not made, however many attempts remain."""
    policy = DependencyRetryPolicy(initial_delay_s=2.0, max_delay_s=60.0, max_attempts=6, window_s=3.0)
    with fault_server([Fault.RESET] * 10) as server:
        with pytest.raises(DependencyTransferError) as failure:
            asyncio.run(_retried(server, tmp_path / "archive.bin", policy=policy))
        requests = len(server.observed)
    # Waits of 1 s and 2 s fit in 3 s; the third, of 4 s, would not.
    assert requests == 3
    assert failure.value.facts["attempts"] == 3


def test_an_interrupted_transfer_resumes_from_its_partial_rather_than_restarting(tmp_path: Path) -> None:
    """A cut-short body is transient; the retry asks only for the missing bytes, and the result is whole."""
    destination = tmp_path / "archive.bin"
    with fault_server([Fault.TRUNCATE]) as server:
        size = asyncio.run(_retried(server, destination))
        ranges = [request.byte_range for request in server.observed]
    assert size == len(PAYLOAD)
    assert hashlib.sha256(destination.read_bytes()).hexdigest() == PAYLOAD_DIGEST
    assert ranges == [None, f"bytes={len(PAYLOAD) // 2}-"]


def test_a_slow_transfer_is_not_a_failure(tmp_path: Path) -> None:
    """A crawling but progressing body completes on its first attempt."""
    events = _RecordedEvents()
    with fault_server([Fault.SLOW]) as server:
        size = asyncio.run(_retried(server, tmp_path / "archive.bin", events=events))
        requests = len(server.observed)
    assert size == len(PAYLOAD)
    assert requests == 1
    assert events.retries == []


def test_cancelling_during_the_backoff_wait_stops_without_another_request(tmp_path: Path) -> None:
    """A person's cancel during the wait is honoured before the next attempt starts."""
    events = _RecordedEvents(cancel_after_retries=1)
    with fault_server([Fault.RESET] * 3) as server:
        with pytest.raises(DependencyTransferError) as failure:
            asyncio.run(_retried(server, tmp_path / "archive.bin", events=events))
        requests = len(server.observed)
    assert failure.value.category is DependencyFailureCategory.CANCELLED
    assert requests == 1


def test_a_full_disk_refuses_before_the_transfer_and_names_both_sizes(tmp_path: Path) -> None:
    """Too little room is the disk-full refusal with the required and the measured size, before any byte moves."""
    free = shutil.disk_usage(tmp_path).free
    with pytest.raises(DependencyTransferError) as refused:
        require_free_space(tmp_path / "components" / "playwright", download_bytes=free)
    assert refused.value.category is DependencyFailureCategory.DISK_FULL
    assert refused.value.facts["required_bytes"] == -(-free * 6 // 5) + 1024**3
    assert isinstance(refused.value.facts["free_bytes"], int)
    assert require_free_space(tmp_path, download_bytes=0) >= 0


def test_running_out_of_space_mid_transfer_is_final(tmp_path: Path) -> None:
    """A write that hits a full disk after real bytes arrived is reported as disk full and not retried."""
    events = _RecordedEvents()
    error = OSError(errno.ENOSPC, "No space left on device")
    with fault_server([]) as server:
        fetched = _download_attempt(server, tmp_path / "archive.bin")

        async def fetch_then_fill() -> int:
            await fetched()
            raise error

        with pytest.raises(DependencyTransferError) as failure:
            asyncio.run(run_with_retry(fetch_then_fill, events=events, sleep=_VirtualClock().sleep))
        requests = len(server.observed)
    assert failure.value.category is DependencyFailureCategory.DISK_FULL
    assert failure.value.facts["attempts"] == 1
    assert requests == 1
    assert events.retries == []

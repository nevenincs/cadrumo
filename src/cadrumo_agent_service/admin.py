"""Bounded authenticated loopback administration, separate from the agent gateway."""

from __future__ import annotations

import contextlib
import hmac
import json
import socket
import struct
import time
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore, Event, Lock, Thread
from typing import Annotated, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError

from .host.credential_frame import wipe
from .providers.application.ports import ProviderCatalogUnavailableError

ADMIN_DOCUMENT_MAX_BYTES = 4096
ADMIN_RESPONSE_MAX_BYTES = 256 * 1024
ADMIN_SECRET_MAX_BYTES = 16 * 1024

type AdminAction = Literal["catalog", "status", "set", "remove", "reset", "auth", "sign_in", "start", "stop"]


class AdminTarget(Protocol):
    """The sole service capability consumed after admin ingress authenticates."""

    def admin(
        self,
        action: AdminAction,
        *,
        provider: str | None = None,
        expected_revision: str | None = None,
        base_url: str | None = None,
        choice: Literal["direct_api", "provider_sign_in"] | None = None,
        secret: bytearray | None = None,
    ) -> JsonValue:
        """Apply validated metadata and separately framed secret bytes under service authority."""
        ...


class AdminRequest(BaseModel):
    """Closed administration metadata; credential bytes use a separate frame."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, hide_input_in_errors=True)
    version: Literal[1]
    request_id: UUID
    action: AdminAction
    provider: Annotated[str, Field(min_length=1, max_length=128)] | None = None
    expected_revision: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")] | None = None
    base_url: Annotated[str, Field(max_length=2048)] | None = None
    choice: Literal["direct_api", "provider_sign_in"] | None = None
    secret_bytes: Annotated[int, Field(ge=1, le=ADMIN_SECRET_MAX_BYTES)] | None = None


def _read_exact(stream: socket.socket, size: int, *, deadline: float) -> bytearray:
    result = bytearray(size)
    view = memoryview(result)
    received = 0
    try:
        while received < size:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("admin_frame_expired")
            stream.settimeout(remaining)
            count = stream.recv_into(view[received:])
            if count == 0:
                raise EOFError
            received += count
        return result
    except BaseException:
        wipe(result)
        raise
    finally:
        view.release()


def _read_frame(stream: socket.socket, maximum: int, *, deadline: float) -> bytearray:
    header = _read_exact(stream, 4, deadline=deadline)
    (size,) = struct.unpack("!I", header)
    if not 0 < size <= maximum:
        raise ValueError("invalid_frame")
    return _read_exact(stream, size, deadline=deadline)


def _write_document(stream: socket.socket, document: dict[str, JsonValue]) -> None:
    encoded = json.dumps(document, separators=(",", ":")).encode("utf-8")
    if len(encoded) > ADMIN_RESPONSE_MAX_BYTES:
        raise ValueError("response_too_large")
    stream.sendall(struct.pack("!I", len(encoded)) + encoded)


class AdminServer:
    """Serve bounded administration requests on a private authenticated endpoint."""

    def __init__(self, service: AdminTarget, *, bearer: bytearray) -> None:
        """Bind an ephemeral loopback endpoint to the native startup bearer."""
        self._service = service
        self._bearer = bearer
        self._stop = Event()
        self._active_guard = Lock()
        self._active: set[socket.socket] = set()
        self._capacity = BoundedSemaphore(4)
        self._workers = ThreadPoolExecutor(max_workers=4, thread_name_prefix="agent-service-admin-request")
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.bind(("127.0.0.1", 0))
        self._socket.listen(4)
        self.port = self._socket.getsockname()[1]
        self._thread = Thread(target=self._serve, name="agent-service-admin", daemon=True)
        self._thread.start()

    def _serve(self) -> None:
        while not self._stop.is_set():
            try:
                stream, _ = self._socket.accept()
            except OSError:
                return
            if not self._capacity.acquire(blocking=False):
                stream.close()
                continue
            with self._active_guard:
                if self._stop.is_set():
                    self._capacity.release()
                    stream.close()
                    return
                self._active.add(stream)
            self._workers.submit(self._handle, stream)

    def _handle(self, stream: socket.socket) -> None:
        try:
            with stream:
                if not self._stop.is_set():
                    stream.settimeout(5)
                    with contextlib.suppress(EOFError, OSError, ValueError, ValidationError):
                        self._exchange(stream)
        finally:
            with self._active_guard:
                self._active.discard(stream)
            self._capacity.release()

    def _exchange(self, stream: socket.socket) -> None:
        deadline = time.monotonic() + 5
        authorization = _read_frame(stream, ADMIN_SECRET_MAX_BYTES, deadline=deadline)
        try:
            authenticated = hmac.compare_digest(authorization, self._bearer)
        finally:
            wipe(authorization)
        if not authenticated:
            _write_document(stream, {"kind": "refused", "code": "unauthenticated"})
            return
        request = AdminRequest.model_validate_json(_read_frame(stream, ADMIN_DOCUMENT_MAX_BYTES, deadline=deadline))
        secret: bytearray | None = None
        result: JsonValue
        try:
            if request.action == "set":
                if request.secret_bytes is None:
                    raise ValueError("missing_secret_length")
                _write_document(stream, {"event": "secret_ready", "request_id": str(request.request_id)})
                secret = _read_frame(stream, ADMIN_SECRET_MAX_BYTES, deadline=deadline)
                if len(secret) != request.secret_bytes:
                    raise ValueError("secret_length_mismatch")
            elif request.secret_bytes is not None:
                raise ValueError("unexpected_secret")
            if self._stop.is_set() or time.monotonic() >= deadline:
                raise ValueError("admin_request_expired")
            result = self._service.admin(
                request.action,
                provider=request.provider,
                expected_revision=request.expected_revision,
                base_url=request.base_url,
                choice=request.choice,
                secret=secret,
            )
        except ProviderCatalogUnavailableError:
            result = {"kind": "refused", "code": "catalog_unavailable"}
        except (ValueError, UnicodeDecodeError):
            result = {"kind": "refused", "code": "invalid_request"}
        except Exception:
            result = {"kind": "refused", "code": "service_failed"}
        finally:
            if secret is not None:
                wipe(secret)
        _write_document(stream, {"version": 1, "request_id": str(request.request_id), "result": result})

    def close(self) -> None:
        """Close admission and await the bounded current exchange."""
        self._stop.set()
        # Accept blocks without a timeout; a connection of its own is the event
        # that wakes it, and the loop then sees the stop and returns.
        with contextlib.suppress(OSError), socket.create_connection(("127.0.0.1", self.port), timeout=1):
            pass
        self._socket.close()
        with self._active_guard:
            for stream in self._active:
                with contextlib.suppress(OSError):
                    stream.shutdown(socket.SHUT_RDWR)
                stream.close()
        self._thread.join(6)
        self._workers.shutdown(wait=True, cancel_futures=True)

"""Exchange bounded packaged-service administration requests."""

from __future__ import annotations

import json
import socket
import struct
import time
from typing import Any, Final
from uuid import uuid4

from pydantic import JsonValue, TypeAdapter, ValidationError

from cadrumo.core.hashing import reject_duplicate_json_members
from cadrumo_agent_service.admin import (
    ADMIN_DOCUMENT_MAX_BYTES,
    ADMIN_RESPONSE_MAX_BYTES,
    ADMIN_SECRET_MAX_BYTES,
    AdminAction,
    AdminRequest,
)

from .caller_owned_root import (
    AcceptanceError,
    require,
)

_JSON_OBJECT: TypeAdapter[dict[str, JsonValue]] = TypeAdapter(dict[str, JsonValue])
ADMIN_EXCHANGE_SECONDS = 6.0


OWNED_SETTINGS_ACTIONS: Final[frozenset[AdminAction]] = frozenset(
    {
        "catalog",
        "status",
        "provider_lanes",
        "local_engine",
        "local_models",
        "local_engine_choose",
        "local_model_add",
        "reading_model_choose",
        "task_model_choose",
    }
)
"""The window's local-model settings: its reads, and the engine, list, reading and task choices it stores."""


def service_admin(
    bearer: bytearray, port: int, action: AdminAction, *, within: float = ADMIN_EXCHANGE_SECONDS, **fields: Any
) -> dict[str, JsonValue]:
    """Use the service's typed, bounded parent-administration protocol for public reads.

    ``within`` bounds every observation of one read, busy answers included; a cold provider status launches the
    agent program several times and needs more than the default.
    """
    if action not in {"catalog", "status"}:
        raise AcceptanceError("shared service admin permits catalog and status reads only")
    return _exchange(bearer, port, _request(action, fields), within=within)


def owned_service_settings(
    bearer: bytearray, port: int, action: AdminAction, *, within: float = ADMIN_EXCHANGE_SECONDS, **fields: Any
) -> dict[str, JsonValue]:
    """Read or store the window's local-model settings on a service this caller launched and alone administers.

    The caller is the service's parent: it minted the startup bearer the service authenticates its parent by, as
    the desktop does, so these are the desktop's own settings requests, each guarded by the ``expected_revision``
    the caller read. No credential frame and no provider, sign-in or lifecycle action is carried. A ``busy`` answer
    did nothing and is asked again inside ``within``; every other answer, refusals included, is returned.
    """
    if action not in OWNED_SETTINGS_ACTIONS:
        raise AcceptanceError("owned service settings permit the local-model settings reads and choices only")
    return _exchange(bearer, port, _request(action, fields), within=within)


def owned_service_credential(
    bearer: bytearray,
    port: int,
    *,
    provider: str,
    expected_revision: str,
    base_url: str | None,
    secret: bytearray,
    within: float = ADMIN_EXCHANGE_SECONDS,
) -> dict[str, JsonValue]:
    """Store one lane's direct credential on a service this caller launched and alone administers.

    This is the window's ``set``: the metadata names the lane, the revision the
    caller read and, optionally, a base URL (``None`` keeps the stored or
    catalogue one), and announces the credential's length; the service answers
    ``secret_ready`` under the request's identity and then reads the credential
    as one separate frame. It is the only request this channel lets carry a
    frame. ``secret`` is wiped on every exit, and nothing derived from it
    reaches an exception, a log or the returned answer, which is the service's
    masked result or typed refusal. A ``busy`` answer did nothing and is asked
    again inside ``within``.
    """
    try:
        require(0 < len(secret) <= ADMIN_SECRET_MAX_BYTES, "service credential is outside the admin secret bound")
        try:
            request = AdminRequest.model_validate(
                {
                    "version": 1,
                    "request_id": uuid4(),
                    "action": "set",
                    "provider": provider,
                    "expected_revision": expected_revision,
                    "base_url": base_url,
                    "secret_bytes": len(secret),
                }
            )
        except ValidationError:
            # The request carries the length only, but its error is not chained, so nothing it read can follow.
            raise AcceptanceError("service credential request failed its typed contract") from None
        return _exchange(bearer, port, request, within=within, secret=secret)
    finally:
        secret[:] = bytes(len(secret))


def _request(action: AdminAction, fields: dict[str, Any]) -> AdminRequest:
    if "secret_bytes" in fields:
        raise AcceptanceError("service admin does not carry credential frames here")
    try:
        return AdminRequest.model_validate({**fields, "version": 1, "request_id": uuid4(), "action": action})
    except ValidationError as error:
        raise AcceptanceError("service admin request failed its typed contract") from error


def _exchange(
    bearer: bytearray, port: int, request: AdminRequest, *, within: float, secret: bytearray | None = None
) -> dict[str, JsonValue]:
    require(bool(bearer), "service admin authority has been closed")
    require((secret is None) == (request.secret_bytes is None), "service admin credential frame differs from request")
    deadline = time.monotonic() + within
    while True:
        request = request.model_copy(update={"request_id": uuid4()})
        encoded = request.model_dump_json(exclude_none=True).encode("utf-8")
        require(0 < len(encoded) <= ADMIN_DOCUMENT_MAX_BYTES, "service admin request exceeds its contract bound")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=_admin_remaining(deadline)) as stream:
                _write_frame(stream, bearer, deadline=deadline)
                _write_frame(stream, encoded, deadline=deadline)
                response = _read_document(stream, ADMIN_RESPONSE_MAX_BYTES, deadline=deadline)
                if secret is not None and response == {"event": "secret_ready", "request_id": str(request.request_id)}:
                    _write_secret_frame(stream, secret, deadline=deadline)
                    response = _read_document(stream, ADMIN_RESPONSE_MAX_BYTES, deadline=deadline)
        except (OSError, TimeoutError, ValueError) as error:
            raise AcceptanceError("service admin exchange failed") from error
        require(response.get("version") == 1, "service admin response version differs")
        require(response.get("request_id") == str(request.request_id), "service admin response correlation differs")
        result = response.get("result")
        require(isinstance(result, dict), "service admin response omitted its typed result")
        result = _JSON_OBJECT.validate_python(result, strict=True)
        if result != {"kind": "refused", "code": "busy"}:
            return result
        # Busy is a completed response that did nothing; observe it again
        # inside the original exchange budget.
        time.sleep(min(0.05, _admin_remaining(deadline)))


def _admin_remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    require(remaining > 0, "service admin exchange exceeded its bound")
    return remaining


def _write_frame(stream: socket.socket, payload: bytes | bytearray, *, deadline: float) -> None:
    """Write one length-prefixed frame within the wire's 32-bit size field."""
    require(0 < len(payload) <= 16 * 1024 * 1024, "service admin frame size refused")
    stream.settimeout(_admin_remaining(deadline))
    stream.sendall(struct.pack("!I", len(payload)) + payload)


def _write_secret_frame(stream: socket.socket, secret: bytearray, *, deadline: float) -> None:
    """Write the credential frame from the caller's own buffer, so no immutable copy of it is made here."""
    require(0 < len(secret) <= ADMIN_SECRET_MAX_BYTES, "service credential is outside the admin secret bound")
    stream.settimeout(_admin_remaining(deadline))
    stream.sendall(struct.pack("!I", len(secret)))
    stream.sendall(secret)


def _read_exact(stream: socket.socket, size: int, *, deadline: float) -> bytes:
    """Read one complete bounded admin frame."""
    remaining = size
    chunks = bytearray()
    while remaining:
        stream.settimeout(_admin_remaining(deadline))
        chunk = stream.recv(remaining)
        if not chunk:
            raise AcceptanceError("service admin response ended early")
        chunks.extend(chunk)
        remaining -= len(chunk)
    return bytes(chunks)


def _read_document(stream: socket.socket, maximum: int, *, deadline: float) -> dict[str, JsonValue]:
    """Read a typed JSON object with the service's response bound."""
    size = struct.unpack("!I", _read_exact(stream, 4, deadline=deadline))[0]
    require(0 < size <= maximum, "service admin response frame size refused")
    try:
        document = json.loads(
            _read_exact(stream, size, deadline=deadline), object_pairs_hook=reject_duplicate_json_members
        )
        return _JSON_OBJECT.validate_python(document, strict=True)
    except (UnicodeError, ValueError, ValidationError) as error:
        raise AcceptanceError("service admin response was malformed") from error

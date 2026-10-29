"""Exchange bounded packaged-service administration requests."""

from __future__ import annotations

import json
import socket
import struct
import time
from typing import Any
from uuid import uuid4

from pydantic import JsonValue, TypeAdapter, ValidationError

from cadrumo.core.hashing import reject_duplicate_json_members
from cadrumo_agent_service.admin import (
    ADMIN_DOCUMENT_MAX_BYTES,
    ADMIN_RESPONSE_MAX_BYTES,
    AdminAction,
    AdminRequest,
)

from .caller_owned_root import (
    AcceptanceError,
    require,
)

_JSON_OBJECT: TypeAdapter[dict[str, JsonValue]] = TypeAdapter(dict[str, JsonValue])
_ADMIN_EXCHANGE_SECONDS = 6.0


def service_admin(bearer: bytearray, port: int, action: AdminAction, **fields: Any) -> dict[str, JsonValue]:
    """Use the service's typed, bounded parent-administration protocol for public reads."""
    if action not in {"catalog", "status"}:
        raise AcceptanceError("shared service admin permits catalog and status reads only")
    if "secret_bytes" in fields:
        raise AcceptanceError("shared service admin does not carry credential frames")
    try:
        request = AdminRequest.model_validate({**fields, "version": 1, "request_id": uuid4(), "action": action})
    except ValidationError as error:
        raise AcceptanceError("service admin request failed its typed contract") from error
    require(bool(bearer), "service admin authority has been closed")
    deadline = time.monotonic() + _ADMIN_EXCHANGE_SECONDS
    while True:
        request = request.model_copy(update={"request_id": uuid4()})
        encoded = request.model_dump_json(exclude_none=True).encode("utf-8")
        require(0 < len(encoded) <= ADMIN_DOCUMENT_MAX_BYTES, "service admin request exceeds its contract bound")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=_admin_remaining(deadline)) as stream:
                _write_frame(stream, bearer, deadline=deadline)
                _write_frame(stream, encoded, deadline=deadline)
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
        # These are reads only. Busy is a completed response whose work
        # continues; observe it again inside the original exchange budget.
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

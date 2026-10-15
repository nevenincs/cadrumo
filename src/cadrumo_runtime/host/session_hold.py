"""Persistent human frontend bridge for bounded generic admission decisions."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import struct
import sys
import time
from collections.abc import Mapping
from queue import Empty, Queue
from threading import Event, Thread
from uuid import UUID, uuid4

from cadrumo.adapters.persistence.storage.profile_persistence_composition import composed_profile_persistence_ports
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.core.hashing import reject_duplicate_json_members
from cadrumo_client.transport.frame_io import MAXIMUM_FRAME_BYTES
from cadrumo_client.transport.installed_client import open_installed_client

_MAXIMUM_REQUEST_LINE_BYTES = 16_384
_MAXIMUM_RESPONSE_LINE_BYTES = MAXIMUM_FRAME_BYTES + 1
_MAXIMUM_PASSWORD_BYTES = 4_096


def _read_stdin_bytes(fd: int, size: int) -> bytearray:
    """Read at most ``size`` raw stdin bytes without buffering ahead."""
    result = bytearray()
    try:
        while len(result) < size:
            chunk = os.read(fd, size - len(result))
            if not chunk:
                break
            result.extend(chunk)
        return result
    except BaseException:
        result[:] = bytes(len(result))
        raise


def _read_stdin_line(fd: int, maximum_bytes: int) -> bytes:
    """Read one bounded newline frame without locking Python's stdin buffer."""
    line = bytearray()
    while len(line) <= maximum_bytes:
        character = os.read(fd, 1)
        if not character:
            break
        line.extend(character)
        if character == b"\n":
            break
    return bytes(line)


def _emit(document: Mapping[str, object]) -> None:
    line = json.dumps(document, ensure_ascii=False, separators=(",", ":")) + "\n"
    if len(line.encode("utf-8")) > _MAXIMUM_RESPONSE_LINE_BYTES:
        raise SystemExit(1)
    sys.stdout.write(line)
    sys.stdout.flush()


def _emit_refusal(code: str, request_id: UUID | None = None) -> None:
    document = {"kind": "session_refused", "code": code}
    if request_id is not None:
        document["request_id"] = str(request_id)
    _emit(document)


async def _hold(
    profile_id: UUID,
    *,
    password_stdin: bool,
    frontend: OperationFrontendProjection = OperationFrontendProjection.DESKTOP,
) -> int:
    client = await open_installed_client(profile_id=profile_id, frontend=frontend)
    try:
        stdin_fd = sys.stdin.fileno()
        if password_stdin:
            header = _read_stdin_bytes(stdin_fd, 4)
            if len(header) != 4:
                return 1
            length = struct.unpack("!I", header)[0]
            if not 0 < length <= _MAXIMUM_PASSWORD_BYTES:
                return 1
            secret = _read_stdin_bytes(stdin_fd, length)
            try:
                if len(secret) != length:
                    return 1
                status = client.login_password(secret, persist_receipt=False)
            finally:
                secret[:] = bytes(len(secret))
        else:
            status = client.resume_receipt()
        _emit(
            {
                "kind": "session_held",
                "profile_id": str(profile_id),
                "session_id": str(status.status.session_id),
                "runtime_boot_id": str(status.runtime_boot_id),
                "connection_id": str(status.connection_id),
            }
        )
        lines: Queue[bytes] = Queue(maxsize=1)
        retired = Event()
        client.subscribe_session_retirement(retired.set)

        def read_lines() -> None:
            while not retired.is_set():
                line = _read_stdin_line(stdin_fd, _MAXIMUM_REQUEST_LINE_BYTES)
                if retired.is_set():
                    return
                lines.put(line)
                if not line or len(line) > _MAXIMUM_REQUEST_LINE_BYTES:
                    return

        Thread(target=read_lines, name="human-session-input", daemon=True).start()
        last_status = time.monotonic()
        while True:
            if retired.is_set():
                _emit({"kind": "session_retired", "profile_id": str(profile_id)})
                return 0
            try:
                line = lines.get(timeout=0.25)
            except Empty:
                if time.monotonic() - last_status >= 5:
                    current = client.status()
                    if current.status.denial is not None:
                        retired.set()
                    last_status = time.monotonic()
                continue
            if not line:
                return 0
            if len(line) > _MAXIMUM_REQUEST_LINE_BYTES or not line.endswith(b"\n"):
                _emit_refusal("invalid", uuid4())
                return 1
            try:
                request = json.loads(line, object_pairs_hook=reject_duplicate_json_members)
            except Exception:
                # No usable request object exists yet, so this response starts
                # its own correlation ID instead of echoing unparsed input.
                _emit_refusal("invalid", uuid4())
                return 1
            if not isinstance(request, dict):
                _emit_refusal("invalid")
                return 1
            try:
                request_id = UUID(request.get("request_id"))
            except (AttributeError, TypeError, ValueError):
                _emit_refusal("invalid")
                return 1
            action = request.get("action")
            if not isinstance(action, str):
                _emit_refusal("invalid", request_id)
                return 1
            action_keys = {
                "service_admission": {"recipient_connection_id", "service_id"},
                "attendance_decision": {"attendance_id", "approve"},
            }
            if set(request) != {"request_id", "action"} | action_keys.get(action, set()):
                _emit_refusal("invalid", request_id)
                return 1
            try:
                if action == "close":
                    _emit({"kind": "session_closed", "request_id": str(request_id)})
                    return 0
                if action == "service_admission":
                    current = client.status()
                    if current.status.session_id is None or current.status.denial is not None:
                        _emit({"kind": "session_refused", "request_id": str(request_id), "code": "inactive"})
                        return 1
                    reply = client.service_admission(
                        UUID(request["recipient_connection_id"]), request["service_id"], request_id=request_id
                    )
                    _emit(reply.model_dump(mode="json"))
                elif action == "attendance_inventory":
                    reply = client.attendance_inventory()
                    _emit({**reply.model_dump(mode="json"), "request_id": str(request_id)})
                elif action == "attendance_decision":
                    if type(request.get("approve")) is not bool:
                        _emit({"kind": "session_refused", "request_id": str(request_id), "code": "invalid"})
                        return 1
                    reply = client.decide_attendance(UUID(request["attendance_id"]), approve=request["approve"])
                    _emit({**reply.model_dump(mode="json"), "request_id": str(request_id)})
                elif action == "status":
                    reply = client.status()
                    _emit({**reply.model_dump(mode="json"), "request_id": str(request_id)})
                elif action == "activity":
                    reply = client.note_activity()
                    _emit({**reply.model_dump(mode="json"), "request_id": str(request_id)})
                else:
                    _emit_refusal("invalid", request_id)
                    return 1
            except (KeyError, TypeError, ValueError):
                _emit_refusal("invalid", request_id)
                return 1
            except Exception:
                # A valid command keeps its correlation key even when transport,
                # validation, or runtime work fails. Never expose the exception.
                _emit_refusal("unavailable", request_id)
                return 1
    finally:
        client.close()


def main(arguments: list[str] | None = None) -> int:
    """Hold verified human authority until explicit close, retirement or stdin EOF."""
    parser = argparse.ArgumentParser(prog="cadrumo-runtime session hold", allow_abbrev=False)
    parser.add_argument("--profile-id", type=UUID, required=True)
    parser.add_argument("--password-stdin", action="store_true")
    parser.add_argument(
        "--frontend",
        type=OperationFrontendProjection,
        choices=(OperationFrontendProjection.DESKTOP, OperationFrontendProjection.CLI),
        default=OperationFrontendProjection.DESKTOP,
    )
    options = parser.parse_args(arguments)
    try:
        with composed_profile_persistence_ports():
            return asyncio.run(
                _hold(options.profile_id, password_stdin=options.password_stdin, frontend=options.frontend)
            )
    except Exception:
        _emit({"kind": "session_refused", "request_id": str(uuid4()), "code": "unavailable"})
        return 1

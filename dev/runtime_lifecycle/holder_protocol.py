"""Bounded launch and correlated wire protocol for real runtime session holders."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from cadrumo.core.hashing import reject_duplicate_json_members
from cadrumo_client.transport.frame_io import MAXIMUM_FRAME_BYTES

from .caller_owned_root import AcceptanceError, require

_PASSWORD_FRAME_LIMIT = 4096
_COMMAND_FRAME_LIMIT = 16_384
_RUNTIME_ROLE = ("--role", "runtime")


def as_desktop_holder(executable: Path, arguments: tuple[str, ...]) -> tuple[Path, tuple[str, ...]]:
    """Start a desktop holder from the image the package admits as the desktop's session holder.

    Where the package's ``desktop-session`` descriptor names the desktop's own image, the
    desktop runs its holder as that image's runtime role, and so does this holder.
    """
    package = executable.parent.parent
    descriptors = package / "data" / "service-descriptors.json"
    if not descriptors.is_file():
        return executable, arguments
    entries = json.loads(descriptors.read_bytes(), object_pairs_hook=reject_duplicate_json_members)
    holder = next((entry for entry in entries if entry.get("service_id") == "desktop-session"), None)
    if holder is None:
        raise AcceptanceError("package declares no desktop session holder")
    launch_image = holder.get("launch_image")
    if not isinstance(launch_image, str):
        raise AcceptanceError(f"desktop session holder names no launch image: {launch_image!r}")
    image = (package / launch_image).resolve(strict=True)
    if image == executable:
        return executable, arguments
    return image, (*_RUNTIME_ROLE, *arguments)


def holder_launch(
    runtime: Path, profile_id: UUID, environment: Mapping[str, str], password: bytearray | None
) -> tuple[Path, tuple[str, ...]]:
    """Resolve the exact runtime image and its fixed holder argument vector."""
    executable = runtime.resolve(strict=True)
    arguments = ["session", "hold", "--profile-id", str(profile_id)]
    if password is not None:
        from cadrumo_runtime.application.development_root import mark_development_root

        require(0 < len(password) <= _PASSWORD_FRAME_LIMIT, "holder password frame is out of bounds")
        configured_root = environment.get("CADRUMO_STORAGE_ROOT")
        require(bool(configured_root), "development holder requires an explicit disposable storage root")
        if configured_root is None:
            raise AcceptanceError("development storage root unavailable")
        mark_development_root(Path(configured_root))
        arguments.append("--password-stdin")
    return executable, tuple(arguments)


def wipe_password(password: bytearray | None) -> None:
    """Erase the retained password buffer after its use."""
    if password is not None:
        password[:] = bytes(len(password))


def decode_holder_line(line: bytes) -> dict[str, Any]:
    """Decode one bounded JSON line and reject duplicate members or non-object replies."""
    require(
        bool(line) and len(line) <= MAXIMUM_FRAME_BYTES + 1 and line.endswith(b"\n"),
        "runtime holder frame refused",
    )
    try:
        document = json.loads(line, object_pairs_hook=reject_duplicate_json_members)
    except (UnicodeError, ValueError) as error:
        raise AcceptanceError("runtime holder document malformed") from error
    require(isinstance(document, dict), "runtime holder document is not an object")
    return document


def validate_holder_identity(identity: dict[str, Any], profile_id: UUID) -> None:
    """Require the native identity returned by the exact held profile session."""
    require(
        identity.get("kind") == "session_held",
        f"runtime did not admit the held session: {identity.get('kind')} {identity.get('code')}",
    )
    require(identity.get("profile_id") == str(profile_id), "holder profile identity differs")
    for member in ("session_id", "runtime_boot_id", "connection_id"):
        try:
            UUID(str(identity[member]))
        except (KeyError, TypeError, ValueError) as error:
            raise AcceptanceError("runtime holder omitted its exact native session coordinates") from error


def encode_holder_command(action: str, fields: Mapping[str, Any]) -> tuple[str, bytes]:
    """Add an unforgeable request identity and return its bounded wire frame."""
    require(not {"action", "request_id"}.intersection(fields), "holder correlation fields are reserved")
    request_id = str(uuid4())
    document = {"request_id": request_id, "action": action, **fields}
    encoded = json.dumps(document, separators=(",", ":")).encode("utf-8") + b"\n"
    require(len(encoded) <= _COMMAND_FRAME_LIMIT, "runtime holder command exceeds bound")
    return request_id, encoded


def validate_holder_reply(
    reply: dict[str, Any],
    *,
    request_id: str,
    action: str,
    fields: Mapping[str, Any],
    identity: Mapping[str, Any],
) -> None:
    """Correlate a reply with its request and the original native session."""
    require(reply.get("request_id") == request_id, "runtime holder reply correlation differs")
    for member in ("runtime_boot_id", "connection_id"):
        if member in reply:
            require(reply[member] == identity[member], "runtime holder reply identity differs")
    if action == "attendance_inventory":
        require(reply.get("profile_id") == identity["profile_id"], "inventory profile differs")
    if action == "attendance_decision":
        require(reply.get("attendance_id") == fields.get("attendance_id"), "decision ask identity differs")

"""Length-prefixed frames of the admin socket, written and read as a plain client would."""

from __future__ import annotations

import json
import socket
import struct


def send_frame(stream: socket.socket, payload: bytes | bytearray) -> None:
    stream.sendall(struct.pack("!I", len(payload)) + payload)


def read_frame(stream: socket.socket) -> dict[str, object]:
    def exact(size: int) -> bytes:
        result = bytearray()
        while len(result) < size:
            value = stream.recv(size - len(result))
            if not value:
                raise EOFError("admin_response_incomplete")
            result.extend(value)
        return bytes(result)

    (size,) = struct.unpack("!I", exact(4))
    document = json.loads(exact(size))
    assert isinstance(document, dict)
    return {str(key): value for key, value in document.items()}

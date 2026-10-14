"""Hold real runtime authority through its bounded generic person channel."""

from __future__ import annotations

import json
import struct
import subprocess
from collections.abc import Mapping
from pathlib import Path
from queue import Empty, Queue
from threading import Lock, Thread
from typing import Any
from uuid import UUID, uuid4

from cadrumo.core.hashing import reject_duplicate_json_members
from cadrumo_client.transport.frame_io import MAXIMUM_FRAME_BYTES

from .caller_owned_root import AcceptanceError, require


def _launch_holder(
    runtime: Path, profile_id: UUID, environment: Mapping[str, str], password: bytearray | None
) -> subprocess.Popen[bytes]:
    """Launch one exact image and wipe borrowed password material on every path."""
    process: subprocess.Popen[bytes] | None = None
    try:
        arguments = [str(runtime.resolve(strict=True)), "session", "hold", "--profile-id", str(profile_id)]
        if password is not None:
            from cadrumo_runtime.application.development_root import mark_development_root

            require(0 < len(password) <= 4096, "holder password frame is out of bounds")
            configured_root = environment.get("CADRUMO_LOCAL_STORAGE_ROOT")
            require(bool(configured_root), "development holder requires an explicit disposable storage root")
            if configured_root is None:
                raise AcceptanceError("development storage root unavailable")
            mark_development_root(Path(configured_root))
            arguments.append("--password-stdin")
        process = subprocess.Popen(
            arguments, env=dict(environment), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        require(process.stdin is not None and process.stdout is not None, "holder pipes unavailable")
        if password is not None:
            if process.stdin is None:
                raise AcceptanceError("holder stdin unavailable")
            process.stdin.write(struct.pack("!I", len(password)))
            process.stdin.write(password)
            process.stdin.flush()
        return process
    except BaseException:
        if process is not None:
            if process.stdin is not None:
                process.stdin.close()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
            for stream in (process.stdout, process.stderr):
                if stream is not None:
                    stream.close()
        raise
    finally:
        if password is not None:
            password[:] = bytes(len(password))


class RuntimeSessionHolder:
    """Own a runtime holder process and correlate each real command reply."""

    def __init__(
        self,
        runtime: Path,
        *,
        profile_id: UUID,
        environment: Mapping[str, str],
        password: bytearray | None = None,
    ) -> None:
        """Use native receipt admission, or explicit development password admission."""
        self._lock = Lock()
        self._closed = False
        self._lines: Queue[bytes] = Queue(maxsize=8)
        self._process = _launch_holder(runtime, profile_id, environment, password)

        def read() -> None:
            stdout = self._process.stdout
            if stdout is None:
                return
            while True:
                line = stdout.readline(MAXIMUM_FRAME_BYTES + 2)
                self._lines.put(line)
                if not line:
                    return

        Thread(target=read, name="runtime-session-holder-output", daemon=True).start()

        def drain_errors() -> None:
            stderr = self._process.stderr
            if stderr is not None:
                while stderr.read(4096):
                    pass

        Thread(target=drain_errors, name="runtime-session-holder-errors", daemon=True).start()
        try:
            self.identity = self._receive()
            require(self.identity.get("kind") == "session_held", "runtime did not admit the held session")
            require(self.identity.get("profile_id") == str(profile_id), "holder profile identity differs")
            for member in ("session_id", "runtime_boot_id", "connection_id"):
                try:
                    UUID(str(self.identity[member]))
                except (KeyError, TypeError, ValueError) as error:
                    raise AcceptanceError("runtime holder omitted its exact native session coordinates") from error
        except BaseException:
            self.close()
            raise

    def _receive(self, seconds: float = 30) -> dict[str, Any]:
        try:
            line = self._lines.get(timeout=seconds)
        except Empty as exc:
            raise AcceptanceError("runtime holder reply timed out") from exc
        require(
            bool(line) and len(line) <= MAXIMUM_FRAME_BYTES + 1 and line.endswith(b"\n"), "runtime holder frame refused"
        )
        try:
            document = json.loads(line, object_pairs_hook=reject_duplicate_json_members)
        except ValueError as exc:
            raise AcceptanceError("runtime holder document malformed") from exc
        require(isinstance(document, dict), "runtime holder document is not an object")
        return document

    def command(self, action: str, **fields: Any) -> dict[str, Any]:
        """Submit one generic command and require its exact correlation identity."""
        with self._lock:
            require(not self._closed, "runtime holder is already closed")
            require(not {"action", "request_id"}.intersection(fields), "holder correlation fields are reserved")
            request_id = str(uuid4())
            document = {"request_id": request_id, "action": action, **fields}
            encoded = json.dumps(document, separators=(",", ":")).encode("utf-8") + b"\n"
            require(len(encoded) <= 16_384, "runtime holder command exceeds bound")
            stream = self._process.stdin
            require(stream is not None, "runtime holder stdin closed")
            if stream is None:
                raise AcceptanceError("runtime holder stdin closed")
            stream.write(encoded)
            stream.flush()
            reply = self._receive()
            if reply.get("kind") in {"session_retired", "session_refused"}:
                self.close()
                raise AcceptanceError("the original human holder retired or refused the command")
            require(reply.get("request_id") == request_id, "runtime holder reply correlation differs")
            for member in ("runtime_boot_id", "connection_id"):
                if member in reply:
                    require(reply[member] == self.identity[member], "runtime holder reply identity differs")
            if action == "attendance_inventory":
                require(reply.get("profile_id") == self.identity["profile_id"], "inventory profile differs")
            if action == "attendance_decision":
                require(reply.get("attendance_id") == fields.get("attendance_id"), "decision ask identity differs")
            return reply

    def close(self) -> None:
        """Close stdin, wait for bounded drain, and reap every owned handle."""
        if self._closed:
            return
        self._closed = True
        if self._process.stdin is not None and not self._process.stdin.closed:
            self._process.stdin.close()
        try:
            self._process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self._process.terminate()
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=10)
        for stream in (self._process.stdout, self._process.stderr):
            if stream is not None:
                stream.close()

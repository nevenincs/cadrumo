"""Own one Windows job-contained runtime session holder."""

from __future__ import annotations

import struct
from collections.abc import Mapping
from pathlib import Path
from queue import Empty, Full
from threading import Event, Thread
from typing import Any, Literal
from uuid import UUID

from cadrumo_client.transport.frame_io import MAXIMUM_FRAME_BYTES
from cadrumo_client.transport.windows_process import WindowsProcessScope, unreturned_windows_process_scope

from .caller_owned_root import AcceptanceError, require
from .holder_protocol import (
    as_desktop_holder,
    decode_holder_line,
    encode_holder_command,
    holder_launch,
    validate_holder_identity,
    validate_holder_reply,
    wipe_password,
)
from .windows_holder_cleanup import WindowsHolderCleanup

_STARTUP_SECONDS = 30.0
_CLOSE_SECONDS = 10.0
_REAP_SECONDS = 10.0
_WRITE_SECONDS = 30.0
_STDERR_CHUNK_BYTES = 4096


class WindowsRuntimeSessionHolder(WindowsHolderCleanup):
    """Synchronously own a Windows job-contained holder for the sync live-evaluation lane."""

    def __init__(
        self,
        runtime: Path,
        *,
        profile_id: UUID,
        environment: Mapping[str, str],
        password: bytearray | None = None,
        frontend: Literal["desktop", "cli"] = "desktop",
    ) -> None:
        """Use a kill-on-close Windows job and private standard pipes."""
        self.identity: dict[str, Any] = {}
        super().__init__()
        try:
            executable, arguments = holder_launch(runtime, profile_id, environment, password)
            if frontend == "cli":
                arguments = (*arguments, "--frontend", "cli")
            else:
                executable, arguments = as_desktop_holder(executable, arguments)
            try:
                self._scope = WindowsProcessScope()
            except BaseException as error:
                self._scope = unreturned_windows_process_scope(error)
                raise
            process, stdin, stdout, stderr = self._scope.launch_with_standard_pipes(
                executable=executable,
                arguments=arguments,
                directory=Path.cwd().resolve(strict=True),
                environment=dict(environment),
            )
            self._process, self._stdin, self._stdout, self._stderr = process, stdin, stdout, stderr
            self._stdout_thread = Thread(target=self._read_stdout, name="runtime-session-holder-output", daemon=True)
            self._stderr_thread = Thread(target=self._drain_stderr, name="runtime-session-holder-errors", daemon=True)
            self._stdout_thread.start()
            self._stderr_thread.start()
            if password is not None:
                self._write_frame(struct.pack("!I", len(password)) + password)
            self.identity = decode_holder_line(self._receive())
            validate_holder_identity(self.identity, profile_id)
        except BaseException as primary:
            try:
                self.close()
            except BaseException as cleanup:
                raise BaseExceptionGroup(
                    "Windows runtime holder startup and cleanup failed", [primary, cleanup]
                ) from primary
            raise
        finally:
            wipe_password(password)

    def _enqueue(self, item: bytes | BaseException) -> None:
        while not self._reader_stop.is_set():
            try:
                self._lines.put(item, timeout=0.1)
                return
            except Full:
                continue

    def _read_stdout(self) -> None:
        if self._stdout is None:
            return
        try:
            while True:
                line = self._stdout.readline(MAXIMUM_FRAME_BYTES + 2)
                self._enqueue(line)
                if not line:
                    return
        except OSError as error:
            self._enqueue(error)

    def _drain_stderr(self) -> None:
        if self._stderr is None:
            return
        try:
            while self._stderr.read(_STDERR_CHUNK_BYTES):
                pass
        except OSError as error:
            if not self._reader_stop.is_set():
                self._stderr_failure = error

    def _receive(self, seconds: float = _STARTUP_SECONDS) -> bytes:
        try:
            line = self._lines.get(timeout=seconds)
        except Empty as error:
            raise AcceptanceError("runtime holder reply timed out") from error
        if isinstance(line, BaseException):
            raise AcceptanceError("runtime holder stdout read failed") from line
        return line

    def command(self, action: str, **fields: Any) -> dict[str, Any]:
        """Submit one generic command and require its exact correlation identity."""
        with self._lock:
            require(not self._closed and not self._closing, "runtime holder is already closed")
            stdin = self._stdin
            if stdin is None:
                raise AcceptanceError("runtime holder stdin closed")
            request_id, encoded = encode_holder_command(action, fields)
            self._write_frame(encoded)
            reply = decode_holder_line(self._receive())
            if reply.get("kind") in {"session_retired", "session_refused"}:
                self._close_locked()
                raise AcceptanceError("the original human holder retired or refused the command")
            validate_holder_reply(
                reply,
                request_id=request_id,
                action=action,
                fields=fields,
                identity=self.identity,
            )
            return reply

    def _write_frame(self, frame: bytes) -> None:
        """Write one bounded frame on a worker so a blocked Windows pipe can be reaped."""
        stdin = self._stdin
        if stdin is None or stdin.closed:
            raise AcceptanceError("runtime holder stdin closed")

        finished = Event()
        failures: list[BaseException] = []

        def write() -> None:
            try:
                stdin.write(frame)
                stdin.flush()
            except BaseException as error:
                failures.append(error)
            finally:
                finished.set()

        writer = Thread(target=write, name="runtime-session-holder-input", daemon=True)
        self._writer_thread = writer
        writer.start()
        if not finished.wait(_WRITE_SECONDS):
            timeout = AcceptanceError("runtime holder input timed out")
            try:
                self._terminate_scope()
            except BaseException as cleanup:
                raise BaseExceptionGroup(
                    "runtime holder input timeout and job cleanup failed", [timeout, cleanup]
                ) from timeout
            writer.join(timeout=_CLOSE_SECONDS)
            if writer.is_alive():
                stopped = AcceptanceError("runtime holder input writer did not stop after job termination")
                raise BaseExceptionGroup(
                    "runtime holder input timeout and writer cleanup failed", [timeout, stopped]
                ) from timeout
            self._writer_thread = None
            try:
                self._close_locked()
            except BaseException as cleanup:
                raise BaseExceptionGroup(
                    "runtime holder input timeout and pipe cleanup failed", [timeout, cleanup]
                ) from timeout
            raise timeout

        writer.join(timeout=_CLOSE_SECONDS)
        if writer.is_alive():
            raise AcceptanceError("runtime holder input writer did not stop")
        self._writer_thread = None
        if failures:
            raise failures[0]

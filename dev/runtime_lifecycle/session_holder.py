"""Own real runtime holders through a bounded, correlated person channel."""

from __future__ import annotations

import asyncio
import json
import struct
from collections.abc import Mapping, Sequence
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Event, Lock, Thread
from typing import Any, BinaryIO, Literal
from uuid import UUID, uuid4

from cadrumo.core.async_cleanup import await_cancellation_complete
from cadrumo.core.hashing import reject_duplicate_json_members
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frame_io import MAXIMUM_FRAME_BYTES
from cadrumo_runtime.adapters.windows_process import (
    WindowsOwnedProcess,
    WindowsProcessScope,
    unreturned_windows_process_scope,
)

from .caller_owned_root import AcceptanceError, require

_PASSWORD_FRAME_LIMIT = 4096
_COMMAND_FRAME_LIMIT = 16_384
_STARTUP_SECONDS = 30.0
_CLOSE_SECONDS = 10.0
_WRITE_SECONDS = 30.0
_STDERR_CHUNK_BYTES = 4096


def _holder_launch(
    runtime: Path, profile_id: UUID, environment: Mapping[str, str], password: bytearray | None
) -> tuple[Path, tuple[str, ...]]:
    """Resolve the exact runtime image and its fixed holder argument vector."""
    executable = runtime.resolve(strict=True)
    arguments = ["session", "hold", "--profile-id", str(profile_id)]
    if password is not None:
        from cadrumo_runtime.application.development_root import mark_development_root

        require(0 < len(password) <= _PASSWORD_FRAME_LIMIT, "holder password frame is out of bounds")
        configured_root = environment.get("CADRUMO_LOCAL_STORAGE_ROOT")
        require(bool(configured_root), "development holder requires an explicit disposable storage root")
        if configured_root is None:
            raise AcceptanceError("development storage root unavailable")
        mark_development_root(Path(configured_root))
        arguments.append("--password-stdin")
    return executable, tuple(arguments)


def _wipe_password(password: bytearray | None) -> None:
    if password is not None:
        password[:] = bytes(len(password))


def _decode_holder_line(line: bytes) -> dict[str, Any]:
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


def _validate_identity(identity: dict[str, Any], profile_id: UUID) -> None:
    """Require the native identity returned by the exact held profile session."""
    require(identity.get("kind") == "session_held", "runtime did not admit the held session")
    require(identity.get("profile_id") == str(profile_id), "holder profile identity differs")
    for member in ("session_id", "runtime_boot_id", "connection_id"):
        try:
            UUID(str(identity[member]))
        except (KeyError, TypeError, ValueError) as error:
            raise AcceptanceError("runtime holder omitted its exact native session coordinates") from error


def _encode_command(action: str, fields: Mapping[str, Any]) -> tuple[str, bytes]:
    """Add an unforgeable request identity and return its bounded wire frame."""
    require(not {"action", "request_id"}.intersection(fields), "holder correlation fields are reserved")
    request_id = str(uuid4())
    document = {"request_id": request_id, "action": action, **fields}
    encoded = json.dumps(document, separators=(",", ":")).encode("utf-8") + b"\n"
    require(len(encoded) <= _COMMAND_FRAME_LIMIT, "runtime holder command exceeds bound")
    return request_id, encoded


def _validate_reply(
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


class _AsyncPipeOwner:
    """Own an asyncio subprocess, its bounded standard streams and stderr drainer."""

    def __init__(self, process: asyncio.subprocess.Process) -> None:
        self.process = process
        self._stderr_task = asyncio.create_task(self._drain_stderr(), name="runtime-session-holder-stderr")
        self._wait_task: asyncio.Task[int] | None = None
        self._closed = False

    @classmethod
    async def launch(
        cls, executable: Path, arguments: Sequence[str], environment: Mapping[str, str]
    ) -> _AsyncPipeOwner:
        """Start one exact image with private pipes and an explicit environment."""
        process = await asyncio.create_subprocess_exec(
            str(executable),
            *arguments,
            env=dict(environment),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=MAXIMUM_FRAME_BYTES + 2,
        )
        owner = cls(process)
        try:
            require(
                process.stdin is not None and process.stdout is not None and process.stderr is not None,
                "runtime holder pipes unavailable",
            )
        except BaseException as primary:
            try:
                await owner.close()
            except BaseException as cleanup:
                raise BaseExceptionGroup("holder pipe validation and cleanup failed", [primary, cleanup]) from primary
            raise
        return owner

    async def write(self, frame: bytes) -> None:
        """Write a complete command frame and bound pipe backpressure."""
        stream = self.process.stdin
        if stream is None:
            raise AcceptanceError("runtime holder stdin closed")
        stream.write(frame)
        try:
            await asyncio.wait_for(stream.drain(), timeout=_STARTUP_SECONDS)
        except TimeoutError as error:
            raise AcceptanceError("runtime holder input timed out") from error

    async def read_line(self, seconds: float) -> bytes:
        """Read one bounded stdout line or refuse the expired reply."""
        stream = self.process.stdout
        if stream is None:
            raise AcceptanceError("runtime holder stdout closed")
        try:
            return await asyncio.wait_for(stream.readline(), timeout=seconds)
        except TimeoutError as error:
            raise AcceptanceError("runtime holder reply timed out") from error
        except (asyncio.LimitOverrunError, ValueError) as error:
            raise AcceptanceError("runtime holder frame refused") from error

    async def _drain_stderr(self) -> None:
        stream = self.process.stderr
        if stream is None:
            return
        while await stream.read(_STDERR_CHUNK_BYTES):
            pass

    async def _wait(self, seconds: float) -> bool:
        if self._wait_task is None:
            self._wait_task = asyncio.create_task(self.process.wait(), name="runtime-session-holder-wait")
        try:
            await asyncio.wait_for(asyncio.shield(self._wait_task), timeout=seconds)
        except TimeoutError:
            return False
        return True

    async def close(self) -> None:
        """Close stdin, settle the exact child, escalate within bounds and finish stderr draining."""
        await await_cancellation_complete(self._close(), task_name="runtime-session-holder-close")

    async def _close(self) -> None:
        if self._closed:
            return
        failures: list[BaseException] = []
        stdin_settled = self.process.stdin is None
        stream = self.process.stdin
        if stream is not None:
            if not stream.is_closing():
                try:
                    stream.close()
                except BaseException as error:
                    failures.append(error)
            if stream.is_closing():
                try:
                    await asyncio.wait_for(stream.wait_closed(), timeout=_CLOSE_SECONDS)
                except (BrokenPipeError, ConnectionResetError):
                    stdin_settled = True
                except TimeoutError as error:
                    failure = AcceptanceError("runtime holder stdin did not close")
                    failure.__cause__ = error
                    failures.append(failure)
                except BaseException as error:
                    failures.append(error)
                else:
                    stdin_settled = True

        settled = False
        try:
            settled = await self._wait(_CLOSE_SECONDS)
        except BaseException as error:
            failures.append(error)
        if not settled:
            try:
                self.process.terminate()
            except ProcessLookupError:
                pass
            except BaseException as error:
                failures.append(error)
            try:
                settled = await self._wait(_CLOSE_SECONDS)
            except BaseException as error:
                failures.append(error)
        if not settled:
            try:
                self.process.kill()
            except ProcessLookupError:
                pass
            except BaseException as error:
                failures.append(error)
            try:
                settled = await self._wait(_CLOSE_SECONDS)
            except BaseException as error:
                failures.append(error)
        if not settled:
            failures.append(AcceptanceError("runtime holder process could not be reaped"))

        stderr_settled = False
        if self._stderr_task.done():
            if self._stderr_task.cancelled():
                failures.append(AcceptanceError("runtime holder stderr drainer was cancelled"))
            else:
                stderr_error = self._stderr_task.exception()
                if stderr_error is None:
                    stderr_settled = True
                else:
                    failures.append(stderr_error)
        else:
            try:
                await asyncio.wait_for(asyncio.shield(self._stderr_task), timeout=_CLOSE_SECONDS)
            except TimeoutError as error:
                failure = AcceptanceError("runtime holder stderr drainer did not stop")
                failure.__cause__ = error
                failures.append(failure)
            except BaseException as error:
                failures.append(error)
            else:
                stderr_settled = True

        self._closed = settled and stdin_settled and stderr_settled and not failures
        if failures:
            raise BaseExceptionGroup("runtime holder process cleanup failed", failures)


class AsyncRuntimeSessionHolder:
    """Asynchronously own a generic-process runtime holder and correlate every reply."""

    def __init__(self) -> None:
        """Start unbound and assign the owned pipe process in ``start``."""
        self.identity: dict[str, Any] = {}
        self._owner: _AsyncPipeOwner | None = None
        self._lock = asyncio.Lock()
        self._closed = False
        self._closing = False

    @classmethod
    async def start(
        cls,
        runtime: Path,
        *,
        profile_id: UUID,
        environment: Mapping[str, str],
        password: bytearray | None = None,
        frontend: Literal["desktop", "cli"] = "desktop",
    ) -> AsyncRuntimeSessionHolder:
        """Start native receipt admission or explicit development password admission."""
        holder = cls()
        try:
            executable, arguments = _holder_launch(runtime, profile_id, environment, password)
            if frontend == "cli":
                arguments = (*arguments, "--frontend", "cli")

            async def assign_owner() -> None:
                holder._owner = await _AsyncPipeOwner.launch(executable, arguments, environment)

            await await_cancellation_complete(assign_owner(), task_name="runtime-session-holder-launch")
            if password is not None:
                owner = holder._owner
                if owner is None:
                    raise AcceptanceError("runtime holder process unavailable")
                await owner.write(struct.pack("!I", len(password)) + password)
            owner = holder._owner
            if owner is None:
                raise AcceptanceError("runtime holder process unavailable")
            holder.identity = _decode_holder_line(await owner.read_line(_STARTUP_SECONDS))
            _validate_identity(holder.identity, profile_id)
            return holder
        except BaseException as primary:
            try:
                await holder.close()
            except BaseException as cleanup:
                raise BaseExceptionGroup("runtime holder startup and cleanup failed", [primary, cleanup]) from primary
            raise
        finally:
            _wipe_password(password)

    async def _receive(self, seconds: float = _STARTUP_SECONDS) -> dict[str, Any]:
        if self._owner is None:
            raise AcceptanceError("runtime holder process unavailable")
        return _decode_holder_line(await self._owner.read_line(seconds))

    async def command(self, action: str, **fields: Any) -> dict[str, Any]:
        """Submit one generic command and require its exact correlation identity."""
        async with self._lock:
            require(not self._closed and not self._closing, "runtime holder is already closed")
            owner = self._owner
            if owner is None:
                raise AcceptanceError("runtime holder process unavailable")
            request_id, encoded = _encode_command(action, fields)
            await owner.write(encoded)
            reply = await self._receive()
            if reply.get("kind") in {"session_retired", "session_refused"}:
                await self._close_locked()
                raise AcceptanceError("the original human holder retired or refused the command")
            _validate_reply(
                reply,
                request_id=request_id,
                action=action,
                fields=fields,
                identity=self.identity,
            )
            return reply

    async def close(self) -> None:
        """Close stdin and settle the holder process with bounded termination escalation."""
        await await_cancellation_complete(self._close_with_lock(), task_name="runtime-session-holder-close")

    async def _close_with_lock(self) -> None:
        async with self._lock:
            await self._close_locked()

    async def _close_locked(self) -> None:
        if self._closed:
            return
        self._closing = True
        try:
            if self._owner is not None:
                await self._owner.close()
        finally:
            self._closing = False
        self._closed = True


class WindowsRuntimeSessionHolder:
    """Synchronously own a Windows job-contained holder for the sync live-evaluation lane."""

    def __init__(
        self,
        runtime: Path,
        *,
        profile_id: UUID,
        environment: Mapping[str, str],
        password: bytearray | None = None,
    ) -> None:
        """Use a kill-on-close Windows job and private standard pipes."""
        self.identity: dict[str, Any] = {}
        self._lock = Lock()
        self._closed = False
        self._closing = False
        self._lines: Queue[bytes | BaseException] = Queue(maxsize=8)
        self._reader_stop = Event()
        self._scope: WindowsProcessScope | None = None
        self._process: WindowsOwnedProcess | None = None
        self._stdin: BinaryIO | None = None
        self._stdout: BinaryIO | None = None
        self._stderr: BinaryIO | None = None
        self._stdout_thread: Thread | None = None
        self._stderr_thread: Thread | None = None
        self._writer_thread: Thread | None = None
        self._scope_termination_attempted = False
        self._stderr_failure: BaseException | None = None
        try:
            executable, arguments = _holder_launch(runtime, profile_id, environment, password)
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
            self.identity = _decode_holder_line(self._receive())
            _validate_identity(self.identity, profile_id)
        except BaseException as primary:
            try:
                self.close()
            except BaseException as cleanup:
                raise BaseExceptionGroup(
                    "Windows runtime holder startup and cleanup failed", [primary, cleanup]
                ) from primary
            raise
        finally:
            _wipe_password(password)

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
            request_id, encoded = _encode_command(action, fields)
            self._write_frame(encoded)
            reply = _decode_holder_line(self._receive())
            if reply.get("kind") in {"session_retired", "session_refused"}:
                self._close_locked()
                raise AcceptanceError("the original human holder retired or refused the command")
            _validate_reply(
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

    def _terminate_scope(self) -> None:
        """Terminate the exact Windows job before any blocked pipe is closed."""
        scope = self._scope
        if scope is None:
            return
        self._scope_termination_attempted = True
        scope.terminate(timeout=_CLOSE_SECONDS)
        self._scope = None

    def close(self) -> None:
        """Close stdin, wait for the exact child and terminate its job within a bound."""
        with self._lock:
            self._close_locked()

    def _close_locked(self) -> None:
        if self._closed:
            return
        self._closing = True
        self._reader_stop.set()
        failures: list[BaseException] = []
        writer = self._writer_thread
        writer_alive = writer is not None and writer.is_alive()
        scope_failed_before_pipe_close = False
        if writer_alive and self._scope is not None:
            try:
                self._terminate_scope()
            except BaseException as error:
                failures.append(error)
                scope_failed_before_pipe_close = True
        if writer_alive and self._scope is None:
            writer.join(timeout=_CLOSE_SECONDS)
            if writer.is_alive():
                failures.append(AcceptanceError("runtime holder input writer did not stop after job termination"))
            else:
                self._writer_thread = None
                writer_alive = False

        if self._stdin is not None and not self._stdin.closed and not writer_alive:
            try:
                self._stdin.close()
            except BaseException as error:
                failures.append(error)

        if self._process is not None and not self._scope_termination_attempted:
            try:
                self._process.wait(timeout=_CLOSE_SECONDS)
            except RefusalError as error:
                if error.reason != RefusalCode.DEADLINE_EXCEEDED:
                    failures.append(error)

        scope_settled = self._scope is None
        if self._scope is not None and not scope_failed_before_pipe_close:
            try:
                self._terminate_scope()
                scope_settled = self._scope is None
            except BaseException as error:
                failures.append(error)

        for stream in (self._stdout, self._stderr):
            if stream is not None and not stream.closed:
                try:
                    stream.close()
                except BaseException as error:
                    failures.append(error)

        for thread in (self._writer_thread, self._stdout_thread, self._stderr_thread):
            if thread is not None and thread.ident is not None:
                thread.join(timeout=_CLOSE_SECONDS)
                if thread.is_alive():
                    failures.append(AcceptanceError(f"runtime holder pipe thread {thread.name} did not stop"))
                else:
                    if thread is self._writer_thread:
                        self._writer_thread = None

        streams_settled = all(stream is None or stream.closed for stream in (self._stdin, self._stdout, self._stderr))
        threads_settled = all(
            thread is None or not thread.is_alive()
            for thread in (self._writer_thread, self._stdout_thread, self._stderr_thread)
        )
        self._closed = scope_settled and streams_settled and threads_settled

        if self._stderr_failure is not None:
            failure = AcceptanceError("runtime holder stderr read failed")
            failure.__cause__ = self._stderr_failure
            failures.append(failure)

        self._closing = False
        if failures:
            if len(failures) == 1:
                raise failures[0]
            raise BaseExceptionGroup("Windows runtime holder cleanup failed", failures)

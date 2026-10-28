"""Contained agent trees reached only through private standard pipes, served or run once."""

from __future__ import annotations

import contextlib
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Lock, Thread
from typing import BinaryIO, Final

from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.windows_process import WindowsOwnedProcess, WindowsProcessScope

from ..host.controller import AgentHostError, AgentHostRefusal, AgentProcess
from ..host.native_refusal import STANDARD_ERROR_TAIL_BYTES
from ..host.store_lifecycle import AgentInvocationResult
from .agent_diagnostics import AgentDiagnosticLines, AgentDiagnosticSink

_STANDARD_ERROR_CHUNK_BYTES: Final = 4096
_STANDARD_ERROR_RELEASE_SECONDS: Final = 1.0
_DIAGNOSTIC_BACKLOG_BYTES: Final = 1024 * 1024
"""Agent output the application log may fall behind by before the excess is dropped."""
_OUTPUT_SETTLE_SECONDS: Final = 2.0
"""How long an invocation that has exited is given to finish delivering its standard output."""
_INVOCATION_TERMINATE_SECONDS: Final = 10.0


class _StandardErrorTail:
    """The bounded end of an agent's standard error, drained for as long as any writer holds the pipe.

    The agent's standard error is a private pipe, so the service must read it
    or a chatty agent would block on a full pipe. Everything but the last
    bytes is discarded after structured diagnostics are forwarded to the application
    log. The host still reads the native launch-profile refusal from the end.

    The drain only reads: diagnostics reach the application log from a thread of
    their own. Writing the log can stall for seconds on a loaded disk, and a
    drain that waited on it would stop reading, fill the pipe and block every
    agent process that logs, its stop included. Output the log has not taken
    when the backlog reaches its bound is dropped and counted, never waited on.
    """

    def __init__(self, stream: BinaryIO, *, limit: int, diagnostics: AgentDiagnosticLines | None = None) -> None:
        """Start draining the stream on a daemon thread that closes it at the end of the output."""
        self._stream = stream
        self._diagnostics = diagnostics
        self._limit = limit
        self._lock = Lock()
        self._tail = bytearray()
        self._backlog: Queue[bytes | None] = Queue()
        self._backlog_bytes = 0
        self._dropping = False
        if diagnostics is not None:
            Thread(target=self._forward, args=(diagnostics,), name="agent-diagnostic-log", daemon=True).start()
        self._drain_thread = Thread(target=self._drain, name="agent-standard-error", daemon=True)
        self._drain_thread.start()

    def settled(self, *, timeout: float) -> bytes:
        """Wait for the output to end, up to the bound, and return the retained end of it.

        A descendant that inherited the pipe can keep it open after the agent
        exits, so the bound ends the wait and what arrived so far is returned.
        """
        self._drain_thread.join(timeout)
        with self._lock:
            return bytes(self._tail)

    def release(self, *, timeout: float) -> None:
        """Wait for the drain to finish after the tree's writers are gone, up to the bound."""
        self._drain_thread.join(timeout)

    def _drain(self) -> None:
        try:
            with contextlib.suppress(OSError, ValueError):
                reader = getattr(self._stream, "read1", self._stream.read)
                while chunk := reader(_STANDARD_ERROR_CHUNK_BYTES):
                    with self._lock:
                        self._tail += chunk
                        del self._tail[: -self._limit]
                        if self._diagnostics is not None:
                            self._hand_to_log(chunk)
        finally:
            with self._lock:
                if self._dropping:
                    self._backlog.put(b"")
            # The end of the output, after every chunk already handed over.
            self._backlog.put(None)
            with contextlib.suppress(OSError):
                self._stream.close()

    def _hand_to_log(self, chunk: bytes) -> None:
        """Queue a chunk for the log, or drop it while the backlog is at its bound; the lock is held."""
        if self._backlog_bytes + len(chunk) > _DIAGNOSTIC_BACKLOG_BYTES:
            self._dropping = True
            return
        if self._dropping:
            # Tells the log that output went missing before this chunk.
            self._backlog.put(b"")
            self._dropping = False
        self._backlog_bytes += len(chunk)
        self._backlog.put(chunk)

    def _forward(self, diagnostics: AgentDiagnosticLines) -> None:
        try:
            while (chunk := self._backlog.get()) is not None:
                if chunk:
                    with self._lock:
                        self._backlog_bytes -= len(chunk)
                    diagnostics.feed(chunk)
                else:
                    diagnostics.lost()
        finally:
            diagnostics.finish()


class WindowsAgentProcess:
    """One agent tree in its own kill-on-close job."""

    def __init__(
        self,
        *,
        scope: WindowsProcessScope,
        process: WindowsOwnedProcess,
        standard_input: BinaryIO,
        standard_output: BinaryIO,
        standard_error: BinaryIO,
        diagnostic_sink: AgentDiagnosticSink | None = None,
        on_exit: Callable[[], None] | None = None,
    ) -> None:
        """Take ownership of the job, the agent and the parent pipe ends, and start draining standard error.

        Every diagnostic of the tree arrives there, the hosted worker's relayed by the agent.
        """
        self._scope = scope
        self._process = process
        self._input: BinaryIO | None = standard_input
        self._output = standard_output
        self._standard_error = _StandardErrorTail(
            standard_error,
            limit=STANDARD_ERROR_TAIL_BYTES,
            diagnostics=AgentDiagnosticLines(diagnostic_sink or AgentDiagnosticSink(), pid=process.pid),
        )
        self._lines: Queue[bytes | BaseException] = Queue(maxsize=1)
        self._reader: Thread | None = None

        def exited() -> None:
            self._notify_output(EOFError())
            if on_exit is not None:
                on_exit()

        waiter = process.retain_waiter()
        try:
            Thread(target=_observe_exit, args=(waiter, exited), name="agent-process-exit", daemon=True).start()
        except BaseException:
            waiter.close()
            raise

    def write_input(self, data: bytearray) -> None:
        """Write and flush these bytes to the agent's standard input."""
        if self._input is None:
            raise BrokenPipeError
        view = memoryview(data)
        try:
            while view:
                written = self._input.write(view)
                if not written:
                    raise BrokenPipeError
                view = view[written:]
            self._input.flush()
        finally:
            view.release()

    def read_output_line(self, *, limit: int, timeout: float) -> bytes:
        """Return the agent's first standard-output line within the bound."""
        if self._reader is None:
            self._reader = Thread(target=self._read_line, args=(limit,), name="agent-ready-line", daemon=True)
            self._reader.start()
        try:
            result = self._lines.get(timeout=timeout)
        except Empty:
            raise TimeoutError from None
        if isinstance(result, BaseException):
            raise result
        return result

    def cancel_output_wait(self) -> None:
        """Wake readiness immediately; the startup owner closes and retires the tree."""
        self._notify_output(InterruptedError())

    def _notify_output(self, result: bytes | BaseException) -> None:
        with contextlib.suppress(Full):
            self._lines.put_nowait(result)

    def settled_standard_error(self, *, timeout: float) -> bytes:
        """Return the retained end of the agent's standard error once it stops writing, or at the bound."""
        return self._standard_error.settled(timeout=timeout)

    def close_input(self) -> None:
        """Close standard input once: the agent's stop signal."""
        standard_input, self._input = self._input, None
        if standard_input is not None:
            standard_input.close()

    def wait(self, *, timeout: float) -> int | None:
        """Return the agent's exit status, or ``None`` while it still runs at the bound."""
        try:
            return self._process.wait(timeout=timeout)
        except RefusalError as error:
            if error.reason is RefusalCode.DEADLINE_EXCEEDED:
                return None
            raise

    def terminate(self, *, timeout: float) -> None:
        """End every member of the job, then release the pipe ends."""
        try:
            self._scope.terminate(timeout=timeout)
        finally:
            self.close_input()
            self._output.close()
            # The drain closes its own end once the job's writers are gone.
            self._standard_error.release(timeout=_STANDARD_ERROR_RELEASE_SECONDS)

    def work_done(self) -> tuple[int, ...] | None:
        """What the whole tree has done so far, as its job accounts it; ``None`` once the job is released."""
        return self._scope.work_done()

    def contains_process_id(self, process_id: int) -> bool:
        """Whether the live process with this identifier is a member of the agent's job.

        The caller holds the process's identity steady: the runtime's transport
        retains the peer's own handle, so its identifier cannot be reused while
        the question is asked.
        """
        import pywintypes
        import win32api
        import win32con

        try:
            handle = win32api.OpenProcess(win32con.SYNCHRONIZE | 0x1000, False, process_id)
        except pywintypes.error:
            return False
        try:
            return self._scope.contains_process(int(handle))
        finally:
            win32api.CloseHandle(handle)

    def _read_line(self, limit: int) -> None:
        try:
            line = self._output.readline(limit + 1)
            if not line.endswith(b"\n") or len(line) > limit:
                raise EOFError
            self._notify_output(line)
        except BaseException as error:
            self._notify_output(error)


class WindowsAgentProcessLauncher:
    """Start each agent tree in a fresh kill-on-close job with private standard pipes."""

    def __init__(self, *, on_exit: Callable[[], None] | None = None) -> None:
        """Wake the lifecycle owner when the gateway process ends."""
        self._on_exit = on_exit

    def launch(
        self, *, executable: Path, arguments: Sequence[str], directory: Path, environment: Mapping[str, str]
    ) -> AgentProcess:
        """Start the tree; its environment is exactly the one given, with no credential in it."""
        if sys.platform != "win32":
            raise AgentHostError(AgentHostRefusal.LAUNCH_FAILED)
        sink = AgentDiagnosticSink()
        scope = WindowsProcessScope()
        try:
            process, standard_input, standard_output, standard_error = scope.launch_with_standard_pipes(
                executable=executable, arguments=arguments, directory=directory, environment=environment
            )
        except BaseException:
            scope.terminate()
            raise
        try:
            return WindowsAgentProcess(
                scope=scope,
                process=process,
                standard_input=standard_input,
                standard_output=standard_output,
                standard_error=standard_error,
                diagnostic_sink=sink,
                on_exit=self._on_exit,
            )
        except BaseException:
            # The drain could not start, so the tree has no owner: end it and release every pipe end.
            try:
                scope.terminate()
            finally:
                for stream in (standard_input, standard_output, standard_error):
                    stream.close()
            raise


def _observe_exit(waiter: WindowsOwnedProcess, wake: Callable[[], None]) -> None:
    """Retain the exact process while waiting; wake the owner to revalidate it."""
    try:
        waiter.wait(timeout=None)
    except RefusalError:
        # A failed observation also needs a fresh lifecycle decision.
        pass
    finally:
        try:
            waiter.close()
        finally:
            wake()


class _StandardOutput:
    """An invocation's standard output, read to its end or one byte past the bound."""

    def __init__(self, stream: BinaryIO, *, limit: int) -> None:
        self._stream = stream
        self._limit = limit
        self._data = bytearray()
        self._thread = Thread(target=self._read, name="agent-invocation-output", daemon=True)
        self._thread.start()

    def collected(self, *, timeout: float) -> bytes:
        """Wait for the output to end, up to the bound, and return what arrived."""
        self._thread.join(timeout)
        return bytes(self._data)

    def _read(self) -> None:
        try:
            with contextlib.suppress(OSError, ValueError):
                while len(self._data) <= self._limit:
                    chunk = self._stream.read(_STANDARD_ERROR_CHUNK_BYTES)
                    if not chunk:
                        break
                    self._data += chunk
                del self._data[self._limit + 1 :]
        finally:
            with contextlib.suppress(OSError):
                self._stream.close()


class WindowsAgentInvocationRunner:
    """Run one agent invocation in a fresh kill-on-close job and end the whole job afterwards."""

    def run(
        self,
        *,
        executable: Path,
        arguments: Sequence[str],
        directory: Path,
        environment: Mapping[str, str],
        timeout: float,
        output_limit: int,
    ) -> AgentInvocationResult:
        """Start the tree with no standard input, wait for it to the bound, then end every member.

        A tree still running at the bound is ended and reported with no
        status. Recognized diagnostics on standard error reach the application log. A job whose end
        cannot be confirmed raises, so the caller learns nothing it could take
        for an outcome.
        """
        if sys.platform != "win32":
            raise AgentHostError(AgentHostRefusal.LAUNCH_FAILED)
        scope = WindowsProcessScope()
        try:
            process, standard_input, standard_output, standard_error = scope.launch_with_standard_pipes(
                executable=executable, arguments=arguments, directory=directory, environment=environment
            )
        except BaseException:
            scope.terminate()
            raise
        streams = (standard_input, standard_output, standard_error)
        try:
            standard_input.close()
            errors = _StandardErrorTail(
                standard_error,
                limit=STANDARD_ERROR_TAIL_BYTES,
                diagnostics=AgentDiagnosticLines(AgentDiagnosticSink(), pid=process.pid, cli=True),
            )
            output = _StandardOutput(standard_output, limit=output_limit)
            try:
                status: int | None = process.wait(timeout=timeout)
            except RefusalError as error:
                if error.reason is not RefusalCode.DEADLINE_EXCEEDED:
                    raise
                status = None
            # The job ends whether or not the invocation exited: a descendant may still hold the stores.
            scope.terminate(timeout=_INVOCATION_TERMINATE_SECONDS)
            collected = output.collected(timeout=_OUTPUT_SETTLE_SECONDS)
            errors.release(timeout=_STANDARD_ERROR_RELEASE_SECONDS)
            return AgentInvocationResult(status=status, standard_output=collected if status is not None else b"")
        except BaseException:
            try:
                scope.terminate(timeout=_INVOCATION_TERMINATE_SECONDS)
            finally:
                for stream in streams:
                    with contextlib.suppress(OSError):
                        stream.close()
            raise

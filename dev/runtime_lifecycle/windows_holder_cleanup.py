"""Retain and settle a Windows holder's job, streams and pipe threads."""

from __future__ import annotations

from queue import Queue
from threading import Event, Lock, Thread
from typing import BinaryIO

from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.windows_owned_process import WindowsOwnedProcess
from cadrumo_client.transport.windows_process import WindowsProcessScope

from .caller_owned_root import AcceptanceError

_CLOSE_SECONDS = 10.0
_REAP_SECONDS = 10.0


class WindowsHolderCleanup:
    """Own native job containment and all pipe cleanup state."""

    def __init__(self) -> None:
        """Initialize retained resources before any native launch."""
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

    def _terminate_scope(self) -> None:
        """Terminate the exact Windows job before any blocked pipe is closed."""
        scope = self._scope
        if scope is None:
            return
        self._scope_termination_attempted = True
        scope.terminate(timeout=_REAP_SECONDS)
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
        writer_alive, scope_failed_before_pipe_close = self._prepare_close_writer(failures)
        self._close_input_and_wait(writer_alive, failures)
        scope_settled = self._settle_close_scope(scope_failed_before_pipe_close, failures)
        streams_settled, threads_settled = self._close_output_threads(failures)
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

    def _prepare_close_writer(self, failures: list[BaseException]) -> tuple[bool, bool]:
        """Stop an active writer before touching its owned pipe."""
        writer = self._writer_thread
        writer_alive = writer is not None and writer.is_alive()
        scope_failed_before_pipe_close = False
        if writer_alive and self._scope is not None:
            try:
                self._terminate_scope()
            except BaseException as error:
                failures.append(error)
                scope_failed_before_pipe_close = True
        if writer is not None and writer_alive and self._scope is None:
            writer.join(timeout=_CLOSE_SECONDS)
            if writer.is_alive():
                failures.append(AcceptanceError("runtime holder input writer did not stop after job termination"))
            else:
                self._writer_thread = None
                writer_alive = False

        return writer_alive, scope_failed_before_pipe_close

    def _close_input_and_wait(self, writer_alive: bool, failures: list[BaseException]) -> None:
        """Close stdin only after its writer ends, then give the process grace."""
        if self._stdin is not None and not self._stdin.closed and not writer_alive:
            try:
                self._stdin.close()
            except BaseException as error:
                failures.append(error)

        if self._process is not None and not self._scope_termination_attempted:
            try:
                self._process.wait(timeout=_CLOSE_SECONDS)
            except RefusalError as error:
                if error.reason != RefusalCode.TIMEOUT:
                    failures.append(error)

    def _settle_close_scope(self, failed: bool, failures: list[BaseException]) -> bool:
        """Retain failed job containment and report whether the scope settled."""
        scope_settled = self._scope is None
        if self._scope is not None and not failed:
            try:
                self._terminate_scope()
                scope_settled = True
            except BaseException as error:
                failures.append(error)

        return scope_settled

    def _close_output_threads(self, failures: list[BaseException]) -> tuple[bool, bool]:
        """Close output pipes and join every retained pipe thread."""
        self._close_output_pipes(failures)
        self._join_pipe_threads(failures)
        streams_settled = all(stream is None or stream.closed for stream in (self._stdin, self._stdout, self._stderr))
        threads_settled = all(
            thread is None or not thread.is_alive()
            for thread in (self._writer_thread, self._stdout_thread, self._stderr_thread)
        )
        return streams_settled, threads_settled

    def _close_output_pipes(self, failures: list[BaseException]) -> None:
        for stream in (self._stdout, self._stderr):
            if stream is not None and not stream.closed:
                try:
                    stream.close()
                except BaseException as error:
                    failures.append(error)

    def _join_pipe_threads(self, failures: list[BaseException]) -> None:
        for thread in (self._writer_thread, self._stdout_thread, self._stderr_thread):
            if thread is not None and thread.ident is not None:
                thread.join(timeout=_CLOSE_SECONDS)
                if thread.is_alive():
                    failures.append(AcceptanceError(f"runtime holder pipe thread {thread.name} did not stop"))
                elif thread is self._writer_thread:
                    self._writer_thread = None

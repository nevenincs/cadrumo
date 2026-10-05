"""Carry the supervisor protocol over the launching process's standard streams.

Under ``--supervised`` the runtime moves the protocol input and output to
private non-inheritable descriptors and leaves descriptors 0, 1 and 2 on the
null device, so a descendant or a native write can neither read nor corrupt
the channel. Python-level diagnostics reach only the redacted log.

Protocol writes run on one writer thread behind a bounded queue: serving
threads never block on the supervisor, and a broken pipe disables the
channel without ending the runtime. End of input means the supervisor is
gone; the runtime keeps serving.
"""

from __future__ import annotations

import io
import logging
import os
import sys
import threading
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from queue import Full, Queue
from threading import Event, Lock, Thread
from types import TracebackType
from typing import Protocol

from ...application.runtime.contracts import RuntimeExitReason
from .shutdown import RuntimeStop
from .supervised_protocol import (
    RuntimeAnnouncement,
    RuntimeBusy,
    RuntimeHeartbeat,
    RuntimeReady,
    RuntimeRefused,
    RuntimeStopping,
    SupervisorCommand,
    SupervisorLineError,
    SupervisorLineFraming,
    SupervisorLineRefusal,
    SupervisorPing,
    SupervisorStop,
    SupervisorStopIfIdle,
    decode_supervisor_command,
    encode_runtime_announcement,
)

_READ_CHUNK_BYTES = 4096
_QUEUE_LIMIT = 64
_IDLE_FENCE_SECONDS = 1.0
_FINAL_FLUSH_SECONDS = 1.0

type _CommandHandler = Callable[[SupervisorCommand], None]


@dataclass(frozen=True, slots=True)
class SupervisorStreams:
    """Private duplicates of the launch streams; ``None`` when one was not open."""

    commands: int | None
    announcements: int | None


class SupervisedServing(Protocol):
    """The transport facts a heartbeat reports."""

    @property
    def ready(self) -> Event:
        """Return the event set once the listener owns the endpoint."""
        ...

    def accept_tick_age(self) -> float | None:
        """Return seconds since the accept loop last turned."""
        ...

    def open_connection_count(self) -> int:
        """Return the number of open verified connections."""
        ...


class SupervisedProfiles(Protocol):
    """The profile facts a heartbeat reports and the idle-only stop."""

    def hosted_profile_count(self) -> int:
        """Return the number of profile hosts."""
        ...

    def stop_if_idle(self, reason: RuntimeExitReason, *, timeout: float) -> bool:
        """Stop only when no profile worker exists."""
        ...


def _private_duplicate(descriptor: int) -> int | None:
    try:
        # os.dup returns a non-inheritable descriptor (and Windows handle).
        return os.dup(descriptor)
    except OSError:
        return None


def _point_windows_standard_handles_at_null() -> None:
    if sys.platform != "win32":
        return
    import ctypes
    import msvcrt
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    set_standard_handle = kernel.SetStdHandle
    set_standard_handle.argtypes = (wintypes.DWORD, wintypes.HANDLE)
    set_standard_handle.restype = wintypes.BOOL
    # Invariant: each handle stays owned by C runtime descriptor 0, 1 or 2,
    # which now names the null device and is never closed or replaced again,
    # so the process standard handles cannot dangle or name a reused object.
    # STD_INPUT_HANDLE, STD_OUTPUT_HANDLE and STD_ERROR_HANDLE as DWORD values.
    for descriptor, standard in ((0, 0xFFFFFFF6), (1, 0xFFFFFFF5), (2, 0xFFFFFFF4)):
        # A child started without explicit redirection receives these handles,
        # whatever the C runtime descriptors say.
        if not set_standard_handle(standard, msvcrt.get_osfhandle(descriptor)):
            raise ctypes.WinError(ctypes.get_last_error())


def take_supervisor_streams() -> SupervisorStreams:
    """Move the protocol streams to private descriptors and silence fd 0, 1 and 2.

    Run this before anything can start a child. Afterwards stdin reads end of
    file, stdout and stderr discard, and ``sys`` streams write to the null
    device, so a final flush cannot fail and no raw text reaches the launcher.
    """
    for stream in (sys.stdout, sys.stderr):
        if stream is not None:
            with suppress(OSError, ValueError):
                stream.flush()
    streams = SupervisorStreams(commands=_private_duplicate(0), announcements=_private_duplicate(1))
    null = os.open(os.devnull, os.O_RDWR)
    try:
        for descriptor in (0, 1, 2):
            os.dup2(null, descriptor, inheritable=True)
    finally:
        os.close(null)
    _point_windows_standard_handles_at_null()
    sys.stdin = _null_text_stream(0, "r")
    sys.stdout = _null_text_stream(1, "w")
    sys.stderr = _null_text_stream(2, "w")
    return streams


def _null_text_stream(descriptor: int, mode: str) -> io.TextIOWrapper:
    # The process-lifetime stream borrows a descriptor that now names the null
    # device; closing the stream never closes the standard descriptor.
    return io.TextIOWrapper(io.FileIO(descriptor, mode, closefd=False), encoding="utf-8", errors="replace")


def route_diagnostics_to_redacted_logging(logger: logging.Logger) -> None:
    """Send uncaught, unraisable and warning diagnostics through the scrubbed log handlers."""

    def uncaught(kind: type[BaseException], value: BaseException, traceback: TracebackType | None) -> None:
        logger.error("uncaught runtime exception", exc_info=(kind, value, traceback))

    def uncaught_in_thread(arguments: threading.ExceptHookArgs) -> None:
        if arguments.exc_type is SystemExit:
            return
        name = arguments.thread.name if arguments.thread is not None else "unknown"
        _log_failure(logger, f"uncaught exception in runtime thread {name}", arguments.exc_type, arguments.exc_value)

    def unraisable(arguments: sys.UnraisableHookArgs) -> None:
        message = f"unraisable runtime exception: {arguments.err_msg or 'Exception ignored'}"
        _log_failure(logger, message, arguments.exc_type, arguments.exc_value)

    sys.excepthook = uncaught
    threading.excepthook = uncaught_in_thread
    sys.unraisablehook = unraisable
    # Warnings then reach the 'py.warnings' logger and its scrubbing handlers.
    logging.captureWarnings(True)


def _log_failure(logger: logging.Logger, message: str, kind: type[BaseException], value: BaseException | None) -> None:
    if value is None:
        logger.error("%s: %s", message, kind.__name__)
    else:
        logger.error("%s", message, exc_info=value)


class SupervisorChannel:
    """Bounded announcement writer and command reader over private descriptors."""

    def __init__(self, streams: SupervisorStreams, *, logger: logging.Logger) -> None:
        """Bind the private descriptors; no thread runs until :meth:`start`."""
        self._streams, self._logger = streams, logger
        self._queue: Queue[bytes | None] = Queue(maxsize=_QUEUE_LIMIT)
        self._enabled = Event()
        if streams.announcements is not None:
            self._enabled.set()
        self.supervisor_gone = Event()
        self._writer = Thread(target=self._write_announcements, name="runtime-supervisor-writer", daemon=True)

    def start(self, handle: _CommandHandler) -> None:
        """Start writing announcements and reading commands for ``handle``."""
        self._writer.start()
        Thread(target=self._read_commands, args=(handle,), name="runtime-supervisor-reader", daemon=True).start()

    def announce(self, message: RuntimeAnnouncement) -> None:
        """Queue one announcement without blocking; drop it when the channel cannot take it."""
        if not self._enabled.is_set():
            return
        try:
            self._queue.put_nowait(encode_runtime_announcement(message))
        except Full:
            self._logger.warning("supervisor announcement dropped: channel queue full")

    @property
    def logger(self) -> logging.Logger:
        """Return the redacted logger that receives this channel's diagnostics."""
        return self._logger

    def close(self, *, timeout: float) -> None:
        """Let queued announcements drain for at most ``timeout`` seconds."""
        try:
            self._queue.put(None, timeout=timeout)
        except Full:
            return
        if self._writer.ident is not None:
            self._writer.join(timeout=timeout)

    def _write_announcements(self) -> None:
        descriptor = self._streams.announcements
        while (line := self._queue.get()) is not None:
            if descriptor is None or not self._enabled.is_set():
                continue
            try:
                view = memoryview(line)
                while view:
                    view = view[os.write(descriptor, view) :]
            except OSError:
                # A reader that went away must never become an exit code.
                self._enabled.clear()
                self._logger.info("supervisor announcement channel closed; serving continues")

    def _read_commands(self, handle: _CommandHandler) -> None:
        descriptor = self._streams.commands
        framing = SupervisorLineFraming()
        while descriptor is not None:
            try:
                chunk = os.read(descriptor, _READ_CHUNK_BYTES)
            except OSError:
                chunk = b""
            if not chunk:
                break
            for line in framing.feed(chunk):
                self._dispatch(handle, line)
        self.supervisor_gone.set()
        self._logger.info("supervisor command channel ended; serving continues")

    def _dispatch(self, handle: _CommandHandler, line: bytes | SupervisorLineRefusal) -> None:
        if isinstance(line, SupervisorLineRefusal):
            self.announce(RuntimeRefused(code=line))
            return
        try:
            command = decode_supervisor_command(line)
        except SupervisorLineError as error:
            self.announce(RuntimeRefused(code=error.reason))
            return
        try:
            handle(command)
        except Exception as error:
            self._logger.error("supervisor command failed", exc_info=error)


class SupervisedRuntime:
    """Answer one launching supervisor for the lifetime of this runtime process."""

    def __init__(self, stop: RuntimeStop, channel: SupervisorChannel) -> None:
        """Bind the runtime's stop latch; serving facts arrive with :meth:`attach`."""
        self._stop, self._channel = stop, channel
        self._serving: SupervisedServing | None = None
        self._profiles: SupervisedProfiles | None = None
        self._announced = Lock()
        self._stopping_sent = False

    def start(self) -> None:
        """Start the channel and announce a stop as soon as one is requested."""
        self._channel.start(self._handle)
        Thread(target=self._announce_stop, name="runtime-supervisor-stop", daemon=True).start()

    def attach(
        self,
        serving: SupervisedServing,
        *,
        profiles: SupervisedProfiles,
        ready: RuntimeReady,
        publish_boot_record: Callable[[], bool],
    ) -> None:
        """Publish the boot record, then report ``ready``, once ``serving`` owns the endpoint.

        Heartbeats are served from ``serving`` from now on. ``publish_boot_record``
        returns False when the record may no longer be published; a failure to
        publish ends the runtime instead of reporting ``ready``.
        """
        self._serving, self._profiles = serving, profiles
        Thread(
            target=self._announce_ready,
            args=(serving, ready, publish_boot_record),
            name="runtime-supervisor-ready",
            daemon=True,
        ).start()

    def finish(self, exit_code: int) -> None:
        """Announce the final reason unless a stop already did, then drain briefly."""
        if exit_code in RuntimeExitReason:
            self._send_stopping(RuntimeExitReason(exit_code))
        self._channel.close(timeout=_FINAL_FLUSH_SECONDS)

    def _announce_ready(
        self, serving: SupervisedServing, ready: RuntimeReady, publish_boot_record: Callable[[], bool]
    ) -> None:
        while not self._stop.is_set():
            if serving.ready.wait(0.05):
                with self._announced:
                    if not self._stopping_sent and self._published(publish_boot_record):
                        self._channel.announce(ready)
                return

    def _published(self, publish_boot_record: Callable[[], bool]) -> bool:
        try:
            return publish_boot_record()
        except Exception as error:
            # A supervisor must never adopt a runtime whose identity claim is missing.
            self._channel.logger.error("runtime boot record was not published", exc_info=error)
            self._stop.request(RuntimeExitReason.UNEXPECTED_FAILURE)
            return False

    def _announce_stop(self) -> None:
        self._stop.wait()
        reason = self._stop.reason
        # A bare set names no reason yet; the final exit code supplies it.
        if reason is not None:
            self._send_stopping(reason)

    def _send_stopping(self, reason: RuntimeExitReason) -> None:
        with self._announced:
            if self._stopping_sent:
                return
            self._stopping_sent = True
            self._channel.announce(RuntimeStopping(reason=reason))

    def _handle(self, command: SupervisorCommand) -> None:
        if isinstance(command, SupervisorPing):
            if not self._channel.supervisor_gone.is_set():
                self._channel.announce(self._heartbeat(command.seq))
        elif isinstance(command, SupervisorStop):
            self._stop.request(RuntimeExitReason.SUPERVISOR_STOP)
        elif isinstance(command, SupervisorStopIfIdle):
            self._stop_if_idle()
        else:
            self._end_session()

    def _heartbeat(self, seq: int) -> RuntimeHeartbeat:
        serving, profiles = self._serving, self._profiles
        age = None if serving is None else serving.accept_tick_age()
        return RuntimeHeartbeat(
            seq=seq,
            tick_age_ms=None if age is None else int(age * 1000),
            frontends=0 if serving is None else serving.open_connection_count(),
            hosted_profiles=0 if profiles is None else profiles.hosted_profile_count(),
        )

    def _stop_if_idle(self) -> None:
        profiles = self._profiles
        # Before attachment no transport serves, so no profile can be hosted.
        if profiles is None:
            self._stop.request(RuntimeExitReason.SUPERVISOR_STOP)
        elif not profiles.stop_if_idle(RuntimeExitReason.SUPERVISOR_STOP, timeout=_IDLE_FENCE_SECONDS):
            self._channel.announce(RuntimeBusy())

    def _end_session(self) -> None:
        # The normal drain stands in until the ordered session-end settle
        # replaces this seam; only the exit reason distinguishes it today.
        self._stop.request(RuntimeExitReason.SESSION_END_SETTLE)

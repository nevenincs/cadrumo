"""One service-owned login process; pipes and browser actions are never logged."""

from __future__ import annotations

import contextlib
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Event, Lock, Thread
from typing import BinaryIO
from uuid import uuid4

from pydantic import JsonValue

from cadrumo.core.logging import get_logger
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.windows_process import (
    WindowsOwnedProcess,
    WindowsProcessScope,
    unreturned_windows_process_scope,
)

from .auth_protocol import MAX_AUTH_LINE, TERMINAL_EVENTS, AuthProtocol, snapshot
from .credential_frame import wipe

_LOGGER = get_logger(__name__)


class AuthAttempt:
    """Own the helper until its whole job is gone, including after host loss."""

    def __init__(
        self,
        *,
        provider: str,
        lane: str,
        executable: Path,
        arguments: Sequence[str],
        directory: Path,
        environment: Mapping[str, str],
        valid: Callable[[], bool],
        settled: Callable[[], None] | None = None,
        prepare: Callable[[], None] | None = None,
    ) -> None:
        """Launch one bounded worker with the caller's exact authority predicate.

        ``prepare`` runs on the attempt's own thread before the helper starts,
        while the attempt reads ``starting``: work such as retiring the agent's
        tree, which takes longer than the request that began the attempt may
        wait. A failure in it ends the attempt as a failed cleanup.
        """
        self.id = str(uuid4())
        self._lane = lane
        self._protocol = AuthProtocol(provider)
        self._executable = executable
        self._arguments = arguments
        self._directory = directory
        self._environment = environment
        self._valid = valid
        self._settled = settled
        self._prepare = prepare
        self._lock = Lock()
        self._cancel = Event()
        self._done = Event()
        self._clean = False
        self._scope: WindowsProcessScope | None = None
        self._input: BinaryIO | None = None
        self._readers: list[Thread] = []
        self._observed = time.monotonic()
        self._deadline: float | None = None
        self._snapshot = snapshot(self.id, lane, "starting")
        self._thread = Thread(target=self._run, name="provider-sign-in", daemon=True)
        self._thread.start()

    @property
    def active(self) -> bool:
        """Unconfirmed cleanup retains ownership even after the worker ends."""
        return not self._done.is_set() or not self._clean

    def observe(self) -> dict[str, JsonValue]:
        """A live dialog renews only its helper watchdog, never person authority."""
        if not self._valid():
            self.cancel()
            return snapshot(self.id, self._lane, "cancelled")
        with self._lock:
            self._observed = time.monotonic()
            return dict(self._snapshot)

    def cancel(self) -> None:
        """Request bounded cleanup and immediately withdraw any browser action."""
        with self._lock:
            self._cancel.set()
            self._snapshot.pop("url", None)
            self._snapshot.pop("user_code", None)

    def submit_code(self, code: bytearray) -> dict[str, JsonValue]:
        """Submit once to this live attempt, never retaining or returning the code."""
        if not code or len(code) > 2048 or any(byte < 33 or byte > 126 for byte in code):
            raise ValueError("invalid_request")
        # JSON escaping can make a printable code exceed the helper's line limit.
        line = bytearray(b'{"version":1,"action":"auth_code","code":"')
        try:
            for byte in code:
                if byte in (34, 92):
                    line.append(92)
                line.append(byte)
            line.extend(b'"}\n')
            if len(line) > 4096:
                raise ValueError("invalid_request")
            with self._lock:
                valid = self._valid()
                now = time.monotonic()
                if (
                    self._cancel.is_set()
                    or not valid
                    or self._deadline is None
                    or now >= self._deadline
                    or now - self._observed > 15
                    or self._snapshot.get("event") != "authorization_code_required"
                    or self._input is None
                ):
                    raise ValueError("invalid_request")
                # Consume the opportunity before writing: a partial write cannot be replayed.
                self._snapshot = snapshot(self.id, self._lane, "started")
                self._protocol.code_submitted = True
                try:
                    if self._input.write(line) != len(line):
                        raise OSError("short_auth_write")
                    self._input.flush()
                except (OSError, ValueError):
                    self._cancel.set()
                    raise ValueError("invalid_request") from None
                self._observed = time.monotonic()
                return dict(self._snapshot)
        finally:
            wipe(line)

    def close(self) -> None:
        """Confirm cleanup before the caller releases the profile reservation."""
        self.cancel()
        self._thread.join(12)
        if self._done.is_set() and not self._clean:
            try:
                self._retire_scope()
                self._settle_readers()
                self._clean = True
            except Exception:
                raise RuntimeError("auth_cleanup_unconfirmed") from None
        if self.active:
            raise RuntimeError("auth_cleanup_unconfirmed")

    def _retire_scope(self) -> None:
        # A failed native termination retains its job handles for a later retry.
        # Keep that owner on the attempt, never only in the worker's local frame.
        if self._scope is not None:
            self._scope.terminate(timeout=3)
            self._scope = None

    def _settle_readers(self) -> None:
        for reader in self._readers:
            reader.join(1)
        if any(reader.is_alive() for reader in self._readers):
            raise RuntimeError("auth_pipe_cleanup_unconfirmed")

    def _publish(self, value: dict[str, JsonValue]) -> None:
        with self._lock:
            if self._cancel.is_set():
                value.pop("url", None)
                value.pop("user_code", None)
            self._snapshot = value

    @staticmethod
    def _read(stream: BinaryIO, queue: Queue[bytes | None]) -> None:
        try:
            while True:
                line = stream.readline(MAX_AUTH_LINE + 1)
                queue.put_nowait(line or None)
                if not line or len(line) > MAX_AUTH_LINE or not line.endswith(b"\n"):
                    return
        except (OSError, ValueError, Full):
            with contextlib.suppress(Empty):
                queue.get_nowait()
            with contextlib.suppress(Full):
                queue.put_nowait(None)
        finally:
            with contextlib.suppress(OSError, ValueError):
                stream.close()

    @staticmethod
    def _discard(stream: BinaryIO) -> None:
        with stream, contextlib.suppress(OSError, ValueError):
            while stream.read(4096):
                pass

    @staticmethod
    def _wait(process: WindowsOwnedProcess, timeout: float) -> int | None:
        try:
            return process.wait(timeout=timeout)
        except RefusalError as error:
            if error.reason is RefusalCode.DEADLINE_EXCEEDED:
                return None
            raise

    def _exchange(self, input_stream: BinaryIO, queue: Queue[bytes | None]) -> tuple[str, str | None]:
        deadline = time.monotonic() + 305
        with self._lock:
            self._deadline = deadline
        checked = 0.0
        while True:
            now = time.monotonic()
            with self._lock:
                observed = self._observed
            if now >= checked:
                if not self._valid():
                    self.cancel()
                checked = now + 1
            if self._cancel.is_set() or now - observed > 15:
                with self._lock, contextlib.suppress(OSError, ValueError):
                    input_stream.write(b'{"version":1,"action":"cancel"}\n')
                    input_stream.flush()
                return "cancelled", "host_disconnected" if not self._cancel.is_set() else None
            if now >= deadline:
                self._publish(snapshot(self.id, self._lane, "started"))
                return "failed", "timeout"
            try:
                raw = queue.get(timeout=0.25)
            except Empty:
                continue
            with self._lock:
                try:
                    # EOF follows the same invalidation path as malformed output.
                    event = self._protocol.read(raw if raw is not None else b"")
                except BaseException:
                    self._cancel.set()
                    self._snapshot = snapshot(self.id, self._lane, "started")
                    raise
                if event.event in TERMINAL_EVENTS:
                    # A submitter must not see code-entry state after terminal input.
                    self._snapshot = snapshot(self.id, self._lane, "started")
            if event.event == "ready":
                input_stream.write(b'{"version":1,"action":"start"}\n')
                input_stream.flush()
            elif event.event in TERMINAL_EVENTS:
                return event.event, event.reason
            else:
                value = snapshot(self.id, self._lane, event.event)
                if event.url is not None:
                    value["url"] = event.url
                if event.user_code is not None:
                    value["user_code"] = event.user_code
                if event.event == "authorization_code_required":
                    with self._lock:
                        url = self._snapshot.get("url")
                    if url is not None:
                        value["url"] = url
                # Never disclose a stale profile action, including a queued one.
                if not self._valid():
                    self.cancel()
                    return "cancelled", None
                self._publish(value)

    def _run(self) -> None:
        process: WindowsOwnedProcess | None = None
        input_stream: BinaryIO | None = None
        outcome, reason = "failed", "provider_error"
        try:
            if not self._valid() or self._cancel.is_set():
                outcome, reason = "cancelled", None
                return
            if self._prepare is not None:
                try:
                    self._prepare()
                except BaseException:
                    outcome, reason = "failed", "cleanup_failed"
                    return
                if not self._valid() or self._cancel.is_set():
                    outcome, reason = "cancelled", None
                    return
            try:
                self._scope = WindowsProcessScope()
            except BaseException as error:
                self._scope = unreturned_windows_process_scope(error)
                raise
            process, input_stream, output, errors = self._scope.launch_with_standard_pipes(
                executable=self._executable,
                arguments=self._arguments,
                directory=self._directory,
                environment=self._environment,
            )
            with self._lock:
                self._input = input_stream
            queue: Queue[bytes | None] = Queue(maxsize=8)
            self._readers = [
                Thread(target=self._read, args=(output, queue), daemon=True),
                Thread(target=self._discard, args=(errors,), daemon=True),
            ]
            for reader in self._readers:
                reader.start()
            outcome, reason = self._exchange(input_stream, queue)
        except BaseException:
            # The exception may contain pipe or provider contents; never retain it.
            outcome, reason = "failed", "provider_error"
        finally:
            try:
                try:
                    if input_stream is not None:
                        with self._lock:
                            self._input = None
                        with contextlib.suppress(OSError, ValueError):
                            input_stream.close()
                    if process is not None:
                        status = self._wait(process, 3)
                        if outcome == "succeeded" and status != 0:
                            outcome, reason = "failed", "provider_error"
                except Exception:
                    outcome, reason = "failed", "provider_error"
                finally:
                    # Even a failed wait or pipe close must retire the whole job.
                    self._retire_scope()
                self._settle_readers()
                self._clean = True
                if outcome == "succeeded" and (self._cancel.is_set() or not self._valid()):
                    outcome, reason = "cancelled", None
            except Exception:
                outcome, reason = "failed", "cleanup_failed"
            self._publish(snapshot(self.id, self._lane, outcome, reason=reason))
            self._done.set()
            _LOGGER.info(
                "provider sign-in settled provider=%s event=%s reason=%s cleanup_confirmed=%s",
                self._lane,
                outcome,
                reason or "none",
                self._clean,
            )
            if self._settled is not None:
                self._settled()

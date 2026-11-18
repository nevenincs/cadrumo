"""One service-owned login process; pipes and browser actions are never logged."""

from __future__ import annotations

import contextlib
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Lock, Thread
from typing import BinaryIO
from uuid import uuid4

from pydantic import JsonValue

from cadrumo.core.logging import get_logger
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.windows_owned_process import WindowsOwnedProcess
from cadrumo_client.transport.windows_process import WindowsProcessScope, unreturned_windows_process_scope

from ..providers.application.contracts import HelperCause, ServiceCause
from .auth_protocol import TERMINAL_EVENTS, AuthEvent, AuthProtocol, append_auth_code, read_event_lines, snapshot
from .credential_frame import wipe
from .sign_in_refusal import log_settlement, new_log_ref

_LOGGER = get_logger(__name__)

EXCHANGE_SECONDS = 305
"""The bound on one helper exchange: a little past the helper's own 300 second login timeout."""

_Settlement = tuple[str, str | None, HelperCause | ServiceCause | None]
"""An outcome event, its reason and its cause."""

_WITHDRAWN: _Settlement = ("cancelled", "profile_required", "profile_signed_out")
"""An attempt whose profile authority ended under it: said as such, never as the person's own cancellation."""

_ACTIVE_EVENTS = frozenset({"starting", "started", "browser_action", "authorization_code_required"})


class HelperStreamError(ValueError):
    """The helper's stream broke the protocol; carries only the service's closed cause word."""

    def __init__(self, cause: ServiceCause) -> None:
        """Keep the cause beside the content-free message."""
        super().__init__("invalid_auth_event")
        self.cause: ServiceCause = cause


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
        confirm: Callable[[], tuple[bool, str | None]] | None = None,
    ) -> None:
        """Launch one bounded worker with the caller's exact authority predicate.

        ``prepare`` runs on the attempt's own thread before the helper starts,
        while the attempt reads ``starting``: work such as retiring the agent's
        tree, which takes longer than the request that began the attempt may
        wait. A failure in it ends the attempt as a failed cleanup.

        ``confirm`` runs on the attempt's own thread once the helper reported
        success and its job is gone. It answers whether the provider now reads
        as signed in, with the cause when it does not; a success it does not
        confirm is served as a failure.
        """
        self.id = str(uuid4())
        self.log_ref = new_log_ref()
        self.lane = lane
        self._stderr_bytes = 0
        self._exit_status: int | None = None
        self._errors: list[str] = []
        self._lane = lane
        self._protocol = AuthProtocol(provider)
        self._executable = executable
        self._arguments = arguments
        self._directory = directory
        self._environment = environment
        self._valid = valid
        self._settled = settled
        self._prepare = prepare
        self._confirm = confirm
        self._lock = Lock()
        self._cancel = Event()
        self._withdrawn = False
        self._done = Event()
        self._clean = False
        self._scope: WindowsProcessScope | None = None
        self._input: BinaryIO | None = None
        self._readers: list[Thread] = []
        self._observed = time.monotonic()
        self._began = self._reached_at = self._observed
        self._reached = "starting"
        self._deadline: float | None = None
        self._snapshot = snapshot(self.id, lane, "starting")
        self._thread = Thread(target=self._run, name="provider-sign-in", daemon=True)
        self._thread.start()

    @property
    def active(self) -> bool:
        """Unconfirmed cleanup retains ownership even after the worker ends."""
        return not self._done.is_set() or not self._clean

    @property
    def finished(self) -> bool:
        """Whether the worker has ended and served its outcome, whether or not its cleanup is confirmed."""
        return self._done.is_set()

    def observe(self) -> dict[str, JsonValue]:
        """A live dialog renews only its helper watchdog, never person authority."""
        if not self._valid():
            self._withdraw()
            event, reason, cause = _WITHDRAWN
            return snapshot(self.id, self._lane, event, reason=reason, cause=cause, log_ref=self.log_ref)
        with self._lock:
            self._observed = time.monotonic()
            return dict(self._snapshot)

    def cancel(self) -> None:
        """Request bounded cleanup and immediately withdraw any browser action."""
        with self._lock:
            self._cancel.set()
            self._snapshot.pop("url", None)
            self._snapshot.pop("user_code", None)

    def _withdraw(self) -> None:
        """Cancel because the profile authority the attempt was started under has ended."""
        with self._lock:
            self._withdrawn = True
        self.cancel()

    def _cancelled(self) -> _Settlement:
        """The cancellation as it happened: lost authority names itself; the person's own has no reason."""
        with self._lock:
            withdrawn = self._withdrawn
        return _WITHDRAWN if withdrawn else ("cancelled", None, None)

    def _held(self) -> bool:
        """Whether neither a cancellation nor lost authority has ended the attempt; lost authority is noted."""
        if self._cancel.is_set():
            return False
        if not self._valid():
            self._withdraw()
            return False
        return True

    def submit_code(self, code: bytearray) -> dict[str, JsonValue]:
        """Submit once to this live attempt, never retaining or returning the code."""
        if not code or len(code) > 2048 or any(byte < 33 or byte > 126 for byte in code):
            raise ValueError("invalid_request")
        # JSON escaping can make a printable code exceed the helper's line limit.
        line = bytearray(b'{"version":1,"action":"auth_code","code":"')
        try:
            append_auth_code(line, code)
            with self._lock:
                input_stream = self._code_input()
                # Consume the opportunity before writing: a partial write cannot be replayed.
                self._snapshot = snapshot(self.id, self._lane, "started")
                self._protocol.code_submitted = True
                try:
                    if input_stream.write(line) != len(line):
                        raise OSError("short_auth_write")
                    input_stream.flush()
                except (OSError, ValueError):
                    self._cancel.set()
                    raise ValueError("invalid_request") from None
                self._observed = time.monotonic()
                return dict(self._snapshot)
        finally:
            wipe(line)

    def _code_input(self) -> BinaryIO:
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
        return self._input

    def close(self) -> None:
        """Confirm cleanup before the caller releases the profile reservation."""
        self.cancel()
        self._thread.join(12)
        if self._done.is_set() and not self._clean:
            try:
                self._retire_scope()
                self._settle_readers()
                self._clean = True
            except Exception as error:
                _LOGGER.warning(
                    "provider sign-in cleanup retry unconfirmed provider=%s error_class=%s log_ref=%s",
                    self._lane,
                    type(error).__name__,
                    self.log_ref,
                )
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
            event = value.get("event")
            if isinstance(event, str) and event in _ACTIVE_EVENTS and event != self._reached:
                self._reached = event
                self._reached_at = time.monotonic()

    def _discard(self, stream: BinaryIO) -> None:
        """Drain the helper's error output unread: it may hold secrets, so only its size is kept."""
        with stream, contextlib.suppress(OSError, ValueError):
            while chunk := stream.read(4096):
                self._stderr_bytes += len(chunk)

    def _note(self, stage: str, error: BaseException) -> None:
        """Keep a swallowed exception's stage and class name for the settle line; never its message."""
        self._errors.append(f"{stage}:{type(error).__name__}")

    @staticmethod
    def _wait(process: WindowsOwnedProcess, timeout: float) -> int | None:
        try:
            return process.wait(timeout=timeout)
        except RefusalError as error:
            if error.reason is RefusalCode.TIMEOUT:
                return None
            raise

    def _exchange(self, input_stream: BinaryIO, queue: Queue[bytes | None]) -> _Settlement:
        deadline = time.monotonic() + EXCHANGE_SECONDS
        with self._lock:
            self._deadline = deadline
        checked = 0.0
        while True:
            now = time.monotonic()
            with self._lock:
                observed = self._observed
            checked = self._recheck_scope(now, checked)
            if self._cancel.is_set() or now - observed > 15:
                return self._cancel_exchange(input_stream)
            if now >= deadline:
                self._publish(snapshot(self.id, self._lane, "started"))
                return "failed", "timeout", "timed_out"
            event = self._next_event(queue)
            if event is None:
                continue
            settlement = self._answer_event(input_stream, event)
            if settlement is not None:
                return settlement

    def _next_event(self, queue: Queue[bytes | None]) -> AuthEvent | None:
        """Read the helper's next event, or nothing when none arrived within the poll."""
        try:
            raw = queue.get(timeout=0.25)
        except Empty:
            return None
        try:
            return self._read_event(raw)
        except ValueError:
            raise HelperStreamError("helper_ended_without_result" if raw is None else "helper_output_invalid") from None

    def _answer_event(self, input_stream: BinaryIO, event: AuthEvent) -> _Settlement | None:
        """Act on one event; a settlement ends the exchange."""
        if event.event == "ready":
            input_stream.write(b'{"version":1,"action":"start"}\n')
            input_stream.flush()
            return None
        if event.event in TERMINAL_EVENTS:
            return event.event, event.reason, event.cause
        if not self._publish_action(event):
            return self._cancelled()
        return None

    def _recheck_scope(self, now: float, checked: float) -> float:
        if now >= checked:
            if not self._valid():
                self._withdraw()
            return now + 1
        return checked

    def _cancel_exchange(self, input_stream: BinaryIO) -> _Settlement:
        with self._lock, contextlib.suppress(OSError, ValueError):
            input_stream.write(b'{"version":1,"action":"cancel"}\n')
            input_stream.flush()
        if self._cancel.is_set():
            return self._cancelled()
        return "cancelled", "host_disconnected", "host_disconnected"

    def _read_event(self, raw: bytes | None) -> AuthEvent:
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
        return event

    def _publish_action(self, event: AuthEvent) -> bool:
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
            self._withdraw()
            return False
        self._publish(value)
        return True

    def _run(self) -> None:
        process: WindowsOwnedProcess | None = None
        input_stream: BinaryIO | None = None
        outcome, reason, cause = "failed", "provider_error", None
        launched = False
        try:
            refused = self._refused_before_launch()
            if refused is not None:
                outcome, reason, cause = refused
                return
            process, input_stream, output, errors = self._open_scope().launch_with_standard_pipes(
                executable=self._executable,
                arguments=self._arguments,
                directory=self._directory,
                environment=self._environment,
            )
            launched = True
            with self._lock:
                self._input = input_stream
            outcome, reason, cause = self._exchange(input_stream, self._start_readers(output, errors))
        except HelperStreamError as error:
            outcome, reason, cause = "failed", "provider_error", error.cause
        except BaseException as error:
            # The exception may contain pipe or provider contents; keep only its class name.
            self._note("exchange" if launched else "launch", error)
            outcome, reason = "failed", "provider_error"
            cause = "helper_ended_without_result" if launched else "helper_start_failed"
        finally:
            self._finish_run(process, input_stream, outcome, reason, cause)

    def _refused_before_launch(self) -> _Settlement | None:
        """Run the preparation unless authority is gone; a settlement means the helper must not start."""
        if not self._held():
            return self._cancelled()
        if self._prepare is not None:
            try:
                self._prepare()
            except BaseException as error:
                self._note("prepare", error)
                return "failed", "cleanup_failed", "agent_stop_failed"
            if not self._held():
                return self._cancelled()
        return None

    def _open_scope(self) -> WindowsProcessScope:
        """Own the job scope on the attempt, including a scope whose creation failed part way."""
        try:
            self._scope = WindowsProcessScope()
        except BaseException as error:
            self._scope = unreturned_windows_process_scope(error)
            raise
        return self._scope

    def _start_readers(self, output: BinaryIO, errors: BinaryIO) -> Queue[bytes | None]:
        """Drain both helper outputs on owned threads; only standard output is read as events."""
        queue: Queue[bytes | None] = Queue(maxsize=8)
        self._readers = [
            Thread(target=read_event_lines, args=(output, queue), daemon=True),
            Thread(target=self._discard, args=(errors,), daemon=True),
        ]
        for reader in self._readers:
            reader.start()
        return queue

    def _close_and_wait(
        self,
        process: WindowsOwnedProcess | None,
        input_stream: BinaryIO | None,
        settlement: _Settlement,
    ) -> _Settlement:
        try:
            if input_stream is not None:
                with self._lock:
                    self._input = None
                with contextlib.suppress(OSError, ValueError):
                    input_stream.close()
            if process is not None:
                status = self._wait(process, 3)
                self._exit_status = status
                # A helper that has not exited after its success is not a clean one either.
                if settlement[0] == "succeeded" and status != 0:
                    return "failed", "provider_error", "helper_exit_nonzero"
        except Exception as error:
            self._note("close", error)
            return "failed", "provider_error", "cleanup_unconfirmed"
        return settlement

    def _confirmed(self) -> tuple[bool, str | None]:
        """Ask whether the provider reads as signed in; a read that cannot be made is a failure to confirm."""
        if self._confirm is None:
            return True, None
        try:
            return self._confirm()
        except Exception as error:
            # The exception may carry provider output; only its closed kind is kept.
            self._note("confirm", error)
            return False, "status_read_failed"

    def _cleaned_up(
        self,
        process: WindowsOwnedProcess | None,
        input_stream: BinaryIO | None,
        settlement: _Settlement,
    ) -> _Settlement:
        """Retire the helper's pipes, job and readers; unconfirmed cleanup replaces the settlement."""
        try:
            try:
                settlement = self._close_and_wait(process, input_stream, settlement)
            finally:
                # Even a failed wait or pipe close must retire the whole job.
                self._retire_scope()
            self._settle_readers()
            self._clean = True
        except Exception as error:
            self._note("cleanup", error)
            return "failed", "cleanup_failed", "cleanup_unconfirmed"
        return settlement

    def _confirmed_settlement(self, settlement: _Settlement) -> tuple[_Settlement, str | None]:
        """Serve a success only while authority holds and the provider confirms it, with the status cause."""
        if settlement[0] != "succeeded":
            return settlement, None
        if not self._held():
            return self._cancelled(), None
        if self._confirm is None:
            return settlement, None
        signed_in, status_cause = self._confirmed()
        if not signed_in:
            return ("failed", "provider_error", "status_not_confirmed"), status_cause
        if not self._held():
            return self._cancelled(), status_cause
        return settlement, status_cause

    def _finish_run(
        self,
        process: WindowsOwnedProcess | None,
        input_stream: BinaryIO | None,
        outcome: str,
        reason: str | None,
        cause: HelperCause | ServiceCause | None,
    ) -> None:
        """Serve the outcome and always end the attempt, even when settling itself fails."""
        try:
            settlement = self._cleaned_up(process, input_stream, (outcome, reason, cause))
            (outcome, reason, cause), status_cause = self._confirmed_settlement(settlement)
            log_settlement(
                _LOGGER,
                self._lane,
                outcome,
                reason,
                cause,
                status_cause,
                cleanup_confirmed=self._clean,
                exit_status=self._exit_status,
                stderr_bytes=self._stderr_bytes,
                errors=self._errors,
                log_ref=self.log_ref,
                reached=self._reached,
                reached_after=self._reached_at - self._began,
                lasted=time.monotonic() - self._began,
            )
            self._publish(
                snapshot(
                    self.id,
                    self._lane,
                    outcome,
                    reason=reason,
                    cause=cause,
                    status_cause=status_cause,
                    log_ref=self.log_ref if outcome == "failed" or reason is not None else None,
                )
            )
        except BaseException as error:
            # Nothing may leave the attempt live: a person must always be able to start again.
            _LOGGER.warning(
                "provider sign-in settle failed provider=%s error_class=%s log_ref=%s",
                self._lane,
                type(error).__name__,
                self.log_ref,
            )
            self._publish(
                snapshot(
                    self.id,
                    self._lane,
                    "failed",
                    reason="provider_error",
                    cause="internal_error",
                    log_ref=self.log_ref,
                )
            )
        finally:
            self._done.set()
        if self._settled is not None:
            try:
                self._settled()
            except Exception as error:
                _LOGGER.warning(
                    "provider sign-in settled callback failed provider=%s error_class=%s log_ref=%s",
                    self._lane,
                    type(error).__name__,
                    self.log_ref,
                )

"""Own the packaged service process and its bounded control channel."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Mapping
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Event, Lock, Thread
from typing import Any
from uuid import UUID

from pydantic import JsonValue, TypeAdapter

from cadrumo.core.hashing import reject_duplicate_json_members
from cadrumo_agent_service.admin import (
    ADMIN_RESPONSE_MAX_BYTES,
    AdminAction,
)
from cadrumo_agent_service.contracts import ServiceStartupFrame
from cadrumo_agent_service.host.controller import AgentHostRefusal
from cadrumo_agent_service.host.native_refusal import NativeLaunchRefusalCode
from cadrumo_agent_service.host.store_lifecycle import StoreOutcome, StoreStep
from cadrumo_client.contracts.contracts import RefusalError
from cadrumo_client.transport.windows_process import WindowsProcessScope, unreturned_windows_process_scope

from .caller_owned_root import (
    AcceptanceError,
    require,
)
from .service_admin_channel import service_admin

_JSON_OBJECT: TypeAdapter[dict[str, JsonValue]] = TypeAdapter(dict[str, JsonValue])
_SERVICE_STOP_SECONDS = 20.0
_SERVICE_EVENT_SECONDS = 180.0
_SERVICE_LINE_BYTES = ADMIN_RESPONSE_MAX_BYTES
_ADMIN_EXCHANGE_SECONDS = 6.0
_STDERR_LINE_BYTES = 4096
_MAX_STDERR_MACHINE_CODES = 8
_NATIVE_REFUSAL_CODES = frozenset(code.value for code in NativeLaunchRefusalCode)
_NATIVE_REFUSAL_PATTERN = re.compile(
    r"agent launch refused by the native host exit=125 native_refusal=([a-z][a-z0-9_]{0,63})"
)
_HOST_STARTUP_REFUSAL_PATTERN = re.compile(
    r"agent startup refused reason=([a-z][a-z0-9_]{0,63}) agent_code=([^\s]{1,256})"
)
_STORE_LIFECYCLE_PATTERN = re.compile(
    r"agent stores not brought to current step=([a-z][a-z0-9_]{0,63}) "
    r"outcome=([a-z][a-z0-9_]{0,63}) failed_stage=[^\s]{1,256}"
)
_MACHINE_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_AGENT_HOST_REFUSAL_REASONS = frozenset(reason.value for reason in AgentHostRefusal)
_STORE_STEPS = frozenset(step.value for step in StoreStep)
_STORE_OUTCOMES = frozenset(outcome.value for outcome in StoreOutcome)


class PackagedServiceProcess:
    """Contain one packaged service tree and its bounded startup event stream."""

    def __init__(
        self,
        executable: Path,
        *,
        profile_id: UUID,
        environment: Mapping[str, str],
        directory: Path,
        bearer: bytearray,
        gateway_bearer: bytearray,
    ) -> None:
        """Launch and retain the service and its bounded event readers."""
        self._scope: WindowsProcessScope | None = None
        self._process: Any = None
        self._stdin: Any = None
        self._stdout: Any = None
        self._stderr: Any = None
        self._events: Queue[bytes | BaseException] = Queue(maxsize=8)
        self._reader_stop = Event()
        self._stdout_thread: Thread | None = None
        self._stderr_thread: Thread | None = None
        self._stderr_machine_codes: list[str] = []
        self._stderr_machine_codes_lock = Lock()
        self._stderr_diagnostics_ready = Event()
        self._closed = False
        self._bearer = bearer
        try:
            try:
                self._scope = WindowsProcessScope()
            except BaseException as error:
                self._scope = unreturned_windows_process_scope(error)
                raise
            process, stdin, stdout, stderr = self._scope.launch_with_standard_pipes(
                executable=executable.resolve(strict=True),
                arguments=("serve", "--profile-id", str(profile_id)),
                directory=directory.resolve(strict=True),
                environment=dict(environment),
            )
            self._process, self._stdin, self._stdout, self._stderr = process, stdin, stdout, stderr
            self._stdout_thread = Thread(target=self._read_events, name="agent-service-events", daemon=True)
            self._stderr_thread = Thread(target=self._drain_stderr, name="agent-service-stderr", daemon=True)
            self._stdout_thread.start()
            self._stderr_thread.start()
            frame = ServiceStartupFrame(
                bearer=bearer.decode("ascii"),
                gateway_bearer=gateway_bearer.decode("ascii"),
            )
            stdin.write(frame.model_dump_json().encode("utf-8") + b"\n")
            stdin.flush()
        except BaseException as primary:
            gateway_bearer[:] = bytes(len(gateway_bearer))
            try:
                self.close()
            except BaseException as cleanup:
                raise BaseExceptionGroup("service startup and cleanup failed", [primary, cleanup]) from primary
            raise
        finally:
            gateway_bearer[:] = bytes(len(gateway_bearer))

    def _enqueue(self, item: bytes | BaseException) -> None:
        while not self._reader_stop.is_set():
            try:
                self._events.put(item, timeout=0.1)
                return
            except Full:
                continue

    def _read_events(self) -> None:
        if self._stdout is None:
            return
        try:
            while True:
                line = self._stdout.readline(_SERVICE_LINE_BYTES + 2)
                self._enqueue(line)
                if not line:
                    return
        except OSError as error:
            self._enqueue(error)

    def _drain_stderr(self) -> None:
        if self._stderr is None:
            return
        discarding_long_line = False
        try:
            while line := self._stderr.readline(_STDERR_LINE_BYTES + 1):
                if discarding_long_line:
                    discarding_long_line = not line.endswith(b"\n")
                    continue
                if len(line) > _STDERR_LINE_BYTES:
                    discarding_long_line = not line.endswith(b"\n")
                    continue
                try:
                    message = line.decode("utf-8", errors="strict")
                except UnicodeError:
                    continue
                self._record_stderr_diagnostics(message)
        except OSError:
            # Retain only closed machine codes; cleanup owns the process result.
            return

    def _record_stderr_diagnostics(self, message: str) -> None:
        match = _NATIVE_REFUSAL_PATTERN.search(message)
        if match is not None and match.group(1) in _NATIVE_REFUSAL_CODES:
            self._record_stderr_machine_code(f"native_launch_profile:{match.group(1)}")
        self._record_host_refusal(message)
        match = _STORE_LIFECYCLE_PATTERN.search(message)
        if match is not None and match.group(1) in _STORE_STEPS and match.group(2) in _STORE_OUTCOMES:
            self._record_stderr_machine_code(f"agent_store_step:{match.group(1)}")
            self._record_stderr_machine_code(f"agent_store_outcome:{match.group(2)}")

    def _record_host_refusal(self, message: str) -> None:
        match = _HOST_STARTUP_REFUSAL_PATTERN.search(message)
        if match is not None and match.group(1) in _AGENT_HOST_REFUSAL_REASONS:
            self._record_stderr_machine_code(f"agent_host_reason:{match.group(1)}")
            agent_code = match.group(2)
            if agent_code != "None" and _MACHINE_CODE_PATTERN.fullmatch(agent_code):
                self._record_stderr_machine_code(f"agent_host_code:{agent_code}")

    def _record_stderr_machine_code(self, code: str) -> None:
        if not _MACHINE_CODE_PATTERN.fullmatch(code.replace(":", "_")):
            return
        with self._stderr_machine_codes_lock:
            if code not in self._stderr_machine_codes and len(self._stderr_machine_codes) < _MAX_STDERR_MACHINE_CODES:
                self._stderr_machine_codes.append(code)
                self._stderr_diagnostics_ready.set()

    def settle_refusal_diagnostics(self) -> None:
        """Let the separate stderr reader deliver a refusal's first bounded diagnostic."""
        self._stderr_diagnostics_ready.wait(timeout=1.0)

    @property
    def stderr_machine_codes(self) -> tuple[str, ...]:
        """Return only bounded, allowlisted machine codes extracted from service stderr."""
        with self._stderr_machine_codes_lock:
            return tuple(self._stderr_machine_codes)

    def event(self, *, timeout: float = _SERVICE_EVENT_SECONDS) -> dict[str, Any]:
        """Read one bounded service event without retaining stderr or credentials."""
        try:
            line = self._events.get(timeout=timeout)
        except Empty as error:
            raise AcceptanceError("packaged service event timed out") from error
        if isinstance(line, BaseException):
            raise AcceptanceError("packaged service output failed") from line
        require(
            bool(line) and len(line) <= _SERVICE_LINE_BYTES + 1 and line.endswith(b"\n"), "service event frame refused"
        )
        try:
            document = json.loads(line, object_pairs_hook=reject_duplicate_json_members)
        except (UnicodeError, ValueError) as error:
            raise AcceptanceError("packaged service event was malformed") from error
        require(isinstance(document, dict), "packaged service event was not an object")
        return document

    def admin(self, port: int, action: AdminAction, **fields: Any) -> dict[str, JsonValue]:
        """Use the bounded parent-administration protocol for public reads."""
        return service_admin(self._bearer, port, action, **fields)

    def close(self) -> None:
        """Close service stdin, settle its tree, and close every pipe and job handle."""
        if self._closed:
            return
        failures: list[BaseException] = []
        self._close_service_input(failures)
        self._wait_for_service_stop(failures)
        self._terminate_service_scope(failures)
        self._close_service_output(failures)
        self._join_service_threads(failures)
        self._bearer[:] = bytes(len(self._bearer))
        self._closed = self._scope is None and not failures
        if failures:
            if len(failures) == 1:
                raise failures[0]
            raise BaseExceptionGroup("packaged service cleanup failed", failures)

    def _close_service_input(self, failures: list[BaseException]) -> None:
        if self._stdin is not None and not self._stdin.closed:
            try:
                self._stdin.close()
            except BaseException as error:
                failures.append(error)

    def _wait_for_service_stop(self, failures: list[BaseException]) -> None:
        process = self._process
        if process is not None:
            try:
                deadline = time.monotonic() + _SERVICE_STOP_SECONDS
                while True:
                    remaining = deadline - time.monotonic()
                    require(remaining > 0, "packaged service did not acknowledge shutdown")
                    stopped = self.event(timeout=remaining)
                    if stopped == {"event": "stopped"}:
                        break
            except BaseException as error:
                failures.append(error)
            try:
                exit_code = process.wait(timeout=_SERVICE_STOP_SECONDS)
                require(exit_code == 0, "packaged service exited unsuccessfully")
            except RefusalError as error:
                failure = AcceptanceError("packaged service did not stop within its shutdown bound")
                failure.__cause__ = error
                failures.append(failure)
            except BaseException as error:
                failures.append(error)

    def _terminate_service_scope(self, failures: list[BaseException]) -> None:
        self._reader_stop.set()
        scope = self._scope
        if scope is not None:
            try:
                scope.terminate(timeout=_SERVICE_STOP_SECONDS)
            except BaseException as error:
                failures.append(error)
            else:
                self._scope = None

    def _close_service_output(self, failures: list[BaseException]) -> None:
        for stream in (self._stdout, self._stderr):
            if stream is not None and not stream.closed:
                try:
                    stream.close()
                except BaseException as error:
                    failures.append(error)

    def _join_service_threads(self, failures: list[BaseException]) -> None:
        for thread in (self._stdout_thread, self._stderr_thread):
            if thread is not None and thread.ident is not None:
                thread.join(timeout=_SERVICE_STOP_SECONDS)
                if thread.is_alive():
                    failures.append(AcceptanceError(f"service pipe thread {thread.name} did not stop"))

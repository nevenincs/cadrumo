"""Share one authenticated packaged runtime and agent service across tests."""

from __future__ import annotations

import json
import os
import re
import secrets
import socket
import struct
import sys
import time
from collections.abc import Generator, Mapping
from contextlib import ExitStack, contextmanager
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Event, Lock, Thread
from typing import Any
from uuid import UUID, uuid4

from pydantic import JsonValue, TypeAdapter, ValidationError

from cadrumo.core.hashing import reject_duplicate_json_members
from cadrumo_agent_service.admin import (
    ADMIN_DOCUMENT_MAX_BYTES,
    ADMIN_RESPONSE_MAX_BYTES,
    AdminAction,
    AdminRequest,
)
from cadrumo_agent_service.contracts import ServiceStartupFrame
from cadrumo_agent_service.host.controller import HOSTING_CONTRACT, AgentHostRefusal
from cadrumo_agent_service.host.native_refusal import NativeLaunchRefusalCode
from cadrumo_agent_service.host.store_lifecycle import StoreOutcome, StoreStep
from cadrumo_agent_service.installed_client import SERVICE_ID
from cadrumo_client.contracts.contracts import RefusalError
from cadrumo_client.contracts.service_access import ServiceConnected
from cadrumo_runtime.adapters.windows_process import WindowsProcessScope, unreturned_windows_process_scope
from cadrumo_runtime.application.development_root import mark_development_root

from .caller_owned_root import (
    AcceptanceError,
    Programs,
    caller_owned_runtime,
    consumer_environment,
    error_code,
    require,
    run_cli,
)
from .proof_support import Profile, create_profile, identify_profile, login_profile, state_taxpayer
from .session_holder import WindowsRuntimeSessionHolder

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


class _PackagedServiceProcess:
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
                match = _NATIVE_REFUSAL_PATTERN.search(message)
                if match is not None and match.group(1) in _NATIVE_REFUSAL_CODES:
                    self._record_stderr_machine_code(f"native_launch_profile:{match.group(1)}")
                match = _HOST_STARTUP_REFUSAL_PATTERN.search(message)
                if match is not None and match.group(1) in _AGENT_HOST_REFUSAL_REASONS:
                    self._record_stderr_machine_code(f"agent_host_reason:{match.group(1)}")
                    agent_code = match.group(2)
                    if agent_code != "None" and _MACHINE_CODE_PATTERN.fullmatch(agent_code):
                        self._record_stderr_machine_code(f"agent_host_code:{agent_code}")
                match = _STORE_LIFECYCLE_PATTERN.search(message)
                if match is not None and match.group(1) in _STORE_STEPS and match.group(2) in _STORE_OUTCOMES:
                    self._record_stderr_machine_code(f"agent_store_step:{match.group(1)}")
                    self._record_stderr_machine_code(f"agent_store_outcome:{match.group(2)}")
        except OSError:
            # Retain only closed machine codes; cleanup owns the process result.
            return

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
        """Use the service's typed, bounded parent-administration protocol for public reads."""
        if action not in {"catalog", "status"}:
            raise AcceptanceError("shared service admin permits catalog and status reads only")
        if "secret_bytes" in fields:
            raise AcceptanceError("shared service admin does not carry credential frames")
        request_id = uuid4()
        try:
            request = AdminRequest.model_validate({"version": 1, "request_id": request_id, "action": action, **fields})
        except ValidationError as error:
            raise AcceptanceError("service admin request failed its typed contract") from error
        encoded = request.model_dump_json(exclude_none=True).encode("utf-8")
        require(0 < len(encoded) <= ADMIN_DOCUMENT_MAX_BYTES, "service admin request exceeds its contract bound")
        bearer = self._bearer
        require(bool(bearer), "service admin authority has been closed")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=_ADMIN_EXCHANGE_SECONDS) as stream:
                stream.settimeout(_ADMIN_EXCHANGE_SECONDS)
                _write_frame(stream, bearer)
                _write_frame(stream, encoded)
                response = _read_document(stream, ADMIN_RESPONSE_MAX_BYTES)
        except (OSError, TimeoutError, ValueError) as error:
            raise AcceptanceError("service admin exchange failed") from error
        require(response.get("version") == 1, "service admin response version differs")
        require(response.get("request_id") == str(request_id), "service admin response correlation differs")
        result = response.get("result")
        require(isinstance(result, dict), "service admin response omitted its typed result")
        return _JSON_OBJECT.validate_python(result, strict=True)

    def close(self) -> None:
        """Close service stdin, settle its tree, and close every pipe and job handle."""
        if self._closed:
            return
        failures: list[BaseException] = []
        if self._stdin is not None and not self._stdin.closed:
            try:
                self._stdin.close()
            except BaseException as error:
                failures.append(error)
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
        self._reader_stop.set()
        scope = self._scope
        if scope is not None:
            try:
                scope.terminate(timeout=_SERVICE_STOP_SECONDS)
            except BaseException as error:
                failures.append(error)
            else:
                self._scope = None
        for stream in (self._stdout, self._stderr):
            if stream is not None and not stream.closed:
                try:
                    stream.close()
                except BaseException as error:
                    failures.append(error)
        for thread in (self._stdout_thread, self._stderr_thread):
            if thread is not None and thread.ident is not None:
                thread.join(timeout=_SERVICE_STOP_SECONDS)
                if thread.is_alive():
                    failures.append(AcceptanceError(f"service pipe thread {thread.name} did not stop"))
        self._bearer[:] = bytes(len(self._bearer))
        self._closed = self._scope is None and not failures
        if failures:
            if len(failures) == 1:
                raise failures[0]
            raise BaseExceptionGroup("packaged service cleanup failed", failures)


def _write_frame(stream: socket.socket, payload: bytes | bytearray) -> None:
    """Write one length-prefixed frame within the wire's 32-bit size field."""
    require(0 < len(payload) <= 16 * 1024 * 1024, "service admin frame size refused")
    stream.sendall(struct.pack("!I", len(payload)) + payload)


def _read_exact(stream: socket.socket, size: int) -> bytes:
    """Read one complete bounded admin frame."""
    remaining = size
    chunks = bytearray()
    while remaining:
        chunk = stream.recv(remaining)
        if not chunk:
            raise AcceptanceError("service admin response ended early")
        chunks.extend(chunk)
        remaining -= len(chunk)
    return bytes(chunks)


def _read_document(stream: socket.socket, maximum: int) -> dict[str, JsonValue]:
    """Read a typed JSON object with the service's response bound."""
    size = struct.unpack("!I", _read_exact(stream, 4))[0]
    require(0 < size <= maximum, "service admin response frame size refused")
    try:
        document = json.loads(_read_exact(stream, size), object_pairs_hook=reject_duplicate_json_members)
        return _JSON_OBJECT.validate_python(document, strict=True)
    except (UnicodeError, ValueError, ValidationError) as error:
        raise AcceptanceError("service admin response was malformed") from error


class AgentServiceSession:
    """One fresh profile, held person session and admitted packaged service."""

    def __init__(
        self,
        *,
        programs: Programs,
        package: Path,
        root: Path,
        environment: Mapping[str, str],
        profile: Profile,
        login_session_persisted: bool,
        runtime_ready: Mapping[str, Any],
        holder: WindowsRuntimeSessionHolder,
        service: _PackagedServiceProcess,
        service_ready: Mapping[str, Any],
        admission: Mapping[str, Any],
        agent_event: Mapping[str, Any],
        setup_counts: Mapping[str, int],
        timings: Mapping[str, float],
    ) -> None:
        """Retain the exact runtime, person, service and setup evidence."""
        self.programs = programs
        self.package = package
        self.root = root
        self.environment = dict(environment)
        self.profile = profile
        self.login_session_persisted = login_session_persisted
        self.runtime_ready = dict(runtime_ready)
        self._holder = holder
        self._service = service
        self.service_ready = dict(service_ready)
        self.holder_identity = dict(holder.identity)
        self.admission = dict(admission)
        self.agent_event = dict(agent_event)
        self.setup_counts = dict(setup_counts)
        self.timings = dict(timings)

    @property
    def first_refusal_code(self) -> str | None:
        """Return the service's first typed agent refusal code, when it refused startup."""
        code = self.agent_event.get("code")
        return code if self.agent_event.get("event") == "refused" and isinstance(code, str) else None

    @property
    def native_refusal_codes(self) -> tuple[str, ...]:
        """Return sanitized native launch codes without retaining raw stderr."""
        codes = getattr(self._service, "stderr_machine_codes", ())
        return tuple(code for code in codes if isinstance(code, str)) if isinstance(codes, tuple) else ()

    def admin(self, action: AdminAction, **fields: Any) -> dict[str, JsonValue]:
        """Request a typed public catalog or service status projection."""
        port = self.service_ready.get("admin_port")
        if type(port) is not int or not 0 < port <= 65535:
            raise AcceptanceError("service admin endpoint is invalid")
        return self._service.admin(port, action, **fields)

    def catalog(self) -> dict[str, JsonValue]:
        """Read the service's currently available provider catalog."""
        return self.admin("catalog")

    def status(self) -> dict[str, JsonValue]:
        """Read service status under this exact admitted session."""
        return self.admin("status")

    def cli_read(self, *arguments: str, reveal_identifiers: bool) -> tuple[int, dict[str, Any]]:
        """Read under stored sign-in, or use protected profile input when persistence was unavailable."""
        environment = dict(self.environment)
        if reveal_identifiers:
            environment["CADRUMO_CLI_REVEAL_IDENTIFIERS"] = "true"
        profile_arguments = () if self.login_session_persisted else ("--profile-secrets-stdin",)
        secret = None if self.login_session_persisted else {"profile_passphrase": self.profile.password}
        return run_cli(
            self.programs,
            environment,
            *profile_arguments,
            *arguments,
            secret=secret,
        )


@contextmanager
def agent_service_session(
    package: Path,
    scratch: Path,
    *,
    external_bin_dirs: tuple[Path, ...] = (),
) -> Generator[AgentServiceSession]:
    """Start the runtime first, then create one profile, holder and admitted service.

    The service's first typed ``agent_ready`` or ``refused`` event is retained
    for the suite. A provider refusal is observable and does not prevent
    structural service tests from using catalog or status administration.
    """
    package = package.resolve(strict=True)
    scratch.mkdir(parents=True, exist_ok=True)
    root, secret_store = scratch / "storage", scratch / "secrets"
    root.mkdir(parents=True, exist_ok=True)
    secret_store.mkdir(parents=True, exist_ok=True)
    environment = consumer_environment(root, secret_store)
    environment["CADRUMO_LOG_STDERR_LEVEL"] = "WARNING"
    if external_bin_dirs:
        normalized = tuple(str(path.resolve(strict=True)) for path in external_bin_dirs)
        environment["CADRUMO_EXTERNAL_BIN_DIRS"] = os.pathsep.join(normalized)
    mark_development_root(root)
    programs = Programs.of(package)
    service_name = "cadrumo-agent-service.exe" if sys.platform == "win32" else "cadrumo-agent-service"
    service_image = (package / "bin" / service_name).resolve(strict=True)
    counts = {
        "runtime_start": 0,
        "profile_create": 0,
        "profile_setup": 0,
        "profile_login": 0,
        "holder_start": 0,
        "service_start": 0,
        "service_admission": 0,
    }
    timings: dict[str, float] = {}
    started = time.monotonic()

    with ExitStack() as cleanup:
        runtime = cleanup.enter_context(caller_owned_runtime(programs, environment, scratch / "runtime-stderr.log"))
        cleanup.callback(_require_runtime_stopped, runtime)
        counts["runtime_start"] += 1
        phase = time.monotonic()
        runtime_ready = runtime.ready()
        require(runtime_ready.get("kind") == "runtime_ready", "packaged runtime did not announce readiness")
        timings["runtime_ready"] = time.monotonic() - phase

        phase = time.monotonic()
        profile = create_profile(programs, environment, "agent-service-session")
        counts["profile_create"] += 1
        login_session_persisted = login_profile(programs, environment, profile)
        counts["profile_login"] += 1
        if login_session_persisted:
            cleanup.callback(_logout_profile, programs, environment)
        profile = identify_profile(programs, environment, profile)
        state_taxpayer(programs, environment, profile)
        counts["profile_setup"] += 1
        timings["profile_setup_and_login"] = time.monotonic() - phase
        if profile.profile_id is None:
            raise AcceptanceError("created profile has no verified identity")
        profile_id = profile.profile_id

        phase = time.monotonic()
        holder = WindowsRuntimeSessionHolder(
            programs.runtime,
            profile_id=profile_id,
            environment=environment,
            password=bytearray(profile.password, "utf-8"),
            frontend="cli",
        )
        cleanup.callback(_close_holder, holder)
        counts["holder_start"] += 1
        timings["holder_start"] = time.monotonic() - phase

        bearer = bytearray(secrets.token_urlsafe(48), "ascii")
        gateway_bearer = bytearray(secrets.token_urlsafe(48), "ascii")
        phase = time.monotonic()
        service = _PackagedServiceProcess(
            service_image,
            profile_id=profile_id,
            environment=environment,
            directory=root,
            bearer=bearer,
            gateway_bearer=gateway_bearer,
        )
        cleanup.callback(service.close)
        counts["service_start"] += 1
        service_ready = service.event()
        _validate_service_ready(service_ready, holder, profile)
        timings["service_ready"] = time.monotonic() - phase

        phase = time.monotonic()
        admission = holder.command(
            "service_admission",
            recipient_connection_id=service_ready["connection_id"],
            service_id=SERVICE_ID,
        )
        _validate_service_lease(admission, holder, service_ready, profile)
        counts["service_admission"] += 1
        agent_event = service.event()
        _validate_agent_event(agent_event)
        if agent_event["event"] == "refused":
            service.settle_refusal_diagnostics()
        timings["service_admission_and_agent_event"] = time.monotonic() - phase
        timings["setup_total"] = time.monotonic() - started

        yield AgentServiceSession(
            programs=programs,
            package=package,
            root=root,
            environment=environment,
            profile=profile,
            login_session_persisted=login_session_persisted,
            runtime_ready=runtime_ready,
            holder=holder,
            service=service,
            service_ready=service_ready,
            admission=admission,
            agent_event=agent_event,
            setup_counts=counts,
            timings=timings,
        )


def _close_holder(holder: WindowsRuntimeSessionHolder) -> None:
    """Retire the held person connection before releasing its contained process."""
    failures: list[BaseException] = []
    try:
        reply = holder.command("close")
        require(reply.get("kind") == "session_closed", "runtime did not confirm held-session closure")
    except BaseException as error:
        failures.append(error)
    try:
        holder.close()
    except BaseException as error:
        failures.append(error)
    if failures:
        if len(failures) == 1:
            raise failures[0]
        raise BaseExceptionGroup("held-session cleanup failed", failures)


def _logout_profile(programs: Programs, environment: Mapping[str, str]) -> None:
    """Retire a persisted sign-in before its disposable product root is removed."""
    code, envelope = run_cli(programs, environment, "config", "logout")
    require(
        code == 0 and envelope.get("status") in {"success", "warning"},
        f"profile logout refused: exit {code}, code {error_code(envelope)}",
    )


def _require_runtime_stopped(runtime: Any) -> None:
    """Require a clean caller-owned runtime drain after service and holder cleanup."""
    require(runtime.stop() == 64, "caller-owned runtime did not drain with its supervised exit")


def _validate_service_ready(event: Mapping[str, Any], holder: WindowsRuntimeSessionHolder, profile: Profile) -> None:
    """Bind service readiness to the held runtime boot, profile and exact peer connection."""
    expected = {
        "event",
        "protocol",
        "admin_port",
        "runtime_boot_id",
        "connection_id",
        "profile_id",
        "service_id",
    }
    require(set(event) == expected, "service readiness fields differ from the typed contract")
    require(event.get("event") == "service_ready" and event.get("protocol") == 1, "service readiness protocol refused")
    require(event.get("profile_id") == str(profile.profile_id), "service profile differs from the CLI profile")
    require(event.get("runtime_boot_id") == holder.identity.get("runtime_boot_id"), "service runtime boot differs")
    require(event.get("service_id") == SERVICE_ID, "service identity differs from its packaged descriptor")
    port = event.get("admin_port")
    require(type(port) is int and 0 < port <= 65535, "service admin port is invalid")
    try:
        UUID(str(event.get("connection_id")))
        UUID(str(event.get("runtime_boot_id")))
    except ValueError as error:
        raise AcceptanceError("service readiness omitted exact native coordinates") from error


def _validate_service_lease(
    reply: Mapping[str, Any],
    holder: WindowsRuntimeSessionHolder,
    service_ready: Mapping[str, Any],
    profile: Profile,
) -> None:
    """Require the person's typed admission to grant the exact service connection lease."""
    try:
        connected = ServiceConnected.model_validate_json(json.dumps(reply), strict=True)
    except ValidationError as error:
        raise AcceptanceError("runtime service-admission reply failed its typed contract") from error
    lease = connected.lease
    if lease is None:
        raise AcceptanceError("runtime returned no exact service lease")
    require(
        connected.runtime_boot_id == UUID(str(holder.identity["runtime_boot_id"])),
        "admission runtime boot differs",
    )
    require(connected.profile_id == profile.profile_id, "admission profile differs")
    require(connected.service_id == SERVICE_ID, "admission service identity differs")
    require(lease.runtime_boot_id == connected.runtime_boot_id, "service lease runtime boot differs")
    require(lease.profile_id == profile.profile_id, "service lease profile differs")
    require(lease.parent_session_id == UUID(str(holder.identity["session_id"])), "service lease parent session differs")
    require(lease.connection_id == UUID(str(service_ready["connection_id"])), "service lease connection differs")
    require(lease.service_id == SERVICE_ID, "service lease identity differs")
    require(lease.session_id != lease.parent_session_id, "service lease reused the person session")


def _validate_agent_event(event: Mapping[str, Any]) -> None:
    """Preserve one typed provider refusal or ready event without demanding readiness."""
    kind = event.get("event")
    require(kind in {"agent_ready", "refused"}, "service emitted no typed agent readiness or refusal event")
    if kind == "refused":
        code = event.get("code")
        require(
            isinstance(code, str) and bool(_MACHINE_CODE_PATTERN.fullmatch(code)),
            "service refusal omitted its typed code",
        )
        return
    require(type(event.get("gateway_port")) is int and 0 < event["gateway_port"] <= 65535, "agent gateway port invalid")
    require(isinstance(event.get("agent_version"), str), "agent readiness omitted its version")
    require(
        type(event.get("hosting_contract")) is int and event["hosting_contract"] == HOSTING_CONTRACT,
        "agent readiness omitted or changed its hosting contract",
    )
    require(isinstance(event.get("workspace_root"), str), "agent readiness omitted its workspace")

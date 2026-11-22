"""Share one authenticated packaged runtime and agent service across tests."""

from __future__ import annotations

import json
import os
import re
import secrets
import sys
import time
from collections.abc import Generator, Mapping
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from pydantic import JsonValue, ValidationError

from cadrumo_agent_service.admin import (
    AdminAction,
)
from cadrumo_agent_service.host.controller import HOSTING_CONTRACT
from cadrumo_agent_service.installed_client import SERVICE_ID
from cadrumo_client.contracts.profile_access import ProfileStatus
from cadrumo_client.contracts.service_access import ServiceConnected
from cadrumo_client.contracts.sign_in import SignInStatus
from cadrumo_runtime.application.development_root import mark_development_root

from .caller_owned_root import (
    AcceptanceError,
    Programs,
    caller_owned_runtime,
    consumer_environment,
    error_code,
    require,
    run_cli,
    run_runtime_cli,
)
from .packaged_service_process import PackagedServiceProcess, package_default_engine
from .proof_support import Profile, create_profile, identify_profile, login_profile, state_taxpayer
from .service_admin_channel import ADMIN_EXCHANGE_SECONDS
from .windows_holder import WindowsRuntimeSessionHolder


@dataclass(slots=True)
class _Generation:
    """The held person session and the agent service admitted under it, closed together."""

    stack: ExitStack = field(default_factory=ExitStack)

    def close(self) -> None:
        """Close the service, then the held session, as the first setup's cleanup always did."""
        self.stack.close()


@dataclass(frozen=True, slots=True)
class _Admitted:
    """One held person session and the service admitted under it, with the evidence of each step."""

    holder: WindowsRuntimeSessionHolder
    service: PackagedServiceProcess
    service_ready: dict[str, Any]
    admission: dict[str, Any]
    agent_event: dict[str, Any]


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
        service: PackagedServiceProcess,
        service_ready: Mapping[str, Any],
        admission: Mapping[str, Any],
        agent_event: Mapping[str, Any],
        setup_counts: Mapping[str, int],
        timings: Mapping[str, float],
        owned: bool = False,
        generation: _Generation | None = None,
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
        self._owned = owned
        self._generation = generation
        self.sign_ins = 1

    @property
    def first_refusal_code(self) -> str | None:
        """Return the service's first typed agent refusal code, when it refused startup."""
        code = self.agent_event.get("code")
        return code if self.agent_event.get("event") == "refused" and isinstance(code, str) else None

    @property
    def native_refusal_codes(self) -> tuple[str, ...]:
        """Return sanitized native launch codes without retaining raw stderr."""
        codes: object = getattr(self._service, "stderr_machine_codes", ())
        return (
            tuple(code for code in cast(tuple[object, ...], codes) if isinstance(code, str))
            if isinstance(codes, tuple)
            else ()
        )

    def admin(
        self, action: AdminAction, *, within: float = ADMIN_EXCHANGE_SECONDS, **fields: Any
    ) -> dict[str, JsonValue]:
        """Request a typed public catalog or service status projection, answered inside ``within``."""
        return self._service.admin(self._admin_port(), action, within=within, **fields)

    def settings(
        self, action: AdminAction, *, within: float = ADMIN_EXCHANGE_SECONDS, **fields: Any
    ) -> dict[str, JsonValue]:
        """Read or store the window's local-model settings, on a session its caller owns alone.

        A shared session serves many tests, so none of them may change what the
        others read: only a session started with ``owned=True`` carries settings.
        """
        if not self._owned:
            raise AcceptanceError("a shared agent service session does not change local-model settings")
        return self._service.settings(self._admin_port(), action, within=within, **fields)

    def credential(
        self,
        *,
        provider: str,
        expected_revision: str,
        base_url: str | None,
        secret: bytearray,
        within: float = ADMIN_EXCHANGE_SECONDS,
    ) -> dict[str, JsonValue]:
        """Store one lane's direct credential as the window does, on a session its caller owns alone.

        ``secret`` is wiped on every exit, a refusal of the session included.
        """
        try:
            if not self._owned:
                raise AcceptanceError("a shared agent service session does not store provider credentials")
            return self._service.credential(
                self._admin_port(),
                provider=provider,
                expected_revision=expected_revision,
                base_url=base_url,
                secret=secret,
                within=within,
            )
        finally:
            secret[:] = bytes(len(secret))

    def _admin_port(self) -> int:
        port = self.service_ready.get("admin_port")
        if type(port) is not int or not 0 < port <= 65535:
            raise AcceptanceError("service admin endpoint is invalid")
        return port

    def catalog(self, *, within: float = ADMIN_EXCHANGE_SECONDS) -> dict[str, JsonValue]:
        """Read the service's currently available provider catalog, answered inside ``within``."""
        return self.admin("catalog", within=within)

    def status(self, *, within: float = ADMIN_EXCHANGE_SECONDS) -> dict[str, JsonValue]:
        """Read service status under this exact admitted session, answered inside ``within``."""
        return self.admin("status", within=within)

    def sign_in_deadline(self) -> datetime | None:
        """The earlier of the stored sign-in's idle deadline and the held person session's expiry.

        Both are read, never extended: the runtime extends them only on the
        person's own input, which a script never is. A held session that has
        already retired answers with its retirement, read here as a deadline
        already past.
        """
        deadlines: list[datetime] = []
        if self.login_session_persisted:
            code, envelope = run_runtime_cli(self.programs, self.environment, "config", "sign-in-status")
            result = envelope.get("result")
            if code == 0 and isinstance(result, dict) and isinstance(result.get("status"), dict):
                status = SignInStatus.model_validate_json(json.dumps(result["status"]))
                if status.idle_deadline is not None:
                    deadlines.append(status.idle_deadline)
        try:
            reply = self._holder.command("status")
        except (AcceptanceError, OSError):
            return datetime.now(UTC)
        held = ProfileStatus.model_validate_json(json.dumps(reply)).status.session_expires_at
        if held is not None:
            deadlines.append(held)
        return min(deadlines) if deadlines else None

    def sign_in_again(self) -> dict[str, Any]:
        """Sign the person in again, as at the window once their sign-in runs out, and admit a new service.

        The runtime ends a person's sign-in after its idle window unless the
        person's own input extends it, and the agent service's lease ends with
        the held session it descends from. A measurement that outlasts the
        window does what the person does: the old service and held session are
        closed, the profile is signed in again with its password, a new held
        session starts and a new service is admitted under it. Closing a held
        session or service that already ended is reported, not raised; every
        later step must succeed.
        """
        if self._generation is None:
            raise AcceptanceError("this agent service session cannot sign in again")
        started = time.monotonic()
        previous: list[str] = []
        try:
            self._generation.close()
        except Exception as error:  # an already retired session or service is expected here
            previous.append(type(error).__name__)
        if self.login_session_persisted:
            require(
                login_profile(self.programs, self.environment, self.profile),
                "the renewed sign-in was not stored as the first one was",
            )
        self.setup_counts["profile_login"] += 1
        timings: dict[str, float] = {}
        generation = _Generation()
        try:
            admitted = _admit_service(
                generation.stack,
                programs=self.programs,
                package=self.package,
                root=self.root,
                environment=self.environment,
                profile=self.profile,
                counts=self.setup_counts,
                timings=timings,
            )
        except BaseException:
            generation.close()
            raise
        self._generation.stack = generation.stack
        self._holder, self._service = admitted.holder, admitted.service
        self.service_ready, self.admission = admitted.service_ready, admitted.admission
        self.holder_identity = dict(admitted.holder.identity)
        self.agent_event = admitted.agent_event
        self.sign_ins += 1
        return {
            "seconds": round(time.monotonic() - started, 3),
            "previous_close_failures": previous,
            "agent_event": admitted.agent_event.get("event"),
            "timings": {key: round(value, 3) for key, value in timings.items()},
        }

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
    owned: bool = False,
) -> Generator[AgentServiceSession]:
    """Start the runtime first, then create one profile, holder and admitted service.

    The service's first typed ``agent_ready`` or ``refused`` event is retained
    for the suite. A provider refusal is observable and does not prevent
    structural service tests from using catalog or status administration.
    ``owned`` marks a session one caller alone uses, which may then store the
    window's local-model settings as the service's parent.
    """
    package = package.resolve(strict=True)
    scratch.mkdir(parents=True, exist_ok=True)
    root = scratch / "storage"
    root.mkdir(parents=True, exist_ok=True)
    environment = consumer_environment(root)
    environment["CADRUMO_LOG_STDERR_LEVEL"] = "WARNING"
    if external_bin_dirs:
        normalized = tuple(str(path.resolve(strict=True)) for path in external_bin_dirs)
        environment["CADRUMO_EXTERNAL_BIN_DIRS"] = os.pathsep.join(normalized)
    mark_development_root(root)
    programs = Programs.of(package)
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
        cleanup.callback(require_runtime_stopped, runtime)
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
            cleanup.callback(logout_profile, programs, environment)
        profile = identify_profile(programs, environment, profile)
        state_taxpayer(programs, environment, profile)
        counts["profile_setup"] += 1
        timings["profile_setup_and_login"] = time.monotonic() - phase
        if profile.profile_id is None:
            raise AcceptanceError("created profile has no verified identity")

        generation = _Generation()
        cleanup.callback(generation.close)
        admitted = _admit_service(
            generation.stack,
            programs=programs,
            package=package,
            root=root,
            environment=environment,
            profile=profile,
            counts=counts,
            timings=timings,
        )
        timings["setup_total"] = time.monotonic() - started

        yield AgentServiceSession(
            programs=programs,
            package=package,
            root=root,
            environment=environment,
            profile=profile,
            login_session_persisted=login_session_persisted,
            runtime_ready=runtime_ready,
            holder=admitted.holder,
            service=admitted.service,
            service_ready=admitted.service_ready,
            admission=admitted.admission,
            agent_event=admitted.agent_event,
            setup_counts=counts,
            timings=timings,
            owned=owned,
            generation=generation,
        )


def _admit_service(
    stack: ExitStack,
    *,
    programs: Programs,
    package: Path,
    root: Path,
    environment: Mapping[str, str],
    profile: Profile,
    counts: dict[str, int],
    timings: dict[str, float],
) -> _Admitted:
    """Hold the person's session with their password, start the packaged service and admit it under that session.

    Each process is registered on ``stack`` as it starts, so closing the stack
    closes the service before the held session.
    """
    if profile.profile_id is None:
        raise AcceptanceError("created profile has no verified identity")
    service_name = "cadrumo-agent-service.exe" if sys.platform == "win32" else "cadrumo-agent-service"
    service_image = (package / "bin" / service_name).resolve(strict=True)
    phase = time.monotonic()
    holder = WindowsRuntimeSessionHolder(
        programs.runtime,
        profile_id=profile.profile_id,
        environment=environment,
        password=bytearray(profile.password, "utf-8"),
        frontend="cli",
    )
    stack.callback(close_holder, holder)
    counts["holder_start"] += 1
    timings["holder_start"] = time.monotonic() - phase

    bearer = bytearray(secrets.token_urlsafe(48), "ascii")
    gateway_bearer = bytearray(secrets.token_urlsafe(48), "ascii")
    phase = time.monotonic()
    service = PackagedServiceProcess(
        service_image,
        profile_id=profile.profile_id,
        environment=environment,
        directory=root,
        bearer=bearer,
        gateway_bearer=gateway_bearer,
        local_engine_default=package_default_engine(package),
    )
    stack.callback(service.close)
    counts["service_start"] += 1
    service_ready = service.event()
    validate_service_ready(service_ready, holder, profile)
    timings["service_ready"] = time.monotonic() - phase

    phase = time.monotonic()
    admission = holder.command(
        "service_admission",
        recipient_connection_id=service_ready["connection_id"],
        service_id=SERVICE_ID,
    )
    validate_service_lease(admission, holder, service_ready, profile)
    counts["service_admission"] += 1
    agent_event = service.event()
    validate_agent_event(agent_event)
    if agent_event["event"] == "refused":
        service.settle_refusal_diagnostics()
    timings["service_admission_and_agent_event"] = time.monotonic() - phase
    return _Admitted(
        holder=holder, service=service, service_ready=service_ready, admission=admission, agent_event=agent_event
    )


def close_holder(holder: WindowsRuntimeSessionHolder) -> None:
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


def logout_profile(programs: Programs, environment: Mapping[str, str]) -> None:
    """Retire a persisted sign-in before its disposable product root is removed."""
    code, envelope = run_cli(programs, environment, "config", "logout")
    require(
        code == 0 and envelope.get("status") in {"success", "warning"},
        f"profile logout refused: exit {code}, code {error_code(envelope)}",
    )


def require_runtime_stopped(runtime: Any) -> None:
    """Require a clean caller-owned runtime drain after service and holder cleanup."""
    require(runtime.stop() == 64, "caller-owned runtime did not drain with its supervised exit")


def validate_service_ready(event: Mapping[str, Any], holder: WindowsRuntimeSessionHolder, profile: Profile) -> None:
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


def validate_service_lease(
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


def validate_agent_event(event: Mapping[str, Any]) -> None:
    """Preserve one typed provider refusal or ready event without demanding readiness."""
    kind = event.get("event")
    require(kind in {"agent_ready", "refused"}, "service emitted no typed agent readiness or refusal event")
    if kind == "refused":
        code = event.get("code")
        require(
            isinstance(code, str) and bool(re.fullmatch(r"[a-z][a-z0-9_]{0,63}", code)),
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

"""Own one cadrumo-agent process tree for the signed-in profile's current generation.

The controller resolves the profile's provider credentials, starts the agent
inside a contained process tree, writes the credentials once as a standard-input
frame, and waits for a single ready line. It publishes the agent only while the
sign-in and provider-settings generations it started under are still current.
Closing the agent's standard input is the stop signal; a tree that has not
exited within the grace period is terminated whole.
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from threading import Lock
from typing import Final, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .credential_frame import AgentCredential, CredentialFrameError, build_credential_frame, wipe

READY_LINE_MAX_BYTES: Final = 4 * 1024
HOSTING_CONTRACT: Final = 1
"""The one hosting-contract version this host speaks; an agent announcing another is refused."""


class AgentHostState(StrEnum):
    """Where the controller is in one agent tree's life."""

    DETACHED = "detached"
    STARTING = "starting"
    READY = "ready"
    STOPPING = "stopping"


class AgentHostRefusal(StrEnum):
    """Closed reasons the agent is not available, worded by each frontend."""

    SIGNED_OUT = "signed_out"
    CREDENTIALS_UNAVAILABLE = "credentials_unavailable"
    CREDENTIALS_INVALID = "credentials_invalid"
    LAUNCH_FAILED = "launch_failed"
    NOT_READY = "not_ready"
    AGENT_REFUSED = "agent_refused"
    STALE_GENERATION = "stale_generation"
    ALREADY_RUNNING = "already_running"


class AgentHostError(RuntimeError):
    """A typed refusal; it carries no credential, path or process detail."""

    def __init__(self, reason: AgentHostRefusal, *, agent_code: str | None = None) -> None:
        """Keep the closed reason and, for an agent refusal, the agent's own closed code."""
        super().__init__(reason.value if agent_code is None else f"{reason.value}:{agent_code}")
        self.reason = reason
        self.agent_code = agent_code


@dataclass(frozen=True, slots=True)
class AgentGenerations:
    """The authority an agent tree was started under; neither value is secret."""

    sign_in: str
    provider_settings: str


@dataclass(frozen=True, slots=True)
class ResolvedAgentCredentials:
    """Credentials for one start, owned by the controller until it wipes them."""

    generations: AgentGenerations
    credentials: Mapping[str, AgentCredential]


class AgentCredentialSource(Protocol):
    """Resolve the signed-in profile's credentials for the hosted assistant."""

    def resolve_for_agent(self) -> ResolvedAgentCredentials:
        """Return fresh credential buffers, or raise ``AgentHostError``."""
        ...

    def current_generations(self) -> AgentGenerations | None:
        """Return the current generations without refreshing the session's idle time."""
        ...


class AgentProcess(Protocol):
    """One contained agent tree reached through its private standard pipes."""

    def write_input(self, data: bytearray) -> None:
        """Write and flush these bytes to the agent's standard input."""
        ...

    def read_output_line(self, *, limit: int, timeout: float) -> bytes:
        """Return one newline-terminated line, raising ``TimeoutError`` past the bound."""
        ...

    def close_input(self) -> None:
        """Close the agent's standard input: its stop signal."""
        ...

    def wait(self, *, timeout: float) -> int | None:
        """Return the exit status, or ``None`` if the agent is still running at the bound."""
        ...

    def terminate(self, *, timeout: float) -> None:
        """End the whole tree and confirm no member remains."""
        ...


class AgentProcessLauncher(Protocol):
    """Start an agent tree in a containment the host owns."""

    def launch(
        self, *, executable: Path, arguments: Sequence[str], directory: Path, environment: Mapping[str, str]
    ) -> AgentProcess:
        """Start the tree with an explicit environment and private standard pipes."""
        ...


@dataclass(frozen=True, slots=True)
class AgentLaunch:
    """What to start; it holds no credential, profile identity or session value."""

    executable: Path
    arguments: tuple[str, ...]
    directory: Path
    environment: Mapping[str, str]
    ready_timeout: float = 60.0
    stop_grace: float = 10.0
    terminate_timeout: float = 10.0


class _ReadyLine(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    event: str = Field(pattern=r"^agent_ready$")
    gateway_port: int = Field(ge=1, le=65535)
    agent_version: str = Field(min_length=1, max_length=64)
    hosting_contract: int = Field(ge=HOSTING_CONTRACT, le=HOSTING_CONTRACT)


class _RefusalLine(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    event: str = Field(pattern=r"^refused$")
    code: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")


@dataclass(frozen=True, slots=True)
class AgentReady:
    """A published, running agent for exactly these generations."""

    generations: AgentGenerations
    gateway_port: int
    agent_version: str
    hosting_contract: int


class AgentHostController:
    """Start, publish and retire one agent tree; at most one exists at a time."""

    def __init__(
        self, *, launcher: AgentProcessLauncher, credentials: AgentCredentialSource, launch: AgentLaunch
    ) -> None:
        """Bind the containment, the credential source and the fixed launch description."""
        self._launcher = launcher
        self._credentials = credentials
        self._launch = launch
        self._lock = Lock()
        self._state = AgentHostState.DETACHED
        self._process: AgentProcess | None = None
        self._ready: AgentReady | None = None

    @property
    def state(self) -> AgentHostState:
        """The controller's current state."""
        return self._state

    def start(self) -> AgentReady:
        """Start the agent for the current generations and return it once ready.

        Any failure leaves no process behind and the controller detached.
        """
        with self._lock:
            if self._state is not AgentHostState.DETACHED:
                raise AgentHostError(AgentHostRefusal.ALREADY_RUNNING)
            self._state = AgentHostState.STARTING
        try:
            ready = self._start()
        except BaseException:
            self._retire()
            raise
        with self._lock:
            # A sign-out or key change while starting retires this tree instead of publishing it.
            if self._credentials.current_generations() != ready.generations:
                stale = True
            else:
                stale = False
                self._ready = ready
                self._state = AgentHostState.READY
        if stale:
            self._retire()
            raise AgentHostError(AgentHostRefusal.STALE_GENERATION)
        return ready

    def published(self) -> AgentReady | None:
        """Return the running agent only while its generations are still current."""
        with self._lock:
            ready = self._ready
        if ready is None:
            return None
        if self._credentials.current_generations() != ready.generations:
            self.stop()
            return None
        return ready

    def stop(self) -> None:
        """Close admission, signal the agent to stop, then end the tree if it overruns."""
        self._retire()

    def restart(self) -> AgentReady:
        """Retire the current tree and start a new one from the committed credentials."""
        self._retire()
        return self.start()

    def _start(self) -> AgentReady:
        resolved = self._credentials.resolve_for_agent()
        try:
            frame = build_credential_frame(resolved.credentials)
        except CredentialFrameError as error:
            raise AgentHostError(AgentHostRefusal.CREDENTIALS_INVALID) from error
        finally:
            for credential in resolved.credentials.values():
                wipe(credential.secret)
        try:
            try:
                process = self._launcher.launch(
                    executable=self._launch.executable,
                    arguments=self._launch.arguments,
                    directory=self._launch.directory,
                    environment=self._launch.environment,
                )
            except AgentHostError:
                raise
            except Exception as error:
                raise AgentHostError(AgentHostRefusal.LAUNCH_FAILED) from error
            with self._lock:
                self._process = process
            try:
                process.write_input(frame)
            except OSError as error:
                raise AgentHostError(AgentHostRefusal.LAUNCH_FAILED) from error
        finally:
            wipe(frame)
        try:
            line = process.read_output_line(limit=READY_LINE_MAX_BYTES, timeout=self._launch.ready_timeout)
        except (TimeoutError, OSError) as error:
            raise AgentHostError(AgentHostRefusal.NOT_READY) from error
        return _ready_from_line(line, resolved.generations)

    def _retire(self) -> None:
        with self._lock:
            process = self._process
            self._process = None
            self._ready = None
            self._state = AgentHostState.STOPPING if process is not None else AgentHostState.DETACHED
        if process is None:
            return
        try:
            with contextlib.suppress(OSError):
                process.close_input()
            # Give the agent its grace to settle the live run, then end the whole
            # tree either way: an exited agent can leave descendants running.
            process.wait(timeout=self._launch.stop_grace)
            process.terminate(timeout=self._launch.terminate_timeout)
        finally:
            with self._lock:
                self._state = AgentHostState.DETACHED


def _ready_from_line(line: bytes, generations: AgentGenerations) -> AgentReady:
    try:
        document = json.loads(line)
    except (ValueError, UnicodeDecodeError) as error:
        raise AgentHostError(AgentHostRefusal.NOT_READY) from error
    try:
        ready = _ReadyLine.model_validate(document)
    except ValidationError:
        try:
            refusal = _RefusalLine.model_validate(document)
        except ValidationError as error:
            raise AgentHostError(AgentHostRefusal.NOT_READY) from error
        raise AgentHostError(AgentHostRefusal.AGENT_REFUSED, agent_code=refusal.code) from None
    return AgentReady(
        generations=generations,
        gateway_port=ready.gateway_port,
        agent_version=ready.agent_version,
        hosting_contract=ready.hosting_contract,
    )

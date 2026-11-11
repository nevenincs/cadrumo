"""The service's demand that the runtime manager start the local AI server before a local read.

The local AI server sleeps until a document is read on this computer. Before a
run on a lane whose engine runs here, the service asks the runtime manager to
start the server, waits until the server listens, and renews the demand while
the run lasts, so the manager's idle stop never ends a read. The manager admits
the demand only from the agent service its admitted desktop started.

The desktop that starts the service names the manager's pipe and the images
that may serve it. A pipe name alone never authenticates its server: the service
reads the kernel's account of the server process and requires one of those
images, owned by this user. Without those names, as outside a package, nothing
is demanded and the run goes as before. A demand the manager refuses, or one
that cannot reach it, refuses the run as ``lane_unavailable``; the setup row
says why the local AI cannot run.
"""

from __future__ import annotations

import json
import socket
import sys
import time
from collections.abc import Callable, Mapping
from enum import StrEnum
from pathlib import Path
from threading import Event, Thread
from typing import Final, Protocol, override

from cadrumo.core.config_runtime_fields import LLAMA_SERVER_ADDRESS, LOCAL_AI_SERVER_ADDRESS
from cadrumo.core.type_guards import is_object_list, is_str_keyed_dict
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.model_runs import (
    ModelRunBody,
    ModelRunLane,
    ModelRunOutput,
    ModelRunRefusal,
    ModelRunRefusalCode,
)
from cadrumo_client.transport.windows_channel import WindowsChannel
from cadrumo_client.transport.windows_native_io import (
    CLIENT_PIPE_ACCESS,
    SECURITY_IDENTIFICATION,
    SECURITY_SQOS_PRESENT,
    native_windows_call,
    windows_deadline_milliseconds,
)

from ..providers.application.model_runs import BackgroundRunGateway
from ..providers.domain.catalog import BackgroundOption
from ..providers.domain.record import LocalEngine

DEMAND_PIPE_VARIABLE: Final = "CADRUMO_LOCAL_AI_DEMAND_PIPE"
"""The runtime manager's pipe, which the desktop names when it starts the service."""
DEMAND_SERVERS_VARIABLE: Final = "CADRUMO_LOCAL_AI_DEMAND_SERVERS"
"""The JSON array of the images that may serve that pipe: the package's manager and desktop."""
SERVICE_SLOTS: Final = frozenset({DEMAND_PIPE_VARIABLE, DEMAND_SERVERS_VARIABLE})
"""The launch slots the desktop fills for the service, which its package profile declares."""

RENEW_SECONDS: Final = 60.0
"""How often a demand is renewed while its read lasts, well inside the manager's idle stop."""
LISTEN_WAIT_SECONDS: Final = 60.0
"""The longest a read waits for a demanded server to listen."""
_DEMAND_SECONDS: Final = 5.0
_RETRY_SECONDS: Final = 0.25
_MAXIMUM_RESPONSE_BYTES: Final = 4096
_REQUEST: Final = json.dumps({"request": "demand_local_ai", "schema": 1}).encode()

_ADDRESSES: Final[Mapping[LocalEngine, str]] = {
    LocalEngine.LLAMACPP: LLAMA_SERVER_ADDRESS,
    LocalEngine.OLLAMA: LOCAL_AI_SERVER_ADDRESS,
}


class DemandOutcome(StrEnum):
    """The manager's answer to a demand."""

    DEMANDED = "local_ai_demanded"
    """The server runs, or starts at once."""
    NOT_SET_UP = "local_ai_not_set_up"
    """The selected engine's program is not set up."""
    HELD = "local_ai_held"
    """The engine's program is being changed; the server starts once that is done."""
    NOT_RUNNING = "local_ai_not_running"
    """The server's supervision is not running, or no server can run in this package."""


class LocalAiDemand(Protocol):
    """One demand to the runtime manager: its answer, or ``None`` where no trusted manager answered."""

    def __call__(self) -> DemandOutcome | None:
        """Demand the local AI server once."""
        ...


def decode_demand_response(payload: bytes) -> DemandOutcome | None:
    """The outcome a manager response carries; ``None`` for anything outside the demand's answers."""
    try:
        response = json.loads(payload)
    except ValueError:
        return None
    if not is_str_keyed_dict(response) or response.get("schema") != 1:
        return None
    outcome = response.get("outcome")
    try:
        return DemandOutcome(outcome) if isinstance(outcome, str) else None
    except ValueError:
        return None


class ManagerPipeDemand:
    """Demand the local AI server over the runtime manager's pipe, from a server of an admitted image."""

    def __init__(self, *, pipe: str, servers: tuple[Path, ...]) -> None:
        """Bind the pipe and the images that may serve it."""
        self._pipe = pipe
        self._servers = tuple(server.resolve() for server in servers)

    def __call__(self) -> DemandOutcome | None:
        """Send one demand and read its answer, within a few seconds; ``None`` where none came."""
        deadline = time.monotonic() + _DEMAND_SECONDS
        channel = self._connected(deadline)
        if channel is None:
            return None
        try:
            if channel.image_path not in self._servers:
                return None
            channel.write_all(_REQUEST, deadline=deadline)
            response = bytearray()
            # The manager answers one small message; it is read up to its closing brace.
            while len(response) < _MAXIMUM_RESPONSE_BYTES:
                response += channel.read_exact(1, deadline=deadline)
                if response.endswith(b"}") and (outcome := decode_demand_response(bytes(response))) is not None:
                    return outcome
            return None
        except RefusalError:
            return None
        finally:
            channel.close()

    def _connected(self, deadline: float) -> WindowsChannel | None:
        """The pipe's channel, or ``None`` where no server of this user answers on it."""
        try:
            return self._connect(deadline)
        except RefusalError:
            return None

    def _connect(self, deadline: float) -> WindowsChannel:
        """Open the pipe with narrow rights; the channel then verifies the server's owner."""
        import pywintypes
        import win32file
        import win32pipe

        while True:
            try:
                handle = win32file.CreateFile(
                    self._pipe,
                    CLIENT_PIPE_ACCESS,
                    0,
                    None,
                    win32file.OPEN_EXISTING,
                    win32file.FILE_FLAG_OVERLAPPED | SECURITY_SQOS_PRESENT | SECURITY_IDENTIFICATION,
                    None,
                )
                return WindowsChannel(int(handle.Detach()), server=False)
            except pywintypes.error as error:
                if error.winerror != 231:
                    raise RefusalError(RefusalCode.ENDPOINT_NOT_READY) from None
                try:
                    native_windows_call(win32pipe, "WaitNamedPipe", self._pipe, windows_deadline_milliseconds(deadline))
                except pywintypes.error:
                    raise RefusalError(RefusalCode.ENDPOINT_NOT_READY) from None


def manager_demand_from_environment(environment: Mapping[str, str]) -> ManagerPipeDemand | None:
    """The demand the desktop named when it started this service; ``None`` where it named none.

    The manager's pipe is a Windows named pipe; elsewhere no demand is named.
    """
    if sys.platform == "win32":
        return _named_demand(environment)
    return None


def _named_demand(environment: Mapping[str, str]) -> ManagerPipeDemand | None:
    """The demand the variables name; ``None`` where they name none, or name it malformed."""
    pipe = environment.get(DEMAND_PIPE_VARIABLE, "")
    servers = _server_images(environment.get(DEMAND_SERVERS_VARIABLE, ""))
    if not pipe or servers is None:
        return None
    return ManagerPipeDemand(pipe=pipe, servers=servers)


def _server_images(named: str) -> tuple[Path, ...] | None:
    """The absolute images a JSON array names; ``None`` for anything else, or for none."""
    try:
        images = json.loads(named) if named else None
    except ValueError:
        return None
    if not is_object_list(images) or not images:
        return None
    paths = tuple(map(_absolute_image, images))
    return None if None in paths else tuple(path for path in paths if path is not None)


def _absolute_image(image: object) -> Path | None:
    """One named image as an absolute path, or ``None`` where it names none."""
    if not isinstance(image, str):
        return None
    path = Path(_plain_spelling(image))
    return path if image and path.is_absolute() else None


def _plain_spelling(image: str) -> str:
    """An image path as the kernel reports a process image: without the verbatim prefix a canonical path carries."""
    if image.startswith(_VERBATIM_UNC):
        return "\\\\" + image.removeprefix(_VERBATIM_UNC)
    return image.removeprefix(_VERBATIM)


_VERBATIM: Final = "\\\\?\\"
_VERBATIM_UNC: Final = _VERBATIM + "UNC\\"


def server_listens(engine: LocalEngine) -> bool:
    """Whether the engine's loopback server accepts a connection now."""
    host, _, port = _ADDRESSES[engine].rpartition(":")
    try:
        with socket.create_connection((host, int(port)), timeout=1.0):
            return True
    except OSError:
        return False


class LocalAiDemandingRuns(BackgroundRunGateway):
    """Runs that demand the local AI server first on a lane whose engine runs on this computer."""

    def __init__(
        self,
        *,
        runs: BackgroundRunGateway,
        demand: LocalAiDemand | None,
        listens: Callable[[LocalEngine], bool] = server_listens,
        renew_seconds: float = RENEW_SECONDS,
        listen_wait_seconds: float = LISTEN_WAIT_SECONDS,
        retry_seconds: float = _RETRY_SECONDS,
    ) -> None:
        """Wrap ``runs``; ``demand`` is ``None`` where the desktop named no manager."""
        self._runs = runs
        self._demand = demand
        self._listens = listens
        self._renew_seconds = renew_seconds
        self._listen_wait_seconds = listen_wait_seconds
        self._retry_seconds = retry_seconds

    @override
    def run(
        self, *, lane: ModelRunLane, body: ModelRunBody, deadline_seconds: int, options: tuple[BackgroundOption, ...]
    ) -> ModelRunOutput | ModelRunRefusal:
        """Demand the server, wait until it listens, and run while renewing the demand."""
        engine = _local_engine(lane)
        if engine is None or self._demand is None:
            return self._runs.run(lane=lane, body=body, deadline_seconds=deadline_seconds, options=options)
        demand = self._demand
        if not self._started(demand, engine):
            return ModelRunRefusal(code=ModelRunRefusalCode.LANE_UNAVAILABLE)
        stop = Event()
        renewal = Thread(target=self._renew, args=(demand, stop), name="local-ai-demand", daemon=True)
        renewal.start()
        try:
            return self._runs.run(lane=lane, body=body, deadline_seconds=deadline_seconds, options=options)
        finally:
            stop.set()
            renewal.join()

    def _started(self, demand: LocalAiDemand, engine: LocalEngine) -> bool:
        """Whether a taken demand's server listens within the wait; a held demand is asked again."""
        deadline = time.monotonic() + self._listen_wait_seconds
        taken = False
        while True:
            if not taken:
                outcome = demand()
                if outcome is DemandOutcome.DEMANDED:
                    taken = True
                elif outcome is not DemandOutcome.HELD:
                    return False
            if taken and self._listens(engine):
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(self._retry_seconds)

    def _renew(self, demand: LocalAiDemand, stop: Event) -> None:
        # A renewal the manager does not take ends nothing here: the run reports its own outcome.
        while not stop.wait(self._renew_seconds):
            demand()


def _local_engine(lane: ModelRunLane) -> LocalEngine | None:
    """The engine a lane runs on this computer; ``None`` for a lane that reads elsewhere."""
    if lane.reads_off_host:
        return None
    try:
        return LocalEngine(lane.provider_id)
    except ValueError:
        return None


__all__ = [
    "DEMAND_PIPE_VARIABLE",
    "DEMAND_SERVERS_VARIABLE",
    "SERVICE_SLOTS",
    "DemandOutcome",
    "LocalAiDemand",
    "LocalAiDemandingRuns",
    "ManagerPipeDemand",
    "decode_demand_response",
    "manager_demand_from_environment",
    "server_listens",
]

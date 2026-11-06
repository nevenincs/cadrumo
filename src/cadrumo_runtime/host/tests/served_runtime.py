"""A real in-process runtime that serves native frontend peers over a test storage root."""

from __future__ import annotations

import sys
import time
from collections.abc import Callable, Generator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from threading import Event
from typing import Literal
from uuid import UUID, uuid4

from cadrumo.application.operations.frontend_projection import OperationPublicProjectionV1
from cadrumo.application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
)
from cadrumo.application.operations.models import OperationId
from cadrumo.application.user_profile.access_contracts import LoginEligibility, OsLockState, OsLoginContext
from cadrumo.application.user_profile.automation_custody_port import AutomationSecretStore
from cadrumo.core.operations import OperationFrontendProjection
from cadrumo_client.contracts.access_vocabulary import Availability
from cadrumo_client.contracts.contracts import ByteChannel, ClientHello
from cadrumo_client.contracts.deadline_budget import exchange_deadline
from cadrumo_client.contracts.login import LoginEvidence
from cadrumo_client.contracts.operation_access import (
    OperationAcknowledged,
    OperationControl,
    OperationObserve,
    OperationObserved,
)
from cadrumo_client.contracts.profile_access import ProfileLogin, ProfileStatus
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_client.transport.startup import LaunchDoor
from cadrumo_client.transport.windows import WindowsEndpoint

from ...adapters.tests.profile_worker_support import owner_id
from ...adapters.tests.retained_server import RetainedRuntimeTransportServer
from ..profile_connections import RuntimeProfileConnections


@dataclass
class SyntheticLogin:
    """Supply explicit synthetic OS-login facts; transport, custody and authority stay real."""

    login_id: str

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=owner_id(),
            active=True,
            lock_state=OsLockState.UNLOCKED,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


@dataclass(frozen=True)
class ServedRuntime:
    """The running transport with the coordinates a test needs to reach or observe it."""

    server: RetainedRuntimeTransportServer
    profiles: RuntimeProfileConnections
    stop: Event
    boot: UUID
    launch: LaunchDoor
    pool: ThreadPoolExecutor


@contextmanager
def serving_runtime(
    endpoint: WindowsEndpoint,
    root: Path,
    *,
    capture_login: Callable[[ByteChannel], LoginEvidence],
    secret_store: Callable[[], AutomationSecretStore],
    workers: int = 1,
    ready_seconds: float = 3,
    drain_seconds: float = 20,
    product_version: str = "test",
) -> Generator[ServedRuntime]:
    """Serve ``endpoint`` until the scope ends, drain the host, then close the endpoint.

    A drain failure is raised only when the scope itself succeeded, so it never hides the failure under test.
    """
    stop, boot = Event(), uuid4()
    profiles = RuntimeProfileConnections(
        storage_root=root,
        storage_identity=endpoint.storage_identity,
        runtime_boot_id=boot,
        stop=stop,
        capture_login=capture_login,
        secret_store=secret_store,
    )
    profiles.prepare_registry()
    server = RetainedRuntimeTransportServer(
        endpoint, product_version=product_version, stop=stop, profiles=profiles, boot_id=boot
    )
    launch = LaunchDoor(
        endpoint, expected=ClientHello(product_version=product_version, storage_identity=endpoint.storage_identity)
    )
    with ThreadPoolExecutor(max_workers=workers) as pool:
        running = pool.submit(server.serve)
        try:
            assert server.ready.wait(ready_seconds), "the runtime transport did not start listening"
            yield ServedRuntime(server=server, profiles=profiles, stop=stop, boot=boot, launch=launch, pool=pool)
        finally:
            primary = sys.exception()
            stop.set()
            try:
                try:
                    running.result(timeout=drain_seconds)
                except Exception:
                    if primary is None:
                        raise
            finally:
                endpoint.close()


def connect_verified(endpoint: WindowsEndpoint) -> VerifiedConnection:
    """Open a handshaken connection to a test runtime that announces the ``test`` product version."""
    return VerifiedConnection(
        endpoint.connect(timeout=3),
        expected=ClientHello(product_version="test", storage_identity=endpoint.storage_identity),
        deadline=time.monotonic() + 3,
    )


def connect_installed(endpoint: WindowsEndpoint) -> VerifiedConnection:
    """Open a handshaken connection to a runtime that announces the installed product version."""
    return VerifiedConnection(
        endpoint.connect(timeout=3),
        expected=ClientHello(product_version=version("cadrumo"), storage_identity=endpoint.storage_identity),
        deadline=time.monotonic() + 3,
    )


def admit_session(
    connection: VerifiedConnection,
    profile_id: UUID,
    *,
    method: Literal["password", "receipt", "api_key"],
    proof: bytes,
    frontend: OperationFrontendProjection = OperationFrontendProjection.CLI,
    deadline_seconds: float | None = None,
) -> UUID:
    """Sign in over ``connection`` and return the admitted session, checking the proof buffer was wiped.

    The exchange budget is the runtime's own unless ``deadline_seconds`` bounds it.
    """
    secret = bytearray(proof)
    reply = connection.login(
        ProfileLogin(request_id=uuid4(), profile_id=profile_id, frontend=frontend, method=method),
        secret,
        deadline=exchange_deadline() if deadline_seconds is None else time.monotonic() + deadline_seconds,
    )
    assert secret == bytes(len(proof))
    assert isinstance(reply, ProfileStatus), reply
    assert reply.status.session_id is not None
    return reply.status.session_id


def start_and_settle(
    connection: VerifiedConnection,
    profile_id: UUID,
    session_id: UUID,
    operation_id: OperationId,
    *,
    settle_seconds: float,
    start_seconds: float = 10,
) -> OperationPublicProjectionV1:
    """Start an accepted operation and poll its observation until it reaches a terminal condition."""
    started = connection.operation(
        OperationControl(
            action="operation_start",
            request_id=uuid4(),
            profile_id=profile_id,
            session_id=session_id,
            operation_id=operation_id,
        ),
        deadline=time.monotonic() + start_seconds,
    )
    assert isinstance(started, OperationAcknowledged), started
    deadline = time.monotonic() + settle_seconds
    while True:
        observed = connection.operation(
            OperationObserve(
                request_id=uuid4(),
                profile_id=profile_id,
                session_id=session_id,
                observation=OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=32),
            ),
            deadline=deadline,
        )
        assert isinstance(observed, OperationObserved), observed
        assert isinstance(observed.observation, OperationObservationSuccessV1)
        projection = observed.observation.projection
        if projection.terminal_condition is not None:
            return projection
        assert time.monotonic() < deadline
        time.sleep(0.02)

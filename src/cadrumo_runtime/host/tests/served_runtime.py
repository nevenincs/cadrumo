"""A real in-process runtime that serves native frontend peers over a test storage root."""

from __future__ import annotations

import sys
from collections.abc import Callable, Generator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

from cadrumo.application.user_profile.access_contracts import LoginEligibility, OsLockState, OsLoginContext
from cadrumo.application.user_profile.automation_custody_port import AutomationSecretStore
from cadrumo_client.contracts.access_vocabulary import Availability
from cadrumo_client.contracts.contracts import ByteChannel, ClientHello
from cadrumo_client.contracts.login import LoginEvidence
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
        endpoint, product_version="test", stop=stop, profiles=profiles, boot_id=boot
    )
    launch = LaunchDoor(
        endpoint, expected=ClientHello(product_version="test", storage_identity=endpoint.storage_identity)
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

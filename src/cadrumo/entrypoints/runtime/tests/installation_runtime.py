"""A real runtime that serves installation acts from a small registry of handlers.

The native transport, the connection service, the installation door and the
framing are the real ones. The native login the runtime observes is a port the
test holds, and the handlers are the test's own, except recovery enrolment,
which runs the real custody service.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from threading import Event
from uuid import uuid4

from cadrumo.adapters.local_runtime.tests.retained_server import RetainedRuntimeTransportServer
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.automation_store_composition import installed_automation_secret_store
from cadrumo.adapters.persistence.storage.profile_persistence_composition import composed_profile_persistence_ports
from cadrumo.application.runtime.installation_requests import (
    INSTALLATION_LOG_TAIL_MAX_LINES,
    RuntimeInstallationPassphrase,
    RuntimeRecoveryEnrollReply,
    RuntimeRecoveryEnrollRequest,
    RuntimeRepairLogsReply,
    RuntimeRepairLogsRequest,
    RuntimeStorageCheckReply,
    RuntimeStorageCheckRequest,
    RuntimeStorageInitReply,
    RuntimeStorageInitRequest,
    RuntimeStorageReclaimReply,
    RuntimeStorageReclaimRequest,
)
from cadrumo.application.storage_management.errors import StorageReclaimUnconfirmedError
from cadrumo.application.user_profile.access_contracts import (
    Availability,
    LoginEligibility,
    OsLockState,
    OsLoginContext,
)
from cadrumo.application.user_profile.automation_custody_port import AutomationSecretStore
from cadrumo.application.user_profile.recovery_custody import ProfileRecoveryEnrollment, enroll_profile_recovery

from ..installation_composition import InstallationActRegistry
from ..installation_door import InstallationActExchange
from ..profile_connections import RuntimeProfileConnections

LOG_LINES = tuple(f"{index:06d} " + "x" * 200 for index in range(INSTALLATION_LOG_TAIL_MAX_LINES))
"""A log tail whose reply is larger than one frame and smaller than the transfer bound."""

FAULT_TEXT = "synthetic-fault-text-that-must-stay-private"
"""The message of the fault one handler stops on; no reply or log record may carry it."""


class InstallationLogin:
    """Native login evidence whose observation the test sets."""

    login_id = "synthetic-installation-login"

    def __init__(self, *, owner: str, lock_state: OsLockState = OsLockState.UNLOCKED, active: bool = True) -> None:
        """Start as the given account's observation."""
        self.owner, self.lock_state, self.active = owner, lock_state, active

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        """Return the observation as it stands now."""
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=self.owner,
            active=self.active,
            lock_state=self.lock_state,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


def serve_check(request: RuntimeStorageCheckRequest, exchange: InstallationActExchange) -> RuntimeStorageCheckReply:
    """Answer with a healthy tree rooted where the runtime's storage is."""
    del request
    return exchange.reply(
        RuntimeStorageCheckReply,
        storage_root=str(exchange.storage_root),
        healthy=True,
        root_mode_enforced=False,
        checked_areas=4,
    )


def serve_tail(request: RuntimeRepairLogsRequest, exchange: InstallationActExchange) -> RuntimeRepairLogsReply:
    """Answer with as many synthetic log lines as were asked for."""
    return exchange.reply(
        RuntimeRepairLogsReply, path=str(exchange.storage_root / "cadrumo.log"), lines=LOG_LINES[: request.lines]
    )


def serve_reclaim(
    request: RuntimeStorageReclaimRequest, exchange: InstallationActExchange
) -> RuntimeStorageReclaimReply:
    """Refuse as the storage service refuses an unconfirmed reclaim."""
    del exchange
    raise StorageReclaimUnconfirmedError(request.area, entry_count=3)


def serve_fault(request: RuntimeStorageInitRequest, exchange: InstallationActExchange) -> RuntimeStorageInitReply:
    """Stop on a fault that has no public facts."""
    raise ValueError(FAULT_TEXT)


def serve_enroll(
    request: RuntimeRecoveryEnrollRequest, exchange: InstallationActExchange
) -> RuntimeRecoveryEnrollReply:
    """Enrol through the real custody service, taking the passphrase in and handing the code out."""
    profile_id = request.profile_id
    assert profile_id is not None
    secrets = exchange.receive_secret(RuntimeInstallationPassphrase)

    def handover(enrollment: ProfileRecoveryEnrollment) -> str:
        read_back = exchange.deliver_secret(bytearray(enrollment.recovery_key.code, "utf-8"))
        return read_back.get_secret_value().decode("utf-8")

    with (
        exchange.reserve_profiles((profile_id,)),
        composed_profile_persistence_ports(automation_secrets_store=exchange.secret_store()),
    ):
        outcome = enroll_profile_recovery(
            profile_id=profile_id,
            current_passphrase=secrets.passphrase.get_secret_value(),
            root=exchange.storage_root,
            recovery_handover=handover,
        )
    return exchange.reply(
        RuntimeRecoveryEnrollReply, profile_id=outcome.profile_id, enrolled=outcome.enrolled, changed=outcome.changed
    )


def installation_test_acts() -> InstallationActRegistry:
    """Register the handlers above; every other act stays without one."""
    registry = InstallationActRegistry()
    registry.register(RuntimeStorageCheckRequest, serve_check)
    registry.register(RuntimeRepairLogsRequest, serve_tail)
    registry.register(RuntimeStorageReclaimRequest, serve_reclaim)
    registry.register(RuntimeStorageInitRequest, serve_fault)
    registry.register(RuntimeRecoveryEnrollRequest, serve_enroll)
    return registry


@contextmanager
def serving_installation_runtime(
    endpoint: WindowsRuntimeEndpoint,
    root: Path,
    login: InstallationLogin,
    *,
    secret_store: Callable[[], AutomationSecretStore] = installed_automation_secret_store,
    product_version: str = "test",
) -> Iterator[RuntimeProfileConnections]:
    """Serve the real transport over ``root`` until the scope ends, then drain it.

    The connection service is yielded so a test can observe what the runtime holds while an act runs.
    """
    stop, boot = Event(), uuid4()
    profiles = RuntimeProfileConnections(
        storage_root=root,
        storage_identity=endpoint.storage_identity,
        runtime_boot_id=boot,
        stop=stop,
        capture_login=lambda _channel: login,
        secret_store=secret_store,
        installation_acts=installation_test_acts(),
    )
    server = RetainedRuntimeTransportServer(
        endpoint, product_version=product_version, stop=stop, profiles=profiles, boot_id=boot
    )
    with ThreadPoolExecutor(max_workers=1) as pool:
        running = pool.submit(server.serve)
        try:
            if not server.ready.wait(3):
                raise TimeoutError("the installation test runtime did not become ready")
            yield profiles
        finally:
            stop.set()
            running.result(timeout=25)

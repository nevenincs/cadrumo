"""Local connection lifecycle over the existing profile authentication authority."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from threading import BoundedSemaphore, Event, RLock
from uuid import UUID

from cadrumo.adapters.persistence.storage.custody.automation_store_composition import installed_automation_secret_store

from ...adapters.local_runtime.login import capture_runtime_login
from ...application.operations.registry import OperationRegistry
from ...application.runtime.contracts import (
    RuntimeByteChannel,
    RuntimeExitReason,
    RuntimeRefusalCode,
    RuntimeRefusalError,
)
from ...application.runtime.installation import RuntimeInstallation
from ...application.runtime.login import RuntimeLoginEvidence, RuntimeLoginInventory
from ...application.runtime.profile_access import (
    RuntimeProfileDrainResult,
)
from ...application.user_profile.access_contracts import (
    Availability,
    LoginEligibility,
)
from ...application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
    AutomationSecretStore,
)
from ...core.logging import get_logger
from ...core.time.clock import now
from ..operation_composition import build_production_operation_registry
from .access_management import RuntimeAccessManagement
from .enrollment_connections import RuntimeEnrollmentConnections
from .profile_connection_access import ProfileConnectionAccessMixin
from .profile_connection_admission import ProfileConnectionAdmissionMixin
from .profile_connection_drain import ProfileConnectionDrainMixin, ProfileDrainRecord
from .profile_connection_operations import ProfileConnectionOperationMixin
from .profile_connection_sessions import ProfileConnectionSessionMixin
from .profile_host import ProfileConnection, RuntimeProfileHost
from .shutdown import request_runtime_stop

_LOGGER = get_logger(__name__)


class RuntimeProfileConnections(
    ProfileConnectionAdmissionMixin,
    ProfileConnectionAccessMixin,
    ProfileConnectionSessionMixin,
    ProfileConnectionOperationMixin,
    ProfileConnectionDrainMixin,
):
    """Keep native connection identity distinct from key routing and proof of possession."""

    def __init__(
        self,
        *,
        storage_root: Path,
        storage_identity: str,
        runtime_boot_id: UUID,
        stop: Event,
        capture_login: Callable[[RuntimeByteChannel], RuntimeLoginEvidence] = capture_runtime_login,
        login_inventory: Callable[[], RuntimeLoginInventory] | None = None,
        secret_store: Callable[[], AutomationSecretStore] = installed_automation_secret_store,
        worker_script: Path | None = None,
        wall_clock: Callable[[], datetime] = now,
    ) -> None:
        """Defer installation/profile/store access until an eligible peer requests login."""
        self.root, self.storage_identity, self.boot, self.stop = storage_root, storage_identity, runtime_boot_id, stop
        self._capture, self._secret_store = capture_login, secret_store
        self._login_inventory = login_inventory
        self._eligible_login_seen = False
        self._login_lifecycle_available = False
        self._worker_script, self._wall_clock = worker_script, wall_clock
        self._guard = RLock()
        self._drain_guard = RLock()
        self._drain_records: dict[UUID, ProfileDrainRecord] | None = None
        self._drain_result: RuntimeProfileDrainResult | None = None
        self._installation: RuntimeInstallation | None = None
        self._registry: OperationRegistry | None = None
        self._profiles: dict[UUID, RuntimeProfileHost] = {}
        self._submission_slots = BoundedSemaphore(4)
        self._connections: dict[UUID, ProfileConnection] = {}
        self._logins: dict[str, RuntimeLoginEvidence] = {}
        self._closed = False
        self._last_poll = 0.0
        self._enrollments = RuntimeEnrollmentConnections(prepare=self._prepare_enrollment, admitting=self._admitting)
        self._management = RuntimeAccessManagement(
            resolve=self._resolve_access_management,
            validate=self._validate_access_connection,
            lock_changed=self._profile_lock_changed,
            synchronize=self._synchronize_profile_sessions,
        )

    def _connected(self, connection_id: UUID) -> ProfileConnection:
        with self._guard:
            connection = self._connections.get(connection_id)
            if self._closed or connection is None:
                raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
            return connection

    def _login_contexts(self) -> tuple[RuntimeLoginEvidence, ...]:
        with self._guard:
            peers = tuple(self._logins.values())
        if self._login_inventory is None:
            return peers
        inventory = self._login_inventory()
        logins = {login.login_id: login for login in inventory.logins}
        # Preserve the original captured incarnation for human/attended leases.
        # A fresh login cannot replace their originating native proof.
        logins.update((login.login_id, login) for login in peers)
        observed = tuple(login.observe(credential_facilities=Availability.UNAVAILABLE) for login in logins.values())
        eligible = any(login.active and login.unattended is LoginEligibility.ELIGIBLE for login in observed)
        with self._guard:
            self._login_lifecycle_available = eligible
            if eligible:
                self._eligible_login_seen = True
            elif self._eligible_login_seen:
                # Losing every positive witness also retires custody when
                # absence is UNKNOWN. This availability choice does not prove
                # logout or change grants; positive locked witnesses survive.
                # The existing server owns bounded drain and custody release.
                _LOGGER.warning("no eligible login witness remains; stopping the runtime")
                request_runtime_stop(self.stop, RuntimeExitReason.LOGIN_WITNESS_LOSS)
        return tuple(logins.values())

    def _private_work_available(self) -> bool:
        return self._admitting() and (self._login_inventory is None or self._login_lifecycle_available)

    def _admitting(self) -> bool:
        return not self._closed and not self.stop.is_set()

    def prepare_registry(self) -> OperationRegistry:
        """Validate the public operation graph before transport readiness.

        This is profile independent and never opens a profile or credential.
        Repeated preparation retains the one graph used by every host in this
        runtime process.
        """
        with self._guard:
            if not self._admitting():
                raise RuntimeRefusalError(RuntimeRefusalCode.DRAINING)
            registry = self._registry
            if registry is None:
                registry = build_production_operation_registry()
                if not self._admitting():
                    raise RuntimeRefusalError(RuntimeRefusalCode.DRAINING)
                self._registry = registry
            if not self._admitting():
                raise RuntimeRefusalError(RuntimeRefusalCode.DRAINING)
            return registry

    def poll(self) -> None:
        """Fence idle leases on expiry, native logout/lock or unavailable custody."""
        instant = time.monotonic()
        if instant - self._last_poll < 0.5:
            return
        self._last_poll = instant
        self._login_contexts()
        if not self._admitting():
            return
        self._enrollments.poll()
        with self._guard:
            if not self._admitting():
                return
            hosts = tuple(self._profiles.values())
        for host in hosts:
            retired = host.retire_replaced_binding(deadline=time.monotonic() + 15)
            if retired is None:
                continue
            if retired:
                self._remove_retired_host(host)
                continue
            host.approvals.expire()
            self._retired(host.authority.revalidate_sessions())
            if host.owner.lost:
                host.close()
                self._remove_retired_host(host)

    def _remove_retired_host(self, host: RuntimeProfileHost) -> None:
        """Forget only the contained incarnation; old connections gain no new lease."""
        profile_id = host.store.binding.profile_id
        self._enrollments.retire_profile(profile_id, host=host)
        with self._guard:
            if self._profiles.get(profile_id) is host:
                self._profiles.pop(profile_id)
                for connection in self._connections.values():
                    if connection.profile_id == profile_id:
                        connection.session_id = None

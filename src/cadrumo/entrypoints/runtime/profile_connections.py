"""Local connection lifecycle over the existing profile authentication authority."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from threading import BoundedSemaphore, Event, RLock
from uuid import UUID

from cadrumo.adapters.persistence.storage.custody.automation_store_composition import installed_automation_secret_store

from ...adapters.local_runtime.installation import read_runtime_installation
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
from ...application.runtime.session_events import RuntimeSessionEvent
from ...application.runtime.transport import RuntimeConnectionContext
from ...application.user_profile.access_contracts import (
    Availability,
    LoginEligibility,
    OsLoginContext,
)
from ...application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
    AutomationSecretStore,
)
from ...core.diagnostic_log import diagnostic_event
from ...core.logging import get_logger
from ...core.time.clock import now
from ..operation_composition import build_production_operation_registry
from .access_management import RuntimeAccessManagement
from .bootstrap_delete import RuntimeBootstrapDeleteMixin
from .bootstrap_reset import RuntimeBootstrapMixin
from .enrollment_connections import RuntimeEnrollmentConnections
from .profile_connection_access import ProfileConnectionAccessMixin
from .profile_connection_admission import ProfileConnectionAdmissionMixin
from .profile_connection_drain import ProfileConnectionDrainMixin, ProfileDrainRecord
from .profile_connection_operations import ProfileConnectionOperationMixin
from .profile_connection_sessions import ProfileConnectionSessionMixin
from .profile_host import ProfileConnection, RuntimeProfileHost
from .session_events import RuntimeSessionEvents
from .shutdown import request_runtime_stop
from .sign_in_sweep import sweep_saved_sign_ins

_LOGGER = get_logger(__name__)


class RuntimeProfileConnections(
    RuntimeBootstrapMixin,
    RuntimeBootstrapDeleteMixin,
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
        os_owner_id: str | None = None,
    ) -> None:
        """Defer installation/profile/store access until an eligible peer requests login."""
        self.root, self.storage_identity, self.boot, self.stop = storage_root, storage_identity, runtime_boot_id, stop
        self._capture, self._secret_store = capture_login, secret_store
        self._login_inventory = login_inventory
        self._os_owner_id = os_owner_id
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
        self._custody_mutations: set[UUID] = set()
        self._submission_slots = BoundedSemaphore(4)
        self._connections: dict[UUID, ProfileConnection] = {}
        self._events = RuntimeSessionEvents()
        self._logins: dict[str, RuntimeLoginEvidence] = {}
        self._closed = False
        self._idle_fenced = False
        self._operation_requests = 0
        self._last_poll = 0.0
        self._last_sign_in_sweep = 0.0
        self._enrollments = RuntimeEnrollmentConnections(prepare=self._prepare_enrollment, admitting=self._admitting)
        self._management = RuntimeAccessManagement(
            resolve=self._resolve_access_management,
            validate=self._validate_access_connection,
            lock_changed=self._profile_lock_changed,
            synchronize=self._synchronize_profile_sessions,
        )

    def connect_events(self, context: RuntimeConnectionContext) -> None:
        """Register a native-verified connection without admitting profile access."""
        self._events.connect(context)

    def take_events(self, context: RuntimeConnectionContext) -> tuple[RuntimeSessionEvent, ...]:
        """Let the connection's sole writer drain its bounded event queue."""
        return self._events.take(context)

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
        inventory_started = time.monotonic()
        inventory = self._login_inventory()
        inventory_elapsed_ms = round((time.monotonic() - inventory_started) * 1000, 3)
        logins = {login.login_id: login for login in inventory.logins}
        # Preserve the original captured incarnation for human/attended leases.
        # A fresh login cannot replace their originating native proof.
        logins.update((login.login_id, login) for login in peers)
        observation_started = time.monotonic()
        observed = tuple(login.observe(credential_facilities=Availability.UNAVAILABLE) for login in logins.values())
        observation_elapsed_ms = round((time.monotonic() - observation_started) * 1000, 3)
        eligible = any(login.active and login.unattended is LoginEligibility.ELIGIBLE for login in observed)
        instant = time.monotonic()
        if not eligible or instant - self._last_sign_in_sweep >= 1.0:
            self._sweep_sign_ins(observed, complete=inventory.complete, include_hosted=not eligible)
            self._last_sign_in_sweep = instant
        with self._guard:
            self._login_lifecycle_available = eligible
            if eligible:
                self._eligible_login_seen = True
            elif self._eligible_login_seen:
                # Losing every positive witness also retires custody when
                # absence is UNKNOWN. This availability choice does not prove
                # logout or change grants; positive locked witnesses survive.
                # The existing server owns bounded drain and custody release.
                diagnostic_event(
                    _LOGGER,
                    "no eligible login witness remains; stopping the runtime",
                    level=logging.WARNING,
                    fields={
                        "reason_code": "login_witness_loss",
                        "inventory_complete": inventory.complete,
                        "inventory_login_count": len(inventory.logins),
                        "retained_peer_witness_count": len(peers),
                        "observed_active_count": sum(login.active for login in observed),
                        "observed_eligible_count": sum(
                            login.active and login.unattended is LoginEligibility.ELIGIBLE for login in observed
                        ),
                        "observed_unknown_count": sum(
                            login.unattended is LoginEligibility.UNKNOWN for login in observed
                        ),
                        "inventory_elapsed_ms": inventory_elapsed_ms,
                        "observation_elapsed_ms": observation_elapsed_ms,
                    },
                )
                request_runtime_stop(self.stop, RuntimeExitReason.LOGIN_WITNESS_LOSS)
        return tuple(logins.values())

    def _sweep_sign_ins(self, logins: tuple[OsLoginContext, ...], *, complete: bool, include_hosted: bool) -> None:
        owner = self._os_owner_id
        if owner is None and self._installation is not None:
            owner = self._installation.os_owner_id
        if owner is None:
            return
        try:
            installation = read_runtime_installation(
                storage_root=self.root, os_owner_id=owner, storage_identity=self.storage_identity
            )
        except RuntimeRefusalError:
            # No validated installation means no saved receipt can be attributed.
            return
        with self._guard:
            hosted = frozenset() if include_hosted else frozenset(self._profiles)
        sweep_saved_sign_ins(
            root=self.root,
            installation=installation,
            logins=logins,
            inventory_complete=complete,
            hosted_profiles=hosted,
        )

    def _private_work_available(self) -> bool:
        # An idle probe fences new requests, not authority for work already
        # admitted. A busy reply must not revoke that work's callbacks.
        return (
            not self._closed
            and not self.stop.is_set()
            and (self._login_inventory is None or self._login_lifecycle_available)
        )

    def _admitting(self) -> bool:
        return not self._closed and not self._idle_fenced and not self.stop.is_set()

    @contextmanager
    def operation_admission(self) -> Generator[None]:
        """Retain pre-fence submissions until their worker exchange has finished."""
        with self._guard:
            if not self._admitting():
                raise RuntimeRefusalError(RuntimeRefusalCode.DRAINING)
            self._operation_requests += 1
        try:
            yield
        finally:
            with self._guard:
                self._operation_requests -= 1

    def in_flight_operation_count(self, *, timeout: float) -> int | None:
        """Sum worker observations within one bound; unavailable is never zero."""
        deadline = time.monotonic() + timeout
        if not self._guard.acquire(timeout=max(0.0, deadline - time.monotonic())):
            return None
        try:
            hosts = tuple(self._profiles.values())
        finally:
            self._guard.release()
        total = 0
        for host in hosts:
            count = host.owner.in_flight_operation_count(deadline=deadline)
            if count is None:
                return None
            total += count
        return total

    def hosted_profile_count(self) -> int:
        """Return the number of profile hosts, each owning the worker its operations run in."""
        # One atomic length read; a supervisor heartbeat never waits on admission.
        return len(self._profiles)

    def stop_if_idle(self, reason: RuntimeExitReason, *, timeout: float) -> bool:
        """Fence new submissions and stop only with a confirmed empty work inventory."""
        deadline = time.monotonic() + timeout
        if not self._guard.acquire(timeout=max(0.0, deadline - time.monotonic())):
            return False
        try:
            if self._idle_fenced or self._operation_requests or self._custody_mutations:
                return False
            self._idle_fenced = True
        finally:
            self._guard.release()
        try:
            # Worker callbacks borrow the admission guard: never hold it while
            # waiting for status. The separate fence rejects new submissions.
            count = self.in_flight_operation_count(timeout=max(0.0, deadline - time.monotonic()))
            if count != 0:
                return False
            request_runtime_stop(self.stop, reason)
            return True
        finally:
            self._idle_fenced = False

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
        """Do not race custody-owned containment or a retained shutdown attempt."""
        if not self._drain_guard.acquire(blocking=False):
            return
        try:
            self._poll_profiles()
        finally:
            self._drain_guard.release()

    def _poll_profiles(self) -> None:
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
            hosts = tuple(host for identity, host in self._profiles.items() if identity not in self._custody_mutations)
        for host in hosts:
            retired = host.retire_replaced_binding(deadline=time.monotonic() + 15)
            if retired is None:
                continue
            if retired:
                self._remove_retired_host(host)
                continue
            host.approvals.expire()
            self._retired(host.observe_human_lock_down())
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

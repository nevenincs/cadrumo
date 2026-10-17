"""Local connection lifecycle over the existing profile authentication authority."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from threading import BoundedSemaphore, Event, RLock
from typing import TYPE_CHECKING
from uuid import UUID

from cadrumo.adapters.persistence.storage.bucket.output_language_hint import read_bucket_output_language_hint
from cadrumo.adapters.persistence.storage.custody.automation_store_composition import installed_automation_secret_store
from cadrumo.application.operations.registry import OperationRegistry
from cadrumo.application.user_profile.access_contracts import (
    Availability,
    LoginEligibility,
    OsLockState,
    OsLoginContext,
)
from cadrumo.application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
    AutomationSecretStore,
)
from cadrumo.core.diagnostic_log import diagnostic_event
from cadrumo.core.logging import get_logger
from cadrumo.core.time.clock import now
from cadrumo.entrypoints.operation_composition import build_manifest_operation_registry
from cadrumo_client.contracts.contracts import ByteChannel, ExitReason, RefusalCode, RefusalError
from cadrumo_client.contracts.installation import Installation
from cadrumo_client.contracts.login import LoginEvidence, LoginInventory
from cadrumo_client.contracts.service_access import InstalledServiceDescriptor, NativeServiceVerifier
from cadrumo_client.contracts.session_events import (
    ConnectionEvent,
    ProfileLanguageChanged,
    ServiceLeaseChanged,
    SessionEvent,
    SignInChanged,
)
from cadrumo_client.contracts.transport import ConnectionContext
from cadrumo_client.transport.installation import read_runtime_installation
from cadrumo_client.transport.native_wake import NativeWake
from cadrumo_runtime.contracts.profile_host import ProfileDrainResult

from ..adapters.login import capture_runtime_login
from ..adapters.service_verification import InstalledNativeServiceVerifier, installed_service_descriptors
from .access_management import RuntimeAccessManagement
from .bootstrap_delete import RuntimeBootstrapDeleteMixin
from .bootstrap_reset import RuntimeBootstrapMixin
from .enrollment_connections import RuntimeEnrollmentConnections
from .installation_door import RuntimeInstallationDoorMixin
from .lifecycle_guard import RuntimeLifecycleGuard
from .notice_observation import NoticeObservation, start_notice_observation
from .profile_connection_access import ProfileConnectionAccessMixin
from .profile_connection_admission import ProfileConnectionAdmissionMixin
from .profile_connection_attendance import AttendedConnection, PendingAttendance, ProfileConnectionAttendanceMixin
from .profile_connection_drain import ProfileConnectionDrainMixin, ProfileDrainRecord
from .profile_connection_extension_records import ProfileConnectionExtensionRecordsMixin
from .profile_connection_operations import ProfileConnectionOperationMixin
from .profile_connection_person_acts import ProfileConnectionPersonActMixin
from .profile_connection_services import ProfileConnectionServicesMixin, ServiceConnection
from .profile_connection_sessions import ProfileConnectionSessionMixin
from .profile_host import ProfileConnection, RuntimeProfileHost
from .session_events import RuntimeSessionEvents
from .shutdown import request_runtime_stop
from .sign_in_sweep import sweep_saved_sign_ins

if TYPE_CHECKING:
    from .installation_composition import InstallationActRegistry

_LOGGER = get_logger(__name__)

# Lifecycle passes stay this far apart, and where nothing reports a login's
# changes it is also how often that login is observed.
_LIFECYCLE_INTERVAL_SECONDS = 0.5


class RuntimeProfileConnections(
    RuntimeBootstrapMixin,
    RuntimeBootstrapDeleteMixin,
    RuntimeInstallationDoorMixin,
    ProfileConnectionPersonActMixin,
    ProfileConnectionServicesMixin,
    ProfileConnectionExtensionRecordsMixin,
    ProfileConnectionAdmissionMixin,
    ProfileConnectionAccessMixin,
    ProfileConnectionAttendanceMixin,
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
        capture_login: Callable[[ByteChannel], LoginEvidence] = capture_runtime_login,
        login_inventory: Callable[[], LoginInventory] | None = None,
        secret_store: Callable[[], AutomationSecretStore] = installed_automation_secret_store,
        worker_script: Path | None = None,
        wall_clock: Callable[[], datetime] = now,
        os_owner_id: str | None = None,
        installation_acts: InstallationActRegistry | None = None,
        service_descriptors: tuple[InstalledServiceDescriptor, ...] | None = None,
        service_verifier: NativeServiceVerifier | None = None,
    ) -> None:
        """Defer installation/profile/store access until an eligible peer requests login.

        ``installation_acts`` names the handlers of the sessionless installation
        door; the installed composition is used when none is given.
        """
        self.root, self.storage_identity, self.boot, self.stop = storage_root, storage_identity, runtime_boot_id, stop
        self._capture, self._secret_store = capture_login, secret_store
        self._login_inventory = login_inventory
        self._os_owner_id = os_owner_id
        self._eligible_login_seen = False
        self._login_lifecycle_available = False
        self._worker_script, self._wall_clock = worker_script, wall_clock
        self._guard = RLock()
        self._human_handover_guard = RLock()
        self._drain_guard = RuntimeLifecycleGuard()
        self._drain_records: dict[UUID, ProfileDrainRecord] | None = None
        self._drain_result: ProfileDrainResult | None = None
        self._installation: Installation | None = None
        self._registry: OperationRegistry | None = None
        self._installation_acts = installation_acts
        self._profiles: dict[UUID, RuntimeProfileHost] = {}
        self._custody_mutations: set[UUID] = set()
        self._submission_slots = BoundedSemaphore(4)
        self._connections: dict[UUID, ProfileConnection] = {}
        self._attendance: dict[UUID, PendingAttendance] = {}
        self._attendance_holders: dict[UUID, UUID] = {}
        self._attended: dict[UUID, AttendedConnection] = {}
        # Connections whose approval ended with the person's session; only a new connection may ask again.
        self._attendance_spent: set[UUID] = set()
        self._events = RuntimeSessionEvents()
        self._sign_in_watchers: set[UUID] = set()
        self._observed_logins: frozenset[tuple[str, bool, OsLockState]] = frozenset()
        self._language_observations: dict[UUID, tuple[UUID, str | None]] = {}
        self._service_descriptors = {
            item.service_id: item
            for item in (installed_service_descriptors() if service_descriptors is None else service_descriptors)
        }
        self._service_verifier = InstalledNativeServiceVerifier() if service_verifier is None else service_verifier
        self._services: dict[UUID, ServiceConnection] = {}
        self._notice_connections: dict[UUID, tuple[ConnectionContext, LoginEvidence]] = {}
        self._notice_observation: NoticeObservation | None = None
        self._logins: dict[str, LoginEvidence] = {}
        self._closed = False
        self._idle_fenced = False
        self._operation_requests = 0
        self._last_poll = 0.0
        self._last_sign_in_sweep = 0.0
        # What the last sweep was given: logins seen, inventory completeness and hosted profiles.
        self._swept: tuple[frozenset[tuple[str, bool, OsLockState]], bool, frozenset[UUID]] | None = None
        # A pass runs when this is set, at the earliest deadline, or when one
        # that could not finish is owed; never on a timer while nothing changes.
        self._lifecycle = NativeWake()
        self._lifecycle_owed: float | None = None
        # Set from the OS session-change callback, which must not wait on this runtime's guard.
        self._session_change = Event()
        # Each profile's next lapse, as the last pass found it; reading it takes no profile guard.
        self._host_dues: dict[UUID, float] = {}
        self._session_changes_pushed = False
        self._unreported_logins = True
        self._enrollments = RuntimeEnrollmentConnections(prepare=self._prepare_enrollment, admitting=self._admitting)
        self._management = RuntimeAccessManagement(
            resolve=self._resolve_access_management,
            validate=self._validate_access_connection,
            lock_changed=self._profile_lock_changed,
            synchronize=self._synchronize_profile_sessions,
        )

    def _publish_retirement(self, event: SessionEvent) -> None:
        """Publish exact retirement; services own shutdown of their native descendants."""
        withdrawn: list[ServiceLeaseChanged] = []
        with self._guard:
            self._language_observations.pop(event.connection_id, None)
            for connection_id, service in self._services.items():
                if service.lease is not None and service.lease.parent_session_id == event.session_id:
                    withdrawn.append(
                        ServiceLeaseChanged(
                            runtime_boot_id=self.boot, connection_id=connection_id, profile_id=service.lease.profile_id
                        )
                    )
                    service.lease = None
        self._events.publish(event)
        for cue in withdrawn:
            self._events.publish_cue(cue)
        self._sign_in_changed()

    def watch_sign_in(self, context: ConnectionContext) -> None:
        """Cue this connection on every later change that can move any sign-in status, until it disconnects."""
        with self._guard:
            self._sign_in_watchers.add(context.connection_id)

    def _sign_in_changed(self) -> None:
        """Cue every sign-in watcher; each re-reads a status that still decides for itself."""
        with self._guard:
            watchers = tuple(self._sign_in_watchers)
        for connection_id in watchers:
            self._events.publish_cue(SignInChanged(runtime_boot_id=self.boot, connection_id=connection_id))

    def connect_events(
        self, context: ConnectionContext, channel: ByteChannel | None = None, *, queued: NativeWake | None = None
    ) -> None:
        """Register a native-verified connection without admitting profile access."""
        self._events.connect(context, queued)
        if context.lifecycle_notices and channel is not None:
            if channel.peer != context.peer:
                raise RefusalError(RefusalCode.PEER_UNTRUSTED)
            login = self._capture(channel)
            if login.observe(credential_facilities=Availability.UNAVAILABLE).os_owner_id != context.peer.os_owner_id:
                raise RefusalError(RefusalCode.PEER_UNTRUSTED)
            with self._guard:
                self._notice_connections[context.connection_id] = context, login

    def take_events(self, context: ConnectionContext) -> tuple[ConnectionEvent, ...]:
        """Let the connection's sole writer drain its bounded event queue."""
        return self._events.take(context)

    def observe_profile_language(self, profile_id: UUID) -> None:
        """Cue each session of the profile that has not yet heard its current language hint.

        Only an operation's worker writes this hint, mirroring the canonical CAS
        write, so operation traffic for the profile is the one moment it can have
        moved. Consumers must re-read the canonical preference through their held
        exact-profile session; a hint and its notification confer neither a value
        nor access authority.
        """
        try:
            language = read_bucket_output_language_hint(storage_root=self.root, bucket_id=str(profile_id))
        except Exception:
            return
        changed: list[ProfileLanguageChanged] = []
        with self._guard:
            for connection_id, connection in self._connections.items():
                session_id = connection.session_id
                if connection.profile_id != profile_id or session_id is None:
                    continue
                if self._language_observations.get(connection_id) == (session_id, language):
                    continue
                self._language_observations[connection_id] = session_id, language
                changed.append(
                    ProfileLanguageChanged(
                        runtime_boot_id=self.boot,
                        connection_id=connection_id,
                        profile_id=profile_id,
                        session_id=session_id,
                    )
                )
        for event in changed:
            self._events.publish(event)

    def event_flushed(self, context: ConnectionContext, event: ConnectionEvent) -> None:
        """Record transport completion without granting session or user acknowledgement."""
        self._events.flushed(context, event)

    def _notify_upgrade(self, deadline: float) -> bool:
        if not self._guard.acquire(timeout=max(0.0, deadline - time.monotonic())):
            return False
        try:
            if self._closed or time.monotonic() >= deadline:
                return False
            if self._notice_observation is not None and not self._notice_observation.done():
                return False
            connections = tuple(self._notice_connections.values())
            # Completed earlier attempts are discarded: only this attempt's
            # fresh observation may influence its bounded notification fence.
            observation = start_notice_observation(connections, deadline=deadline)
            self._notice_observation = observation
        finally:
            self._guard.release()
        try:
            eligible = observation.result(timeout=max(0.0, deadline - time.monotonic()))
        except Exception:
            return False
        if eligible is None or time.monotonic() >= deadline:
            return False
        pending: list[Event] = []
        for context in eligible:
            if time.monotonic() >= deadline:
                return False
            flushed = self._events.upgrade_pending(context)
            if flushed is not None:
                pending.append(flushed)
        return (
            all(flushed.wait(max(0.0, deadline - time.monotonic())) for flushed in pending)
            and time.monotonic() < deadline
        )

    def _connected(self, connection_id: UUID) -> ProfileConnection:
        with self._guard:
            connection = self._connections.get(connection_id)
            if self._closed or connection is None:
                raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
            return connection

    def _login_contexts(self) -> tuple[LoginEvidence, ...]:
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
        # A sign-in status reads its peer's login and lock state, so a change there moves it too.
        logins_seen = frozenset((login.login_id, login.active, login.lock_state) for login in observed)
        with self._guard:
            logins_moved, self._observed_logins = logins_seen != self._observed_logins, logins_seen
        if logins_moved:
            self._sign_in_changed()
        eligible = any(login.active and login.unattended is LoginEligibility.ELIGIBLE for login in observed)
        # Request threads observe the logins too: one decides under the guard, claiming the sweep it runs.
        with self._guard:
            sweep = (logins_seen, inventory.complete, frozenset(self._profiles) if eligible else frozenset())
            instant = time.monotonic()
            sweeping = not eligible or instant - self._last_sign_in_sweep >= 1.0
            # A pass observes logins again through each profile's checks: only
            # a change the rate limit held back is swept later, or each pass
            # would owe the next one forever.
            held_back = not sweeping and sweep != self._swept
            if sweeping:
                self._last_sign_in_sweep, self._swept = instant, sweep
            last_sweep = self._last_sign_in_sweep
        if sweeping:
            self._sweep_sign_ins(observed, complete=inventory.complete, include_hosted=not eligible)
        elif held_back:
            self._owe_lifecycle_pass(last_sweep + 1.0)
        # A logon without a lock surface, or one in an unknown state, changes with no session notification.
        self._unreported_logins = any(
            login.lock_state in (OsLockState.NOT_APPLICABLE, OsLockState.UNKNOWN) for login in observed
        )
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
                request_runtime_stop(self.stop, ExitReason.LOGIN_WITNESS_LOSS)
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
        except RefusalError:
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
                raise RefusalError(RefusalCode.DRAINING)
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

    def stop_if_idle(self, reason: ExitReason, *, timeout: float) -> bool:
        """Fence new submissions and stop only with a confirmed empty work inventory."""
        deadline = time.monotonic() + timeout
        if not self._notify_upgrade(deadline):
            return False
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
            if count != 0 or time.monotonic() >= deadline:
                return False
            request_runtime_stop(self.stop, reason)
            return True
        finally:
            self._idle_fenced = False

    def prepare_registry(self) -> OperationRegistry:
        """Bind the public operation contracts before transport readiness.

        The contracts come from the shipped manifest; an operation's group is
        composed and checked against it on first use. This is profile
        independent and never opens a profile or credential.
        Repeated preparation retains the one graph used by every host in this
        runtime process.
        """
        with self._guard:
            if not self._admitting():
                raise RefusalError(RefusalCode.DRAINING)
            registry = self._registry
            if registry is None:
                registry = build_manifest_operation_registry()
                if not self._admitting():
                    raise RefusalError(RefusalCode.DRAINING)
                self._registry = registry
            if not self._admitting():
                raise RefusalError(RefusalCode.DRAINING)
            return registry

    def poll(self) -> None:
        """Run a lifecycle pass when one is called for or due, never racing custody containment or shutdown."""
        # Cleared first, so a change during this pass calls for another.
        self._lifecycle.clear()
        called = self._session_change.is_set()
        if called:
            # A change reported after this still falls before the pass, which observes it.
            self._session_change.clear()
        due = self._lifecycle_due()
        if not called and (due is None or time.monotonic() < due):
            # Woken only to decide the wait again: no pass is due yet.
            return
        with self._guard:
            self._lifecycle_owed = None
        if not self._drain_guard.acquire_poll():
            self._owe_lifecycle_pass()
            return
        try:
            self._poll_profiles()
        finally:
            self._drain_guard.release()

    @property
    def lifecycle_wake(self) -> NativeWake:
        """Return the flag set when the wait for the next lifecycle pass must be decided again."""
        return self._lifecycle

    def lifecycle_changed(self) -> None:
        """Have a pass look, one interval from now, at what a request or a disconnect changed.

        A burst of requests costs one pass, as when passes ran on an interval.
        """
        self._owe_lifecycle_pass()
        self._lifecycle.set()

    def os_session_changed(self) -> None:
        """Call for a pass now: the OS reported a logon, logoff, lock, unlock, connect or disconnect.

        This runs in the window procedure Windows calls, so it takes no lock
        another thread may hold through long work.
        """
        self._session_change.set()
        self._lifecycle.set()

    def session_changes_pushed(self, pushed: bool) -> None:
        """Say whether OS session changes reach ``os_session_changed``; without them logins are observed."""
        self._session_changes_pushed = pushed

    def lifecycle_due_in(self) -> float | None:
        """Return the seconds until a pass is due with nothing happening, or ``None`` when only a call brings one."""
        due = self._lifecycle_due()
        if due is None:
            return None
        return max(0.0, max(due, self._last_poll + _LIFECYCLE_INTERVAL_SECONDS) - time.monotonic())

    def _lifecycle_due(self) -> float | None:
        with self._guard:
            owed = self._lifecycle_owed
            host_dues = tuple(self._host_dues.values())
        instants = [owed, self._enrollments.next_lapse(), *host_dues]
        if not self._session_changes_pushed or self._unreported_logins:
            # Nothing reports these logins' changes, so observing them on an interval is their only source.
            instants.append(self._last_poll + _LIFECYCLE_INTERVAL_SECONDS)
        return min((instant for instant in instants if instant is not None), default=None)

    def _owe_lifecycle_pass(self, at: float | None = None) -> None:
        """Owe a pass that could not finish now, by ``at`` or one interval from now, without waking the loop."""
        due = time.monotonic() + _LIFECYCLE_INTERVAL_SECONDS if at is None else at
        with self._guard:
            self._lifecycle_owed = due if self._lifecycle_owed is None else min(self._lifecycle_owed, due)

    def _poll_profiles(self) -> None:
        """Fence idle leases on expiry, native logout/lock or unavailable custody."""
        instant = time.monotonic()
        if instant - self._last_poll < _LIFECYCLE_INTERVAL_SECONDS:
            self._owe_lifecycle_pass(self._last_poll + _LIFECYCLE_INTERVAL_SECONDS)
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
            mutating = bool(self._custody_mutations)
        if mutating:
            # A profile under a custody mutation is looked at again once that settles.
            self._owe_lifecycle_pass()
        dues: dict[UUID, float] = {}
        for host in hosts:
            retired = host.retire_replaced_binding(deadline=time.monotonic() + 15)
            if retired is None:
                # Another owner holds its fence; look again shortly.
                self._owe_lifecycle_pass()
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
                continue
            due = host.lifecycle_due()
            if due is not None:
                dues[host.store.binding.profile_id] = due
        with self._guard:
            self._host_dues = dues

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
        self._sign_in_changed()

"""Local connection lifecycle over the existing profile authentication authority."""

from __future__ import annotations

import time
from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import BoundedSemaphore, Event, RLock, Thread
from uuid import UUID, uuid4

from pydantic import SecretBytes

from cadrumo.adapters.persistence.storage.custody.automation_store_composition import installed_automation_secret_store

from ...adapters.local_runtime.framing import read_secret, write_document
from ...adapters.local_runtime.installation import runtime_installation
from ...adapters.local_runtime.login import capture_runtime_login
from ...adapters.local_runtime.profile_worker import ProfileWorkerProcess
from ...adapters.persistence.storage.custody.automation_profile import current_automation_profile_binding
from ...adapters.persistence.storage.custody.automation_store import AutomationControlStore
from ...application.operations.registry import OperationFrontendProjection, OperationRegistry
from ...application.runtime.access_management import (
    RuntimeAccessManagementRequest,
    RuntimeProfileRecoveryPrepare,
    RuntimeProfileResume,
)
from ...application.runtime.contracts import (
    RuntimeByteChannel,
    RuntimeRefusalCode,
    RuntimeRefusalError,
    RuntimeShutdownIncompleteError,
)
from ...application.runtime.enrollment_access import (
    RuntimeEnrollmentPrepare,
    RuntimeEnrollmentReconcile,
    RuntimeEnrollmentRecorded,
    RuntimeEnrollmentRequest,
)
from ...application.runtime.installation import RuntimeInstallation
from ...application.runtime.login import RuntimeLoginEvidence, RuntimeLoginInventory
from ...application.runtime.operation_access import (
    RuntimeOperationAcknowledged,
    RuntimeOperationContract,
    RuntimeOperationContractReply,
    RuntimeOperationReply,
    RuntimeOperationRequest,
    RuntimeOperationSecret,
    RuntimeOperationSubmitPayload,
)
from ...application.runtime.profile_access import (
    RuntimeAccessRefusal,
    RuntimeProfileDrainResult,
    RuntimeProfileLogin,
    RuntimeProfileStatus,
    RuntimeSecretReady,
    RuntimeSessionRequest,
    RuntimeSessionsLocked,
)
from ...application.runtime.profile_worker import ProfileWorkerDrained, ProfileWorkerOperationReceipt
from ...application.runtime.submission_payload import SUBMISSION_PAYLOAD_TIMEOUT_SECONDS
from ...application.runtime.transport import RuntimeConnectionContext
from ...application.user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    AccessDenied,
    AccessSession,
    Availability,
    LoginEligibility,
)
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...application.user_profile.automation_administration import reconcile_automation_receipt
from ...application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
    AutomationSecretStore,
)
from ...core.time.clock import now
from ..operation_composition import build_production_operation_registry
from .access_management import RuntimeAccessManagement
from .enrollment_connections import RuntimeEnrollmentConnections
from .operation_projection import prepare_operation_projection
from .profile_host import ProfileConnection, RuntimeProfileHost
from .submission_stream import stream_operation_submission


@dataclass
class _ProfileDrainRecord:
    """Retain the original worker and its actual shutdown attempts until settlement."""

    host: RuntimeProfileHost
    worker: ProfileWorkerProcess | None = None
    begun: bool = False
    request: Thread | None = None
    containment: Thread | None = None
    receipt: ProfileWorkerDrained | None = None
    contained: bool = False
    guard: RLock = field(default_factory=RLock, repr=False)


class RuntimeProfileConnections:
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
        self._drain_records: dict[UUID, _ProfileDrainRecord] | None = None
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
                self.stop.set()
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

    def _host(self, profile_id: UUID, context: RuntimeConnectionContext) -> RuntimeProfileHost:
        with self._guard:
            if not self._admitting():
                raise RuntimeRefusalError(RuntimeRefusalCode.DRAINING)
            if self._installation is None:
                self._installation = runtime_installation(
                    storage_root=self.root,
                    os_owner_id=context.peer.os_owner_id,
                    storage_identity=self.storage_identity,
                )
            if self._installation.os_owner_id != context.peer.os_owner_id:
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            binding = current_automation_profile_binding(
                profile_id=profile_id,
                installation_id=self._installation.installation_id,
                os_owner_id=self._installation.os_owner_id,
                root=self.root,
            )
            existing = self._profiles.get(profile_id)
            if existing is not None:
                if existing.store.binding != binding:
                    raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
                return existing
            registry = self._registry
            if registry is None:
                # Direct in-process hosts may omit startup preparation. The
                # installed server calls prepare_registry before listening.
                registry = self.prepare_registry()
            host = RuntimeProfileHost(
                store=AutomationControlStore(root=self.root, binding=binding, secrets_store_factory=self._secret_store),
                runtime_boot_id=self.boot,
                registry=registry,
                connected=self._connected,
                logins=self._login_contexts,
                admitting=self._private_work_available,
                recipient=self._enrollments.recipient,
                worker_script=self._worker_script,
                wall_clock=self._wall_clock,
            )
            if not self._admitting():
                raise RuntimeRefusalError(RuntimeRefusalCode.DRAINING)
            self._profiles[profile_id] = host
            return host

    def _prepare(
        self, context: RuntimeConnectionContext, channel: RuntimeByteChannel, request: RuntimeProfileLogin
    ) -> tuple[ProfileConnection, RuntimeProfileHost]:
        if request.method in {"password", "receipt"} and request.scope is not None:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        if request.method in {"password", "receipt"} and request.frontend not in {
            OperationFrontendProjection.CLI,
            OperationFrontendProjection.TUI,
        }:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        if request.persist_receipt and (
            request.method != "password"
            or request.frontend not in {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        with self._guard:
            previous = self._connections.get(context.connection_id)
        if previous is not None:
            if (
                previous.context != context
                or previous.profile_id != request.profile_id
                or previous.frontend != request.frontend
                or previous.method == "enrollment"
            ):
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            connection = previous
        else:
            login = self._capture(channel)
            observed = login.observe(credential_facilities=Availability.UNAVAILABLE)
            if not observed.active or observed.os_owner_id != context.peer.os_owner_id:
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            connection = ProfileConnection(context, login, uuid4(), request.profile_id, request.frontend)
        host = self._host(request.profile_id, context)
        with host.guard:
            if not self._admitting():
                raise RuntimeRefusalError(RuntimeRefusalCode.DRAINING)
            if connection.session_id is not None:
                try:
                    prior = self._status(connection, host, request.request_id, connection.session_id)
                    valid = isinstance(prior, RuntimeProfileStatus) and prior.status.denial is None
                except AutomationCustodyError:
                    valid = False
                if valid:
                    raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
                host.authority.disconnect(context.connection_id)
                connection.session_id = None
            observation = connection.login.observe(credential_facilities=Availability.UNAVAILABLE)
            if not observation.active or (request.method in {"password", "receipt"} and observation.locked):
                raise AutomationCustodyError(AutomationCustodyCode.NEEDS_USER)
            connection.method = request.method
            connection.persist_human_receipt = request.persist_receipt
            if request.method in {"password", "receipt"}:
                connection.client_id = uuid4()
            with self._guard:
                if not self._admitting():
                    raise RuntimeRefusalError(RuntimeRefusalCode.DRAINING)
                self._connections[context.connection_id] = connection
                self._logins[connection.login.login_id] = connection.login
        return connection, host

    def _prepare_enrollment(
        self, context: RuntimeConnectionContext, channel: RuntimeByteChannel, request: RuntimeEnrollmentPrepare
    ) -> tuple[ProfileConnection, RuntimeProfileHost]:
        """Bind a new recipient or the exact currently authenticated root key."""
        if request.session_id is None:
            return self._prepare_unadmitted(context, channel, request, method="enrollment")
        if context.runtime_boot_id != self.boot or context.peer != channel.peer:
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        connection = self._connected(context.connection_id)
        if (
            connection.context != context
            or connection.profile_id != request.profile_id
            or connection.frontend != request.frontend
            or connection.method != "api_key"
            or connection.session_id != request.session_id
        ):
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        host = self._host(request.profile_id, context)
        with host.guard:
            host.authority.automation_request_session(
                connection_id=context.connection_id, session_id=request.session_id
            )
        return connection, host

    def _prepare_unadmitted(
        self,
        context: RuntimeConnectionContext,
        channel: RuntimeByteChannel,
        request: RuntimeEnrollmentPrepare | RuntimeProfileRecoveryPrepare,
        *,
        method: str,
    ) -> tuple[ProfileConnection, RuntimeProfileHost]:
        """Bind a verified native context without publishing a profile access lease."""
        if context.runtime_boot_id != self.boot or context.peer != channel.peer:
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        with self._guard:
            if context.connection_id in self._connections:
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
        login = self._capture(channel)
        observed = login.observe(credential_facilities=Availability.UNAVAILABLE)
        if not observed.active or observed.locked or observed.os_owner_id != context.peer.os_owner_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        host = self._host(request.profile_id, context)
        connection = ProfileConnection(context, login, uuid4(), request.profile_id, request.frontend, method=method)
        with host.guard, self._guard:
            if not self._admitting():
                raise RuntimeRefusalError(RuntimeRefusalCode.DRAINING)
            if context.connection_id in self._connections:
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            self._connections[context.connection_id] = connection
            self._logins[login.login_id] = login
        return connection, host

    def _validate_access_connection(self, connection: ProfileConnection, host: RuntimeProfileHost) -> None:
        with self._guard:
            if (
                not self._admitting()
                or self._connections.get(connection.context.connection_id) is not connection
                or self._profiles.get(connection.profile_id) is not host
            ):
                raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        observed = connection.login.observe(credential_facilities=Availability.UNAVAILABLE)
        if (
            connection.frontend not in {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}
            or not observed.active
            or observed.locked
            or observed.os_owner_id != connection.context.peer.os_owner_id
        ):
            raise AutomationCustodyError(AutomationCustodyCode.NEEDS_USER)

    def _resolve_access_management(
        self, context: RuntimeConnectionContext, channel: RuntimeByteChannel, request: RuntimeAccessManagementRequest
    ) -> tuple[ProfileConnection, RuntimeProfileHost]:
        if context.runtime_boot_id != self.boot or context.peer != channel.peer:
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        if isinstance(request, RuntimeProfileRecoveryPrepare):
            if request.frontend not in {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}:
                raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
            with self._guard:
                connection = self._connections.get(context.connection_id)
            if connection is None:
                connection, host = self._prepare_unadmitted(context, channel, request, method="management")
            else:
                if (
                    connection.context != context
                    or connection.profile_id != request.profile_id
                    or connection.frontend is not request.frontend
                    or connection.method != "management"
                    or connection.session_id is not None
                ):
                    raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
                host = self._host(request.profile_id, context)
        else:
            connection = self._connected(context.connection_id)
            with self._guard:
                host = self._profiles.get(request.profile_id)
            if host is None or connection.context != context or connection.profile_id != request.profile_id:
                raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
            if isinstance(request, RuntimeProfileResume):
                if (
                    connection.method != "management"
                    or connection.session_id is not None
                    or connection.frontend is not request.frontend
                    or connection.recovery_generation != request.lock_generation
                ):
                    raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            elif connection.session_id != request.session_id:
                raise ProfileAccessRefusedError(AccessDenialCode.CONNECTION_MISMATCH)
        self._validate_access_connection(connection, host)
        return connection, host

    def _profile_lock_changed(self, profile_id: UUID) -> None:
        self._enrollments.retire_profile(profile_id)
        with self._guard:
            host = self._profiles.get(profile_id)
            connections = tuple(item for item in self._connections.values() if item.profile_id == profile_id)
        for connection in connections:
            connection.recovery_generation = None
            if host is not None:
                host.approvals.retire_connection(connection.context.connection_id)

    def _synchronize_profile_sessions(self, host: RuntimeProfileHost) -> None:
        with self._guard:
            connections = tuple(
                item for item in self._connections.values() if item.profile_id == host.store.binding.profile_id
            )
        retired: list[UUID] = []
        with host.guard:
            for connection in connections:
                session_id = connection.session_id
                if session_id is None:
                    continue
                try:
                    status = self._status(connection, host, uuid4(), session_id)
                    denied = isinstance(status, AccessDenied) or status.status.denial is not None
                except AutomationCustodyError:
                    denied = True
                if denied:
                    connection.session_id = None
                    retired.append(session_id)
            host.approvals.retire_sessions(tuple(retired))

    def manage_access(
        self, context: RuntimeConnectionContext, channel: RuntimeByteChannel, request: RuntimeAccessManagementRequest
    ) -> None:
        """Project the existing exact-profile security services over native transport."""
        self._management.handle(context, channel, request)

    def enrollment(
        self, context: RuntimeConnectionContext, channel: RuntimeByteChannel, request: RuntimeEnrollmentRequest
    ) -> None:
        """Dispatch the bounded pre-unlock request and protected client delivery door."""
        if context.runtime_boot_id != self.boot:
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        if isinstance(request, RuntimeEnrollmentReconcile):
            self._reconcile_enrollment(context, channel, request)
            return
        self._enrollments.handle(context, channel, request)

    def _reconcile_enrollment(
        self, context: RuntimeConnectionContext, channel: RuntimeByteChannel, request: RuntimeEnrollmentReconcile
    ) -> None:
        """Release own-grant terminal metadata only under current root authority."""
        if context.peer != channel.peer:
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        try:
            connection = self._connected(context.connection_id)
            if (
                connection.context != context
                or connection.profile_id != request.profile_id
                or connection.method != "api_key"
                or connection.session_id != request.session_id
            ):
                raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
            host = self._host(request.profile_id, context)
            with host.authority.owner.admission_guard():
                if not self._admitting():
                    raise RuntimeRefusalError(RuntimeRefusalCode.DRAINING)
                session = host.authority.automation_request_session(
                    connection_id=context.connection_id, session_id=request.session_id
                )
                receipt = reconcile_automation_receipt(
                    state=host.store.enrollment_state(), session=session, request_id=request.enrollment_request_id
                )
                session = host.authority.automation_request_session(
                    connection_id=context.connection_id, session_id=request.session_id
                )
                remaining = min(5.0, (session.expires_at - self._wall_clock()).total_seconds())
                if remaining <= 0:
                    raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
                write_document(
                    channel,
                    RuntimeEnrollmentRecorded(
                        request_id=request.request_id,
                        runtime_boot_id=context.runtime_boot_id,
                        connection_id=context.connection_id,
                        receipt=receipt,
                    ),
                    deadline=time.monotonic() + remaining,
                )
        except (AutomationCustodyError, ProfileAccessRefusedError) as error:
            write_document(
                channel,
                RuntimeAccessRefusal(
                    request_id=request.request_id,
                    runtime_boot_id=context.runtime_boot_id,
                    connection_id=context.connection_id,
                    code=error.reason,
                ),
                deadline=time.monotonic() + 5,
            )

    def _status(
        self, connection: ProfileConnection, host: RuntimeProfileHost, request_id: UUID, session_id: UUID
    ) -> RuntimeProfileStatus | AccessDenied:
        status = host.authority.status(
            connection_id=connection.context.connection_id,
            session_id=session_id,
            published_authority=Availability.UNAVAILABLE,
            provider=Availability.NEEDS_USER,
        )
        if isinstance(status, AccessDenied):
            return status
        if status.denial is not None:
            connection.session_id = None
        return RuntimeProfileStatus(
            request_id=request_id,
            runtime_boot_id=self.boot,
            connection_id=connection.context.connection_id,
            status=status,
        )

    def _login(
        self, context: RuntimeConnectionContext, channel: RuntimeByteChannel, request: RuntimeProfileLogin
    ) -> RuntimeProfileStatus | AccessDenied:
        connection, host = self._prepare(context, channel, request)
        write_document(
            channel,
            RuntimeSecretReady(
                request_id=request.request_id, runtime_boot_id=self.boot, connection_id=context.connection_id
            ),
            deadline=time.monotonic() + 5,
        )
        # Slow/unresponsive secret senders do not hold any profile admission guard.
        with read_secret(channel, deadline=time.monotonic() + 10) as secret:
            if request.method in {"password", "receipt"}:
                with host.guard:
                    if not self._admitting():
                        raise RuntimeRefusalError(RuntimeRefusalCode.DRAINING)
                    connection.human_secret = secret
                try:
                    admitted = host.authority.admit_human(connection_id=context.connection_id)
                finally:
                    with host.guard:
                        connection.human_secret = None
            else:
                with host.guard:
                    if not self._admitting():
                        raise RuntimeRefusalError(RuntimeRefusalCode.DRAINING)
                    credential = SecretBytes(bytes(secret))
                    key_id, _ = host.issuer.verifier(credential)
                    snapshot = host.store.snapshot()
                    key = next((item for item in snapshot.keys if item.key_id == key_id), None)
                    grant = next(
                        (item for item in snapshot.grants if key is not None and item.grant_id == key.grant_id), None
                    )
                    if grant is None:
                        return AccessDenied(code=AccessDenialCode.AUTHENTICATION_REQUIRED)
                    # This is routing from protected state, not proof. No lease is
                    # published until the existing authority verifies and unwraps it.
                    connection.client_id = grant.client_id
                admitted = host.authority.admit_api_key(
                    connection_id=context.connection_id,
                    target=host.store.binding,
                    credential=credential,
                    scope=request.scope or grant.scope,
                )
        with host.guard:
            if isinstance(admitted, AccessDenied):
                return admitted
            if not self._admitting():
                host.authority.disconnect(context.connection_id)
                raise RuntimeRefusalError(RuntimeRefusalCode.DRAINING)
            connection.session_id = admitted.session_id
            receipt = host.owner.take_human_login_receipt(admitted.session_id)
            result = self._status(connection, host, request.request_id, admitted.session_id)
            if isinstance(result, RuntimeProfileStatus):
                return result.model_copy(update={"human_login": receipt})
            return result

    def _session(
        self, context: RuntimeConnectionContext, request: RuntimeSessionRequest
    ) -> RuntimeProfileStatus | RuntimeSessionsLocked | AccessDenied:
        connection = self._connected(context.connection_id)
        if connection.context != context or connection.profile_id != request.profile_id:
            return AccessDenied(code=AccessDenialCode.PROFILE_MISMATCH)
        if connection.session_id != request.session_id:
            return AccessDenied(code=AccessDenialCode.CONNECTION_MISMATCH)
        with self._guard:
            host = self._profiles[connection.profile_id]
        with host.guard:
            if not self._admitting():
                raise RuntimeRefusalError(RuntimeRefusalCode.DRAINING)
            if request.action == "session_lock":
                retired = host.authority.lock_session(
                    connection_id=context.connection_id,
                    session_id=request.session_id,
                    target_session_id=request.target_session_id or request.session_id,
                )
                if isinstance(retired, AccessDenied):
                    return retired
                self._retired(retired)
                return RuntimeSessionsLocked(
                    request_id=request.request_id,
                    runtime_boot_id=self.boot,
                    connection_id=context.connection_id,
                    session_ids=retired,
                )
            if request.target_session_id is not None:
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            if request.action == "session_refresh":
                refreshed = host.authority.refresh_api_key(
                    connection_id=context.connection_id, session_id=request.session_id
                )
                if not isinstance(refreshed, AccessSession):
                    return refreshed
            return self._status(connection, host, request.request_id, request.session_id)

    def _retired(self, identities: tuple[UUID, ...]) -> None:
        with self._guard:
            hosts = tuple(self._profiles.values())
            for connection in self._connections.values():
                if connection.session_id in identities:
                    connection.session_id = None
        for host in hosts:
            host.approvals.retire_sessions(identities)

    def handle(
        self,
        context: RuntimeConnectionContext,
        channel: RuntimeByteChannel,
        request: RuntimeProfileLogin | RuntimeSessionRequest,
    ) -> RuntimeProfileStatus | RuntimeSessionsLocked | RuntimeAccessRefusal:
        """Keep credentials out of request/response documents and refuse unknown authority."""
        try:
            if context.runtime_boot_id != self.boot or context.peer != channel.peer:
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            if not self._admitting():
                raise RuntimeRefusalError(RuntimeRefusalCode.DRAINING)
            result = (
                self._login(context, channel, request)
                if isinstance(request, RuntimeProfileLogin)
                else self._session(context, request)
            )
            if not isinstance(result, AccessDenied):
                return result
            code = result.code
        except (AutomationCustodyError, ProfileAccessRefusedError) as error:
            code = error.reason
        except RuntimeRefusalError as error:
            code = error.reason
        return RuntimeAccessRefusal(
            request_id=request.request_id, runtime_boot_id=self.boot, connection_id=context.connection_id, code=code
        )

    def disconnect(self, context: RuntimeConnectionContext) -> None:
        """Release only this connection's authority; keep native login provenance separate."""
        self._enrollments.disconnect(context.connection_id)
        with self._guard:
            connection = self._connections.get(context.connection_id)
            host = None if connection is None else self._profiles.get(connection.profile_id)
        try:
            if host is not None:
                host.authority.disconnect(context.connection_id)
        finally:
            if host is not None:
                host.approvals.retire_connection(context.connection_id)
            with self._guard:
                self._connections.pop(context.connection_id, None)

    def _operation_secret(
        self,
        host: RuntimeProfileHost,
        connection: ProfileConnection,
        channel: RuntimeByteChannel,
        request: RuntimeOperationSecret,
    ) -> None:
        """Preflight before bytes, then reauthorize their one-use canonical delivery."""
        if connection.frontend not in {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}:
            raise ProfileAccessRefusedError(AccessDenialCode.FRONTEND_DENIED)
        worker = host.owner.operation_worker()

        def checked(receipt: ProfileWorkerOperationReceipt) -> None:
            release = receipt.release
            if (
                receipt.operation_id != request.requirement.identity.operation_id
                or release.operation_id != receipt.operation_id
                or release.connection_id != connection.context.connection_id
                or release.session_id != request.session_id
                or release.request.profile_id != request.profile_id
                or release.request.frontend != connection.frontend
                or release.request.destination_id != connection.client_id
                or release.request.action is not AccessAction.SUBMIT
            ):
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)

        ready = worker.operation_secret(request.session_id, request.requirement, frontend=connection.frontend)
        checked(ready)
        with host.authorize(ready.release):
            write_document(
                channel,
                RuntimeSecretReady(
                    request_id=request.request_id,
                    runtime_boot_id=self.boot,
                    connection_id=connection.context.connection_id,
                ),
                deadline=time.monotonic() + 5,
            )
        # Never hold the profile fence while awaiting a client secret or a
        # worker callback. Each delivery and output acquires fresh authority.
        with read_secret(channel, deadline=time.monotonic() + 5) as secret:
            delivered = worker.operation_secret(
                request.session_id, request.requirement, frontend=connection.frontend, secret=secret
            )
        checked(delivered)
        with host.authorize(delivered.release) as allowed:
            remaining = (allowed.expires_at - self._wall_clock()).total_seconds()
            if remaining <= 0:
                raise ProfileAccessRefusedError(AccessDenialCode.SESSION_EXPIRED)
            write_document(
                channel,
                RuntimeOperationAcknowledged(
                    request_id=request.request_id,
                    runtime_boot_id=self.boot,
                    connection_id=connection.context.connection_id,
                    operation_id=delivered.operation_id,
                ),
                deadline=time.monotonic() + min(5, remaining),
            )

    def operation(
        self, context: RuntimeConnectionContext, channel: RuntimeByteChannel, request: RuntimeOperationRequest
    ) -> None:
        """Hold newly observed authority through the final bounded frontend write."""
        reply: RuntimeOperationReply | RuntimeAccessRefusal
        deadline = time.monotonic() + 5
        with ExitStack() as release_guard:
            try:
                if context.runtime_boot_id != self.boot or context.peer != channel.peer:
                    raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
                if not self._admitting():
                    raise RuntimeRefusalError(RuntimeRefusalCode.DRAINING)
                connection = self._connected(context.connection_id)
                if connection.context != context or connection.profile_id != request.profile_id:
                    raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
                if connection.session_id != request.session_id:
                    raise ProfileAccessRefusedError(AccessDenialCode.CONNECTION_MISMATCH)
                with self._guard:
                    host = self._profiles.get(connection.profile_id)
                if host is None:
                    raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
                if isinstance(request, RuntimeOperationSecret):
                    self._operation_secret(host, connection, channel, request)
                    return
                if isinstance(request, RuntimeOperationContract):
                    # Public registry discovery has no private domain operands.
                    # Hold the profile fence while observing its current scope.
                    release_guard.enter_context(host.guard)
                    status = self._status(connection, host, request.request_id, request.session_id)
                    if isinstance(status, AccessDenied):
                        raise ProfileAccessRefusedError(status.code)
                    if status.status.denial is not None:
                        raise ProfileAccessRefusedError(status.status.denial)
                    if request.definition_id not in status.status.effective_scope.operations:
                        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
                    description = host.owner.operation_worker().describe(request.session_id, request.definition_id)
                    contract = description.contract
                    if connection.frontend not in contract.permitted_frontends:
                        raise ProfileAccessRefusedError(AccessDenialCode.FRONTEND_DENIED)
                    reply = RuntimeOperationContractReply(
                        request_id=request.request_id,
                        runtime_boot_id=self.boot,
                        connection_id=context.connection_id,
                        contract=contract,
                        request_json_schema=description.request_json_schema,
                    )
                    expires_at = status.status.session_expires_at
                elif isinstance(request, RuntimeOperationSubmitPayload):
                    self._require_upload_session(connection, host, request)
                    contract = (
                        host.owner.operation_worker().describe(request.session_id, request.definition_id).contract
                    )
                    if connection.frontend not in contract.permitted_frontends:
                        raise ProfileAccessRefusedError(AccessDenialCode.FRONTEND_DENIED)
                    reply, release = stream_operation_submission(
                        host,
                        connection,
                        request,
                        channel,
                        slots=self._submission_slots,
                        require_session=lambda: self._require_upload_session(connection, host, request),
                        deadline=time.monotonic() + SUBMISSION_PAYLOAD_TIMEOUT_SECONDS,
                    )
                    allowed = release_guard.enter_context(host.authorize(release))
                    expires_at = allowed.expires_at
                else:
                    # Worker callbacks need this same profile guard; never hold
                    # it while waiting for the native execution channel.
                    reply, release = prepare_operation_projection(host, connection, request)
                    allowed = release_guard.enter_context(host.authorize(release))
                    expires_at = allowed.expires_at
                if expires_at is None:
                    raise ProfileAccessRefusedError(AccessDenialCode.SESSION_INACTIVE)
                remaining = (expires_at - self._wall_clock()).total_seconds()
                if remaining <= 0:
                    raise ProfileAccessRefusedError(AccessDenialCode.SESSION_EXPIRED)
                deadline = time.monotonic() + min(5, remaining)
            except (AutomationCustodyError, RuntimeRefusalError, ProfileAccessRefusedError) as error:
                release_guard.close()
                reply = RuntimeAccessRefusal(
                    request_id=request.request_id,
                    runtime_boot_id=self.boot,
                    connection_id=context.connection_id,
                    code=error.reason,
                )
                deadline = time.monotonic() + 5
            # Write errors propagate: a partially written frame is never retried
            # as a refusal. No private payload escapes the scope of its fence.
            write_document(channel, reply, deadline=deadline)

    def _require_upload_session(
        self, connection: ProfileConnection, host: RuntimeProfileHost, request: RuntimeOperationSubmitPayload
    ) -> None:
        """Recheck connection and coarse SUBMIT scope while no operation yet exists."""
        if not self._admitting():
            raise RuntimeRefusalError(RuntimeRefusalCode.DRAINING)
        current = self._connected(connection.context.connection_id)
        if current is not connection or connection.session_id != request.session_id:
            raise ProfileAccessRefusedError(AccessDenialCode.CONNECTION_MISMATCH)
        with host.guard:
            status = self._status(connection, host, request.request_id, request.session_id)
            if isinstance(status, AccessDenied):
                raise ProfileAccessRefusedError(status.code)
            if status.status.denial is not None:
                raise ProfileAccessRefusedError(status.status.denial)
            scope = status.status.effective_scope
            if request.definition_id not in scope.operations or AccessAction.SUBMIT not in scope.actions:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            expires_at = status.status.session_expires_at
            if expires_at is None or expires_at <= self._wall_clock():
                raise ProfileAccessRefusedError(AccessDenialCode.SESSION_EXPIRED)

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
        self._enrollments.retire_profile(profile_id)
        with self._guard:
            if self._profiles.get(profile_id) is host:
                self._profiles.pop(profile_id)
                for connection in self._connections.values():
                    if connection.profile_id == profile_id:
                        connection.session_id = None

    def close(self) -> None:
        """Fence all admissions before releasing profile workers and nonsecret state."""
        if not self._drain_guard.acquire(blocking=False):
            raise RuntimeShutdownIncompleteError()
        try:
            if self._drain_records is not None and self._drain_result is None:
                # A plain close cannot forget the original daemon threads or
                # compete with their native containment. Resume through drain.
                raise RuntimeShutdownIncompleteError()
            self._close_profiles()
        finally:
            self._drain_guard.release()

    def _close_profiles(self) -> None:
        with self._guard:
            self._closed = True
            hosts = tuple(self._profiles.items())
        self._enrollments.close()
        failures: list[Exception] = []
        for profile_id, host in hosts:
            try:
                host.close()
            except Exception as error:
                failures.append(error)
            else:
                with self._guard:
                    if self._profiles.get(profile_id) is host:
                        self._profiles.pop(profile_id)
        with self._guard:
            self._connections.clear()
            self._logins.clear()
        if failures:
            raise ExceptionGroup("runtime profile cleanup failed", failures)

    def drain(self, *, deadline: float) -> RuntimeProfileDrainResult:
        """Resume the original fenced shutdown under this attempt's absolute deadline."""
        self.stop.set()
        if not self._drain_guard.acquire(timeout=max(0.0, deadline - time.monotonic())):
            raise RuntimeShutdownIncompleteError()
        try:
            return self._drain_profiles(deadline=deadline)
        finally:
            self._drain_guard.release()

    def _drain_profiles(self, *, deadline: float) -> RuntimeProfileDrainResult:
        if self._drain_result is not None:
            return self._drain_result
        if not self._guard.acquire(timeout=max(0.0, deadline - time.monotonic())):
            raise RuntimeShutdownIncompleteError()
        try:
            self._closed = True
            if self._drain_records is None:
                self._drain_records = {
                    profile_id: _ProfileDrainRecord(host) for profile_id, host in self._profiles.items()
                }
            records = tuple(self._drain_records.items())
        finally:
            self._guard.release()
        self._enrollments.close()
        approval_failures: set[UUID] = set()
        for profile_id, record in records:
            try:
                # Retire idle password/DEK proof before containing the worker;
                # active callback phases retain their own cleanup until settled.
                record.host.approvals.close()
            except Exception:
                approval_failures.add(profile_id)
            if not record.begun:
                record.worker = record.host.owner.begin_drain()
                record.begun = True
            if record.worker is not None and record.request is None:
                self._start_drain_request(record, deadline=deadline)
            # A prior terminal failed containment may have left its request
            # blocked. Retry containment before joining that original request.
            if (
                record.containment is not None
                and record.containment.ident is not None
                and not record.containment.is_alive()
            ):
                with record.guard:
                    contained = record.contained
                if not contained:
                    self._start_drain_containment(record, deadline=deadline)
        for _, record in records:
            if record.request is not None and record.request.ident is not None:
                record.request.join(timeout=max(0.0, deadline - time.monotonic()))

        uncontained: list[UUID] = []
        unsettled: list[UUID] = list(approval_failures)
        for _, record in records:
            with record.guard:
                contained = record.contained
            if record.worker is not None and not contained and record.containment is None:
                self._start_drain_containment(record, deadline=deadline)
        for _, record in records:
            if record.containment is not None and record.containment.ident is not None:
                record.containment.join(timeout=max(0.0, deadline - time.monotonic()))

        received: dict[UUID, ProfileWorkerDrained] = {}
        for profile_id, record in records:
            with record.guard:
                contained, receipt = record.contained, record.receipt
            if receipt is not None:
                received[profile_id] = receipt
            if record.worker is not None and not contained:
                uncontained.append(profile_id)
            running = any(
                thread is not None and (thread.ident is None or thread.is_alive())
                for thread in (record.request, record.containment)
            )
            if running:
                unsettled.append(profile_id)
            # A pre-fence launch may own a native scope without a published
            # worker. Its incomplete containment retains runtime ownership.
            if not record.host.owner.wait_construction(deadline=deadline):
                uncontained.append(profile_id)
                continue
            if running or (record.worker is not None and not contained):
                continue
            try:
                record.host.owner.settle(deadline=deadline)
            except Exception:
                unsettled.append(profile_id)
            try:
                # Callback settlement may complete a retired proof phase. Reap
                # again and retain this host if any proof still owns cleanup.
                if record.host.approvals.close():
                    unsettled.append(profile_id)
            except Exception:
                unsettled.append(profile_id)
        result = RuntimeProfileDrainResult(
            receipts=tuple(received[profile_id] for profile_id in sorted(received)),
            missing_receipts=tuple(
                sorted(
                    profile_id
                    for profile_id, record in records
                    if record.worker is not None and profile_id not in received
                )
            ),
            uncontained=tuple(sorted(set(uncontained))),
            unsettled=tuple(sorted(set(unsettled))),
        )
        if not uncontained and not unsettled:
            if not self._guard.acquire(timeout=max(0.0, deadline - time.monotonic())):
                raise RuntimeShutdownIncompleteError()
            try:
                self._profiles.clear()
                self._connections.clear()
                self._logins.clear()
                self._drain_result = result
                self._drain_records.clear()
            finally:
                self._guard.release()
        return result

    @staticmethod
    def _start_drain_request(record: _ProfileDrainRecord, *, deadline: float) -> None:
        worker = record.worker
        if worker is None:
            return

        def request() -> None:
            try:
                receipt = worker.drain(deadline=deadline)
            except BaseException:
                # The original worker remains owned, regardless of why its
                # protocol request failed. Only a real receipt may be recorded.
                return
            with record.guard:
                record.receipt = receipt
                record.contained = True

        thread = Thread(target=request, name="profile-worker-drain", daemon=True)
        record.request = thread
        thread.start()

    @staticmethod
    def _start_drain_containment(record: _ProfileDrainRecord, *, deadline: float) -> None:
        worker = record.worker
        if worker is None:
            return

        def contain() -> None:
            try:
                worker.close(deadline=deadline)
            except BaseException:
                return
            with record.guard:
                record.contained = True

        thread = Thread(target=contain, name="profile-worker-contain", daemon=True)
        record.containment = thread
        thread.start()

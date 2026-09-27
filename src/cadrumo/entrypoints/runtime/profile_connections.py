"""Local connection lifecycle over the existing profile authentication authority."""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from contextlib import ExitStack
from pathlib import Path
from threading import Event, RLock
from uuid import UUID, uuid4

from pydantic import SecretBytes

from ...adapters.local_runtime.framing import read_secret, write_document
from ...adapters.local_runtime.installation import runtime_installation
from ...adapters.local_runtime.login import capture_runtime_login
from ...adapters.persistence.storage.custody.automation_profile import current_automation_profile_binding
from ...adapters.persistence.storage.custody.automation_secret_store import native_automation_secret_store
from ...adapters.persistence.storage.custody.automation_store import AutomationControlStore
from ...application.operations.registry import OperationRegistry
from ...application.runtime.contracts import RuntimeByteChannel, RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.installation import RuntimeInstallation
from ...application.runtime.login import RuntimeLoginEvidence
from ...application.runtime.operation_access import (
    RuntimeOperationContract,
    RuntimeOperationContractReply,
    RuntimeOperationReply,
    RuntimeOperationRequest,
)
from ...application.runtime.profile_access import (
    RuntimeAccessRefusal,
    RuntimeProfileLogin,
    RuntimeProfileStatus,
    RuntimeSecretReady,
    RuntimeSessionRequest,
    RuntimeSessionsLocked,
)
from ...application.runtime.transport import RuntimeConnectionContext
from ...application.user_profile.access_contracts import AccessDenialCode, AccessDenied, AccessSession, Availability
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
    AutomationSecretStore,
    NativeSecretBackend,
)
from ...core.time.clock import now
from ..operation_composition import build_production_operation_registry
from .operation_projection import prepare_operation_projection
from .profile_host import ProfileConnection, RuntimeProfileHost


def _native_store() -> AutomationSecretStore:
    backend = {
        "win32": NativeSecretBackend.WINDOWS_CREDENTIAL_MANAGER,
        "darwin": NativeSecretBackend.MACOS_KEYCHAIN,
        "linux": NativeSecretBackend.LINUX_DBUS,
    }.get(sys.platform)
    if backend is None:
        raise AutomationCustodyError(AutomationCustodyCode.UNSUPPORTED)
    return native_automation_secret_store(backend)


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
        secret_store: Callable[[], AutomationSecretStore] = _native_store,
    ) -> None:
        """Defer installation/profile/store access until an eligible peer requests login."""
        self.root, self.storage_identity, self.boot, self.stop = storage_root, storage_identity, runtime_boot_id, stop
        self._capture, self._secret_store = capture_login, secret_store
        self._guard = RLock()
        self._installation: RuntimeInstallation | None = None
        self._registry: OperationRegistry | None = None
        self._profiles: dict[UUID, RuntimeProfileHost] = {}
        self._connections: dict[UUID, ProfileConnection] = {}
        self._logins: dict[str, RuntimeLoginEvidence] = {}
        self._closed = False
        self._last_poll = 0.0

    def _connected(self, connection_id: UUID) -> ProfileConnection:
        with self._guard:
            connection = self._connections.get(connection_id)
            if self._closed or connection is None:
                raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
            return connection

    def _login_contexts(self) -> tuple[RuntimeLoginEvidence, ...]:
        with self._guard:
            return tuple(self._logins.values())

    def _admitting(self) -> bool:
        return not self._closed and not self.stop.is_set()

    def _host(self, profile_id: UUID, context: RuntimeConnectionContext) -> RuntimeProfileHost:
        with self._guard:
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
            if self._registry is None:
                self._registry = build_production_operation_registry()
            host = RuntimeProfileHost(
                store=AutomationControlStore(root=self.root, binding=binding, secrets_store=self._secret_store()),
                runtime_boot_id=self.boot,
                registry=self._registry,
                connected=self._connected,
                logins=self._login_contexts,
                admitting=self._admitting,
            )
            self._profiles[profile_id] = host
            return host

    def _prepare(
        self, context: RuntimeConnectionContext, channel: RuntimeByteChannel, request: RuntimeProfileLogin
    ) -> tuple[ProfileConnection, RuntimeProfileHost]:
        if request.method == "password" and request.scope is not None:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        with self._guard:
            previous = self._connections.get(context.connection_id)
        if previous is not None:
            if (
                previous.context != context
                or previous.profile_id != request.profile_id
                or previous.frontend != request.frontend
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
            if not observation.active or (request.method == "password" and observation.locked):
                raise AutomationCustodyError(AutomationCustodyCode.NEEDS_USER)
            connection.method = request.method
            if request.method == "password":
                connection.client_id = uuid4()
            with self._guard:
                self._connections[context.connection_id] = connection
                self._logins[connection.login.login_id] = connection.login
        return connection, host

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
        with read_secret(channel, deadline=time.monotonic() + 10) as secret, host.guard:
            if not self._admitting():
                raise RuntimeRefusalError(RuntimeRefusalCode.DRAINING)
            if request.method == "password":
                connection.password = secret
                try:
                    admitted = host.authority.admit_human(connection_id=context.connection_id)
                finally:
                    connection.password = None
            else:
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
            if isinstance(admitted, AccessDenied):
                return admitted
            connection.session_id = admitted.session_id
            return self._status(connection, host, request.request_id, admitted.session_id)

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
            for connection in self._connections.values():
                if connection.session_id in identities:
                    connection.session_id = None

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
        except AutomationCustodyError as error:
            code = error.reason
        except RuntimeRefusalError as error:
            code = error.reason
        return RuntimeAccessRefusal(
            request_id=request.request_id, runtime_boot_id=self.boot, connection_id=context.connection_id, code=code
        )

    def disconnect(self, context: RuntimeConnectionContext) -> None:
        """Release only this connection's authority; keep native login provenance separate."""
        with self._guard:
            connection = self._connections.get(context.connection_id)
            host = None if connection is None else self._profiles.get(connection.profile_id)
        try:
            if host is not None:
                host.authority.disconnect(context.connection_id)
        finally:
            with self._guard:
                self._connections.pop(context.connection_id, None)

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
                    contract = host.owner.operation_worker().contract(request.session_id, request.definition_id)
                    if connection.frontend not in contract.permitted_frontends:
                        raise ProfileAccessRefusedError(AccessDenialCode.FRONTEND_DENIED)
                    reply = RuntimeOperationContractReply(
                        request_id=request.request_id,
                        runtime_boot_id=self.boot,
                        connection_id=context.connection_id,
                        contract=contract,
                    )
                    expires_at = status.status.session_expires_at
                else:
                    # Worker callbacks need this same profile guard; never hold
                    # it while waiting for the native execution channel.
                    reply, release = prepare_operation_projection(host, connection, request)
                    allowed = release_guard.enter_context(host.authorize(release))
                    expires_at = allowed.expires_at
                if expires_at is None:
                    raise ProfileAccessRefusedError(AccessDenialCode.SESSION_INACTIVE)
                remaining = (expires_at - now()).total_seconds()
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

    def poll(self) -> None:
        """Fence idle leases on expiry, native logout/lock or unavailable custody."""
        instant = time.monotonic()
        if instant - self._last_poll < 0.5:
            return
        self._last_poll = instant
        with self._guard:
            hosts = tuple(self._profiles.values())
        for host in hosts:
            self._retired(host.authority.revalidate_sessions())
            if host.owner.lost:
                host.close()
                with self._guard:
                    profile_id = host.store.binding.profile_id
                    if self._profiles.get(profile_id) is host:
                        self._profiles.pop(profile_id)
                        for connection in self._connections.values():
                            if connection.profile_id == profile_id:
                                connection.session_id = None

    def close(self) -> None:
        """Fence all admissions before releasing profile workers and nonsecret state."""
        with self._guard:
            self._closed = True
            hosts = tuple(self._profiles.values())
        failures: list[Exception] = []
        for host in hosts:
            try:
                host.close()
            except Exception as error:
                failures.append(error)
        with self._guard:
            self._profiles.clear()
            self._connections.clear()
            self._logins.clear()
        if failures:
            raise ExceptionGroup("runtime profile cleanup failed", failures)

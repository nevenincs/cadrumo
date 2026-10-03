"""Runtime admission behavior for profile connections."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from ...adapters.local_runtime.installation import runtime_installation
from ...adapters.persistence.storage.custody.automation_profile import current_automation_profile_binding
from ...adapters.persistence.storage.custody.automation_store import AutomationControlStore
from ...application.operations.registry import OperationFrontendProjection
from ...application.runtime.access_management import (
    RuntimeAutomationDeny,
    RuntimeProfileRecoveryPrepare,
    RuntimeProfileResume,
    RuntimeSessionInventory,
)
from ...application.runtime.contracts import (
    RuntimeByteChannel,
    RuntimeRefusalCode,
    RuntimeRefusalError,
)
from ...application.runtime.enrollment_access import (
    RuntimeEnrollmentPrepare,
)
from ...application.runtime.profile_access import (
    RuntimeProfileLogin,
    RuntimeProfileStatus,
)
from ...application.runtime.transport import RuntimeConnectionContext
from ...application.user_profile.access_contracts import (
    Availability,
)
from ...application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
)
from .profile_host import ProfileConnection, RuntimeProfileHost

if TYPE_CHECKING:
    from .profile_connections import RuntimeProfileConnections


type _ExistingRuntimeAccessRequest = RuntimeAutomationDeny | RuntimeProfileResume | RuntimeSessionInventory


class ProfileConnectionAdmissionMixin:
    """Own the admission behavior of the profile connection service."""

    def _host(
        self: RuntimeProfileConnections, profile_id: UUID, context: RuntimeConnectionContext
    ) -> RuntimeProfileHost:
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
        self: RuntimeProfileConnections,
        context: RuntimeConnectionContext,
        channel: RuntimeByteChannel,
        request: RuntimeProfileLogin,
    ) -> tuple[ProfileConnection, RuntimeProfileHost]:
        self._validate_login_request(request)
        connection = self._existing_or_captured_connection(context, channel, request)
        host = self._host(request.profile_id, context)
        with host.guard:
            self._prepare_profile_login(connection, host, context, request)
        return connection, host

    @staticmethod
    def _validate_login_request(request: RuntimeProfileLogin) -> None:
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

    def _existing_or_captured_connection(
        self: RuntimeProfileConnections,
        context: RuntimeConnectionContext,
        channel: RuntimeByteChannel,
        request: RuntimeProfileLogin,
    ) -> ProfileConnection:
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
            return previous
        login = self._capture(channel)
        observed = login.observe(credential_facilities=Availability.UNAVAILABLE)
        if not observed.active or observed.os_owner_id != context.peer.os_owner_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        return ProfileConnection(context, login, uuid4(), request.profile_id, request.frontend)

    def _prepare_profile_login(
        self: RuntimeProfileConnections,
        connection: ProfileConnection,
        host: RuntimeProfileHost,
        context: RuntimeConnectionContext,
        request: RuntimeProfileLogin,
    ) -> None:
        if not self._admitting():
            raise RuntimeRefusalError(RuntimeRefusalCode.DRAINING)
        self._retire_invalid_prior_session(connection, host, context, request)
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

    def _retire_invalid_prior_session(
        self: RuntimeProfileConnections,
        connection: ProfileConnection,
        host: RuntimeProfileHost,
        context: RuntimeConnectionContext,
        request: RuntimeProfileLogin,
    ) -> None:
        if connection.session_id is None:
            return
        try:
            prior = self._status(connection, host, request.request_id, connection.session_id)
            valid = isinstance(prior, RuntimeProfileStatus) and prior.status.denial is None
        except AutomationCustodyError:
            valid = False
        if valid:
            raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
        host.authority.disconnect(context.connection_id)
        connection.session_id = None

    def _prepare_enrollment(
        self: RuntimeProfileConnections,
        context: RuntimeConnectionContext,
        channel: RuntimeByteChannel,
        request: RuntimeEnrollmentPrepare,
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
        self: RuntimeProfileConnections,
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

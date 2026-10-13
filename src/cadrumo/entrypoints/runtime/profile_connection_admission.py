"""Runtime admission behavior for profile connections."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from ...adapters.local_runtime.installation import runtime_installation
from ...adapters.persistence.storage.custody.automation_profile import current_automation_profile_binding
from ...adapters.persistence.storage.custody.automation_store import AutomationControlStore
from ...application.operations.mcp_surfaces import McpSurfaceName, mcp_surface
from ...application.operations.registry import OperationFrontendProjection
from ...application.runtime.access_management import (
    RuntimeAutomationDeny,
    RuntimeProfileRecoveryPrepare,
    RuntimeProfileResume,
    RuntimeSessionInventory,
)
from ...application.runtime.bootstrap import RuntimePasswordResetPrepare
from ...application.runtime.contracts import (
    RuntimeByteChannel,
    RuntimeRefusalCode,
    RuntimeRefusalError,
    RuntimeShutdownIncompleteError,
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

_HELD_FENCE_FIRST_WAIT_SECONDS = 0.01
"""How long an admission first leaves a replaced incarnation's held fence before trying it again."""

_HELD_FENCE_LONGEST_WAIT_SECONDS = 0.25
"""The wait between tries grows to this: a commit body or a containment holds its fence for a while."""


class ProfileConnectionAdmissionMixin:
    """Own the admission behavior of the profile connection service."""

    def _host(
        self: RuntimeProfileConnections, profile_id: UUID, context: RuntimeConnectionContext
    ) -> RuntimeProfileHost:
        deadline = time.monotonic() + 15
        while True:
            with self._guard:
                if not self._admitting() or profile_id in self._custody_mutations:
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
                if existing is not None and existing.store.binding == binding:
                    return existing
                if existing is None:
                    registry = self._registry
                    if registry is None:
                        # Direct in-process hosts may omit startup preparation. The
                        # installed server calls prepare_registry before listening.
                        registry = self.prepare_registry()
                    store = AutomationControlStore(
                        root=self.root, binding=binding, secrets_store_factory=self._secret_store
                    )
                    # An eligible native peer has selected this exact verified
                    # binding. Finish only a surviving earlier denial; failure
                    # keeps its fence, while password admission stays independent.
                    store.reconcile_denial()
                    host = RuntimeProfileHost(
                        store=store,
                        runtime_boot_id=self.boot,
                        registry=registry,
                        connected=self._connected,
                        logins=self._login_contexts,
                        admitting=lambda: self._private_work_available() and profile_id not in self._custody_mutations,
                        recipient=self._enrollments.recipient,
                        worker_script=self._worker_script,
                        wall_clock=self._wall_clock,
                        retired=self._events.publish,
                    )
                    if not self._admitting():
                        raise RuntimeRefusalError(RuntimeRefusalCode.DRAINING)
                    self._profiles[profile_id] = host
                    return host
            # Retirement needs callbacks that may borrow connection state.
            # Release the connection guard before waiting for containment.
            retired = self._retire_once_fence_is_free(profile_id, existing, deadline=deadline)
            if retired is None:
                continue
            if not retired:
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            self._remove_retired_host(existing)

    def _retire_once_fence_is_free(
        self: RuntimeProfileConnections, profile_id: UUID, replaced: RuntimeProfileHost, *, deadline: float
    ) -> bool | None:
        """Retire a replaced incarnation, waiting out another owner's hold on its fence.

        Another owner holds the fence during a commit body, or during a
        containment already under way. Its hold is not this admission's
        refusal, so the retirement is tried again inside the same bound. The
        wait reads nothing from disk and holds no guard: the profile binding
        is observed again only when the incarnation has left service, which
        ``None`` reports.
        """
        wait = _HELD_FENCE_FIRST_WAIT_SECONDS
        while True:
            if time.monotonic() >= deadline:
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            try:
                retired = replaced.retire_replaced_binding(deadline=deadline)
            except (RuntimeRefusalError, RuntimeShutdownIncompleteError, ExceptionGroup):
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT) from None
            if retired is not None:
                return retired
            self.stop.wait(min(wait, max(0.0, deadline - time.monotonic())))
            wait = min(wait * 2, _HELD_FENCE_LONGEST_WAIT_SECONDS)
            with self._guard:
                if not self._admitting() or profile_id in self._custody_mutations:
                    raise RuntimeRefusalError(RuntimeRefusalCode.DRAINING)
                if self._profiles.get(profile_id) is not replaced:
                    return None

    def _prepare(
        self: RuntimeProfileConnections,
        context: RuntimeConnectionContext,
        channel: RuntimeByteChannel,
        request: RuntimeProfileLogin,
    ) -> tuple[ProfileConnection, RuntimeProfileHost]:
        self._validate_login_request(request)
        if request.method == "password":
            # Signing in by password is the person's act, never an agent's.
            self._require_persons_frontend(request.frontend)
        if request.frontend is OperationFrontendProjection.AGENT_HOST and request.method != "receipt":
            # The agent host is admitted only by resuming the person's stored sign-in.
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        surface = self._login_surface(request)
        connection = self._existing_or_captured_connection(context, channel, request, surface)
        host = self._host(request.profile_id, context)
        with host.guard:
            self._prepare_profile_login(connection, host, context, request)
        return connection, host

    @staticmethod
    def _validate_login_request(request: RuntimeProfileLogin) -> None:
        """Refuse a login whose method and options do not belong together, on any frontend.

        A sign-in holds the profile's whole ceiling, so neither a password nor
        the proof of a stored sign-in takes a narrowing scope. Only a password
        login can ask for the sign-in to be stored: a proof resumes one that
        already is, and a key stores none.
        """
        if request.method in {"password", "receipt"} and request.scope is not None:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        if request.persist_receipt and request.method != "password":
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)

    @staticmethod
    def _login_surface(request: RuntimeProfileLogin) -> McpSurfaceName | None:
        """Resolve the MCP surface a login names, refusing a name that cannot be enforced.

        A surface narrows what the MCP frontend is admitted to, so no other
        frontend may name one. An unknown name is refused, never ignored: the
        connection would otherwise run without the narrowing it asked for.
        """
        if request.surface is None:
            return None
        if request.frontend is not OperationFrontendProjection.MCP:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        try:
            return mcp_surface(request.surface).name
        except KeyError:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None

    def _existing_or_captured_connection(
        self: RuntimeProfileConnections,
        context: RuntimeConnectionContext,
        channel: RuntimeByteChannel,
        request: RuntimeProfileLogin,
        surface: McpSurfaceName | None,
    ) -> ProfileConnection:
        with self._guard:
            previous = self._connections.get(context.connection_id)
        if previous is not None:
            if (
                previous.context != context
                or previous.profile_id != request.profile_id
                or previous.frontend != request.frontend
                # The first login fixes the surface; a later one cannot widen or swap it.
                or previous.surface is not surface
                or previous.method in {"enrollment", "bootstrap-reset", "bootstrap-delete"}
            ):
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            return previous
        login = self._capture(channel)
        observed = login.observe(credential_facilities=Availability.UNAVAILABLE)
        if not observed.active or observed.os_owner_id != context.peer.os_owner_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        return ProfileConnection(context, login, uuid4(), request.profile_id, request.frontend, surface=surface)

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
        if not observation.active or (request.method in {"password", "receipt"} and not observation.unlocked):
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
        # Requesting or changing a key is the person's act, never an agent's.
        self._require_persons_frontend(request.frontend)
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
        request: RuntimeEnrollmentPrepare | RuntimeProfileRecoveryPrepare | RuntimePasswordResetPrepare,
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
        if not observed.active or not observed.unlocked or observed.os_owner_id != context.peer.os_owner_id:
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

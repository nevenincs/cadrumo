"""The runtime door that starts a person's hosted agent, bound to the session that asked.

Only the agent host's frontend, signed in by resuming the person's stored
sign-in, may ask, and only for its own live human session of the one signed-in
profile. The gateway bearer arrives on the one secret frame the runtime
authorizes after its preflight. The provider credentials are resolved by the
profile worker and written only into the agent's standard-input frame; no
client ever receives one. The tree is bound to the asking session's exact
lease and ends with it, through the same retirement funnel that ends the
session.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Final
from uuid import UUID

from ...adapters.local_runtime.agent_process import WindowsAgentProcessLauncher
from ...adapters.local_runtime.agent_programs import (
    AgentProgramRefusalError,
    agent_image,
    hosted_programs,
    profile_agent_root,
    profile_agent_workspace,
)
from ...adapters.local_runtime.runtime_frame_io import read_secret, write_document
from ...application.agent_host.controller import (
    AgentGenerations,
    AgentHostController,
    AgentHostError,
    AgentHostRefusal,
    AgentLaunch,
    AgentProcessLauncher,
    ResolvedAgentCredentials,
)
from ...application.agent_host.credential_frame import AgentCredential, wipe
from ...application.agent_host.development_fallback import development_fallback
from ...application.agent_host.lane_root import is_marked_lane_root
from ...application.agent_host.launch_environment import agent_launch_environment
from ...application.agent_host.launcher_protocol import (
    HOSTED_ASSISTANT_PROVIDERS,
    AgentLauncherRefusal,
    launcher_refusal_for,
)
from ...application.operations.registry import OperationFrontendProjection
from ...application.runtime.agent_host import RuntimeAgentRefused, RuntimeAgentStart, RuntimeAgentStarted
from ...application.runtime.contracts import RuntimeByteChannel, RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.profile_access import (
    RuntimeAccessRefusal,
    RuntimeProfileLogin,
    RuntimeProfileStatus,
    RuntimeSecretReady,
)
from ...application.runtime.session_events import RuntimeSessionEvent
from ...application.runtime.transport import RuntimeConnectionContext
from ...application.user_profile.access_contracts import AccessDenialCode, AccessDenied, Availability
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...application.user_profile.automation_custody_port import AutomationCustodyError
from ...core.config import load_settings
from ...core.logging import get_logger
from ...core.storage_environment import storage_mode
from ...domain.provider_settings.catalog import ProviderCatalog, load_provider_catalog
from .agent_hosts import AgentTreeOwner
from .profile_connection_attendance import ATTENDANCE_METHOD, AttendedConnection
from .profile_host import ProfileConnection, RuntimeProfileHost

if TYPE_CHECKING:
    from .profile_connections import RuntimeProfileConnections

_LOGGER = get_logger(__name__)

_WRITE_SECONDS: Final = 5
_BEARER_SECONDS: Final = 10
_AGENT_SHUTDOWN_SECONDS: Final = 30.0


class _SessionAgentCredentials:
    """The asking session's credential source: the worker resolves, the controller wipes."""

    def __init__(
        self,
        *,
        host: RuntimeProfileHost,
        session_id: UUID,
        is_current: Callable[[UUID], bool],
        bearer: bytearray,
    ) -> None:
        self._host = host
        self._session_id = session_id
        self._is_current = is_current
        self._bearer: bytearray | None = bearer
        self._generations: AgentGenerations | None = None

    def resolve_for_agent(self) -> ResolvedAgentCredentials:
        try:
            description, material = self._host.owner.agent_credentials(self._session_id, HOSTED_ASSISTANT_PROVIDERS)
        except (AutomationCustodyError, ProfileAccessRefusedError, RuntimeRefusalError) as error:
            _LOGGER.warning(
                "agent credentials refused by the profile worker error_type=%s reason=%s",
                type(error).__name__,
                error.reason,
            )
            raise AgentHostError(AgentHostRefusal.SIGNED_OUT) from error
        # The frame names each credential by the id the agent keys it by; a lane with none contributes nothing.
        catalog = load_provider_catalog()
        credentials: dict[str, AgentCredential] = {}
        try:
            offset = 0
            for item in description.credentials:
                credential_id = _agent_credential_id(catalog, item.provider)
                secret = material[offset : offset + item.secret_bytes]
                offset += item.secret_bytes
                if credential_id is None:
                    wipe(secret)
                    continue
                credentials[credential_id] = AgentCredential(secret, item.base_url)
        finally:
            wipe(material)
        settings = load_settings()
        for provider in description.unset:
            credential_id = _agent_credential_id(catalog, provider)
            fallback = development_fallback(provider, settings=settings, storage_mode=storage_mode().mode)
            if credential_id is not None and fallback is not None:
                credentials[credential_id] = AgentCredential(
                    bytearray(fallback.secret.get_secret_value(), "utf-8"), fallback.base_url
                )
        if not credentials:
            raise AgentHostError(AgentHostRefusal.CREDENTIALS_UNAVAILABLE)
        self._generations = AgentGenerations(sign_in=str(self._session_id), provider_settings=description.generation)
        bearer, self._bearer = self._bearer, None
        return ResolvedAgentCredentials(generations=self._generations, credentials=credentials, gateway_bearer=bearer)

    def current_generations(self) -> AgentGenerations | None:
        if not self._is_current(self._session_id):
            return None
        return self._generations

    def discard(self) -> None:
        if self._bearer is not None:
            wipe(self._bearer)
            self._bearer = None


def _agent_credential_id(catalog: ProviderCatalog, provider_id: str) -> str | None:
    entry = catalog.entry(provider_id)
    return None if entry is None else entry.agent_credential_id


class ProfileConnectionAgentMixin:
    """Start, bind and retire the hosted agent of a person's session."""

    _agent_launcher: AgentProcessLauncher

    def agent(
        self: RuntimeProfileConnections,
        context: RuntimeConnectionContext,
        channel: RuntimeByteChannel,
        request: RuntimeAgentStart,
    ) -> None:
        """Answer one start request on its own connection; the reply carries no credential."""
        reply = self._agent_start(context, channel, request)
        write_document(channel, reply, deadline=time.monotonic() + _WRITE_SECONDS)

    def _agent_refused(
        self: RuntimeProfileConnections,
        context: RuntimeConnectionContext,
        request: RuntimeAgentStart,
        code: AgentLauncherRefusal,
    ) -> RuntimeAgentRefused:
        return RuntimeAgentRefused(
            request_id=request.request_id, runtime_boot_id=self.boot, connection_id=context.connection_id, code=code
        )

    def _agent_start(
        self: RuntimeProfileConnections,
        context: RuntimeConnectionContext,
        channel: RuntimeByteChannel,
        request: RuntimeAgentStart,
    ) -> RuntimeAgentStarted | RuntimeAgentRefused | RuntimeAccessRefusal:
        if context.runtime_boot_id != self.boot or context.peer != channel.peer or not self._admitting():
            return self._agent_refused(context, request, AgentLauncherRefusal.RUNTIME_UNAVAILABLE)
        if self._agent_tree_peer(context):
            # An agent never starts an agent.
            return RuntimeAccessRefusal(
                request_id=request.request_id,
                runtime_boot_id=self.boot,
                connection_id=context.connection_id,
                code=AccessDenialCode.PERSON_ACT_REQUIRED,
            )
        with self._guard:
            connection = self._connections.get(context.connection_id)
            host = None if connection is None else self._profiles.get(connection.profile_id)
            others = tuple(item for profile_id, item in self._profiles.items() if profile_id != request.profile_id)
        if connection is not None and connection.frontend is not OperationFrontendProjection.AGENT_HOST:
            # Only the agent host's own frontend serves an agent; every other frontend is refused outright.
            return RuntimeAccessRefusal(
                request_id=request.request_id,
                runtime_boot_id=self.boot,
                connection_id=context.connection_id,
                code=AccessDenialCode.FRONTEND_DENIED,
            )
        if (
            connection is None
            or host is None
            or connection.context != context
            or connection.profile_id != request.profile_id
            or connection.session_id != request.session_id
        ):
            return self._agent_refused(context, request, AgentLauncherRefusal.SIGNED_OUT)
        try:
            with host.guard:
                # A live, unlocked human lease of this exact connection; an attended or key session is refused.
                host.authority.human_administration_facts(
                    connection_id=context.connection_id, session_id=request.session_id
                )
        except (ProfileAccessRefusedError, AutomationCustodyError):
            return self._agent_refused(context, request, AgentLauncherRefusal.SIGNED_OUT)
        if any(other.authority.human_login_ids() for other in others):
            # Another profile holds the person's sign-in: this one is not the signed-in profile.
            return self._agent_refused(context, request, AgentLauncherRefusal.SIGNED_OUT)
        if not is_marked_lane_root(self.root):
            return self._agent_refused(context, request, AgentLauncherRefusal.ROOT_UNMARKED)
        try:
            agent_root = profile_agent_root(self.root, request.profile_id)
            workspace = profile_agent_workspace(agent_root)
            image = agent_image(request.agent_source, agent_root=agent_root)
            programs = hosted_programs()
        except AgentProgramRefusalError as refused:
            return self._agent_refused(context, request, refused.code)
        except OSError:
            return self._agent_refused(context, request, AgentLauncherRefusal.SERVICE_FAILED)
        if not self._agents.reserve(
            profile_id=request.profile_id, session_id=request.session_id, connection_id=context.connection_id
        ):
            # One agent tree per signed-in profile: a second start is refused, never shared.
            return self._agent_refused(context, request, AgentLauncherRefusal.SERVICE_FAILED)
        try:
            write_document(
                channel,
                RuntimeSecretReady(
                    request_id=request.request_id, runtime_boot_id=self.boot, connection_id=context.connection_id
                ),
                deadline=time.monotonic() + _WRITE_SECONDS,
            )
            with read_secret(channel, deadline=time.monotonic() + _BEARER_SECONDS) as secret:
                bearer = bytearray(secret)
        except BaseException:
            self._agents.release(request.session_id)
            raise
        source = _SessionAgentCredentials(
            host=host, session_id=request.session_id, is_current=self._agents.is_current, bearer=bearer
        )
        controller = AgentHostController(
            launcher=self._agent_launcher,
            credentials=source,
            launch=AgentLaunch(
                executable=image.executable,
                arguments=image.arguments,
                directory=image.directory,
                environment=agent_launch_environment(
                    storage_root=self.root, agent_root=agent_root, received=os.environ, programs=programs
                ),
            ),
        )
        # Tracked before it starts, so a process of the tree is known as the agent's from its first moment.
        self._agents.track(
            controller,
            AgentTreeOwner(
                profile_id=request.profile_id, session_id=request.session_id, connection_id=context.connection_id
            ),
        )
        try:
            ready = controller.start()
        except AgentHostError as error:
            self._agents.release(request.session_id)
            self._agents.untrack(controller)
            return self._agent_refused(context, request, launcher_refusal_for(error))
        except BaseException:
            controller.stop()
            self._agents.release(request.session_id)
            self._agents.untrack(controller)
            raise
        finally:
            source.discard()
        if not self._agents.publish(request.session_id, controller):
            # The session ended while the agent started: its tree never serves.
            controller.stop()
            self._agents.release(request.session_id)
            self._agents.untrack(controller)
            return self._agent_refused(context, request, AgentLauncherRefusal.SIGNED_OUT)
        return RuntimeAgentStarted(
            request_id=request.request_id,
            runtime_boot_id=self.boot,
            connection_id=context.connection_id,
            gateway_port=ready.gateway_port,
            agent_version=ready.agent_version,
            workspace_root=str(workspace),
        )

    def _agent_tree_owner(self: RuntimeProfileConnections, context: RuntimeConnectionContext) -> AgentTreeOwner | None:
        """The lease whose agent tree the connection's kernel-verified peer belongs to, while it serves."""
        process_id = context.peer.process_id
        return None if process_id is None else self._agents.owner_of_process(process_id)

    def _login_agent_tree(
        self: RuntimeProfileConnections,
        context: RuntimeConnectionContext,
        channel: RuntimeByteChannel,
        request: RuntimeProfileLogin,
    ) -> RuntimeProfileStatus | AccessDenied:
        """Admit a process of a hosted agent's tree as that agent, under the lease that started the tree.

        Its identity is its membership of the tree's job, which the kernel
        reports; no key, no person's decision and no stored sign-in admits it.
        It is admitted only on the MCP frontend, and only as an attended child
        of the owning lease, so it takes no person's act and ends with that
        lease. A proof it presents is read and discarded unexamined: the
        person's stored sign-in is never resumed for it.
        """
        self._validate_login_request(request)
        owner = self._agent_tree_owner(context)
        if (
            owner is None
            or request.frontend is not OperationFrontendProjection.MCP
            or request.method != "receipt"
            or request.profile_id != owner.profile_id
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PERSON_ACT_REQUIRED)
        surface = self._login_surface(request)
        write_document(
            channel,
            RuntimeSecretReady(
                request_id=request.request_id, runtime_boot_id=self.boot, connection_id=context.connection_id
            ),
            deadline=time.monotonic() + _WRITE_SECONDS,
        )
        with read_secret(channel, deadline=time.monotonic() + _BEARER_SECONDS):
            pass
        with self._guard:
            host = self._profiles.get(owner.profile_id)
            holder = self._connections.get(owner.connection_id)
            previous = self._connections.get(context.connection_id)
        if host is None or holder is None or holder.session_id != owner.session_id or previous is not None:
            return AccessDenied(code=AccessDenialCode.AUTHENTICATION_REQUIRED)
        login = self._capture(channel)
        observed = login.observe(credential_facilities=Availability.UNAVAILABLE)
        if not observed.active or observed.os_owner_id != context.peer.os_owner_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        connection = ProfileConnection(
            context,
            login,
            holder.client_id,
            owner.profile_id,
            OperationFrontendProjection.MCP,
            method=ATTENDANCE_METHOD,
            surface=surface,
        )
        with host.guard:
            with self._guard:
                if not self._admitting():
                    raise RuntimeRefusalError(RuntimeRefusalCode.DRAINING)
                self._connections[context.connection_id] = connection
                self._logins[login.login_id] = login
            return self._attend_agent_tree(connection, host, owner, request.request_id)

    def _attend_agent_tree(
        self: RuntimeProfileConnections,
        connection: ProfileConnection,
        host: RuntimeProfileHost,
        owner: AgentTreeOwner,
        request_id: UUID,
    ) -> RuntimeProfileStatus | AccessDenied:
        """Issue the tree's connection an attended child of the owning lease; the caller holds the profile guard."""
        with self._guard:
            holder = self._connections.get(owner.connection_id)
            if holder is None or holder.session_id != owner.session_id:
                return AccessDenied(code=AccessDenialCode.AUTHENTICATION_REQUIRED)
            # Disclosures name the owning sign-in as their destination, as an attended connection's do.
            connection.client_id = holder.client_id
        child = host.authority.attend(
            connection_id=owner.connection_id,
            parent_session_id=owner.session_id,
            recipient_connection_id=connection.context.connection_id,
            surface=connection.surface,
        )
        if isinstance(child, AccessDenied):
            return child
        connection.session_id = child.session_id
        with self._guard:
            self._attended[connection.context.connection_id] = AttendedConnection(owner.connection_id, owner.session_id)
        return self._status(connection, host, request_id, child.session_id)

    def _publish_retirement(self: RuntimeProfileConnections, event: RuntimeSessionEvent) -> None:
        """The retirement funnel's one exit: hand the lease's agent stop to its reaper, then notify."""
        self._agents.session_retired(event.session_id)
        self._events.publish(event)

    def _stop_profile_agents(self: RuntimeProfileConnections, profile_ids: frozenset[UUID]) -> None:
        """Reap these profiles' agent trees before another profile's sign-in is answered."""
        if profile_ids and not self._agents.stop_profiles(
            profile_ids, deadline=time.monotonic() + _AGENT_SHUTDOWN_SECONDS
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)

    def _close_agents(self: RuntimeProfileConnections, *, deadline: float | None = None) -> frozenset[UUID]:
        """Stop every agent tree and wait for its reaper; return the profiles whose tree was not confirmed gone."""
        bound = deadline if deadline is not None else time.monotonic() + _AGENT_SHUTDOWN_SECONDS
        return self._agents.close(deadline=bound)


def default_agent_launcher() -> AgentProcessLauncher:
    """The platform's contained agent launcher."""
    return WindowsAgentProcessLauncher()

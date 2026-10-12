"""A live key lease for adapter tests whose subject is not admission itself.

Every tool but ``status`` needs a session, so a test of what a tool answers
under one starts from an adapter holding a lease. The lease is a connection
double that reports itself live and admitted for its profile; what a test
proves through it is the adapter's own handling, never the runtime's decision.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from functools import cache
from types import MappingProxyType, SimpleNamespace
from typing import NoReturn, cast
from uuid import UUID, uuid4

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.application.auth.read_operation import build_auth_read_definition, build_auth_read_registration
from cadrumo.application.operations.mcp_surfaces import DEFAULT_MCP_SURFACE, MCP_SURFACES, McpSurface
from cadrumo.application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionDescriptionV1,
    OperationRegistry,
)
from cadrumo.application.user_profile.access_contracts import (
    AccessScope,
    AuthorityState,
    Availability,
    ProfileAccessStatus,
)
from cadrumo.application.user_profile.operations import (
    USER_PROFILE_OPERATION_DEFINITIONS,
    build_user_profile_operation_registrations,
)
from cadrumo.core.time.clock import now
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter


class AdmittedLease:
    """A lease the runtime reports live and admitted for one profile, under a grant with nothing in scope."""

    def __init__(self, profile_id: UUID) -> None:
        self.profile_id = profile_id
        self.frontend = OperationFrontendProjection.MCP
        self.session_id = uuid4()
        self.closed = False
        self._status = ProfileAccessStatus(
            connected=True,
            credential_authenticated=True,
            profile_id=profile_id,
            session_id=self.session_id,
            session_expires_at=now() + timedelta(minutes=5),
            grant_state=AuthorityState.ACTIVE,
            grant_expires_at=now() + timedelta(minutes=5),
            grant_valid=True,
            profile_bound=True,
            storage=Availability.AVAILABLE,
            automation_custody=Availability.AVAILABLE,
            published_authority=Availability.AVAILABLE,
            provider=Availability.NOT_REQUIRED,
            effective_scope=AccessScope(
                operations=frozenset(),
                actions=frozenset(),
                disclosures=frozenset(),
                periods=None,
                allow_period_independent=True,
                allow_delegation=False,
            ),
            denial=None,
        )

    def status(self) -> SimpleNamespace:
        assert not self.closed
        return SimpleNamespace(status=self._status)

    def subscribe_session_retirement(self, receive: object) -> None:
        """The runtime retires no lease of this double."""

    def subscribe_lifecycle_notices(self, receive: object) -> None:
        """The runtime sends this double no lifecycle notice."""

    def close(self) -> None:
        self.closed = True


def admitted_adapter(
    profile_id: UUID | None = None, *, surface: McpSurface = MCP_SURFACES[DEFAULT_MCP_SURFACE]
) -> RuntimeMcpAdapter:
    """An adapter holding a live lease for one profile, as one admitted by a configured key holds it."""
    lease = AdmittedLease(profile_id or uuid4())
    return RuntimeMcpAdapter(profile_id=lease.profile_id, client=cast(RuntimeFrontendClient, lease), surface=surface)


def _unused_ports(*_args: object, **_kwargs: object) -> NoReturn:
    raise AssertionError("no executor or resolver runs behind a lease double")


@cache
def public_descriptions() -> Mapping[str, OperationPublicDefinitionDescriptionV1]:
    """Real public descriptions of registered operations, by definition id, for a lease double to answer with."""
    auth = build_auth_read_definition(_unused_ports)
    registry = OperationRegistry(
        definitions=(auth, *USER_PROFILE_OPERATION_DEFINITIONS),
        public_registrations=(
            build_auth_read_registration(auth),
            *build_user_profile_operation_registrations(USER_PROFILE_OPERATION_DEFINITIONS),
        ),
    )
    return MappingProxyType(
        {
            item.contract.definition_id: registry.describe_public_definition(item.contract.definition_id)
            for item in registry.public_registrations
        }
    )
